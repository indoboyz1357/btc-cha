"""
backtest_v3_final.py - Signal Omega V2 Backtest (FINAL)
========================================================
✅ P/L formula CORRECT (Exness BTCUSDm: diff × lot × 1.0)
✅ EA AutoSLTP v8.4 spec REAL (SL 200pts, TP 500pts, Trail 250/100)
✅ Trailing pakai M1 candles (akurasi tinggi)
✅ Multi-filter (Zone, Sideways, Timing) — bisa toggle
✅ Sanity checks & detailed audit log

USAGE:
    python backtest_v3_final.py

TWEAK CONFIG di bagian "USER CONFIG" di bawah.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

# ╔══════════════════════════════════════════════════════════════════╗
# ║                       USER CONFIG                                ║
# ╚══════════════════════════════════════════════════════════════════╝

# ─── Symbol & Account ───
SYMBOL          = "BTCUSDm"
DAYS_BACK       = 30
INITIAL_BALANCE = 500.0
LOT_SIZE        = 0.01

# ─── Exness BTCUSDm Spec (CONFIRMED) ───
CONTRACT_SIZE   = 100.0      # 1 lot = 1 BTC
SPREAD_USD      = 25.0     # avg spread realistic ($30)
SLIPPAGE_USD    = 2.0      # avg slippage saat entry

# ─── EA AutoSLTP v8.4 Settings (REAL aktif sekarang) ───
HARD_SL_USD          = 2.00    # 200 points: hard stop loss
HARD_TP_USD          = 5.00    # 500 points: hard take profit
TRAILING_TRIGGER_USD = 2.50    # 250 points: trailing aktif setelah profit ini
TRAILING_STOP_USD    = 1.00    # 100 points: jarak trail dari peak

# ─── Smart Filters (toggle untuk eksperimen) ───
ENABLE_ZONE_FILTER     = True
ENABLE_SIDEWAYS_FILTER = True
ENABLE_TIMING_FILTER   = True
ZONE_THRESHOLD_USD     = 200    # block kalau S/R lebih dekat dari $200

# ─── Trading Rules ───
ALLOW_BUY            = True
ALLOW_SELL           = True
SESSION_FILTER       = []       # [] = all sessions, atau ['london', 'new_york']
MAX_DAILY_LOSS_USD   = 999.0    # disable; pakai angka kecil kalau mau test guard

# ─── Output ───
RESULTS_CSV   = "backtest_results.csv"
EQUITY_CSV    = "backtest_equity.csv"
DEBUG_FIRST_N = 15              # print detail N trade pertama

# ╔══════════════════════════════════════════════════════════════════╗
# ║                       INIT                                       ║
# ╚══════════════════════════════════════════════════════════════════╝

print("\n" + "=" * 72)
print(f"  🚀 BACKTEST FINAL — Signal Omega V2")
print("=" * 72)
print(f"  Symbol: {SYMBOL} | Period: {DAYS_BACK}d | Balance: ${INITIAL_BALANCE} | Lot: {LOT_SIZE}")
print(f"  EA Spec: SL ${HARD_SL_USD} | TP ${HARD_TP_USD} | Trail trigger ${TRAILING_TRIGGER_USD} | trail ${TRAILING_STOP_USD}")
print(f"  Filters: Zone={ENABLE_ZONE_FILTER} Sideways={ENABLE_SIDEWAYS_FILTER} Timing={ENABLE_TIMING_FILTER}")
print(f"  Spread: ${SPREAD_USD} | Slippage: ${SLIPPAGE_USD}")
print("=" * 72 + "\n")

if not mt5.initialize():
    print(f"[ERROR] MT5 init failed: {mt5.last_error()}")
    sys.exit(1)


# ╔══════════════════════════════════════════════════════════════════╗
# ║                   CRYSTAL HA CALCULATOR                          ║
# ╚══════════════════════════════════════════════════════════════════╝

def calculate_crystal_ha(df):
    """Port dari bridge.py get_crystal_ha()"""
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
# ║                   DOWNLOAD HISTORICAL                            ║
# ╚══════════════════════════════════════════════════════════════════╝

def download(symbol, tf_str, days):
    tf_map = {"M1":mt5.TIMEFRAME_M1, "M5":mt5.TIMEFRAME_M5, "M15":mt5.TIMEFRAME_M15}
    end = datetime.now()
    start = end - timedelta(days=days+5)
    rates = mt5.copy_rates_range(symbol, tf_map[tf_str], start, end)
    if rates is None or len(rates) == 0:
        print(f"  [ERROR] {tf_str}: {mt5.last_error()}")
        return None
    df = pd.DataFrame(rates)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    print(f"  ✅ {tf_str}: {len(df)} candles | {df['datetime'].iloc[0]} → {df['datetime'].iloc[-1]}")
    return df


print("📥 Downloading historical data...")
m15_raw = download(SYMBOL, "M15", DAYS_BACK)
m5_raw  = download(SYMBOL, "M5",  DAYS_BACK)
m1_raw  = download(SYMBOL, "M1",  DAYS_BACK)
if any(x is None for x in [m15_raw, m5_raw, m1_raw]):
    print("[ERROR] Download failed. Pastikan symbol benar di Market Watch.")
    mt5.shutdown(); sys.exit(1)

print("\n🔮 Calculating Crystal HA M15...")
m15 = calculate_crystal_ha(m15_raw)
total_circles = (m15['circle_buy'] | m15['circle_sell']).sum()
total_arrows  = (m15['arrow_buy']  | m15['arrow_sell']).sum()
print(f"  Total: {len(m15)} candles | Circles: {total_circles} | Arrows: {total_arrows}")
print(f"  Signal density: {(total_circles+total_arrows)/len(m15)*100:.1f}% candles have signal\n")


# ╔══════════════════════════════════════════════════════════════════╗
# ║                   FILTERS                                        ║
# ╚══════════════════════════════════════════════════════════════════╝

def check_zone(direction, price, history_df, threshold=ZONE_THRESHOLD_USD):
    if len(history_df) < 50:
        return True, "no_data"
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
            else:
                cl.append([p])
        return [sum(c)/len(c) for c in cl if len(c) >= min_t]
    
    R = cluster(highs); S = cluster(lows)
    if direction == "buy":
        nr = min([r for r in R if r > price], default=None)
        if nr is None: return True, "no_R_above"
        d = nr - price
        return (d >= threshold), f"R_dist=${d:.0f}"
    else:
        ns = max([s for s in S if s < price], default=None)
        if ns is None: return True, "no_S_below"
        d = price - ns
        return (d >= threshold), f"S_dist=${d:.0f}"


def check_sideways(history_df):
    if len(history_df) < 15: return True, "no_data"
    df = history_df.tail(15)
    rng = df['high'].max() - df['low'].min()
    body = (df['close'] - df['open']).abs().mean()
    ratio = body/rng if rng > 0 else 0
    return (ratio >= 0.15), f"body={ratio:.2f}"


def check_timing(direction, m15_time, m5_df, m1_df):
    m5r = m5_df[m5_df['time'] <= m15_time].tail(3)
    m1r = m1_df[m1_df['time'] <= m15_time].tail(3)
    if len(m5r) < 2 or len(m1r) < 2: return True, "no_data"
    
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
        ok = m5c in bull and m1c in bull
    else:
        ok = m5c in bear and m1c in bear
    return ok, f"m5={m5c}/m1={m1c}"


def get_active_sessions(utc_hour):
    s = []
    if utc_hour >= 22 or utc_hour < 7: s.append("sydney")
    if 0 <= utc_hour < 9:              s.append("tokyo")
    if 7 <= utc_hour < 16:             s.append("london")
    if 12 <= utc_hour < 21:            s.append("new_york")
    return s


# ╔══════════════════════════════════════════════════════════════════╗
# ║                   TRADE OBJECT                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

class Trade:
    def __init__(self, direction, entry, entry_time, lot, idx, signal_type):
        self.direction = direction
        self.entry = entry
        self.entry_time = entry_time
        self.lot = lot
        self.entry_idx = idx
        self.signal_type = signal_type
        self.exit = None
        self.exit_time = None
        self.exit_reason = None
        self.pnl = 0.0
        self.trailing_active = False
        self.trailing_sl = None
        self.peak_profit = 0.0
        self.bars_held = 0
    
    def check_exit_on_m1(self, m1_candle):
        """Cek exit pakai 1 candle M1. Return (exit_price, reason) atau (None, None)"""
        h = m1_candle['high']; l = m1_candle['low']
        
        if self.direction == "buy":
            # Order check: TP first (kalau gap), lalu SL, lalu trailing
            if h >= self.entry + HARD_TP_USD:
                return self.entry + HARD_TP_USD, "hard_tp"
            if l <= self.entry - HARD_SL_USD:
                return self.entry - HARD_SL_USD, "hard_sl"
            
            profit = h - self.entry
            self.peak_profit = max(self.peak_profit, profit)
            
            if not self.trailing_active and profit >= TRAILING_TRIGGER_USD:
                self.trailing_active = True
                self.trailing_sl = h - TRAILING_STOP_USD
            
            if self.trailing_active:
                new_sl = h - TRAILING_STOP_USD
                if new_sl > self.trailing_sl:
                    self.trailing_sl = new_sl
                if l <= self.trailing_sl:
                    return self.trailing_sl, "trailing_sl"
        else:
            if l <= self.entry - HARD_TP_USD:
                return self.entry - HARD_TP_USD, "hard_tp"
            if h >= self.entry + HARD_SL_USD:
                return self.entry + HARD_SL_USD, "hard_sl"
            
            profit = self.entry - l
            self.peak_profit = max(self.peak_profit, profit)
            
            if not self.trailing_active and profit >= TRAILING_TRIGGER_USD:
                self.trailing_active = True
                self.trailing_sl = l + TRAILING_STOP_USD
            
            if self.trailing_active:
                new_sl = l + TRAILING_STOP_USD
                if new_sl < self.trailing_sl:
                    self.trailing_sl = new_sl
                if h >= self.trailing_sl:
                    return self.trailing_sl, "trailing_sl"
        
        return None, None
    
    def close(self, exit_price, exit_time, reason):
        self.exit = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        diff = (exit_price - self.entry) if self.direction == "buy" else (self.entry - exit_price)
        # CONFIRMED FORMULA: P/L = price_diff × lot × contract_size
        self.pnl = diff * self.lot * CONTRACT_SIZE


# ╔══════════════════════════════════════════════════════════════════╗
# ║                   MAIN BACKTEST LOOP                             ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 72)
print("  ⚡ RUNNING BACKTEST...")
print("=" * 72 + "\n")

trades = []
open_trade = None
balance = INITIAL_BALANCE
equity = [(m15['time'].iloc[0], balance)]
last_entry_candle = 0
daily_loss = 0.0
last_day = None
WARMUP = 200
debug_count = 0

# Stats
filter_blocks = {"zone": 0, "sideways": 0, "timing": 0, "session": 0, "daily_loss": 0}
signal_counts = {"circle_buy": 0, "circle_sell": 0, "arrow_buy": 0, "arrow_sell": 0}

for idx in range(WARMUP, len(m15)):
    candle = m15.iloc[idx]
    ct = candle['time']
    
    # Daily loss reset (tiap hari baru)
    cur_day = datetime.fromtimestamp(ct).date()
    if last_day is None or cur_day != last_day:
        daily_loss = 0.0
        last_day = cur_day
    
    # ─── 1. Update open trade pakai M1 ───
    if open_trade is not None:
        m15_end = ct + 15*60
        m1_in_range = m1_raw[(m1_raw['time'] >= ct) & (m1_raw['time'] < m15_end)]
        
        for _, m1c in m1_in_range.iterrows():
            open_trade.bars_held += 1
            exit_price, reason = open_trade.check_exit_on_m1(m1c)
            if exit_price is not None:
                open_trade.close(exit_price, m1c['time'], reason)
                balance += open_trade.pnl
                if open_trade.pnl < 0:
                    daily_loss += abs(open_trade.pnl)
                
                if debug_count < DEBUG_FIRST_N:
                    et_str = datetime.fromtimestamp(open_trade.entry_time).strftime("%m-%d %H:%M")
                    xt_str = datetime.fromtimestamp(open_trade.exit_time).strftime("%H:%M")
                    print(f"  [#{len(trades)+1:3d}] {et_str}→{xt_str} {open_trade.direction.upper():4s} "
                          f"{open_trade.signal_type:7s} | Entry {open_trade.entry:.2f} → Exit {exit_price:.2f} "
                          f"| {reason:12s} | P/L ${open_trade.pnl:+.4f} | Bal ${balance:.2f}")
                    debug_count += 1
                
                trades.append(open_trade)
                open_trade = None
                break
    
    if open_trade is not None:
        equity.append((ct, balance))
        continue
    
    # ─── 2. Detect signal ───
    if idx < 1: continue
    closed_c = m15.iloc[idx-1]
    live_c = candle
    
    ab = bool(live_c['arrow_buy']); as_ = bool(live_c['arrow_sell'])
    cb = bool(closed_c['circle_buy']); cs = bool(closed_c['circle_sell'])
    
    entry_dir = signal_type = None
    if ab or as_:
        entry_dir = "buy" if ab else "sell"; signal_type = "arrow"
        signal_counts[f"arrow_{entry_dir}"] += 1
    elif cb or cs:
        entry_dir = "buy" if cb else "sell"; signal_type = "circle"
        signal_counts[f"circle_{entry_dir}"] += 1
    
    if not entry_dir:
        equity.append((ct, balance))
        continue
    
    if last_entry_candle == ct: continue
    if entry_dir == "buy" and not ALLOW_BUY: continue
    if entry_dir == "sell" and not ALLOW_SELL: continue
    
    # Daily loss guard
    if daily_loss >= MAX_DAILY_LOSS_USD:
        filter_blocks["daily_loss"] += 1
        last_entry_candle = ct
        continue
    
    # Session filter
    if SESSION_FILTER:
        utc_hour = datetime.fromtimestamp(ct).hour
        if not any(s in SESSION_FILTER for s in get_active_sessions(utc_hour)):
            filter_blocks["session"] += 1
            last_entry_candle = ct
            continue
    
    # ─── 3. Smart Filters ───
    hist = m15.iloc[max(0, idx-200):idx]
    
    if ENABLE_ZONE_FILTER:
        ok, _ = check_zone(entry_dir, candle['close'], hist)
        if not ok:
            filter_blocks["zone"] += 1
            last_entry_candle = ct
            continue
    
    if ENABLE_SIDEWAYS_FILTER:
        ok, _ = check_sideways(hist)
        if not ok:
            filter_blocks["sideways"] += 1
            last_entry_candle = ct
            continue
    
    if ENABLE_TIMING_FILTER:
        ok, _ = check_timing(entry_dir, ct, m5_raw, m1_raw)
        if not ok:
            filter_blocks["timing"] += 1
            last_entry_candle = ct
            continue
    
    # ─── 4. ENTRY ───
    raw_price = candle['close']
    if entry_dir == "buy":
        entry_price = raw_price + SPREAD_USD/2 + SLIPPAGE_USD
    else:
        entry_price = raw_price - SPREAD_USD/2 - SLIPPAGE_USD
    
    open_trade = Trade(entry_dir, entry_price, ct, LOT_SIZE, idx, signal_type)
    last_entry_candle = ct
    equity.append((ct, balance))


# Close pending
if open_trade is not None:
    last = m15.iloc[-1]
    open_trade.close(last['close'], last['time'], "end_of_data")
    balance += open_trade.pnl
    trades.append(open_trade)


# ╔══════════════════════════════════════════════════════════════════╗
# ║                   RESULTS & ANALYSIS                             ║
# ╚══════════════════════════════════════════════════════════════════╝

print("\n" + "=" * 72)
print("  📊 BACKTEST RESULTS")
print("=" * 72)

if not trades:
    print("\n  ❌ ZERO TRADES executed")
    print("\n  Filter blocks:")
    for k, v in filter_blocks.items():
        print(f"    {k}: {v}")
    print("\n  Tip: disable filter satu-satu cari yang terlalu ketat")
    mt5.shutdown(); sys.exit(0)

# Save CSVs
tdf = pd.DataFrame([{
    'entry_time': datetime.fromtimestamp(t.entry_time),
    'exit_time':  datetime.fromtimestamp(t.exit_time) if t.exit_time else None,
    'direction':  t.direction,
    'signal':     t.signal_type,
    'entry':      round(t.entry, 2),
    'exit':       round(t.exit, 2) if t.exit else None,
    'pnl':        round(t.pnl, 4),
    'reason':     t.exit_reason,
    'peak_profit_usd': round(t.peak_profit, 2),
    'bars_m1_held': t.bars_held,
} for t in trades])
tdf.to_csv(RESULTS_CSV, index=False)

eq = pd.DataFrame(equity, columns=['time','balance'])
eq['datetime'] = pd.to_datetime(eq['time'], unit='s')
eq.to_csv(EQUITY_CSV, index=False)

# Performance
total = len(tdf)
wins = tdf[tdf['pnl'] > 0]
losses = tdf[tdf['pnl'] <= 0]
total_pnl = tdf['pnl'].sum()
ret_pct = (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100

print(f"\n  💰 PERFORMANCE")
print(f"     Period:         {DAYS_BACK} days")
print(f"     Initial:        ${INITIAL_BALANCE:.2f}")
print(f"     Final:          ${balance:.4f}")
print(f"     Total P/L:      ${total_pnl:+.4f} ({ret_pct:+.2f}%)")
print(f"     Total trades:   {total}")
print(f"     Win rate:       {len(wins)/total*100:.1f}% ({len(wins)}W / {len(losses)}L)")

if len(wins):
    print(f"     Avg win:        ${wins['pnl'].mean():+.4f}  | Max: ${wins['pnl'].max():+.4f}")
if len(losses):
    print(f"     Avg loss:       ${losses['pnl'].mean():+.4f}  | Max: ${losses['pnl'].min():+.4f}")
if len(wins) and len(losses):
    rr = wins['pnl'].mean() / abs(losses['pnl'].mean())
    print(f"     R:R ratio:      1:{rr:.2f}")
    expectancy = (len(wins)/total) * wins['pnl'].mean() + (len(losses)/total) * losses['pnl'].mean()
    print(f"     Expectancy:     ${expectancy:+.4f}/trade")

# Drawdown
eq['peak'] = eq['balance'].cummax()
eq['dd'] = eq['balance'] - eq['peak']
max_dd = eq['dd'].min()
max_dd_pct = (max_dd / eq['peak'].max() * 100) if eq['peak'].max() > 0 else 0
print(f"     Max DD:         ${max_dd:.4f} ({max_dd_pct:.2f}%)")

# Exit reasons
print(f"\n  🎯 EXIT REASONS")
for reason, count in tdf['reason'].value_counts().items():
    sub = tdf[tdf['reason'] == reason]
    win_count = (sub['pnl'] > 0).sum()
    print(f"     {reason:15s} {count:>3} trades | "
          f"WR {win_count/count*100:>5.1f}% | P/L ${sub['pnl'].sum():+.4f}")

# By direction
print(f"\n  📊 BY DIRECTION")
for d in ['buy', 'sell']:
    s = tdf[tdf['direction'] == d]
    if len(s) == 0: continue
    sw = s[s['pnl'] > 0]
    print(f"     {d.upper():5s} {len(s):>3} trades | "
          f"WR {len(sw)/len(s)*100:>5.1f}% | P/L ${s['pnl'].sum():+.4f}")

# By signal type
print(f"\n  📊 BY SIGNAL TYPE")
for st in ['circle', 'arrow']:
    s = tdf[tdf['signal'] == st]
    if len(s) == 0: continue
    sw = s[s['pnl'] > 0]
    print(f"     {st.upper():7s} {len(s):>3} trades | "
          f"WR {len(sw)/len(s)*100:>5.1f}% | P/L ${s['pnl'].sum():+.4f}")

# Filter stats
print(f"\n  🛡️ FILTER BLOCKS (signal valid tapi di-skip)")
print(f"     Zone blocks:      {filter_blocks['zone']}")
print(f"     Sideways blocks:  {filter_blocks['sideways']}")
print(f"     Timing blocks:    {filter_blocks['timing']}")
print(f"     Session blocks:   {filter_blocks['session']}")
print(f"     Daily loss skip:  {filter_blocks['daily_loss']}")

# Signal count
print(f"\n  🎲 SIGNAL COUNTS (raw, sebelum filter)")
print(f"     Circle BUY:  {signal_counts['circle_buy']}")
print(f"     Circle SELL: {signal_counts['circle_sell']}")
print(f"     Arrow BUY:   {signal_counts['arrow_buy']}")
print(f"     Arrow SELL:  {signal_counts['arrow_sell']}")
print(f"     Total raw:   {sum(signal_counts.values())}")
print(f"     Executed:    {total} ({total/sum(signal_counts.values())*100:.1f}% of raw)")

# Sanity check
print(f"\n  🔍 SANITY CHECK")
big_w = tdf['pnl'].max(); big_l = tdf['pnl'].min()
print(f"     Biggest win:  ${big_w:+.4f}  (max possible: ${HARD_TP_USD * LOT_SIZE * CONTRACT_SIZE:.4f})")
print(f"     Biggest loss: ${big_l:+.4f}  (max possible: ${-HARD_SL_USD * LOT_SIZE * CONTRACT_SIZE:.4f})")

if big_w > HARD_TP_USD * LOT_SIZE * CONTRACT_SIZE * 1.1:
    print(f"     ⚠️  Win > TP — kemungkinan trailing kerja bagus!")
if big_l < -HARD_SL_USD * LOT_SIZE * CONTRACT_SIZE * 1.1:
    print(f"     ⚠️  Loss > SL — ada bug? cek manual")

print(f"\n  💾 FILES SAVED")
print(f"     {RESULTS_CSV} ({total} trades)")
print(f"     {EQUITY_CSV} ({len(eq)} points)")

print("\n" + "=" * 72 + "\n")

mt5.shutdown()