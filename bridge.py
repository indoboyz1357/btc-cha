"""
BTCUSD Signal Omega V2 — Python WebSocket Bridge
Connects MT5 to the Next.js frontend via WebSocket.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional

import MetaTrader5 as mt5
import websockets
from websockets.server import WebSocketServerProtocol

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("OmegaBridge")

# ===== SMART FILTERS IMPORT =====
try:
    from filters import check_all_filters_async, FilterResult
    FILTERS_AVAILABLE = True
    print("[BRIDGE] [OK] Smart filters loaded")
except ImportError as e:
    FILTERS_AVAILABLE = False
    print(f"[BRIDGE] ⚠️  Smart filters not available: {e}")

    class FilterResult:
        def __init__(self):
            self.final_decision = 'ENTRY'
            self.blocked_by = None

    async def check_all_filters_async(*args, **kwargs):
        result = FilterResult()
        return result


# ── Config ───────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> dict:
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

cfg = load_config()

SYMBOL                  = cfg.get("symbol", "BTCUSD")
WS_PORT                 = cfg.get("websocket_port", 8765)

at_cfg                  = cfg.get("auto_trading", {})
AUTO_ENABLED            = at_cfg.get("enabled", False)
AUTO_SCAN_INTERVAL      = at_cfg.get("scan_interval_seconds", 30)
AUTO_LOT_SIZE           = at_cfg.get("lot_size", 0.01)
AUTO_MAX_POSITIONS      = at_cfg.get("max_positions", 2)
AUTO_MAX_DAILY_LOSS     = at_cfg.get("max_daily_loss_usd", 5.0)
AUTO_SESSION_FILTER     = at_cfg.get("session_filter", [])
AUTO_ALLOW_BUY          = at_cfg.get("allow_buy", True)
AUTO_ALLOW_SELL         = at_cfg.get("allow_sell", True)
AUTO_FOLLOW_TREND       = at_cfg.get("follow_trend", True)

# ── Timeframes map ────────────────────────────────────────────────────────────
TF_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
}

COLOR_MAP = {
    0: "bullish_strong",
    1: "bullish_weak",
    2: "bearish_weak",
    3: "bearish_strong",
}

# ── Global State ──────────────────────────────────────────────────────────────
clients: set[WebSocketServerProtocol] = set()
mt5_connected: bool = False
mt5_reconnect_attempts: int = 0

# Rejection orders: ticket → dict
rejection_orders: dict = {}
rejection_counter: int = 0

# Auto trading state
auto_state = {
    "enabled":            AUTO_ENABLED,
    "scan_interval":      AUTO_SCAN_INTERVAL,
    "lot_size":           AUTO_LOT_SIZE,
    "max_positions":      AUTO_MAX_POSITIONS,
    "max_daily_loss":     AUTO_MAX_DAILY_LOSS,
    "session_filter":     AUTO_SESSION_FILTER,
    "allow_buy":          AUTO_ALLOW_BUY,
    "allow_sell":         AUTO_ALLOW_SELL,
    "follow_trend":       AUTO_FOLLOW_TREND,
    "logic_timeframe":    "M15",
    # Runtime state
    "daily_loss":         0.0,
    "trades_today":       0,
    "last_scan":          "",
    "last_signal":        "",
    "trend_direction":    "none",
    "trend_confidence":   0,
    "entry_signal":       "none",
    "circle_active":      None,
    "last_entry_candle":  0,
    "log":                [],
    "paused_mt5_disconnect": False,
}

# ── MT5 Connection ────────────────────────────────────────────────────────────
def connect_mt5(login: int = None, password: str = None, server: str = None) -> bool:
    global mt5_connected, mt5_reconnect_attempts
    terminal_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    acc      = login or cfg["mt5_login"]
    pw       = password or cfg["mt5_password"]
    srv      = server or cfg["mt5_server"]
    log.info(f"Connecting to MT5 (Account: {acc}, Server: {srv})...")
    try:
        if not mt5.initialize(path=terminal_path):
            log.error(f"mt5.initialize() failed at {terminal_path}, error code: {mt5.last_error()}")
            if not mt5.initialize():
                log.error(f"Default mt5.initialize() also failed, error code: {mt5.last_error()}")
                return False
    except Exception as e:
        log.error(f"Exception during MT5 init: {e}")
        return False
    authorized = mt5.login(acc, password=pw, server=srv)
    if not authorized:
        log.error(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        return False
    mt5_connected = True
    mt5_reconnect_attempts = 0
    log.info(f"MT5 connected — account {login} @ {server}")
    return True


def disconnect_mt5():
    global mt5_connected
    mt5.shutdown()
    mt5_connected = False


async def mt5_reconnect_loop():
    global mt5_connected, mt5_reconnect_attempts
    while True:
        await asyncio.sleep(5)
        if not mt5_connected:
            delay = min(2 ** mt5_reconnect_attempts, 30)
            log.info(f"MT5 reconnect attempt #{mt5_reconnect_attempts+1} in {delay}s...")
            await asyncio.sleep(delay)
            if connect_mt5():
                if auto_state.get("paused_mt5_disconnect"):
                    auto_state["paused_mt5_disconnect"] = False
                    log.info("Auto trading resumed after MT5 reconnect")
                await broadcast({"type": "connected", "message": "MT5 reconnected"})
            else:
                mt5_reconnect_attempts += 1
                await broadcast({"type": "disconnected", "message": "MT5 reconnect failed"})

# ── Broadcast helper ──────────────────────────────────────────────────────────
async def broadcast(payload: dict):
    if not clients:
        return
    msg = json.dumps(payload, default=str)
    await asyncio.gather(
        *[ws.send(msg) for ws in list(clients)],
        return_exceptions=True,
    )

# ── Data helpers ──────────────────────────────────────────────────────────────
def get_tick() -> Optional[dict]:
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        return None
    return {
        "type":   "tick",
        "symbol": SYMBOL,
        "bid":    tick.bid,
        "ask":    tick.ask,
        "time":   datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
    }


def get_candles(timeframe: str = "M15", count: int = 200) -> Optional[dict]:
    tf = TF_MAP.get(timeframe)
    if tf is None:
        return None
    rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, count)
    if rates is None:
        return None
    candles = [
        {
            "time":        int(r["time"]),
            "open":        float(r["open"]),
            "high":        float(r["high"]),
            "low":         float(r["low"]),
            "close":       float(r["close"]),
            "volume":      int(r["real_volume"]),
            "tick_volume": int(r["tick_volume"]),
        }
        for r in rates
    ]
    return {"type": "candles", "timeframe": timeframe, "data": candles}


CRYSTAL_HA_FILE = r"C:\Users\nexag\AppData\Roaming\MetaQuotes\Terminal\Common\Files\crystal_ha_live.json"
_crystal_cache: dict = {}

def get_crystal_ha_from_file(timeframe: str) -> Optional[dict]:
    try:
        if not os.path.exists(CRYSTAL_HA_FILE):
            return None
        raw = open(CRYSTAL_HA_FILE, "rb").read()
        if raw[:2] == b"\xff\xfe":
            text = raw.decode("utf-16-le", errors="ignore").lstrip("\ufeff")
        elif raw[:2] == b"\xfe\xff":
            text = raw.decode("utf-16-be", errors="ignore").lstrip("\ufeff")
        else:
            text = raw.decode("utf-8", errors="ignore").lstrip("\ufeff")
        data = json.loads(text)
        if data.get("timeframe") != timeframe:
            return None
        return data
    except Exception as e:
        log.warning(f"crystal_ha_file read error: {e}")
        return None


def get_crystal_ha(timeframe: str, count: int = 100):
    log.debug(f"Crystal HA [{timeframe}]: hitung sendiri")
    if not mt5_connected: return None
    tf = TF_MAP.get(timeframe, mt5.TIMEFRAME_M15)
    CONFIRM_CANDLES = 3
    try:
        rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, count)
        if rates is None or len(rates) == 0:
            return None
        res = []
        prev_ha_o = 0.0
        prev_ha_c = 0.0
        ema20 = 0.0
        ema50 = 0.0
        pending_signal = None
        for i in range(len(rates)):
            r = rates[i]
            o, h, l, c = float(r[1]), float(r[2]), float(r[3]), float(r[4])
            if i == 0:
                ema20 = c; ema50 = c
            else:
                ema20 = (c - ema20) * (2 / 21) + ema20
                ema50 = (c - ema50) * (2 / 51) + ema50
            if i == 0:
                ha_o = (o + c) / 2
                ha_c = (o + h + l + c) / 4
                ha_h = h; ha_l = l
            else:
                ha_c = (o + h + l + c) / 4
                ha_o = (prev_ha_o + prev_ha_c) / 2
                ha_h = max(h, ha_o, ha_c)
                ha_l = min(l, ha_o, ha_c)
            prev_ha_o = ha_o
            prev_ha_c = ha_c
            is_bull = ha_c > ha_o
            if i == 0:
                color = "bullish_weak" if is_bull else "bearish_weak"
            else:
                prev_is_bull = res[-1]["ha_close"] > res[-1]["ha_open"]
                if is_bull:
                    color = "bullish_strong" if not prev_is_bull else "bullish_weak"
                else:
                    color = "bearish_strong" if prev_is_bull else "bearish_weak"
            circle_buy  = False
            circle_sell = False
            arrow_buy   = False
            arrow_sell  = False
            if i > 0:
                prev = res[-1]
                prev_bull = prev["ha_close"] > prev["ha_open"]
                if not prev_bull and is_bull:
                    circle_buy = True
                    pending_signal = {"type": "buy", "ref_high": ha_h, "ref_low": ha_l, "candles_waited": 0}
                elif prev_bull and not is_bull:
                    circle_sell = True
                    pending_signal = {"type": "sell", "ref_high": ha_h, "ref_low": ha_l, "candles_waited": 0}
                if pending_signal and not circle_buy and not circle_sell:
                    pending_signal["candles_waited"] += 1
                    if pending_signal["type"] == "buy":
                        if ha_c > pending_signal["ref_high"]:
                            arrow_buy = True
                            pending_signal = None
                        elif not is_bull or pending_signal["candles_waited"] >= CONFIRM_CANDLES:
                            pending_signal = None
                    elif pending_signal["type"] == "sell":
                        if ha_c < pending_signal["ref_low"]:
                            arrow_sell = True
                            pending_signal = None
                        elif is_bull or pending_signal["candles_waited"] >= CONFIRM_CANDLES:
                            pending_signal = None
            res.append({
                "time":        int(r[0]),
                "ha_open":     ha_o,
                "ha_high":     ha_h,
                "ha_low":      ha_l,
                "ha_close":    ha_c,
                "close":       c,
                "ema20":       ema20,
                "ema50":       ema50,
                "color":       color,
                "circle_buy":  circle_buy,
                "circle_sell": circle_sell,
                "arrow_buy":   arrow_buy,
                "arrow_sell":  arrow_sell,
            })
        circle_count = sum(1 for c in res if c["circle_buy"] or c["circle_sell"])
        arrow_count = sum(1 for c in res if c["arrow_buy"] or c["arrow_sell"])
        log.info(f"Crystal HA [{timeframe}]: {len(res)} candles, {circle_count} circles, {arrow_count} arrows")
        return {"type": "crystal_ha", "timeframe": timeframe, "data": res}
    except Exception as e:
        log.error(f"Error in get_crystal_ha: {e}")
        return None


def get_positions() -> dict:
    positions = mt5.positions_get(symbol=SYMBOL) or []
    data = []
    for p in positions:
        data.append({
            "ticket":     p.ticket,
            "type":       "buy" if p.type == 0 else "sell",
            "volume":     p.volume,
            "open_price": p.price_open,
            "sl":         p.sl,
            "tp":         p.tp,
            "profit":     p.profit,
            "open_time":  datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
        })
    return {"type": "positions", "data": data}


def get_orders() -> dict:
    data = []
    for tid, o in rejection_orders.items():
        data.append({
            "ticket":        tid,
            "type":          f"rejection_{o['direction']}",
            "volume":        o["volume"],
            "trigger_price": o["trigger_price"],
            "entry_price":   o["entry_price"],
            "status":        o["status"],
            "created_at":    o["created_at"],
        })
    return {"type": "orders", "data": data}


# ── Session Detector ──────────────────────────────────────────────────────────
def get_active_sessions(utc_hour: int) -> list[str]:
    sessions = []
    if utc_hour >= 22 or utc_hour < 7:
        sessions.append("sydney")
    if 0 <= utc_hour < 9:
        sessions.append("tokyo")
    if 7 <= utc_hour < 16:
        sessions.append("london")
    if 12 <= utc_hour < 21:
        sessions.append("new_york")
    return sessions


# ── Rejection Entry Logic ─────────────────────────────────────────────────────
async def rejection_monitor_loop():
    global rejection_counter
    while True:
        await asyncio.sleep(1)
        if not mt5_connected:
            continue
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick is None:
            continue
        now = datetime.now(tz=timezone.utc)
        for tid in list(rejection_orders.keys()):
            o = rejection_orders[tid]
            direction     = o["direction"]
            trigger_price = o["trigger_price"]
            entry_price   = o["entry_price"]
            timeout_dt    = o["timeout_dt"]
            status        = o["status"]
            if now >= timeout_dt and status not in ("executed", "timeout"):
                o["status"] = "timeout"
                del rejection_orders[tid]
                await broadcast({"type": "rejection_status", "ticket": tid, "status": "timeout", "message": "Rejection order timed out"})
                continue
            if direction == "sell":
                if status == "waiting_trigger" and tick.ask >= trigger_price:
                    o["status"] = "waiting_rejection"
                    await broadcast({"type": "rejection_status", "ticket": tid, "status": "waiting_rejection"})
                elif status == "waiting_rejection" and tick.bid <= entry_price:
                    result = _place_market_order("sell", o["volume"])
                    if result:
                        o["status"] = "executed"
                        del rejection_orders[tid]
                        await broadcast({"type": "rejection_status", "ticket": tid, "status": "executed", "exec_price": tick.bid})
            elif direction == "buy":
                if status == "waiting_trigger" and tick.bid <= trigger_price:
                    o["status"] = "waiting_rejection"
                    await broadcast({"type": "rejection_status", "ticket": tid, "status": "waiting_rejection"})
                elif status == "waiting_rejection" and tick.ask >= entry_price:
                    result = _place_market_order("buy", o["volume"])
                    if result:
                        o["status"] = "executed"
                        del rejection_orders[tid]
                        await broadcast({"type": "rejection_status", "ticket": tid, "status": "executed", "exec_price": tick.ask})


def get_equity() -> dict:
    if not mt5_connected:
        return {"balance": 0.0, "equity": 0.0, "margin": 0.0, "free_margin": 0.0}
    info = mt5.account_info()
    if info is None:
        return {"balance": 0.0, "equity": 0.0, "margin": 0.0, "free_margin": 0.0}
    return {
        "balance":     round(info.balance, 2),
        "equity":      round(info.equity, 2),
        "margin":      round(info.margin, 2),
        "free_margin": round(info.margin_free, 2),
    }


def _place_market_order(direction: str, volume: float) -> Optional[int]:
    """Kirim market order BERSIH — SL/TP/Trailing dihandle oleh EA AutoSLTP di MT5."""
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        return None
    order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
    price = tick.ask if direction == "buy" else tick.bid
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       SYMBOL,
        "volume":       volume,
        "type":         order_type,
        "price":        price,
        "sl":           0.0,
        "tp":           0.0,
        "deviation":    20,
        "magic":        20260505,
        "comment":      "OmegaV2",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"Order placed: {direction.upper()} {volume} @ {price:.2f} ticket={result.order}")
        return result.order
    log.error(f"Order failed: {mt5.last_error()}")
    return None


# ── Trend Calculator ──────────────────────────────────────────────────────────
def calculate_trend() -> dict:
    """Tentukan arah tren dari Crystal HA confluence semua TF.
    Hanya sebagai penentu arah BULLISH/BEARISH — bukan filter entry.
    """
    all_ha: dict[str, list] = {}
    for tf in ["H4", "H1", "M15", "M5", "M1"]:
        ha = get_crystal_ha(tf, count=10)
        if ha and ha["data"]:
            all_ha[tf] = ha["data"]
        else:
            all_ha[tf] = []

    scores: dict[str, tuple] = {}
    for tf, candles in all_ha.items():
        if len(candles) < 5:
            scores[tf] = ("none", "sideways")
            continue
        last5 = candles[-5:]
        bs = sum(1 for c in last5 if c["color"] == "bullish_strong")
        bw = sum(1 for c in last5 if c["color"] == "bullish_weak")
        rs = sum(1 for c in last5 if c["color"] == "bearish_strong")
        rw = sum(1 for c in last5 if c["color"] == "bearish_weak")
        if bs >= 3:
            scores[tf] = ("buy", "strong")
        elif bs + bw >= 3:
            scores[tf] = ("buy", "weak")
        elif rs >= 3:
            scores[tf] = ("sell", "strong")
        elif rs + rw >= 3:
            scores[tf] = ("sell", "weak")
        else:
            scores[tf] = ("none", "sideways")

    h4_dir = scores.get("H4", ("none", "sideways"))[0]
    if h4_dir == "none":
        return {"direction": "none", "confidence": 0, "scores": scores}

    weight = {"H4": 30, "H1": 25, "M15": 20, "M5": 15, "M1": 10}
    confidence = 0.0
    for tf, (direction, strength) in scores.items():
        if direction == h4_dir:
            confidence += weight[tf] if strength == "strong" else weight[tf] * 0.6

    valid_dirs = [d for d, _ in scores.values() if d != "none"]
    if valid_dirs and all(d == h4_dir for d in valid_dirs):
        confidence = min(confidence * 1.1, 95)

    return {
        "direction":  h4_dir,
        "confidence": round(confidence),
        "scores":     {tf: {"direction": d, "strength": s} for tf, (d, s) in scores.items()},
    }


# ── Entry Signal helper (untuk backward compat) ───────────────────────────────
def get_entry_signal() -> dict:
    ha = get_crystal_ha("M15", count=5)
    if not ha or not ha["data"] or len(ha["data"]) < 2:
        return {"signal": "none", "circle": None, "arrow": None}
    latest = ha["data"][-1]
    prev   = ha["data"][-2]
    circle = None
    arrow  = None
    if latest.get("circle_buy"):
        circle = {"type": "buy", "time": latest["time"]}
    elif latest.get("circle_sell"):
        circle = {"type": "sell", "time": latest["time"]}
    elif prev.get("circle_buy"):
        circle = {"type": "buy", "time": prev["time"]}
    elif prev.get("circle_sell"):
        circle = {"type": "sell", "time": prev["time"]}
    if latest.get("arrow_buy"):
        arrow = {"type": "buy", "time": latest["time"], "price": latest["ha_close"]}
    elif latest.get("arrow_sell"):
        arrow = {"type": "sell", "time": latest["time"], "price": latest["ha_close"]}
    if arrow:
        return {"signal": "arrow", "circle": circle, "arrow": arrow}
    if circle:
        return {"signal": "circle", "circle": circle, "arrow": None}
    return {"signal": "none", "circle": None, "arrow": None}


# ── Daily Loss Tracker ────────────────────────────────────────────────────────
async def daily_loss_reset_loop():
    while True:
        now = datetime.now(tz=timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
        wait_secs = (next_midnight - now).total_seconds()
        await asyncio.sleep(wait_secs)
        today_start = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(today_start, datetime.now(tz=timezone.utc)) or []
        loss = sum(d.profit for d in deals if d.profit < 0)
        auto_state["daily_loss"] = abs(loss)
        auto_state["trades_today"] = 0
        auto_state["last_entry_candle"] = 0
        log.info(f"Daily stats reset. Loss today: ${auto_state['daily_loss']:.2f}")


def update_daily_loss():
    if not mt5_connected:
        return
    today_start = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(today_start, datetime.now(tz=timezone.utc)) or []
    loss = sum(d.profit for d in deals if d.profit < 0 and d.symbol == SYMBOL)
    auto_state["daily_loss"] = abs(loss)


def get_current_m15_candle_time() -> int:
    now = datetime.now(tz=timezone.utc)
    minute_block = (now.minute // 15) * 15
    candle_start = now.replace(minute=minute_block, second=0, microsecond=0)
    return int(candle_start.timestamp())


def check_safety(signal_direction: str) -> tuple[bool, str]:
    if not mt5_connected:
        return False, "MT5 not connected"
    positions = mt5.positions_get(symbol=SYMBOL) or []
    if len(positions) >= auto_state["max_positions"]:
        return False, f"Max positions ({auto_state['max_positions']}) reached"
    current_candle = get_current_m15_candle_time()
    if auto_state["last_entry_candle"] == current_candle:
        return False, "Already entered this M15 candle"
    update_daily_loss()
    if auto_state["daily_loss"] >= auto_state["max_daily_loss"]:
        return False, f"Daily loss limit ${auto_state['max_daily_loss']:.2f} reached"
    utc_hour = datetime.now(tz=timezone.utc).hour
    active = get_active_sessions(utc_hour)
    if not any(s in auto_state["session_filter"] for s in active):
        return False, f"No active session (current: {active})"
    if signal_direction == "buy" and not auto_state["allow_buy"]:
        return False, "BUY direction disabled"
    if signal_direction == "sell" and not auto_state["allow_sell"]:
        return False, "SELL direction disabled"
    if positions:
        existing_type = "buy" if positions[0].type == 0 else "sell"
        if existing_type != signal_direction:
            return False, f"Conflicting open {existing_type} position"
    return True, "OK"


# ── Auto Trading Loop ─────────────────────────────────────────────────────────
async def auto_trading_loop():
    """
    Auto Trading Logic — Signal Omega V2
    =====================================
    TREN  : Confluence semua TF (H4+H1+M15+M5+M1) → info/display saja, TIDAK memblokir entry
    ENTRY : M15 saja, dua jenis sinyal:

      CIRCLE (searah tren):
        - Circle muncul di candle M15 yang sudah CLOSED (data[-2])
        - Entry di candle baru yang sedang berjalan (data[-1])
        - Alasan: circle di candle live bisa hilang/batal sebelum close

      ARROW (melawan tren / counter-trend):
        - Arrow muncul di candle live (data[-1]) → langsung entry market
        - Arrow sudah merupakan konfirmasi lebih kuat, tidak perlu tunggu close

    RULES UMUM:
      - Max posisi sesuai setting (default 2)
      - 1 entry per candle M15 (same candle tidak boleh entry 2x)
      - Tren sideways / H4 sideways TIDAK menghalangi entry — sinyal tetap jalan
    """
    while True:
        await asyncio.sleep(auto_state["scan_interval"])

        if not auto_state["enabled"]:
            continue

        if not mt5_connected:
            auto_state["paused_mt5_disconnect"] = True
            log.warning("Auto trading paused — MT5 disconnected")
            continue

        auto_state["last_scan"] = datetime.now(tz=timezone.utc).isoformat()

        # Step 1: Hitung tren — hanya untuk display, TIDAK memblokir entry
        trend = calculate_trend()
        trend_dir  = trend["direction"]
        trend_conf = trend["confidence"]
        auto_state["trend_direction"]  = trend_dir
        auto_state["trend_confidence"] = trend_conf

        # Step 2: Cek posisi open — max sesuai setting
        positions = mt5.positions_get(symbol=SYMBOL) or []
        if len(positions) >= auto_state["max_positions"]:
            existing_types = "/".join(set("BUY" if p.type == 0 else "SELL" for p in positions))
            auto_state["last_signal"] = f"Holding {existing_types} ({len(positions)}/{auto_state['max_positions']}) — tunggu close"
            _auto_log("HOLD", f"Max posisi {auto_state['max_positions']} tercapai — tunggu close", "skip")
            await broadcast_auto_status()
            continue

        # Step 3: Ambil Crystal HA M15 — butuh minimal 3 candle
        ha = get_crystal_ha("M15", count=10)
        if not ha or not ha["data"] or len(ha["data"]) < 3:
            await broadcast_auto_status()
            continue

        # candle[-2] = candle terakhir yang sudah CLOSED (untuk circle)
        # candle[-1] = candle live yang sedang berjalan (untuk arrow & waktu entry)
        closed_candle = ha["data"][-2]
        live_candle   = ha["data"][-1]
        live_time     = live_candle["time"]

        # ── Cek ARROW di candle live → langsung entry ──
        arrow_buy  = live_candle.get("arrow_buy",  False)
        arrow_sell = live_candle.get("arrow_sell", False)

        # ── Cek CIRCLE di candle yang sudah CLOSED → entry di candle baru ──
        circle_buy  = closed_candle.get("circle_buy",  False)
        circle_sell = closed_candle.get("circle_sell", False)

        entry_dir   = None
        signal_type = None
        is_counter  = False

        if arrow_buy or arrow_sell:
            # Arrow → langsung entry tanpa tunggu close
            entry_dir   = "buy" if arrow_buy else "sell"
            signal_type = "arrow"
            is_counter  = (entry_dir != trend_dir) if trend_dir != "none" else False

        elif circle_buy or circle_sell:
            # Circle di candle closed → entry sekarang di candle baru
            entry_dir   = "buy" if circle_buy else "sell"
            signal_type = "circle"
            is_counter  = False  # circle hanya untuk searah tren

        if entry_dir is None:
            auto_state["entry_signal"]  = "none"
            auto_state["circle_active"] = None
            trend_label = trend_dir.upper() if trend_dir != "none" else "SIDEWAYS"
            auto_state["last_signal"] = f"TREN={trend_label} | Menunggu sinyal M15..."
            await broadcast_auto_status()
            continue

        auto_state["entry_signal"]  = signal_type
        auto_state["circle_active"] = entry_dir

        trend_label  = trend_dir.upper() if trend_dir != "none" else "SIDEWAYS"
        signal_label = f"{'↕ Counter' if is_counter else '↗ Trend'} {signal_type.upper()}"
        auto_state["last_signal"] = (
            f"TREN={trend_label} | {signal_label} {entry_dir.upper()} M15 → ENTRY!"
        )

        # Step 4: Sudah entry di candle M15 ini?
        if auto_state["last_entry_candle"] == live_time:
            _auto_log("SKIP", "Sudah entry di candle M15 ini — tunggu candle baru", "skip")
            await broadcast_auto_status()
            continue

        # Step 5: Guards (daily loss, session, direction lock)
        update_daily_loss()
        if auto_state["daily_loss"] >= auto_state["max_daily_loss"]:
            _auto_log("SKIP", f"Daily loss limit ${auto_state['max_daily_loss']:.2f} tercapai", "skip")
            await broadcast_auto_status()
            continue

        utc_hour = datetime.now(tz=timezone.utc).hour
        active_sessions = get_active_sessions(utc_hour)
        if auto_state["session_filter"] and not any(s in auto_state["session_filter"] for s in active_sessions):
            _auto_log("SKIP", f"Di luar session trading (current: {active_sessions})", "skip")
            await broadcast_auto_status()
            continue

        if entry_dir == "buy" and not auto_state["allow_buy"]:
            _auto_log("SKIP", "BUY direction dikunci di settings", "skip")
            await broadcast_auto_status()
            continue
        if entry_dir == "sell" and not auto_state["allow_sell"]:
            _auto_log("SKIP", "SELL direction dikunci di settings", "skip")
            await broadcast_auto_status()
            continue

        # ════════════════════════════════════════════════════════════════════════
        # NEW: SMART FILTERS (GATE #7, #8, #9)
        # ════════════════════════════════════════════════════════════════════════
        if FILTERS_AVAILABLE:
            filter_cfg = cfg.get("filters", {})
            filter_result = await check_all_filters_async(
                symbol=SYMBOL,
                direction=entry_dir,
                signal_type=signal_type,
                candle_time=live_time,
                enable_zone=filter_cfg.get("zone_enabled", True),
                enable_sideways=filter_cfg.get("sideways_enabled", True),
                enable_timing=filter_cfg.get("timing_enabled", True),
                timing_wait_mode=filter_cfg.get("timing_wait_mode", True),
                max_timing_wait=filter_cfg.get("max_timing_wait_sec", 900),
                shadow_mode=filter_cfg.get("shadow_mode", False),
            )
            
            if filter_result.final_decision != 'ENTRY':
                log.info(f"[FILTER BLOCKED] {filter_result.blocked_by}: skipping entry")
                auto_state["last_entry_candle"] = live_time
                await broadcast_auto_status()
                continue

        # ════════════════════════════════════════════════════════════════════════
        # EXECUTE ORDER
        # ════════════════════════════════════════════════════════════════════════
        tick = mt5.symbol_info_tick(SYMBOL)
        entry_price = (tick.ask if entry_dir == "buy" else tick.bid) if tick else 0.0

        ticket = _place_market_order(entry_dir, auto_state["lot_size"])
        if ticket:
            auto_state["trades_today"]      += 1
            auto_state["last_entry_candle"]  = live_time
            counter_label = " [COUNTER-TREND via Arrow]" if is_counter else " [WITH TREND via Circle]"
            msg = (
                f"{entry_dir.upper()} {auto_state['lot_size']} @ {entry_price:.2f} "
                f"| Tren={trend_label} {trend_conf}%{counter_label}"
            )
            _auto_log("TRADE", msg, "executed")
            await broadcast({
                "type":        "auto_trade_executed",
                "direction":   entry_dir,
                "signal_type": signal_type,
                "is_counter":  is_counter,
                "volume":      auto_state["lot_size"],
                "entry":       entry_price,
                "confidence":  trend_conf,
                "ticket":      ticket,
            })
        else:
            _auto_log("ERROR", "Order send gagal — cek log MT5", "error")

        await broadcast_auto_status()


def _auto_log(action: str, reason: str, result: str):
    entry = {
        "time":   datetime.now(tz=timezone.utc).strftime("%H:%M:%S"),
        "action": action,
        "reason": reason,
        "result": result,
    }
    auto_state["log"].insert(0, entry)
    auto_state["log"] = auto_state["log"][:50]
    log.info(f"[AUTO] {action}: {reason}")


# ── Stream Helpers ────────────────────────────────────────────────────────────
async def broadcast_auto_status():
    acc = get_equity()
    td = auto_state.get("trend_direction", "none")
    ha_trend = "BULLISH" if td == "buy" else "BEARISH" if td == "sell" else "—"
    entry_sig = auto_state.get("entry_signal", "none")
    circle    = auto_state.get("circle_active")
    enabled   = auto_state.get("enabled", False)
    if not enabled:
        status_text = "Auto OFF"
    elif entry_sig == "circle" and circle:
        status_text = f"Circle {circle.upper()} — masuk posisi!"
    elif entry_sig == "arrow" and circle:
        status_text = f"Arrow {circle.upper()} — masuk posisi!"
    else:
        status_text = f"Menunggu sinyal M15 ({ha_trend})"

    payload = {
        "type":                    "auto_trading_status",
        "enabled":                 auto_state["enabled"],
        "scan_interval":           auto_state["scan_interval"],
        "max_positions":           auto_state["max_positions"],
        "max_daily_loss":          auto_state["max_daily_loss"],
        "session_filter":          auto_state["session_filter"],
        "daily_loss_current":      auto_state["daily_loss"],
        "last_scan":               auto_state["last_scan"],
        "last_signal":             auto_state["last_signal"],
        "trend_direction":         auto_state["trend_direction"],
        "trend_confidence":        auto_state["trend_confidence"],
        "entry_signal":            auto_state["entry_signal"],
        "circle_active":           auto_state["circle_active"],
        "last_entry_candle":       auto_state["last_entry_candle"],
        "total_auto_trades_today": auto_state["trades_today"],
        "auto_log":                auto_state["log"][:20],
        "ha_trend":                ha_trend,
        "status_text":             status_text,
        "equity":                  acc["equity"],
        "balance":                 acc["balance"],
        "free_margin":             acc["free_margin"],
    }
    await broadcast(payload)


# ── WebSocket Command Handler ─────────────────────────────────────────────────
async def handle_command(cmd: dict, ws: WebSocketServerProtocol):
    global rejection_counter
    action = cmd.get("cmd", "")

    if action == "get_candles":
        tf    = cmd.get("timeframe", "M15")
        count = cmd.get("count", 200)
        data  = get_candles(tf, count)
        if data:
            await ws.send(json.dumps(data, default=str))
        else:
            await ws.send(json.dumps({"type": "error", "message": f"Cannot get candles for {tf}"}))

    elif action == "order_market":
        direction = cmd.get("type", "buy")
        volume    = float(cmd.get("volume", 0.01))
        ticket    = _place_market_order(direction, volume)
        if ticket:
            await ws.send(json.dumps({"type": "order_result", "status": "ok", "ticket": ticket}))
        else:
            await ws.send(json.dumps({"type": "error", "message": "Order failed — check MT5 logs"}))

    elif action == "order_pending_rejection":
        rejection_counter += 1
        tid = f"REJ{rejection_counter:04d}"
        timeout_min = int(cmd.get("timeout_minutes", 5))
        rejection_orders[tid] = {
            "direction":     cmd.get("direction", "sell"),
            "volume":        float(cmd.get("volume", 0.01)),
            "trigger_price": float(cmd.get("trigger_price", 0)),
            "entry_price":   float(cmd.get("entry_price", 0)),
            "status":        "waiting_trigger",
            "created_at":    datetime.now(tz=timezone.utc).isoformat(),
            "timeout_dt":    datetime.now(tz=timezone.utc) + timedelta(minutes=timeout_min),
        }
        await ws.send(json.dumps({"type": "order_result", "status": "ok", "ticket": tid}))
        await broadcast(get_orders())

    elif action == "close_position":
        ticket = int(cmd.get("ticket", 0))
        pos    = mt5.positions_get(ticket=ticket)
        if pos:
            p = pos[0]
            tick = mt5.symbol_info_tick(SYMBOL)
            close_price = tick.bid if p.type == 0 else tick.ask
            req = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       SYMBOL,
                "volume":       p.volume,
                "type":         mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                "position":     ticket,
                "price":        close_price,
                "deviation":    20,
                "magic":        20260505,
                "comment":      "OmegaV2 close",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            ok  = res and res.retcode == mt5.TRADE_RETCODE_DONE
            await ws.send(json.dumps({"type": "order_result", "status": "ok" if ok else "error", "ticket": ticket}))
        else:
            await ws.send(json.dumps({"type": "error", "message": f"Position {ticket} not found"}))

    elif action == "close_all":
        positions = mt5.positions_get(symbol=SYMBOL) or []
        results   = []
        for p in positions:
            tick        = mt5.symbol_info_tick(SYMBOL)
            close_price = tick.bid if p.type == 0 else tick.ask
            req = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       SYMBOL,
                "volume":       p.volume,
                "type":         mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                "position":     p.ticket,
                "price":        close_price,
                "deviation":    20,
                "magic":        20260505,
                "comment":      "OmegaV2 close_all",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(req)
            results.append({"ticket": p.ticket, "ok": res and res.retcode == mt5.TRADE_RETCODE_DONE})
        await ws.send(json.dumps({"type": "close_all_result", "results": results}))

    elif action == "cancel_order":
        ticket = str(cmd.get("ticket", ""))
        if ticket in rejection_orders:
            del rejection_orders[ticket]
            await ws.send(json.dumps({"type": "order_result", "status": "cancelled", "ticket": ticket}))
            await broadcast(get_orders())
        else:
            await ws.send(json.dumps({"type": "error", "message": f"Order {ticket} not found"}))

    elif action == "set_auto_trading":
        updatable_keys = [
            "enabled", "scan_interval", "lot_size",
            "max_positions", "max_daily_loss", "session_filter",
            "allow_buy", "allow_sell", "follow_trend",
            "logic_timeframe",
        ]
        for key in updatable_keys:
            if key in cmd:
                auto_state[key] = cmd[key]
        log.info(f"Auto settings updated: enabled={auto_state['enabled']} lot={auto_state.get('lot_size',0.01)}")
        await broadcast_auto_status()

    elif action == "get_auto_status":
        await broadcast_auto_status()

    elif action == "reconnect_mt5":
        global mt5_connected, mt5_reconnect_attempts
        disconnect_mt5()
        mt5_reconnect_attempts = 0
        ok = connect_mt5(
            login    = cmd.get("login"),
            password = cmd.get("password"),
            server   = cmd.get("server"),
        )
        if ok:
            await ws.send(json.dumps({"type": "connected", "message": "MT5 reconnected with new credentials"}))
        else:
            await ws.send(json.dumps({"type": "error", "message": "MT5 reconnect failed"}))

    else:
        await ws.send(json.dumps({"type": "error", "message": f"Unknown command: {action}"}))


# ── WebSocket Client Handler ──────────────────────────────────────────────────
async def client_handler(ws: WebSocketServerProtocol):
    clients.add(ws)
    log.info(f"Client connected: {ws.remote_address} (total: {len(clients)})")
    await ws.send(json.dumps({"type": "connected", "message": "Bridge ready", "mt5": mt5_connected}))
    if mt5_connected:
        tick = get_tick()
        if tick:
            await ws.send(json.dumps(tick, default=str))
        await ws.send(json.dumps(get_positions(), default=str))
        await ws.send(json.dumps(get_orders(), default=str))
        await broadcast_auto_status()
    try:
        async for raw in ws:
            try:
                cmd = json.loads(raw)
                await handle_command(cmd, ws)
            except json.JSONDecodeError:
                await ws.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(ws)
        log.info(f"Client disconnected: {ws.remote_address} (total: {len(clients)})")


# ── Streaming Loops ───────────────────────────────────────────────────────────
async def tick_stream_loop():
    last_bid = 0.0
    last_positions_time = 0.0
    while True:
        await asyncio.sleep(0.5)
        if not mt5_connected or not clients:
            continue
        now = asyncio.get_event_loop().time()
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick and abs(tick.bid - last_bid) >= 0.01:
            last_bid = tick.bid
            await broadcast({
                "type":   "tick",
                "symbol": SYMBOL,
                "bid":    tick.bid,
                "ask":    tick.ask,
                "time":   datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
            })
        if now - last_positions_time >= 3.0:
            last_positions_time = now
            await broadcast(get_positions())
            await broadcast(get_orders())


async def candle_stream_loop():
    tf_list = ["M1", "M5", "M15", "H1", "H4"]
    tf_index = 0
    last_full_update = 0.0
    while True:
        await asyncio.sleep(1)
        if not mt5_connected or not clients:
            continue
        now = asyncio.get_event_loop().time()
        tf = tf_list[tf_index % len(tf_list)]
        tf_index += 1
        cha = get_crystal_ha(tf, 250)
        if cha:
            await broadcast(cha)
        if now - last_full_update >= 30:
            last_full_update = now
            for t in tf_list:
                candles = get_candles(t, 200)
                if candles:
                    await broadcast(candles)
                await asyncio.sleep(0.2)


async def heartbeat_loop():
    while True:
        await asyncio.sleep(10)
        dead = set()
        for ws in list(clients):
            try:
                await ws.ping()
            except Exception:
                dead.add(ws)
        clients.difference_update(dead)


# ── Main Entry Point ──────────────────────────────────────────────────────────
async def main():
    log.info("=" * 55)
    log.info("  BTCUSD SIGNAL OMEGA V2 — BRIDGE")
    log.info("=" * 55)
    if not connect_mt5():
        log.warning("Initial MT5 connect failed — will retry in background")
    server = await websockets.serve(client_handler, "0.0.0.0", WS_PORT)
    log.info(f"WebSocket server listening on ws://0.0.0.0:{WS_PORT}")
    await asyncio.gather(
        server.wait_closed(),
        mt5_reconnect_loop(),
        tick_stream_loop(),
        candle_stream_loop(),
        rejection_monitor_loop(),
        auto_trading_loop(),
        daily_loss_reset_loop(),
        heartbeat_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bridge stopped by user.")
        disconnect_mt5()
