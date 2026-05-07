"""
test_arrow_circle_zone.py
Backtest cepat tapi VALID:
- ARROW + ZONE
- CIRCLE + ZONE

Pakai logic exit yang sama seperti optimizer:
SL/TP + trailing di M1
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import sys

# ================== CONFIG ==================
SYMBOL = "BTCUSDm"
DAYS_BACK = 30
INITIAL_BALANCE = 500.0
LOT_SIZE = 0.01
CONTRACT_SIZE = 100.0
SPREAD_USD = 25.0
SLIPPAGE_USD = 3.0
HARD_SL_USD = 2.0
HARD_TP_USD = 5.0
TRAILING_TRIGGER_USD = 2.50
TRAILING_STOP_USD = 1.00
WARMUP = 200

# ================== CRYSTAL HA ==================
def calculate_crystal_ha(df):
    res = []
    prev_ha_o = prev_ha_c = ema20 = ema50 = 0.0
    pending = None
    CONFIRM = 3

    df = df.reset_index(drop=True)

    for i, row in df.iterrows():
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])

        if i == 0:
            ema20 = c
            ema50 = c
            ha_o = (o + c) / 2
            ha_c = (o + h + l + c) / 4
            ha_h = h
            ha_l = l
        else:
            ema20 = (c - ema20) * (2 / 21) + ema20
            ema50 = (c - ema50) * (2 / 51) + ema50
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

            if (not prev_bull) and is_bull:
                cb = True
                pending = {
                    "type": "buy",
                    "ref_high": ha_h,
                    "ref_low": ha_l,
                    "waited": 0
                }
            elif prev_bull and (not is_bull):
                cs = True
                pending = {
                    "type": "sell",
                    "ref_high": ha_h,
                    "ref_low": ha_l,
                    "waited": 0
                }

            if pending and not cb and not cs:
                pending["waited"] += 1

                if pending["type"] == "buy":
                    if ha_c > pending["ref_high"]:
                        ab = True
                        pending = None
                    elif (not is_bull) or pending["waited"] >= CONFIRM:
                        pending = None
                else:
                    if ha_c < pending["ref_low"]:
                        as_ = True
                        pending = None
                    elif is_bull or pending["waited"] >= CONFIRM:
                        pending = None

        res.append({
            "time": int(row["time"]),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "ha_open": ha_o,
            "ha_high": ha_h,
            "ha_low": ha_l,
            "ha_close": ha_c,
            "ema20": ema20,
            "ema50": ema50,
            "color": color,
            "circle_buy": cb,
            "circle_sell": cs,
            "arrow_buy": ab,
            "arrow_sell": as_,
        })

    return pd.DataFrame(res)

# ================== ZONE FILTER ==================
def check_zone(direction, price, history_df, threshold_pct=0.003,
               swing_window=5, cluster_tol=0.15, min_touches=2):
    try:
        if len(history_df) < 50:
            return True

        df = history_df.tail(200).reset_index(drop=True)
        highs, lows = [], []

        for i in range(swing_window, len(df) - swing_window):
            left = df.iloc[i - swing_window:i]
            right = df.iloc[i + 1:i + swing_window + 1]
            cur = df.iloc[i]

            if cur["high"] > left["high"].max() and cur["high"] > right["high"].max():
                highs.append(float(cur["high"]))

            if cur["low"] < left["low"].min() and cur["low"] < right["low"].min():
                lows.append(float(cur["low"]))

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
        threshold = price * float(threshold_pct)

        if direction == "buy":
            above = [r for r in R if r > price]
            if not above:
                return True
            nr = min(above)
            return (nr - price) >= threshold

        elif direction == "sell":
            below = [s for s in S if s < price]
            if not below:
                return True
            ns = max(below)
            return (price - ns) >= threshold

        return True

    except Exception as e:
        print(f"[ZONE ERROR] {e}")
        return True

# ================== TRADE CLASS ==================
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
        h = float(m1_candle["high"])
        l = float(m1_candle["low"])

        if self.direction == "buy":
            if h >= self.entry + HARD_TP_USD:
                return self.entry + HARD_TP_USD, "hard_tp"
            if l <= self.entry - HARD_SL_USD:
                return self.entry - HARD_SL_USD, "hard_sl"

            profit = h - self.entry
            if (not self.trailing_active) and profit >= TRAILING_TRIGGER_USD:
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
            if (not self.trailing_active) and profit >= TRAILING_TRIGGER_USD:
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
        self.pnl = diff * LOT_SIZE * CONTRACT_SIZE

# ================== BACKTEST ==================
def run_backtest_zone_signal(m15, m1_raw, signal_mode="arrow", zone_pct=0.003):
    trades = []
    open_trade = None
    balance = INITIAL_BALANCE
    eq_track = [balance]
    last_entry = 0

    for idx in range(WARMUP, len(m15)):
        candle = m15.iloc[idx]
        ct = int(candle["time"])

        # manage open trade on M1
        if open_trade is not None:
            m15_end = ct + 15 * 60
            m1_in = m1_raw[(m1_raw["time"] >= ct) & (m1_raw["time"] < m15_end)]
            for _, m1c in m1_in.iterrows():
                ep, rsn = open_trade.check_exit_on_m1(m1c)
                if ep is not None:
                    open_trade.close(ep, int(m1c["time"]), rsn)
                    balance += open_trade.pnl
                    trades.append(open_trade)
                    open_trade = None
                    break

        eq_track.append(balance)

        if open_trade is not None:
            continue

        if idx < 1:
            continue

        closed_c = m15.iloc[idx - 1]
        live_c = candle

        if signal_mode == "arrow":
            ab = bool(live_c["arrow_buy"])
            as_ = bool(live_c["arrow_sell"])
            cb = False
            cs = False
        else:
            ab = False
            as_ = False
            cb = bool(closed_c["circle_buy"])
            cs = bool(closed_c["circle_sell"])

        entry_dir = None
        signal_type = None

        if ab or as_:
            entry_dir = "buy" if ab else "sell"
            signal_type = "arrow"
        elif cb or cs:
            entry_dir = "buy" if cb else "sell"
            signal_type = "circle"

        if not entry_dir:
            continue

        if last_entry == ct:
            continue

        hist = m15.iloc[max(0, idx - 200):idx]
        if not check_zone(entry_dir, candle["close"], hist, threshold_pct=zone_pct):
            last_entry = ct
            continue

        rp = float(candle["close"])
        if entry_dir == "buy":
            ep = rp + SPREAD_USD / 2 + SLIPPAGE_USD
        else:
            ep = rp - SPREAD_USD / 2 - SLIPPAGE_USD

        open_trade = Trade(entry_dir, ep, ct, signal_type)
        last_entry = ct

    if open_trade is not None:
        last = m15.iloc[-1]
        open_trade.close(float(last["close"]), int(last["time"]), "end")
        balance += open_trade.pnl
        trades.append(open_trade)

    if not trades:
        return {
            "trades": 0,
            "wr": 0,
            "pnl": 0,
            "max_dd": 0,
            "expectancy": 0,
            "rr": 0
        }

    tdf = pd.DataFrame([{"pnl": t.pnl} for t in trades])
    total = len(tdf)
    wins = tdf[tdf["pnl"] > 0]
    losses = tdf[tdf["pnl"] <= 0]
    pnl = float(tdf["pnl"].sum())

    eq = pd.Series(eq_track)
    peak = eq.cummax()
    dd = (eq - peak).min()

    rr = wins["pnl"].mean() / abs(losses["pnl"].mean()) if len(wins) and len(losses) else 0

    return {
        "trades": total,
        "wr": round(len(wins) / total * 100, 1),
        "pnl": round(pnl, 2),
        "max_dd": round(float(dd), 2),
        "expectancy": round(pnl / total, 3),
        "rr": round(rr, 2),
    }

# ================== MAIN ==================
def main():
    print("\n" + "=" * 80)
    print("TEST CEPAT VALID — ARROW + ZONE & CIRCLE + ZONE")
    print("=" * 80)

    if not mt5.initialize():
        print(f"MT5 init gagal: {mt5.last_error()}")
        sys.exit(1)

    end = datetime.now()
    start = end - timedelta(days=DAYS_BACK + 5)

    m15_rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M15, start, end)
    m1_rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start, end)

    if m15_rates is None or m1_rates is None:
        print("Gagal download data dari MT5")
        mt5.shutdown()
        sys.exit(1)

    m15_raw = pd.DataFrame(m15_rates)
    m1_raw = pd.DataFrame(m1_rates)

    if len(m15_raw) == 0 or len(m1_raw) == 0:
        print("Data kosong")
        mt5.shutdown()
        sys.exit(1)

    m15 = calculate_crystal_ha(m15_raw)

    print(f"M15 candles: {len(m15_raw)} | M1 candles: {len(m1_raw)}")
    print(f"Signals total: {((m15['circle_buy'] | m15['circle_sell']) | (m15['arrow_buy'] | m15['arrow_sell'])).sum()}")
    print()

    pcts = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]

    print(f"{'Config':<28} {'Trd':>5} {'WR%':>6} {'P/L $':>9} {'MaxDD':>8} {'E/trd':>7} {'R:R':>5}")
    print("-" * 80)

    best_arrow = None
    best_circle = None

    for pct in pcts:
        zone_pct = pct / 100.0

        r1 = run_backtest_zone_signal(m15, m1_raw, signal_mode="arrow", zone_pct=zone_pct)
        print(f"{('ARROW + Zone ' + f'{pct:.2f}%'):<28} {r1['trades']:>5} {r1['wr']:>6.1f} {r1['pnl']:>+9.2f} {r1['max_dd']:>+8.2f} {r1['expectancy']:>+7.3f} {r1['rr']:>5.2f}")

        r2 = run_backtest_zone_signal(m15, m1_raw, signal_mode="circle", zone_pct=zone_pct)
        print(f"{('CIRCLE + Zone ' + f'{pct:.2f}%'):<28} {r2['trades']:>5} {r2['wr']:>6.1f} {r2['pnl']:>+9.2f} {r2['max_dd']:>+8.2f} {r2['expectancy']:>+7.3f} {r2['rr']:>5.2f}")

        if best_arrow is None or r1["pnl"] > best_arrow[1]["pnl"]:
            best_arrow = (pct, r1)

        if best_circle is None or r2["pnl"] > best_circle[1]["pnl"]:
            best_circle = (pct, r2)

    print("\n" + "=" * 80)
    print(f"BEST ARROW  + ZONE: {best_arrow[0]:.2f}% | P/L {best_arrow[1]['pnl']:+.2f} | WR {best_arrow[1]['wr']:.1f}% | Trd {best_arrow[1]['trades']}")
    print(f"BEST CIRCLE + ZONE: {best_circle[0]:.2f}% | P/L {best_circle[1]['pnl']:+.2f} | WR {best_circle[1]['wr']:.1f}% | Trd {best_circle[1]['trades']}")
    print("=" * 80)

    mt5.shutdown()

if __name__ == "__main__":
    main()