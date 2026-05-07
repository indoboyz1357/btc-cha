"""
backtest_optimizer_v2.py
========================
Sistematis test filter:
  Phase 1: Baseline (no filter)
  Phase 2: ISOLATE — tiap filter sendirian
  Phase 3: TWEAK — filter yang bagus → coba berbagai parameter
  Phase 4: STACK — combine yang terbaik
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys, time

# ╔══════════════════════════════════════════════════════════════════╗
# ║                    GLOBAL CONFIG                                 ║
# ╚══════════════════════════════════════════════════════════════════╝
SYMBOL          = "BTCUSDm"
DAYS_BACK       = 30
INITIAL_BALANCE = 500.0
LOT_SIZE        = 0.01
CONTRACT_SIZE   = 100.0
SPREAD_USD      = 25.0
SLIPPAGE_USD    = 3.0
HARD_SL_USD          = 2.00
HARD_TP_USD          = 5.00
TRAILING_TRIGGER_USD = 2.50
TRAILING_STOP_USD    = 1.00
WARMUP = 200


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
            ha_o = (o + c) / 2; ha_c = (o + h + l + c) / 4
            ha_h, ha_l = h, l
        else:
            ema20 = (c - ema20) * (2/21) + ema20
            ema50 = (c - ema50) * (2/51) + ema50
            ha_c = (o + h + l + c) / 4
            ha_o = (prev_ha_o + prev_ha_c) / 2
            ha_h = max(h, ha_o, ha_c); ha_l = min(l, ha_o, ha_c)
        prev_ha_o, prev_ha_c = ha_o, ha_c
        is_bull = ha_c > ha_o
        if i == 0:
            color = "bullish_weak" if is_bull else "bearish_weak"
        else:
            prev_bull = res[-1]["ha_close"] > res[-1]["ha_open"]
            if is_bull: color = "bullish_strong" if not prev_bull else "bullish_weak"
            else: color = "bearish_strong" if prev_bull else "bearish_weak"
        cb = cs = ab = as_ = False
        if i > 0:
            prev = res[-1]; prev_bull = prev["ha_close"] > prev["ha_open"]
            if not prev_bull and is_bull:
                cb = True; pending = {"type":"buy","ref_high":ha_h,"ref_low":ha_l,"waited":0}
            elif prev_bull and not is_bull:
                cs = True; pending = {"type":"sell","ref_high":ha_h,"ref_low":ha_l,"waited":0}
            if pending and not cb and not cs:
                pending["waited"] += 1
                if pending["type"] == "buy":
                    if ha_c > pending["ref_high"]: ab = True; pending = None
                    elif not is_bull or pending["waited"] >= CONFIRM: pending = None
                else:
                    if ha_c < pending["ref_low"]: as_ = True; pending = None
                    elif is_bull or pending["waited"] >= CONFIRM: pending = None
        res.append({
            "time": int(row['time']), "open": o, "high": h, "low": l, "close": c,
            "ha_open": ha_o, "ha_high": ha_h, "ha_low": ha_l, "ha_close": ha_c,
            "ema20": ema20, "ema50": ema50, "color": color,
            "circle_buy": cb, "circle_sell": cs, "arrow_buy": ab, "arrow_sell": as_,
        })
    return pd.DataFrame(res)


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  FILTERS (PARAMETERIZED)                         ║
# ╚══════════════════════════════════════════════════════════════════╝
def check_zone(direction, price, history_df, threshold_usd=None, threshold_pct=None,
               swing_window=5, cluster_tol=0.15, min_touches=2):
    try:
        if len(history_df) < 50:
            return True

        df = history_df.tail(200).reset_index(drop=True)
        sw = swing_window
        highs, lows = [], []

        for i in range(sw, len(df) - sw):
            l_w = df.iloc[i-sw:i]
            r_w = df.iloc[i+1:i+sw+1]
            cur = df.iloc[i]

            if cur['high'] > l_w['high'].max() and cur['high'] > r_w['high'].max():
                highs.append(float(cur['high']))

            if cur['low'] < l_w['low'].min() and cur['low'] < r_w['low'].min():
                lows.append(float(cur['low']))

        def cluster(pts, tol, min_t):
            if not pts:
                return []
            sp = sorted(pts)
            cl = [[sp[0]]]
            for p in sp[1:]:
                if abs(p - cl[-1][-1]) / cl[-1][-1] * 100 <= tol:
                    cl[-1].append(p)
                else:
                    cl.append([p])
            return [sum(c) / len(c) for c in cl if len(c) >= min_t]

        R = cluster(highs, cluster_tol, min_touches)
        S = cluster(lows, cluster_tol, min_touches)

        price = float(price)

        if threshold_pct is not None:
            effective_threshold = price * float(threshold_pct)
        elif threshold_usd is not None:
            effective_threshold = float(threshold_usd)
        else:
            effective_threshold = price * 0.003

        if direction == "buy":
            above = [r for r in R if r > price]
            if not above:
                return True
            nr = min(above)
            return (nr - price) >= effective_threshold

        elif direction == "sell":
            below = [s for s in S if s < price]
            if not below:
                return True
            ns = max(below)
            return (price - ns) >= effective_threshold

        return True

    except Exception as e:
        print(f"[ZONE ERROR] {e}")
        return True


def check_sideways(history_df, body_threshold=0.15, lookback=15):
    if len(history_df) < lookback: return True
    df = history_df.tail(lookback)
    rng = df['high'].max() - df['low'].min()
    body = (df['close'] - df['open']).abs().mean()
    ratio = body/rng if rng > 0 else 0
    return ratio >= body_threshold


def check_timing(direction, m15_time, m5_df, m1_df, require_m5=True, require_m1=True):
    m5r = m5_df[m5_df['time'] <= m15_time].tail(3)
    m1r = m1_df[m1_df['time'] <= m15_time].tail(3)
    if len(m5r) < 2 or len(m1r) < 2: return True
    def color(df):
        prev = df.iloc[-2]; cur = df.iloc[-1]
        prev_ha_c = (prev['open']+prev['high']+prev['low']+prev['close'])/4
        prev_ha_o = (prev['open']+prev['close'])/2
        cur_ha_c = (cur['open']+cur['high']+cur['low']+cur['close'])/4
        cur_ha_o = (prev_ha_o + prev_ha_c) / 2
        prev_b = prev_ha_c > prev_ha_o
        cur_b = cur_ha_c > cur_ha_o
        if cur_b: return 'green' if not prev_b else 'blue'
        else: return 'orange' if prev_b else 'red'
    m5c = color(m5r); m1c = color(m1r)
    bull = ['blue','green']; bear = ['red','orange']
    if direction == "buy":
        m5_ok = m5c in bull if require_m5 else True
        m1_ok = m1c in bull if require_m1 else True
    else:
        m5_ok = m5c in bear if require_m5 else True
        m1_ok = m1c in bear if require_m1 else True
    return m5_ok and m1_ok


def get_active_sessions(utc_hour):
    s = []
    if utc_hour >= 22 or utc_hour < 7: s.append("sydney")
    if 0 <= utc_hour < 9:              s.append("tokyo")
    if 7 <= utc_hour < 16:             s.append("london")
    if 12 <= utc_hour < 21:            s.append("new_york")
    return s


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  TRADE                                           ║
# ╚══════════════════════════════════════════════════════════════════╝
class Trade:
    def __init__(self, direction, entry, entry_time, signal_type):
        self.direction = direction; self.entry = entry; self.entry_time = entry_time
        self.signal_type = signal_type; self.exit = None; self.exit_time = None
        self.exit_reason = None; self.pnl = 0.0
        self.trailing_active = False; self.trailing_sl = None
    
    def check_exit_on_m1(self, m1_candle):
        h = m1_candle['high']; l = m1_candle['low']
        if self.direction == "buy":
            if h >= self.entry + HARD_TP_USD: return self.entry + HARD_TP_USD, "hard_tp"
            if l <= self.entry - HARD_SL_USD: return self.entry - HARD_SL_USD, "hard_sl"
            profit = h - self.entry
            if not self.trailing_active and profit >= TRAILING_TRIGGER_USD:
                self.trailing_active = True; self.trailing_sl = h - TRAILING_STOP_USD
            if self.trailing_active:
                new_sl = h - TRAILING_STOP_USD
                if new_sl > self.trailing_sl: self.trailing_sl = new_sl
                if l <= self.trailing_sl: return self.trailing_sl, "trailing_sl"
        else:
            if l <= self.entry - HARD_TP_USD: return self.entry - HARD_TP_USD, "hard_tp"
            if h >= self.entry + HARD_SL_USD: return self.entry + HARD_SL_USD, "hard_sl"
            profit = self.entry - l
            if not self.trailing_active and profit >= TRAILING_TRIGGER_USD:
                self.trailing_active = True; self.trailing_sl = l + TRAILING_STOP_USD
            if self.trailing_active:
                new_sl = l + TRAILING_STOP_USD
                if new_sl < self.trailing_sl: self.trailing_sl = new_sl
                if h >= self.trailing_sl: return self.trailing_sl, "trailing_sl"
        return None, None
    
    def close(self, exit_price, exit_time, reason):
        self.exit = exit_price; self.exit_time = exit_time; self.exit_reason = reason
        diff = (exit_price - self.entry) if self.direction == "buy" else (self.entry - exit_price)
        self.pnl = diff * LOT_SIZE * CONTRACT_SIZE


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  SINGLE BACKTEST                                 ║
# ╚══════════════════════════════════════════════════════════════════╝
def run_backtest(m15, m5_raw, m1_raw, cfg):
    """
    cfg keys:
      zone (bool), sideways (bool), timing (bool)
      buy (bool), sell (bool), circle (bool), arrow (bool)
      zone_threshold (USD), zone_swing (int), zone_min_touches (int)
      sideways_threshold (float), sideways_lookback (int)
      timing_m5 (bool), timing_m1 (bool)
      sessions (list)
    """
    enable_zone     = cfg.get("zone", False)
    enable_sideways = cfg.get("sideways", False)
    enable_timing   = cfg.get("timing", False)
    allow_buy       = cfg.get("buy", True)
    allow_sell      = cfg.get("sell", True)
    allow_circle    = cfg.get("circle", True)
    allow_arrow     = cfg.get("arrow", True)
    
    z_thr  = cfg.get("zone_threshold", None)
    z_pct  = cfg.get("zone_threshold_pct", None)
    z_sw   = cfg.get("zone_swing", 5)
    z_mt   = cfg.get("zone_min_touches", 2)
    sw_thr = cfg.get("sideways_threshold", 0.15)
    sw_lb  = cfg.get("sideways_lookback", 15)
    t_m5   = cfg.get("timing_m5", True)
    t_m1   = cfg.get("timing_m1", True)
    sessions = cfg.get("sessions", [])
    
    trades = []
    open_trade = None
    balance = INITIAL_BALANCE
    eq_track = [balance]
    last_entry = 0
    
    for idx in range(WARMUP, len(m15)):
        candle = m15.iloc[idx]; ct = candle['time']
        if open_trade is not None:
            m15_end = ct + 15*60
            m1_in = m1_raw[(m1_raw['time'] >= ct) & (m1_raw['time'] < m15_end)]
            for _, m1c in m1_in.iterrows():
                ep, rsn = open_trade.check_exit_on_m1(m1c)
                if ep is not None:
                    open_trade.close(ep, m1c['time'], rsn)
                    balance += open_trade.pnl
                    trades.append(open_trade); open_trade = None; break
        eq_track.append(balance)
        if open_trade is not None: continue
        if idx < 1: continue
        
        closed_c = m15.iloc[idx-1]; live_c = candle
        ab = bool(live_c['arrow_buy']) and allow_arrow
        as_ = bool(live_c['arrow_sell']) and allow_arrow
        cb = bool(closed_c['circle_buy']) and allow_circle
        cs = bool(closed_c['circle_sell']) and allow_circle
        
        entry_dir = sig_type = None
        if ab or as_:
            entry_dir = "buy" if ab else "sell"; sig_type = "arrow"
        elif cb or cs:
            entry_dir = "buy" if cb else "sell"; sig_type = "circle"
        
        if not entry_dir: continue
        if last_entry == ct: continue
        if entry_dir == "buy" and not allow_buy: continue
        if entry_dir == "sell" and not allow_sell: continue
        
        if sessions:
            uh = datetime.fromtimestamp(ct).hour
            if not any(s in sessions for s in get_active_sessions(uh)):
                last_entry = ct; continue
        
        hist = m15.iloc[max(0, idx-200):idx]
        if enable_zone and not check_zone(
            entry_dir,
            candle['close'],
            hist,
            threshold_usd=z_thr,
            threshold_pct=z_pct,
            swing_window=z_sw,
            cluster_tol=0.15,
            min_touches=z_mt
        ):
            last_entry = ct
            continue
        if enable_sideways and not check_sideways(hist, sw_thr, sw_lb):
            last_entry = ct; continue
        if enable_timing and not check_timing(entry_dir, ct, m5_raw, m1_raw, t_m5, t_m1):
            last_entry = ct; continue
        
        rp = candle['close']
        if entry_dir == "buy":
            ep = rp + SPREAD_USD/2 + SLIPPAGE_USD
        else:
            ep = rp - SPREAD_USD/2 - SLIPPAGE_USD
        open_trade = Trade(entry_dir, ep, ct, sig_type)
        last_entry = ct
    
    if open_trade is not None:
        last = m15.iloc[-1]
        open_trade.close(last['close'], last['time'], "end")
        balance += open_trade.pnl
        trades.append(open_trade)
    
    if not trades:
        return {"trades": 0, "wr": 0, "pnl": 0, "max_dd": 0, "expectancy": 0, "rr": 0}
    
    tdf = pd.DataFrame([{'pnl': t.pnl} for t in trades])
    total = len(tdf)
    wins = tdf[tdf['pnl'] > 0]; losses = tdf[tdf['pnl'] <= 0]
    pnl = tdf['pnl'].sum()
    eq = pd.Series(eq_track); peak = eq.cummax(); dd = (eq - peak).min()
    rr = wins['pnl'].mean() / abs(losses['pnl'].mean()) if len(wins) and len(losses) else 0
    return {
        "trades": total, "wins": len(wins), "losses": len(losses),
        "wr": round(len(wins)/total*100, 1),
        "pnl": round(pnl, 2),
        "max_dd": round(dd, 2),
        "expectancy": round(pnl/total, 3),
        "rr": round(rr, 2),
    }


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  HELPER: Print row                               ║
# ╚══════════════════════════════════════════════════════════════════╝
def print_header():
    print(f"{'Config':<45} {'Trd':>4} {'WR%':>6} {'P/L $':>9} {'MaxDD':>8} {'E/trd':>7} {'R:R':>5}")
    print("─" * 90)

def print_row(label, r):
    print(f"{label:<45} {r['trades']:>4} {r['wr']:>6.1f} {r['pnl']:>+9.2f} "
          f"{r['max_dd']:>+8.2f} {r['expectancy']:>+7.3f} {r['rr']:>5.2f}")

def diff_vs_baseline(label, r, baseline):
    pnl_diff = r['pnl'] - baseline['pnl']
    wr_diff = r['wr'] - baseline['wr']
    trd_diff = r['trades'] - baseline['trades']
    arrow = "✅" if pnl_diff > 0 else "❌" if pnl_diff < 0 else "➖"
    print(f"  {arrow} {label:<42s} P/L {pnl_diff:>+8.2f} | WR {wr_diff:>+5.1f}% | Trd {trd_diff:>+4d}")


# ╔══════════════════════════════════════════════════════════════════╗
# ║                  MAIN                                            ║
# ╚══════════════════════════════════════════════════════════════════╝
def main():
    print("\n" + "="*90)
    print(f"  🧪 SYSTEMATIC FILTER OPTIMIZER — {SYMBOL} | {DAYS_BACK}d")
    print("="*90 + "\n")
    
    if not mt5.initialize():
        print(f"[ERROR] {mt5.last_error()}"); sys.exit(1)
    
    print("📥 Downloading...")
    tf_map = {"M1":mt5.TIMEFRAME_M1,"M5":mt5.TIMEFRAME_M5,"M15":mt5.TIMEFRAME_M15}
    end = datetime.now(); start = end - timedelta(days=DAYS_BACK+5)
    def dl(tf):
        r = mt5.copy_rates_range(SYMBOL, tf_map[tf], start, end)
        return pd.DataFrame(r) if r is not None else None
    m15_raw = dl("M15"); m5_raw = dl("M5"); m1_raw = dl("M1")
    print(f"  M15: {len(m15_raw)}, M5: {len(m5_raw)}, M1: {len(m1_raw)}")
    print("\n🔮 Calculating Crystal HA...")
    m15 = calculate_crystal_ha(m15_raw)
    print(f"  Signals: {((m15['circle_buy']|m15['circle_sell'])|(m15['arrow_buy']|m15['arrow_sell'])).sum()}\n")
    
    all_results = {}
    
    # ════════════════════════════════════════════════════════════════
    # PHASE 1: BASELINE (no filter)
    # ════════════════════════════════════════════════════════════════
    print("="*90)
    print("  📋 PHASE 1: BASELINE (NO FILTER)")
    print("="*90)
    print_header()
    
    baseline = run_backtest(m15, m5_raw, m1_raw, {
        "zone":False, "sideways":False, "timing":False,
        "buy":True, "sell":True, "circle":True, "arrow":True
    })
    print_row("BASELINE (raw signals, no filter)", baseline)
    all_results["BASELINE"] = baseline
    
    # ════════════════════════════════════════════════════════════════
    # PHASE 2: ISOLATE — tiap filter sendirian
    # ════════════════════════════════════════════════════════════════
    print("\n" + "="*90)
    print("  🔬 PHASE 2: ISOLATE EACH FILTER (vs baseline)")
    print("="*90)
    print_header()
    
    isolation_tests = [
        ("ZONE filter only (live 0.3%)",     {"zone":True, "sideways":False, "timing":False, "zone_threshold_pct":0.003}),
        ("SIDEWAYS filter only (default)",   {"zone":False, "sideways":True, "timing":False}),
        ("TIMING filter only (M5+M1)",       {"zone":False, "sideways":False, "timing":True}),
        ("TIMING filter only (M5 only)",     {"zone":False, "sideways":False, "timing":True, "timing_m1":False}),
        ("TIMING filter only (M1 only)",     {"zone":False, "sideways":False, "timing":True, "timing_m5":False}),
    ]
    iso_results = {}
    for label, cfg in isolation_tests:
        cfg.update({"buy":True, "sell":True, "circle":True, "arrow":True})
        r = run_backtest(m15, m5_raw, m1_raw, cfg)
        print_row(label, r)
        iso_results[label] = r
        all_results[label] = r
    
    print("\n  📊 IMPACT vs BASELINE:")
    for label, r in iso_results.items():
        diff_vs_baseline(label, r, baseline)
    
    # Pick winners
    helpers = {l: r for l, r in iso_results.items() if r['pnl'] > baseline['pnl']}
    hurters = {l: r for l, r in iso_results.items() if r['pnl'] <= baseline['pnl']}
    
    print(f"\n  ✅ Filters yang BANTU: {len(helpers)}")
    for l, r in helpers.items():
        print(f"     • {l}  (+${r['pnl']-baseline['pnl']:.2f})")
    print(f"\n  ❌ Filters yang RUGIIN: {len(hurters)}")
    for l, r in hurters.items():
        print(f"     • {l}  (${r['pnl']-baseline['pnl']:+.2f})")
    
    # ════════════════════════════════════════════════════════════════
    # PHASE 3: TWEAK — varying parameters per filter
    # ════════════════════════════════════════════════════════════════
    print("\n" + "="*90)
    print("  🔧 PHASE 3: TWEAK PARAMETERS")
    print("="*90)
    
    # ─── 3A. Zone filter sweep ───
    print("\n  🔵 ZONE FILTER — Percent Sweep (LIVE LOGIC):")
    print_header()
    zone_sweep = {}
    for pct in [0.001, 0.0015, 0.002, 0.0025, 0.003, 0.0035, 0.004, 0.005]:
        cfg = {
            "zone": True,
            "sideways": False,
            "timing": False,
            "buy": True,
            "sell": True,
            "circle": True,
            "arrow": True,
            "zone_threshold_pct": pct
        }
        r = run_backtest(m15, m5_raw, m1_raw, cfg)
        label = f"  Zone threshold {pct*100:.2f}%"
        print_row(label, r)
        zone_sweep[pct] = r
        all_results[f"ZONE_PCT_{pct}"] = r

    best_zone = max(zone_sweep.items(), key=lambda x: x[1]['pnl'])
    print(f"\n  🏆 Best Zone threshold: {best_zone[0]*100:.2f}% → P/L ${best_zone[1]['pnl']:+.2f}")
    
    # ─── 3B. Sideways filter sweep ───
    print("\n  🟡 SIDEWAYS FILTER — Body Ratio Sweep:")
    print_header()
    sw_sweep = {}
    for thr in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]:
        cfg = {"zone":False, "sideways":True, "timing":False,
               "buy":True, "sell":True, "circle":True, "arrow":True,
               "sideways_threshold": thr}
        r = run_backtest(m15, m5_raw, m1_raw, cfg)
        label = f"  Sideways body_ratio {thr}"
        print_row(label, r)
        sw_sweep[thr] = r
        all_results[f"SW_{thr}"] = r
    best_sw = max(sw_sweep.items(), key=lambda x: x[1]['pnl'])
    print(f"\n  🏆 Best Sideways threshold: {best_sw[0]} → P/L ${best_sw[1]['pnl']:+.2f}")
    
    # ─── 3C. Sideways lookback sweep ───
    print("\n  🟡 SIDEWAYS FILTER — Lookback Sweep (best threshold):")
    print_header()
    sw_lb_sweep = {}
    for lb in [5, 10, 15, 20, 30, 50]:
        cfg = {"zone":False, "sideways":True, "timing":False,
               "buy":True, "sell":True, "circle":True, "arrow":True,
               "sideways_threshold": best_sw[0], "sideways_lookback": lb}
        r = run_backtest(m15, m5_raw, m1_raw, cfg)
        label = f"  Sideways lookback={lb} (thr={best_sw[0]})"
        print_row(label, r)
        sw_lb_sweep[lb] = r
        all_results[f"SW_LB_{lb}"] = r
    
    # ─── 3D. Direction & Signal type ───
    print("\n  🎯 DIRECTION & SIGNAL TYPE FILTER:")
    print_header()
    for label, cfg in [
        ("BUY only (no other filter)",    {"zone":False, "sideways":False, "timing":False, "buy":True, "sell":False, "circle":True, "arrow":True}),
        ("SELL only (no other filter)",   {"zone":False, "sideways":False, "timing":False, "buy":False, "sell":True, "circle":True, "arrow":True}),
        ("ARROW only (no other filter)",  {"zone":False, "sideways":False, "timing":False, "buy":True, "sell":True, "circle":False, "arrow":True}),
        ("CIRCLE only (no other filter)", {"zone":False, "sideways":False, "timing":False, "buy":True, "sell":True, "circle":True, "arrow":False}),
        ("BUY + ARROW only",              {"zone":False, "sideways":False, "timing":False, "buy":True, "sell":False, "circle":False, "arrow":True}),
        ("SELL + ARROW only",             {"zone":False, "sideways":False, "timing":False, "buy":False, "sell":True, "circle":False, "arrow":True}),
        ("BUY + CIRCLE only",             {"zone":False, "sideways":False, "timing":False, "buy":True, "sell":False, "circle":True, "arrow":False}),
    ]:
        r = run_backtest(m15, m5_raw, m1_raw, cfg)
        print_row(label, r)
        all_results[label] = r
    
    # ─── 3E. Session filter ───
    print("\n  🕐 SESSION FILTER:")
    print_header()
    for label, sessions in [
        ("Tokyo only",        ["tokyo"]),
        ("London only",       ["london"]),
        ("NY only",           ["new_york"]),
        ("Sydney only",       ["sydney"]),
        ("London + NY",       ["london", "new_york"]),
        ("Tokyo + London",    ["tokyo", "london"]),
        ("All 4 (=baseline)", ["sydney","tokyo","london","new_york"]),
    ]:
        cfg = {"zone":False, "sideways":False, "timing":False,
               "buy":True, "sell":True, "circle":True, "arrow":True,
               "sessions": sessions}
        r = run_backtest(m15, m5_raw, m1_raw, cfg)
        print_row(f"  Session: {label}", r)
        all_results[f"SESSION_{label}"] = r
    
    # ════════════════════════════════════════════════════════════════
    # PHASE 4: STACK — combine the winners
    # ════════════════════════════════════════════════════════════════
    print("\n" + "="*90)
    print("  🏗️ PHASE 4: STACK BEST FILTERS")
    print("="*90)
    print_header()
    
    # Auto-detect best params
    best_zone_pct = best_zone[0] if best_zone[1]['pnl'] > baseline['pnl'] else None
    best_sw_thr   = best_sw[0]   if best_sw[1]['pnl']   > baseline['pnl'] else None
    
    print(f"\n  Using best params:")
    print(f"    Zone threshold:      {best_zone_pct*100:.2f}%" if best_zone_pct else "    Zone:      DISABLED (didn't help)")
    print(f"    Sideways threshold:  {best_sw_thr}" if best_sw_thr else "    Sideways:  DISABLED (didn't help)")
    print()
    
    stack_tests = [
        ("STACK: best zone only",        {"zone":bool(best_zone_pct), "zone_threshold_pct":best_zone_pct or 0.003}),
        ("STACK: best sideways only",    {"sideways":bool(best_sw_thr), "sideways_threshold":best_sw_thr or 0.15}),
        ("STACK: zone + sideways",       {"zone":True, "sideways":True, "zone_threshold_pct":best_zone_pct or 0.003, "sideways_threshold":best_sw_thr or 0.15}),
        ("STACK: zone + timing",         {"zone":True, "timing":True, "zone_threshold_pct":best_zone_pct or 0.003}),
        ("STACK: sideways + timing",     {"sideways":True, "timing":True, "sideways_threshold":best_sw_thr or 0.15}),
        ("STACK: ALL (zone+sw+timing)",  {"zone":True, "sideways":True, "timing":True, "zone_threshold_pct":best_zone_pct or 0.003, "sideways_threshold":best_sw_thr or 0.15}),
        ("STACK: ALL + BUY only",        {"zone":True, "sideways":True, "timing":True, "buy":True, "sell":False, "zone_threshold_pct":best_zone_pct or 0.003, "sideways_threshold":best_sw_thr or 0.15}),
        ("STACK: ALL + ARROW only",      {"zone":True, "sideways":True, "timing":True, "circle":False, "arrow":True, "zone_threshold_pct":best_zone_pct or 0.003, "sideways_threshold":best_sw_thr or 0.15}),
        ("STACK: ALL + BUY + ARROW",     {"zone":True, "sideways":True, "timing":True, "buy":True, "sell":False, "circle":False, "arrow":True, "zone_threshold_pct":best_zone_pct or 0.003, "sideways_threshold":best_sw_thr or 0.15}),
    ]
    stack_results = {}
    for label, override in stack_tests:
        cfg = {"zone":False, "sideways":False, "timing":False,
               "buy":True, "sell":True, "circle":True, "arrow":True}
        cfg.update(override)
        r = run_backtest(m15, m5_raw, m1_raw, cfg)
        print_row(label, r)
        stack_results[label] = r
        all_results[label] = r
    
    # ════════════════════════════════════════════════════════════════
    # FINAL: BEST OVERALL
    # ════════════════════════════════════════════════════════════════
    print("\n" + "="*90)
    print("  🏆 FINAL: TOP 10 OVERALL")
    print("="*90)
    
    sorted_all = sorted(all_results.items(), key=lambda x: x[1]['pnl'], reverse=True)
    print_header()
    for label, r in sorted_all[:10]:
        print_row(label, r)
    
    print("\n  📈 TOP 5 BY EXPECTANCY (min 10 trades):")
    sorted_exp = sorted([(l, r) for l, r in all_results.items() if r['trades'] >= 10],
                         key=lambda x: x[1]['expectancy'], reverse=True)
    for label, r in sorted_exp[:5]:
        print(f"    • {label:<45s} ${r['expectancy']:>+.3f}/trd | "
              f"{r['trades']:>3d} trd | ${r['pnl']:>+.2f} total | WR {r['wr']:.1f}%")
    
    print("\n  🛡️ TOP 5 BY RISK-ADJUSTED (P/L / |DD|, min 10 trades):")
    for l, r in all_results.items():
        r['risk_adj'] = r['pnl'] / abs(r['max_dd']) if r['max_dd'] != 0 else r['pnl']
    sorted_ra = sorted([(l, r) for l, r in all_results.items() if r['trades'] >= 10],
                       key=lambda x: x[1].get('risk_adj', 0), reverse=True)
    for label, r in sorted_ra[:5]:
        print(f"    • {label:<45s} ratio {r.get('risk_adj',0):>+.2f} | "
              f"P/L ${r['pnl']:>+.2f} | DD ${r['max_dd']:.2f}")
    
    # Save all
    df = pd.DataFrame([{"label": l, **r} for l, r in all_results.items()])
    df.to_csv("optimizer_results_v2.csv", index=False)
    print("\n  💾 All results saved to: optimizer_results_v2.csv")
    
    # ════════════════════════════════════════════════════════════════
    # CONCLUSIONS
    # ════════════════════════════════════════════════════════════════
    print("\n" + "="*90)
    print("  💡 CONCLUSIONS")
    print("="*90)
    
    best = sorted_all[0]
    print(f"\n  🥇 BEST CONFIG: {best[0]}")
    print(f"     P/L ${best[1]['pnl']:+.2f} | WR {best[1]['wr']:.1f}% | "
          f"{best[1]['trades']} trades | DD ${best[1]['max_dd']:.2f}")
    print(f"     Improvement vs baseline: ${best[1]['pnl'] - baseline['pnl']:+.2f} "
          f"({(best[1]['pnl']/baseline['pnl']*100 - 100):+.1f}% if baseline > 0)")
    
    print(f"\n  📊 Filter Verdict (vs no-filter baseline):")
    if best_zone_pct:
        b = zone_sweep[best_zone_pct]
        print(f"     ✅ ZONE: HELPS at threshold {best_zone_pct*100:.2f}% → +${b['pnl']-baseline['pnl']:.2f}")
    else:
        print(f"     ❌ ZONE: HURTS at all tested thresholds")
    if best_sw_thr:
        b = sw_sweep[best_sw_thr]
        print(f"     ✅ SIDEWAYS: HELPS at threshold {best_sw_thr} → +${b['pnl']-baseline['pnl']:.2f}")
    else:
        print(f"     ❌ SIDEWAYS: HURTS at all tested thresholds")
    
    timing_results = [iso_results[k] for k in iso_results if 'TIMING' in k]
    if any(r['pnl'] > baseline['pnl'] for r in timing_results):
        print(f"     ✅ TIMING: HELPS")
    else:
        print(f"     ❌ TIMING: HURTS")
    
    print("\n" + "="*90 + "\n")
    mt5.shutdown()


if __name__ == "__main__":
    main()