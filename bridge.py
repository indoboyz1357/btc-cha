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

# ── Config ───────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> dict:
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

cfg = load_config()

SYMBOL                  = cfg.get("symbol", "BTCUSD")
WS_PORT                 = cfg.get("websocket_port", 8765)
TRAILING_TRIGGER_PTS    = cfg.get("trailing_trigger_points", 500)
TRAILING_STOP_PTS       = cfg.get("trailing_stop_points", 250)

at_cfg                  = cfg.get("auto_trading", {})
AUTO_ENABLED            = at_cfg.get("enabled", False)
AUTO_SCAN_INTERVAL      = at_cfg.get("scan_interval_seconds", 30)
AUTO_MIN_CONFIDENCE     = at_cfg.get("min_confidence", 70)
AUTO_LOT_SIZE           = at_cfg.get("lot_size", 0.01)
AUTO_MAX_POSITIONS      = at_cfg.get("max_positions", 2)
AUTO_MAX_DAILY_LOSS     = at_cfg.get("max_daily_loss_usd", 10.0)
AUTO_SESSION_FILTER     = at_cfg.get("session_filter", ["london", "new_york"])
AUTO_ALLOW_BUY          = at_cfg.get("allow_buy", True)
AUTO_ALLOW_SELL         = at_cfg.get("allow_sell", True)

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

# Trailing state: ticket → {"high": float, "low": float, "triggered": bool}
trailing_state: dict = {}

# Rejection orders: ticket → dict
rejection_orders: dict = {}
rejection_counter: int = 0

# Auto trading state
auto_state = {
    "enabled":            AUTO_ENABLED,
    "scan_interval":      AUTO_SCAN_INTERVAL,
    "min_confidence":     AUTO_MIN_CONFIDENCE,
    "lot_size":           AUTO_LOT_SIZE,
    "max_positions":      AUTO_MAX_POSITIONS,
    "max_daily_loss":     AUTO_MAX_DAILY_LOSS,
    "session_filter":     AUTO_SESSION_FILTER,
    "allow_buy":          AUTO_ALLOW_BUY,
    "allow_sell":         AUTO_ALLOW_SELL,
    "daily_loss":         0.0,
    "trades_today":       0,
    "last_scan":          "",
    "last_signal":        "",
    "log":                [],
    "paused_mt5_disconnect": False,
}

# ── MT5 Connection ────────────────────────────────────────────────────────────
def connect_mt5(login: int = None, password: str = None, server: str = None) -> bool:
    global mt5_connected, mt5_reconnect_attempts
    login    = login    or cfg["mt5_login"]
    password = password or cfg["mt5_password"]
    server   = server   or cfg["mt5_server"]

    if not mt5.initialize():
        log.error("mt5.initialize() failed")
        return False

    authorized = mt5.login(login, password=password, server=server)
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
    """Background task: keep MT5 connected with exponential backoff."""
    global mt5_connected, mt5_reconnect_attempts
    while True:
        await asyncio.sleep(5)
        if not mt5_connected:
            delay = min(2 ** mt5_reconnect_attempts, 30)
            log.info(f"MT5 reconnect attempt #{mt5_reconnect_attempts+1} in {delay}s…")
            await asyncio.sleep(delay)
            if connect_mt5():
                # resume auto trading if it was paused due to disconnect
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


def get_crystal_ha(timeframe: str = "M15", count: int = 50) -> Optional[dict]:
    tf = TF_MAP.get(timeframe)
    if tf is None:
        return None

    # Buffer indices as per Crystal Heikin Ashi indicator
    b0 = mt5.copy_buffer("Crystal Heikin Ashi", 0, SYMBOL, tf, 0, count)  # HA Open
    b1 = mt5.copy_buffer("Crystal Heikin Ashi", 1, SYMBOL, tf, 0, count)  # HA High
    b2 = mt5.copy_buffer("Crystal Heikin Ashi", 2, SYMBOL, tf, 0, count)  # HA Low
    b3 = mt5.copy_buffer("Crystal Heikin Ashi", 3, SYMBOL, tf, 0, count)  # HA Close
    b4 = mt5.copy_buffer("Crystal Heikin Ashi", 4, SYMBOL, tf, 0, count)  # Color

    rates = mt5.copy_rates_from_pos(SYMBOL, tf, 0, count)

    if any(x is None for x in [b0, b1, b2, b3, b4, rates]):
        log.warning(f"Crystal HA buffer read failed for {timeframe}")
        return None

    candles = []
    for i in range(len(rates)):
        color_idx = int(round(b4[i])) if not (b4[i] != b4[i]) else 0  # NaN guard
        color_str = COLOR_MAP.get(color_idx, "bullish_weak")

        # Reversal signal: color switched from strong→weak or direction change
        prev_color = int(round(b4[i - 1])) if i > 0 else color_idx
        reversal = (color_idx in [1, 2]) and (prev_color in [0, 3])

        candles.append({
            "time":            int(rates[i]["time"]),
            "ha_open":         float(b0[i]),
            "ha_high":         float(b1[i]),
            "ha_low":          float(b2[i]),
            "ha_close":        float(b3[i]),
            "color":           color_str,
            "reversal_signal": reversal,
        })

    return {"type": "crystal_ha", "timeframe": timeframe, "data": candles}


def get_positions() -> dict:
    positions = mt5.positions_get(symbol=SYMBOL) or []
    data = []
    for p in positions:
        ts = trailing_state.get(p.ticket, {})
        data.append({
            "ticket":          p.ticket,
            "type":            "buy" if p.type == 0 else "sell",
            "volume":          p.volume,
            "open_price":      p.price_open,
            "sl":              p.sl,
            "tp":              p.tp,
            "profit":          p.profit,
            "open_time":       datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
            "trailing_status": "active" if ts.get("triggered") else "standby",
            "trailing_high":   ts.get("high", 0.0),
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
            "sl":            o["sl"],
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


# ── Trailing Stop Engine ──────────────────────────────────────────────────────
async def trailing_stop_loop():
    """Monitor all positions and apply trailing stop logic every second."""
    while True:
        await asyncio.sleep(1)
        if not mt5_connected:
            continue
        positions = mt5.positions_get(symbol=SYMBOL) or []
        for p in positions:
            tick = mt5.symbol_info_tick(SYMBOL)
            if tick is None:
                continue

            ts = trailing_state.setdefault(p.ticket, {"triggered": False, "high": p.price_open, "low": p.price_open})

            if p.type == 0:  # BUY
                ts["high"] = max(ts["high"], tick.bid)
                profit_pts = (tick.bid - p.price_open) / mt5.symbol_info(SYMBOL).point

                if not ts["triggered"] and profit_pts >= TRAILING_TRIGGER_PTS:
                    ts["triggered"] = True
                    log.info(f"Trailing triggered for BUY #{p.ticket}")

                if ts["triggered"]:
                    new_sl = ts["high"] - TRAILING_STOP_PTS * mt5.symbol_info(SYMBOL).point
                    if new_sl > p.sl + mt5.symbol_info(SYMBOL).point:
                        _modify_sl(p.ticket, new_sl)
                        await broadcast({
                            "type":       "trailing_update",
                            "ticket":     p.ticket,
                            "new_sl":     new_sl,
                            "high_price": ts["high"],
                        })

            else:  # SELL
                ts["low"] = min(ts["low"], tick.ask)
                profit_pts = (p.price_open - tick.ask) / mt5.symbol_info(SYMBOL).point

                if not ts["triggered"] and profit_pts >= TRAILING_TRIGGER_PTS:
                    ts["triggered"] = True
                    log.info(f"Trailing triggered for SELL #{p.ticket}")

                if ts["triggered"]:
                    new_sl = ts["low"] + TRAILING_STOP_PTS * mt5.symbol_info(SYMBOL).point
                    if new_sl < p.sl - mt5.symbol_info(SYMBOL).point:
                        _modify_sl(p.ticket, new_sl)
                        await broadcast({
                            "type":       "trailing_update",
                            "ticket":     p.ticket,
                            "new_sl":     new_sl,
                            "low_price":  ts["low"],
                        })

        # Clean up closed positions from trailing_state
        open_tickets = {p.ticket for p in positions}
        for t in list(trailing_state.keys()):
            if t not in open_tickets:
                del trailing_state[t]


def _modify_sl(ticket: int, sl: float) -> bool:
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return False
    p = pos[0]
    req = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   SYMBOL,
        "position": ticket,
        "sl":       sl,
        "tp":       p.tp,
    }
    res = mt5.order_send(req)
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"SL modified #{ticket} → {sl:.2f}")
        return True
    log.error(f"SL modify failed #{ticket}: {mt5.last_error()}")
    return False


# ── Rejection Entry Logic ─────────────────────────────────────────────────────
async def rejection_monitor_loop():
    """Monitor rejection orders every second."""
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

            # Timeout check
            if now >= timeout_dt and status not in ("executed", "timeout"):
                o["status"] = "timeout"
                del rejection_orders[tid]
                await broadcast({
                    "type":    "rejection_status",
                    "ticket":  tid,
                    "status":  "timeout",
                    "message": "Rejection order timed out",
                })
                continue

            if direction == "sell":
                if status == "waiting_trigger" and tick.ask >= trigger_price:
                    o["status"] = "waiting_rejection"
                    await broadcast({"type": "rejection_status", "ticket": tid, "status": "waiting_rejection"})

                elif status == "waiting_rejection" and tick.bid <= entry_price:
                    # Execute SELL
                    result = _place_market_order("sell", o["volume"], o["sl"])
                    if result:
                        o["status"] = "executed"
                        del rejection_orders[tid]
                        await broadcast({"type": "rejection_status", "ticket": tid, "status": "executed", "exec_price": tick.bid})

            elif direction == "buy":
                if status == "waiting_trigger" and tick.bid <= trigger_price:
                    o["status"] = "waiting_rejection"
                    await broadcast({"type": "rejection_status", "ticket": tid, "status": "waiting_rejection"})

                elif status == "waiting_rejection" and tick.ask >= entry_price:
                    result = _place_market_order("buy", o["volume"], o["sl"])
                    if result:
                        o["status"] = "executed"
                        del rejection_orders[tid]
                        await broadcast({"type": "rejection_status", "ticket": tid, "status": "executed", "exec_price": tick.ask})


def _place_market_order(direction: str, volume: float, sl: float) -> Optional[int]:
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
        "sl":           sl,
        "tp":           0.0,
        "deviation":    20,
        "magic":        20260505,
        "comment":      "OmegaV2",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        log.info(f"Order placed: {direction.upper()} {volume} @ {price:.2f} SL={sl:.2f} ticket={result.order}")
        return result.order
    log.error(f"Order failed: {mt5.last_error()}")
    return None


# ── Signal Calculator (Rule-Based) ────────────────────────────────────────────
def calculate_signal() -> dict:
    """Calculate trade signal from Crystal HA confluence across all TFs."""
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
        return {"direction": "none", "confidence": 0, "entry": 0, "sl": 0, "scores": scores}

    weight = {"H4": 30, "H1": 25, "M15": 20, "M5": 15, "M1": 10}
    confidence = 0.0
    for tf, (direction, strength) in scores.items():
        if direction == h4_dir:
            confidence += weight[tf] if strength == "strong" else weight[tf] * 0.6

    valid_dirs = [d for d, _ in scores.values() if d != "none"]
    if valid_dirs and all(d == h4_dir for d in valid_dirs):
        confidence = min(confidence * 1.1, 95)

    m15_candles = all_ha.get("M15", [])
    entry = m15_candles[-1]["ha_close"] if m15_candles else 0.0

    last10 = m15_candles[-10:] if len(m15_candles) >= 10 else m15_candles
    pt = mt5.symbol_info(SYMBOL).point if mt5_connected else 1.0
    if h4_dir == "buy":
        sl = (min(c["ha_low"] for c in last10) - 50 * pt) if last10 else 0.0
    else:
        sl = (max(c["ha_high"] for c in last10) + 50 * pt) if last10 else 0.0

    return {
        "direction":  h4_dir,
        "confidence": round(confidence),
        "entry":      entry,
        "sl":         sl,
        "scores":     {tf: {"direction": d, "strength": s} for tf, (d, s) in scores.items()},
    }


# ── Daily Loss Tracker ────────────────────────────────────────────────────────
async def daily_loss_reset_loop():
    """Reset daily loss counter at 00:00 UTC every day."""
    while True:
        now = datetime.now(tz=timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
        wait_secs = (next_midnight - now).total_seconds()
        await asyncio.sleep(wait_secs)

        # Recalculate daily loss from closed deals
        today_start = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(today_start, datetime.now(tz=timezone.utc)) or []
        loss = sum(d.profit for d in deals if d.profit < 0)
        auto_state["daily_loss"] = abs(loss)
        auto_state["trades_today"] = 0
        log.info(f"Daily stats reset. Accumulated loss today: ${auto_state['daily_loss']:.2f}")


def update_daily_loss():
    """Sync daily_loss from MT5 closed deals for today."""
    if not mt5_connected:
        return
    today_start = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(today_start, datetime.now(tz=timezone.utc)) or []
    loss = sum(d.profit for d in deals if d.profit < 0 and d.symbol == SYMBOL)
    auto_state["daily_loss"] = abs(loss)


# ── Safety Conditions ─────────────────────────────────────────────────────────
def check_safety(signal_direction: str) -> tuple[bool, str]:
    if not mt5_connected:
        return False, "MT5 not connected"

    positions = mt5.positions_get(symbol=SYMBOL) or []

    if len(positions) >= auto_state["max_positions"]:
        return False, f"Max positions ({auto_state['max_positions']}) reached"

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
    """Background auto trading engine — runs on scan_interval."""
    while True:
        await asyncio.sleep(auto_state["scan_interval"])

        if not auto_state["enabled"]:
            continue

        if not mt5_connected:
            if auto_state["enabled"]:
                auto_state["paused_mt5_disconnect"] = True
                log.warning("Auto trading paused — MT5 disconnected")
            continue

        auto_state["last_scan"] = datetime.now(tz=timezone.utc).isoformat()

        signal = calculate_signal()
        direction  = signal["direction"]
        confidence = signal["confidence"]

        auto_state["last_signal"] = (
            f"{direction.upper()} (conf: {confidence}%)" if direction != "none"
            else "No signal"
        )

        if direction == "none" or confidence < auto_state["min_confidence"]:
            _auto_log("SKIP", f"No signal or low confidence ({confidence}%)", "skip")
            await broadcast_auto_status()
            continue

        ok, reason = check_safety(direction)
        if not ok:
            _auto_log("SKIP", reason, "skip")
            await broadcast_auto_status()
            continue

        ticket = _place_market_order(direction, auto_state["lot_size"], signal["sl"])
        if ticket:
            auto_state["trades_today"] += 1
            msg = f"{direction.upper()} {auto_state['lot_size']} @ {signal['entry']:.2f} (conf:{confidence}%)"
            _auto_log("TRADE", msg, "executed")
            await broadcast({
                "type":       "auto_trade_executed",
                "direction":  direction,
                "volume":     auto_state["lot_size"],
                "entry":      signal["entry"],
                "sl":         signal["sl"],
                "confidence": confidence,
                "ticket":     ticket,
            })
        else:
            _auto_log("ERROR", "Order send failed", "error")

        await broadcast_auto_status()


def _auto_log(action: str, reason: str, result: str):
    entry = {
        "time":   datetime.now(tz=timezone.utc).strftime("%H:%M:%S"),
        "action": action,
        "reason": reason,
        "result": result,
    }
    auto_state["log"].insert(0, entry)
    auto_state["log"] = auto_state["log"][:50]  # keep last 50
    log.info(f"[AUTO] {action}: {reason}")


async def broadcast_auto_status():
    payload = {
        "type":                  "auto_trading_status",
        "enabled":               auto_state["enabled"],
        "scan_interval":         auto_state["scan_interval"],
        "min_confidence":        auto_state["min_confidence"],
        "max_positions":         auto_state["max_positions"],
        "max_daily_loss":        auto_state["max_daily_loss"],
        "session_filter":        auto_state["session_filter"],
        "daily_loss_current":    auto_state["daily_loss"],
        "last_scan":             auto_state["last_scan"],
        "last_signal":           auto_state["last_signal"],
        "total_auto_trades_today": auto_state["trades_today"],
        "auto_log":              auto_state["log"][:20],
    }
    await broadcast(payload)


# ── WebSocket Command Handler ─────────────────────────────────────────────────
async def handle_command(cmd: dict, ws: WebSocketServerProtocol):
    global rejection_counter
    action = cmd.get("cmd", "")

    # ── get_candles ──────────────────────────────────────────────────────────
    if action == "get_candles":
        tf    = cmd.get("timeframe", "M15")
        count = cmd.get("count", 200)
        data  = get_candles(tf, count)
        if data:
            await ws.send(json.dumps(data, default=str))
        else:
            await ws.send(json.dumps({"type": "error", "message": f"Cannot get candles for {tf}"}))

    # ── order_market ─────────────────────────────────────────────────────────
    elif action == "order_market":
        direction = cmd.get("type", "buy")
        volume    = float(cmd.get("volume", 0.01))
        sl        = float(cmd.get("sl", 0.0))
        ticket    = _place_market_order(direction, volume, sl)
        if ticket:
            await ws.send(json.dumps({"type": "order_result", "status": "ok", "ticket": ticket}))
        else:
            await ws.send(json.dumps({"type": "error", "message": "Order failed — check MT5 logs"}))

    # ── order_pending_rejection ───────────────────────────────────────────────
    elif action == "order_pending_rejection":
        rejection_counter += 1
        tid = f"REJ{rejection_counter:04d}"
        timeout_min = int(cmd.get("timeout_minutes", 5))
        rejection_orders[tid] = {
            "direction":    cmd.get("direction", "sell"),
            "volume":       float(cmd.get("volume", 0.01)),
            "trigger_price":float(cmd.get("trigger_price", 0)),
            "entry_price":  float(cmd.get("entry_price", 0)),
            "sl":           float(cmd.get("sl", 0)),
            "status":       "waiting_trigger",
            "created_at":   datetime.now(tz=timezone.utc).isoformat(),
            "timeout_dt":   datetime.now(tz=timezone.utc) + timedelta(minutes=timeout_min),
        }
        await ws.send(json.dumps({"type": "order_result", "status": "ok", "ticket": tid}))
        await broadcast(get_orders())

    # ── modify_sl ─────────────────────────────────────────────────────────────
    elif action == "modify_sl":
        ticket = int(cmd.get("ticket", 0))
        sl     = float(cmd.get("sl", 0))
        ok     = _modify_sl(ticket, sl)
        await ws.send(json.dumps({"type": "order_result", "status": "ok" if ok else "error", "ticket": ticket}))

    # ── close_position ────────────────────────────────────────────────────────
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

    # ── close_all ────────────────────────────────────────────────────────────
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

    # ── cancel_order (rejection) ──────────────────────────────────────────────
    elif action == "cancel_order":
        ticket = str(cmd.get("ticket", ""))
        if ticket in rejection_orders:
            del rejection_orders[ticket]
            await ws.send(json.dumps({"type": "order_result", "status": "cancelled", "ticket": ticket}))
            await broadcast(get_orders())
        else:
            await ws.send(json.dumps({"type": "error", "message": f"Order {ticket} not found"}))

    # ── set_auto_trading ─────────────────────────────────────────────────────
    elif action == "set_auto_trading":
        for key in ["enabled", "scan_interval", "min_confidence", "lot_size",
                    "max_positions", "max_daily_loss", "session_filter",
                    "allow_buy", "allow_sell"]:
            if key in cmd:
                auto_state[key] = cmd[key]
        log.info(f"Auto trading settings updated: enabled={auto_state['enabled']}")
        await broadcast_auto_status()

    # ── get_auto_status ───────────────────────────────────────────────────────
    elif action == "get_auto_status":
        await broadcast_auto_status()

    # ── reconnect_mt5 ─────────────────────────────────────────────────────────
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

    # Send initial state on connect
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
    """Broadcast tick every 1 second."""
    while True:
        await asyncio.sleep(1)
        if mt5_connected and clients:
            tick = get_tick()
            if tick:
                await broadcast(tick)
            await broadcast(get_positions())
            await broadcast(get_orders())


async def candle_stream_loop():
    """Broadcast candles + Crystal HA every 5 seconds."""
    while True:
        await asyncio.sleep(5)
        if not mt5_connected or not clients:
            continue
        for tf in ["M1", "M5", "M15", "H1", "H4"]:
            candles = get_candles(tf, 200)
            if candles:
                await broadcast(candles)
            cha = get_crystal_ha(tf, 50)
            if cha:
                await broadcast(cha)


async def heartbeat_loop():
    """Ping clients every 10 seconds to keep connections alive."""
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

    # Initial MT5 connect
    if not connect_mt5():
        log.warning("Initial MT5 connect failed — will retry in background")

    # Start WebSocket server
    server = await websockets.serve(client_handler, "0.0.0.0", WS_PORT)
    log.info(f"WebSocket server listening on ws://0.0.0.0:{WS_PORT}")

    # Start background tasks
    await asyncio.gather(
        server.wait_closed(),
        mt5_reconnect_loop(),
        tick_stream_loop(),
        candle_stream_loop(),
        trailing_stop_loop(),
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
