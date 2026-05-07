"""
backtest_optimizer.py — Run banyak config sekaligus, output table comparison
=============================================================================
Otomatis test semua kombinasi:
- Filter combo (Zone, Sideways, Timing on/off)
- Direction (Buy only, Sell only, Both)
- Signal type (Circle only, Arrow only, Both)
- Sideways threshold variations
- Session filters

Output: comparison table + ranked best configs
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from itertools import product
import sys
import time

# ╔══════════════════════════════════════════════════════════════════╗
# ║                     GLOBAL CONFIG                                ║
# ╚══════════════════════════════════════════════════════════════════╝

SYMBOL          = "BTCUSDm"
DAYS_BACK       = 30
INITIAL_BALANCE = 500.0
LOT_SIZE        = 0.01
CONTRACT_SIZE   = 100.0    # XM CFD style
SPREAD_USD      = 25.0
SLIPPAGE_USD    = 3.0

# EA AutoSLTP v8.4
HARD_SL_USD          = 2.00
HARD_TP_USD          = 5.00
TRAILING_TRIGGER_USD = 2.50
TRAILING_STOP_USD    = 1.00

WARMUP = 200

# ╔══════════════════════════════════════════════════════════════════╗
# ║              EXPERIMENTS TO RUN (TWEAK DI SINI!)                 ║
# ╚══════════════════════════════════════════════════════════════════╝
# Format: (label, config_dict)
EXPERIMENTS = [
    # ─── Baseline ───
    ("NO filters",              {"zone":False, "sideways":False, "timing":False, "buy":True, "sell":True, "circle":True, "arrow":True}),
    ("BASELINE (all on)",       {"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True}),

    # ─── Single Filter Test ───
    ("Only ZONE filter",        {"zone":True,  "sideways":False, "timing":False, "buy":True, "sell":True, "circle":True, "arrow":True}),
    ("Only SIDEWAYS filter",    {"zone":False, "sideways":True,  "timing":False, "buy":True, "sell":True, "circle":True, "arrow":True}),
    ("Only TIMING filter",      {"zone":False, "sideways":False, "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True}),

    # ─── Filter Pairs ───
    ("ZONE + TIMING",           {"zone":True,  "sideways":False, "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True}),
    ("ZONE + SIDEWAYS",         {"zone":True,  "sideways":True,  "timing":False, "buy":True, "sell":True, "circle":True, "arrow":True}),
    ("SIDEWAYS + TIMING",       {"zone":False, "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True}),

    # ─── Direction Tests ───
    ("BUY only (all filters)",  {"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":False,"circle":True, "arrow":True}),
    ("SELL only (all filters)", {"zone":True,  "sideways":True,  "timing":True,  "buy":False,"sell":True, "circle":True, "arrow":True}),

    # ─── Signal Type Tests ───
    ("ARROW only (all filters)",{"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":False,"arrow":True}),
    ("CIRCLE only (all filters)",{"zone":True, "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":False}),

    # ─── Arrow combos ───
    ("ARROW + BUY only",        {"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":False,"circle":False,"arrow":True}),
    ("ARROW + No filters",      {"zone":False, "sideways":False, "timing":False, "buy":True, "sell":True, "circle":False,"arrow":True}),
    ("ARROW + Zone only",       {"zone":True,  "sideways":False, "timing":False, "buy":True, "sell":True, "circle":False,"arrow":True}),
    ("ARROW + Zone+Timing",     {"zone":True,  "sideways":False, "timing":True,  "buy":True, "sell":True, "circle":False,"arrow":True}),

    # ─── Sideways threshold sweep ───
    ("Sideways threshold 0.05", {"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True, "sideways_threshold":0.05}),
    ("Sideways threshold 0.08", {"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True, "sideways_threshold":0.08}),
    ("Sideways threshold 0.12", {"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True, "sideways_threshold":0.12}),

    # ─── Session Tests ───
    ("London + NY session",     {"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True, "sessions":["london","new_york"]}),
    ("Asia session",            {"zone":True,  "sideways":True,  "timing":True,  "buy":True, "sell":True, "circle":True, "arrow":True, "sessions":["tokyo","sydney"]}),
]


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  CRYSTAL HA CALCULATOR                           ║
# ╚══════════════════════════════════════════════════════════════════╝

def calculate_crystal_ha(df):
    res = []
    prev_ha_o = prev_ha_c = ema20 = ema50 = 0.0
    pending = None
    CONFIRM = 3
    for i, row in df.iterrows():
        o, h, l, c = float(row['open']), float(row['high']), float(row['low']), float(row['close'])
        if i == 0:
            ema20 = ema50 = c
            ha_o = (o + c) / 2
            ha_c = (o + h + l + c) / 4
            ha_h, ha_l = h, l
        else:
            ema20 = (c - ema20) * (2/21) + ema20
            ema50 = (c - ema50) * (2/51) + ema50
            ha_c = (o + h + l + c) / 4
            ha_o = (prev_ha_o + prev_ha_c) / 2
            ha_h = max(h, ha_o, ha_c)
            ha_l = min(l, ha_o, ha_c)
        prev_ha_o, prev_ha_c = ha_o, ha_c
        is_bull = ha_c > ha_o
        if i == 0:
            color = "bullish_weak" if is_bull else "bearish_weak"
        else:
            prev_bull = res[-1]["ha_close"] > res[-1]["ha_open"]
            if is_bull:
                color = "bullish_strong" if not prev_bull else "bullish_weak"
            else:
                color = "bearish_strong" if prev_bull else "bearish_weak"
        cb = cs = ab = as_ = False
        if i > 0:
            prev = res[-1]
            prev_bull = prev["ha_close"] > prev["ha_open"]
            if not prev_bull and is_bull:
                cb = True
                pending = {"type":"buy","ref_high":ha_h,"ref_low":ha_l,"waited":0}
            elif prev_bull and not is_bull:
                cs = True
                pending = {"type":"sell","ref_high":ha_h,"ref_low":ha_l,"waited":0}
            if pending and not cb and not cs:
                pending["waited"] += 1
                if pending["type"] == "buy":
                    if ha_c > pending["ref_high"]:
                        ab = True; pending = None
                    elif not is_bull or pending["waited"] >= CONFIRM:
                        pending = None
                else:
                    if ha_c < pending["ref_low"]:
                        as_ = True; pending = None
                    elif is_bull or pending["waited"] >= CONFIRM:
                        pending = None
        res.append({
            "time": int(row['time']), "open": o, "high": h, "low": l, "close": c,
            "ha_open": ha_o, "ha_high": ha_h, "ha_low": ha_l, "ha_close": ha_c,
            "ema20": ema20, "ema50": ema50, "color": color,
            "circle_buy": cb, "circle_sell": cs, "arrow_buy": ab, "arrow_sell": as_,
        })
    return pd.DataFrame(res)


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  FILTERS                                         ║
# ╚══════════════════════════════════════════════════════════════════╝

def check_zone(direction, price, history_df, threshold=200):
    if len(history_df) < 50: return True
    df = history_df.tail(200).reset_index(drop=True)
    sw = 5
    highs, lows = [], []
    for i in range(sw, len(df)-sw):
        l_w = df.iloc[i-sw:i]; r_w = df.iloc[i+1:i+sw+1]; cur = df.iloc[i]
        if cur['high'] > l_w['high'].max() and cur['high'] > r_w['high'].max():
            highs.append(cur['high'])
        if cur['low'] < l_w['low'].min() and cur['low'] < r_w['low'].min():
            lows.append(cur['low'])
    def cluster(pts, tol=0.15, min_t=2):
        if not pts: return []
        sp = sorted(pts)
        cl = [[sp[0]]]
        for p in sp[1:]:
            if abs(p - cl[-1][-1]) / cl[-1][-1] * 100 <= tol:
                cl[-1].append(p)
            else: cl.append([p])
        return [sum(c)/len(c) for c in cl if len(c) >= min_t]
    R = cluster(highs); S = cluster(lows)
    if direction == "buy":
        nr = min([r for r in R if r > price], default=None)
        if nr is None: return True
        return (nr - price) >= threshold
    else:
        ns = max([s for s in S if s < price], default=None)
        if ns is None: return True
        return (price - ns) >= threshold


def check_sideways(history_df, threshold=0.08):
    """FIX: threshold turun 0.15→0.08, KEDUA method harus setuju"""
    if len(history_df) < 20: return True
    df = history_df.tail(20)
    rng = df['high'].max() - df['low'].min()
    body = (df['close'] - df['open']).abs().mean()
    ratio = body/rng if rng > 0 else 0
    candle_chop = ratio < threshold

    # Crystal chop: hitung arrow reversals
    buy_c = sell_c = 0
    for i in range(1, len(df)):
        prev_b = df['close'].iloc[i-1] > df['open'].iloc[i-1]
        cur_b  = df['close'].iloc[i]   > df['open'].iloc[i]
        if not prev_b and cur_b: buy_c += 1
        elif prev_b and not cur_b: sell_c += 1
    total = buy_c + sell_c
    crystal_chop = False
    if total >= 4:
        ratio_cs = min(buy_c, sell_c) / max(buy_c, sell_c) if max(buy_c, sell_c) > 0 else 0
        crystal_chop = ratio_cs > 0.5

    # FIX: harus KEDUA setuju baru block
    return not (crystal_chop and candle_chop)


def check_timing(direction, m15_time, m5_df, m1_df, max_wait_sec=900):
    """
    Simulasi timing filter dengan window tunggu — sama seperti live trading.
    Cek setiap 5 menit selama max 15 menit apakah M5+M1 align.
    Kalau dalam window itu ada momen align → PASS.
    Ini yang benar secara logika, bukan snapshot satu titik.
    """
    def ha_color(df_slice):
        if len(df_slice) < 10:
            return 'unknown'
        ha_o = (df_slice['open'].iloc[0] + df_slice['close'].iloc[0]) / 2
        ha_c_p = (df_slice['open'].iloc[0]+df_slice['high'].iloc[0]+
                  df_slice['low'].iloc[0]+df_slice['close'].iloc[0]) / 4
        ha_o_p = ha_o
        for i in range(1, len(df_slice)):
            ha_c = (df_slice['open'].iloc[i]+df_slice['high'].iloc[i]+
                    df_slice['low'].iloc[i]+df_slice['close'].iloc[i]) / 4
            ha_o = (ha_o_p + ha_c_p) / 2
            ha_o_p, ha_c_p = ha_o, ha_c
        n = len(df_slice)
        r_p = df_slice.iloc[n-2]; r_c = df_slice.iloc[n-1]
        p_ha_c = (r_p['open']+r_p['high']+r_p['low']+r_p['close']) / 4
        c_ha_c = (r_c['open']+r_c['high']+r_c['low']+r_c['close']) / 4
        c_ha_o = (ha_o_p + p_ha_c) / 2
        prev_b = p_ha_c > ha_o_p
        cur_b  = c_ha_c > c_ha_o
        if cur_b:  return 'green' if not prev_b else 'blue'
        else:      return 'orange' if prev_b else 'red'

    bull = {'blue', 'green'}
    bear = {'red', 'orange'}
    m15_end = m15_time + 15 * 60  # batas candle M15 ini

    # Cek setiap 5 menit dalam window candle M15 (maks 15 menit)
    check_times = range(m15_time, min(m15_time + max_wait_sec, m15_end), 300)

    for t in check_times:
        m5r = m5_df[m5_df['time'] <= t].tail(50)
        m1r = m1_df[m1_df['time'] <= t].tail(50)
        if len(m5r) < 10 or len(m1r) < 10:
            continue
        m5c = ha_color(m5r)
        m1c = ha_color(m1r)
        if direction == 'buy'  and m5c in bull and m1c in bull: return True
        if direction == 'sell' and m5c in bear and m1c in bear: return True

    return False


def get_active_sessions(utc_hour):
    s = []
    if utc_hour >= 22 or utc_hour < 7: s.append("sydney")
    if 0 <= utc_hour < 9:              s.append("tokyo")
    if 7 <= utc_hour < 16:             s.append("london")
    if 12 <= utc_hour < 21:            s.append("new_york")
    return s


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  TRADE OBJECT                                    ║
# ╚══════════════════════════════════════════════════════════════════╝

class Trade:
    def __init__(self, direction, entry, entry_time, signal_type):
        self.direction = direction
        self.entry = entry
        self.entry_time = entry_time
        self.signal_type = signal_type
        self.exit = None
        self.exit_time = None
        self.exit_reason = None
        self.pnl = 0.0
        self.trailing_active = False
        self.trailing_sl = None
    
    def check_exit_on_m1(self, m1_candle):
        h = m1_candle['high']; l = m1_candle['low']
        if self.direction == "buy":
            if h >= self.entry + HARD_TP_USD: return self.entry + HARD_TP_USD, "hard_tp"
            if l <= self.entry - HARD_SL_USD: return self.entry - HARD_SL_USD, "hard_sl"
            profit = h - self.entry
            if not self.trailing_active and profit >= TRAILING_TRIGGER_USD:
                self.trailing_active = True
                self.trailing_sl = h - TRAILING_STOP_USD
            if self.trailing_active:
                new_sl = h - TRAILING_STOP_USD
                if new_sl > self.trailing_sl: self.trailing_sl = new_sl
                if l <= self.trailing_sl: return self.trailing_sl, "trailing_sl"
        else:
            if l <= self.entry - HARD_TP_USD: return self.entry - HARD_TP_USD, "hard_tp"
            if h >= self.entry + HARD_SL_USD: return self.entry + HARD_SL_USD, "hard_sl"
            profit = self.entry - l
            if not self.trailing_active and profit >= TRAILING_TRIGGER_USD:
                self.trailing_active = True
                self.trailing_sl = l + TRAILING_STOP_USD
            if self.trailing_active:
                new_sl = l + TRAILING_STOP_USD
                if new_sl < self.trailing_sl: self.trailing_sl = new_sl
                if h >= self.trailing_sl: return self.trailing_sl, "trailing_sl"
        return None, None
    
    def close(self, exit_price, exit_time, reason):
        self.exit = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        diff = (exit_price - self.entry) if self.direction == "buy" else (self.entry - exit_price)
        self.pnl = diff * LOT_SIZE * CONTRACT_SIZE


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  SINGLE BACKTEST RUN                             ║
# ╚══════════════════════════════════════════════════════════════════╝

def run_single_backtest(m15, m5_raw, m1_raw, config):
    """Run 1 backtest dengan config tertentu, return result dict."""
    enable_zone     = config.get("zone", True)
    enable_sideways = config.get("sideways", True)
    enable_timing   = config.get("timing", True)
    allow_buy       = config.get("buy", True)
    allow_sell      = config.get("sell", True)
    allow_circle    = config.get("circle", True)
    allow_arrow     = config.get("arrow", True)
    sw_threshold    = config.get("sideways_threshold", 0.15)
    sessions        = config.get("sessions", [])
    
    trades = []
    open_trade = None
    balance = INITIAL_BALANCE
    equity_track = [balance]
    last_entry_candle = 0
    
    for idx in range(WARMUP, len(m15)):
        candle = m15.iloc[idx]
        ct = candle['time']
        
        # Update open trade
        if open_trade is not None:
            m15_end = ct + 15*60
            m1_in_range = m1_raw[(m1_raw['time'] >= ct) & (m1_raw['time'] < m15_end)]
            for _, m1c in m1_in_range.iterrows():
                exit_price, reason = open_trade.check_exit_on_m1(m1c)
                if exit_price is not None:
                    open_trade.close(exit_price, m1c['time'], reason)
                    balance += open_trade.pnl
                    trades.append(open_trade)
                    open_trade = None
                    break
        
        equity_track.append(balance)
        
        if open_trade is not None: continue
        if idx < 1: continue
        
        # Detect signal
        closed_c = m15.iloc[idx-1]
        live_c = candle
        ab = bool(live_c['arrow_buy']) and allow_arrow
        as_ = bool(live_c['arrow_sell']) and allow_arrow
        cb = bool(closed_c['circle_buy']) and allow_circle
        cs = bool(closed_c['circle_sell']) and allow_circle
        
        entry_dir = signal_type = None
        if ab or as_:
            entry_dir = "buy" if ab else "sell"; signal_type = "arrow"
        elif cb or cs:
            entry_dir = "buy" if cb else "sell"; signal_type = "circle"
        
        if not entry_dir: continue
        if last_entry_candle == ct: continue
        if entry_dir == "buy" and not allow_buy: continue
        if entry_dir == "sell" and not allow_sell: continue
        
        # Session filter
        if sessions:
            utc_hour = datetime.fromtimestamp(ct).hour
            if not any(s in sessions for s in get_active_sessions(utc_hour)):
                last_entry_candle = ct; continue
        
        # Smart filters
        hist = m15.iloc[max(0, idx-200):idx]
        if enable_zone and not check_zone(entry_dir, candle['close'], hist):
            last_entry_candle = ct; continue
        if enable_sideways and not check_sideways(hist, sw_threshold):
            last_entry_candle = ct; continue
        if enable_timing and not check_timing(entry_dir, ct, m5_raw, m1_raw):
            last_entry_candle = ct; continue
        
        # Entry
        raw_price = candle['close']
        if entry_dir == "buy":
            entry_price = raw_price + SPREAD_USD/2 + SLIPPAGE_USD
        else:
            entry_price = raw_price - SPREAD_USD/2 - SLIPPAGE_USD
        open_trade = Trade(entry_dir, entry_price, ct, signal_type)
        last_entry_candle = ct
    
    # Close pending
    if open_trade is not None:
        last = m15.iloc[-1]
        open_trade.close(last['close'], last['time'], "end_of_data")
        balance += open_trade.pnl
        trades.append(open_trade)
    
    # Stats
    if not trades:
        return {
            "trades": 0, "wins": 0, "losses": 0, "wr": 0.0,
            "pnl": 0.0, "ret_pct": 0.0, "max_dd": 0.0, "max_dd_pct": 0.0,
            "expectancy": 0.0, "rr": 0.0,
            "buy_trades": 0, "sell_trades": 0,
            "circle_trades": 0, "arrow_trades": 0,
            "buy_pnl": 0.0, "sell_pnl": 0.0,
            "circle_pnl": 0.0, "arrow_pnl": 0.0,
        }
    
    tdf = pd.DataFrame([{
        'direction': t.direction, 'signal': t.signal_type, 'pnl': t.pnl,
    } for t in trades])
    
    total = len(tdf)
    wins = tdf[tdf['pnl'] > 0]
    losses = tdf[tdf['pnl'] <= 0]
    pnl = tdf['pnl'].sum()
    
    # Drawdown
    eq = pd.Series(equity_track)
    peak = eq.cummax()
    dd = (eq - peak).min()
    max_dd_pct = (dd / peak.max() * 100) if peak.max() > 0 else 0
    
    # Expectancy
    expectancy = pnl / total if total > 0 else 0
    
    # R:R
    rr = 0.0
    if len(wins) > 0 and len(losses) > 0:
        rr = wins['pnl'].mean() / abs(losses['pnl'].mean())
    
    # By direction & signal
    buy = tdf[tdf['direction'] == 'buy']
    sell = tdf[tdf['direction'] == 'sell']
    circle = tdf[tdf['signal'] == 'circle']
    arrow = tdf[tdf['signal'] == 'arrow']
    
    return {
        "trades": total, "wins": len(wins), "losses": len(losses),
        "wr": len(wins)/total*100 if total > 0 else 0,
        "pnl": round(pnl, 2),
        "ret_pct": round((balance - INITIAL_BALANCE)/INITIAL_BALANCE*100, 2),
        "max_dd": round(dd, 2),
        "max_dd_pct": round(max_dd_pct, 2),
        "expectancy": round(expectancy, 3),
        "rr": round(rr, 2),
        "buy_trades": len(buy), "sell_trades": len(sell),
        "circle_trades": len(circle), "arrow_trades": len(arrow),
        "buy_pnl": round(buy['pnl'].sum(), 2),
        "sell_pnl": round(sell['pnl'].sum(), 2),
        "circle_pnl": round(circle['pnl'].sum(), 2),
        "arrow_pnl": round(arrow['pnl'].sum(), 2),
    }


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  MAIN ORCHESTRATOR                               ║
# ╚══════════════════════════════════════════════════════════════════╝

def main():
    print("\n" + "="*90)
    print(f"  🧪 BACKTEST OPTIMIZER — {SYMBOL} | {DAYS_BACK} days | {len(EXPERIMENTS)} configs")
    print("="*90)
    print(f"  Spec: lot {LOT_SIZE} × contract {CONTRACT_SIZE} | SL ${HARD_SL_USD} TP ${HARD_TP_USD}")
    print(f"  Spread ${SPREAD_USD} | Slippage ${SLIPPAGE_USD} | Initial ${INITIAL_BALANCE}")
    print("="*90 + "\n")
    
    if not mt5.initialize():
        print(f"[ERROR] MT5 init failed: {mt5.last_error()}")
        sys.exit(1)
    
    # Download once
    print("📥 Downloading data (once)...")
    tf_map = {"M1":mt5.TIMEFRAME_M1, "M5":mt5.TIMEFRAME_M5, "M15":mt5.TIMEFRAME_M15}
    end = datetime.now()
    start = end - timedelta(days=DAYS_BACK+5)
    
    def dl(tf_str):
        rates = mt5.copy_rates_range(SYMBOL, tf_map[tf_str], start, end)
        if rates is None: return None
        df = pd.DataFrame(rates)
        print(f"  ✅ {tf_str}: {len(df)} candles")
        return df
    
    m15_raw = dl("M15"); m5_raw = dl("M5"); m1_raw = dl("M1")
    if any(x is None for x in [m15_raw, m5_raw, m1_raw]):
        mt5.shutdown(); sys.exit(1)
    
    print("\n🔮 Calculating Crystal HA M15 (once)...")
    m15 = calculate_crystal_ha(m15_raw)
    total_signals = ((m15['circle_buy']|m15['circle_sell'])|(m15['arrow_buy']|m15['arrow_sell'])).sum()
    print(f"  Total signals: {total_signals}\n")
    
    # Run all experiments
    print("="*90)
    print(f"  ⚡ Running {len(EXPERIMENTS)} experiments...")
    print("="*90 + "\n")
    
    results = []
    for i, (label, cfg) in enumerate(EXPERIMENTS, 1):
        t0 = time.time()
        print(f"  [{i:2d}/{len(EXPERIMENTS)}] {label:<40s}", end=" ", flush=True)
        res = run_single_backtest(m15, m5_raw, m1_raw, cfg)
        elapsed = time.time() - t0
        results.append({"label": label, **res, "config": cfg})
        print(f"→ {res['trades']:>3d} trades | WR {res['wr']:>5.1f}% | "
              f"P/L ${res['pnl']:>+8.2f} | DD ${res['max_dd']:>+7.2f} | ({elapsed:.1f}s)")
    
    # ─── COMPARISON TABLE ───
    print("\n" + "="*90)
    print("  📊 COMPARISON TABLE")
    print("="*90)
    
    df = pd.DataFrame(results)
    df_display = df[['label', 'trades', 'wr', 'pnl', 'ret_pct', 'max_dd', 'max_dd_pct', 'expectancy', 'rr']].copy()
    df_display.columns = ['Config', 'Trd', 'WR%', 'P/L $', 'Ret%', 'MaxDD', 'DD%', 'E/trd', 'R:R']
    
    # Print table
    print(f"\n{'Config':<40} {'Trd':>4} {'WR%':>6} {'P/L $':>9} {'Ret%':>7} {'MaxDD':>8} {'DD%':>6} {'E/trd':>7} {'R:R':>5}")
    print("─" * 100)
    for _, r in df_display.iterrows():
        print(f"{r['Config']:<40} {r['Trd']:>4} {r['WR%']:>6.1f} {r['P/L $']:>+9.2f} "
              f"{r['Ret%']:>+7.2f} {r['MaxDD']:>+8.2f} {r['DD%']:>+6.2f} {r['E/trd']:>+7.3f} {r['R:R']:>5.2f}")
    
    # ─── RANKINGS ───
    print("\n" + "="*90)
    print("  🏆 TOP 5 RANKINGS")
    print("="*90)
    
    print("\n  💰 BY TOTAL P/L:")
    top_pnl = df.nlargest(5, 'pnl')[['label', 'pnl', 'wr', 'trades', 'max_dd']]
    for i, (_, r) in enumerate(top_pnl.iterrows(), 1):
        print(f"    {i}. {r['label']:<40s} ${r['pnl']:>+8.2f} | WR {r['wr']:>5.1f}% | {r['trades']:>3d} trades | DD ${r['max_dd']:>+.2f}")
    
    print("\n  📈 BY EXPECTANCY (P/L per trade):")
    top_exp = df[df['trades'] >= 5].nlargest(5, 'expectancy')[['label', 'expectancy', 'trades', 'pnl', 'wr']]
    for i, (_, r) in enumerate(top_exp.iterrows(), 1):
        print(f"    {i}. {r['label']:<40s} ${r['expectancy']:>+6.3f}/trd | {r['trades']:>3d} trd | "
              f"${r['pnl']:>+7.2f} total | WR {r['wr']:>5.1f}%")
    
    print("\n  🛡️ BY RISK-ADJUSTED RETURN (P/L / |MaxDD|):")
    df['risk_adj'] = df['pnl'] / df['max_dd'].abs().replace(0, 1)
    top_risk = df[df['trades'] >= 5].nlargest(5, 'risk_adj')[['label', 'risk_adj', 'pnl', 'max_dd']]
    for i, (_, r) in enumerate(top_risk.iterrows(), 1):
        print(f"    {i}. {r['label']:<40s} ratio {r['risk_adj']:>+6.2f} | "
              f"P/L ${r['pnl']:>+7.2f} | DD ${r['max_dd']:>+.2f}")
    
    print("\n  🎯 BY WIN RATE (min 10 trades):")
    top_wr = df[df['trades'] >= 10].nlargest(5, 'wr')[['label', 'wr', 'trades', 'pnl']]
    for i, (_, r) in enumerate(top_wr.iterrows(), 1):
        print(f"    {i}. {r['label']:<40s} WR {r['wr']:>5.1f}% | {r['trades']:>3d} trades | P/L ${r['pnl']:>+.2f}")
    
    # Save full results
    df.to_csv("optimizer_results.csv", index=False)
    print(f"\n  💾 Saved full results to: optimizer_results.csv")
    
    # ─── INSIGHTS ───
    print("\n" + "="*90)
    print("  💡 KEY INSIGHTS")
    print("="*90)
    
    baseline = next((r for r in results if r['label'] == 'BASELINE (all on)'), None)
    no_filter = next((r for r in results if r['label'] == 'NO filters'), None)
    
    if baseline and no_filter:
        diff = baseline['pnl'] - no_filter['pnl']
        if diff > 0:
            print(f"  ✅ Filters HELP: Baseline ${baseline['pnl']:+.2f} vs No filter ${no_filter['pnl']:+.2f} (diff +${diff:.2f})")
        else:
            print(f"  ⚠️  Filters HURT: Baseline ${baseline['pnl']:+.2f} vs No filter ${no_filter['pnl']:+.2f} (diff ${diff:+.2f})")
    
    # Direction analysis
    buy_only = next((r for r in results if 'BUY only' in r['label']), None)
    sell_only = next((r for r in results if 'SELL only' in r['label']), None)
    if buy_only and sell_only:
        print(f"  📊 Direction: BUY-only ${buy_only['pnl']:+.2f} vs SELL-only ${sell_only['pnl']:+.2f}")
    
    # Signal analysis
    arrow_only = next((r for r in results if 'ARROW only' in r['label']), None)
    circle_only = next((r for r in results if 'CIRCLE only' in r['label']), None)
    if arrow_only and circle_only:
        print(f"  🎯 Signal: ARROW-only ${arrow_only['pnl']:+.2f} vs CIRCLE-only ${circle_only['pnl']:+.2f}")
    
    # Best overall
    best = max(results, key=lambda x: x['pnl'])
    print(f"\n  🏆 OVERALL BEST: {best['label']}")
    print(f"     P/L ${best['pnl']:+.2f} | WR {best['wr']:.1f}% | {best['trades']} trades | "
          f"DD ${best['max_dd']:.2f} | Expectancy ${best['expectancy']:.3f}/trade")
    print(f"     Config: {best['config']}")
    
    print("\n" + "="*90 + "\n")
    mt5.shutdown()


if __name__ == "__main__":
    main()