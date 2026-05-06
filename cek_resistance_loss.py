"""
cek_resistance_loss.py
Cek apakah trade LOSS itu BENAR-BENAR terjadi di resistance/support level
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

SYMBOL = "BTCUSD"
MAGIC = 20260505

if not mt5.initialize():
    quit()

# Load trades
deals = mt5.history_deals_get(datetime.now() - timedelta(days=30), datetime.now())
df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df[(df['symbol'] == SYMBOL) & (df['magic'] == MAGIC)]

entries = df[df['entry'] == 0].copy()
exits = df[df['entry'] == 1].copy()

print("=" * 95)
print("🎯 ANALISIS: APAKAH BOT BUY DI TOP & SELL DI BOTTOM?")
print("=" * 95)

for _, entry in entries.iterrows():
    matches = exits[exits['position_id'] == entry['position_id']]
    if len(matches) == 0:
        continue
    exit_deal = matches.iloc[0]
    
    direction = 'BUY' if entry['type'] == 0 else 'SELL'
    entry_time = entry['time']
    entry_price = entry['price']
    pnl = exit_deal['profit']
    
    # Ambil 96 candle M15 sebelum entry (= 24 jam)
    rates = mt5.copy_rates_from(SYMBOL, mt5.TIMEFRAME_M15, entry_time, 96)
    if rates is None or len(rates) < 50:
        continue
    
    df_m15 = pd.DataFrame(rates)
    
    # Hitung high/low 24 jam
    high_24h = df_m15['high'].max()
    low_24h = df_m15['low'].min()
    range_24h = high_24h - low_24h
    
    # Posisi harga entry dalam range
    if range_24h > 0:
        position_pct = ((entry_price - low_24h) / range_24h) * 100
    else:
        position_pct = 50
    
    # Cari swing high & low (last 50 candles)
    last_50 = df_m15.tail(50)
    swing_high = last_50['high'].max()
    swing_low = last_50['low'].min()
    
    # Distance to nearest swing
    dist_to_high = ((swing_high - entry_price) / entry_price) * 100
    dist_to_low = ((entry_price - swing_low) / entry_price) * 100
    
    # Fibonacci levels (dari swing range)
    fib_range = swing_high - swing_low
    fib_618 = swing_low + (fib_range * 0.618)
    fib_786 = swing_low + (fib_range * 0.786)
    fib_236 = swing_low + (fib_range * 0.236)
    fib_382 = swing_low + (fib_range * 0.382)
    
    # RSI
    delta = df_m15['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = (100 - (100 / (1 + gain/loss))).iloc[-1]
    
    # === PRINT ANALYSIS ===
    print(f"\n{'='*95}")
    print(f"📍 {entry_time} | {direction} @ {entry_price:.2f} | P/L: ${pnl:+.2f}")
    print(f"{'='*95}")
    
    print(f"\n  📊 24-HOUR RANGE:")
    print(f"     High 24h:    {high_24h:.2f}")
    print(f"     Low 24h:     {low_24h:.2f}")
    print(f"     Range:       {range_24h:.2f} points")
    print(f"     Entry @:     {entry_price:.2f}")
    print(f"     Position:    {position_pct:.1f}% dari bottom range")
    
    # Visual indicator
    bar_len = 50
    pos_in_bar = int((position_pct / 100) * bar_len)
    bar = "─" * pos_in_bar + "🎯" + "─" * (bar_len - pos_in_bar)
    print(f"\n     Low [{bar}] High")
    
    print(f"\n  📐 FIBONACCI LEVELS (last 50 M15 candles):")
    print(f"     Swing High (1.000): {swing_high:.2f}")
    print(f"     Fib 0.786:          {fib_786:.2f}  {'⬅️ ENTRY DEKAT SINI' if abs(entry_price - fib_786) < 100 else ''}")
    print(f"     Fib 0.618:          {fib_618:.2f}  {'⬅️ ENTRY DEKAT SINI' if abs(entry_price - fib_618) < 100 else ''}")
    print(f"     Fib 0.382:          {fib_382:.2f}  {'⬅️ ENTRY DEKAT SINI' if abs(entry_price - fib_382) < 100 else ''}")
    print(f"     Fib 0.236:          {fib_236:.2f}  {'⬅️ ENTRY DEKAT SINI' if abs(entry_price - fib_236) < 100 else ''}")
    print(f"     Swing Low (0.000):  {swing_low:.2f}")
    
    print(f"\n  📏 DISTANCE TO KEY LEVELS:")
    print(f"     Distance to Swing High: {dist_to_high:.2f}% ({swing_high - entry_price:+.2f} points)")
    print(f"     Distance to Swing Low:  {dist_to_low:.2f}% ({entry_price - swing_low:+.2f} points)")
    
    print(f"\n  📊 RSI: {rsi:.1f}")
    
    # === VERDICT ===
    print(f"\n  🎯 VERDICT:")
    
    issues = []
    
    if direction == 'BUY':
        if position_pct > 75:
            issues.append(f"❌ BUY di {position_pct:.0f}% atas range (TERLALU TINGGI)")
        if entry_price > fib_618:
            issues.append(f"❌ BUY di atas Fib 0.618 (zona resistance)")
        if dist_to_high < 1.0:
            issues.append(f"❌ BUY hanya {dist_to_high:.2f}% dari swing high (TIDAK ADA ROOM)")
        if rsi > 65:
            issues.append(f"❌ RSI {rsi:.0f} = OVERBOUGHT")
    
    else:  # SELL
        if position_pct < 25:
            issues.append(f"❌ SELL di {position_pct:.0f}% bawah range (TERLALU RENDAH)")
        if entry_price < fib_382:
            issues.append(f"❌ SELL di bawah Fib 0.382 (zona support)")
        if dist_to_low < 1.0:
            issues.append(f"❌ SELL hanya {dist_to_low:.2f}% dari swing low (TIDAK ADA ROOM)")
        if rsi < 35:
            issues.append(f"❌ RSI {rsi:.0f} = OVERSOLD")
    
    if issues:
        print(f"     🚨 BAD ENTRY DETECTED:")
        for issue in issues:
            print(f"        {issue}")
        print(f"\n     💡 KESIMPULAN: Trade ini SEHARUSNYA DI-BLOCK oleh filter context!")
    else:
        print(f"     ✅ Entry context OK — loss mungkin karena alasan lain (TS, market shock, etc)")

print("\n" + "=" * 95)

mt5.shutdown()