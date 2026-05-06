"""
cek_dan_analisis.py - Quick analysis untuk lihat pattern trade Anda
Magic ID: 20260505
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

SYMBOL = "BTCUSD"
MAGIC = 20260505
DAYS_BACK = 30

# Initialize
if not mt5.initialize():
    print(f"❌ MT5 init failed: {mt5.last_error()}")
    quit()

print("=" * 75)
print(f"🔍 ANALISIS TRADE BOT - Magic ID: {MAGIC}")
print("=" * 75)

# ============================================
# 1. AMBIL SEMUA DEALS
# ============================================
from_date = datetime.now() - timedelta(days=DAYS_BACK)
deals = mt5.history_deals_get(from_date, datetime.now())

if not deals:
    print("❌ Tidak ada history")
    quit()

df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df[(df['symbol'] == SYMBOL) & (df['magic'] == MAGIC)]

print(f"\n✅ Total deals dari bot: {len(df)}")

# ============================================
# 2. PAIR ENTRY-EXIT MENJADI TRADE LENGKAP
# ============================================
trades = []
entries = df[df['entry'] == 0].copy()
exits = df[df['entry'] == 1].copy()

for _, entry in entries.iterrows():
    matches = exits[exits['position_id'] == entry['position_id']]
    if len(matches) == 0:
        continue
    exit_deal = matches.iloc[0]
    
    direction = 'BUY' if entry['type'] == 0 else 'SELL'
    pnl = exit_deal['profit']
    
    trades.append({
        'entry_time': entry['time'],
        'exit_time': exit_deal['time'],
        'direction': direction,
        'entry_price': entry['price'],
        'exit_price': exit_deal['price'],
        'pnl': pnl,
        'duration_min': (exit_deal['time'] - entry['time']).total_seconds() / 60,
        'price_diff': abs(exit_deal['price'] - entry['price']),
    })

trades_df = pd.DataFrame(trades)

if len(trades_df) == 0:
    print("❌ Tidak bisa pair entry-exit")
    quit()

print(f"✅ Trade lengkap (paired): {len(trades_df)}")

# ============================================
# 3. STATISTIK KESELURUHAN
# ============================================
print("\n" + "=" * 75)
print("📊 STATISTIK KESELURUHAN")
print("=" * 75)

total = len(trades_df)
wins = trades_df[trades_df['pnl'] > 0]
losses = trades_df[trades_df['pnl'] <= 0]
total_pnl = trades_df['pnl'].sum()

print(f"  Total trades:     {total}")
print(f"  Win trades:       {len(wins)} ({len(wins)/total*100:.1f}%)")
print(f"  Loss trades:      {len(losses)} ({len(losses)/total*100:.1f}%)")
print(f"  Total P/L:        ${total_pnl:+.2f}")

if len(wins) > 0:
    print(f"  Avg WIN:          ${wins['pnl'].mean():+.2f}")
    print(f"  Max WIN:          ${wins['pnl'].max():+.2f}")
    
if len(losses) > 0:
    print(f"  Avg LOSS:         ${losses['pnl'].mean():+.2f}")
    print(f"  Max LOSS:         ${losses['pnl'].min():+.2f}")

# Risk:Reward
if len(wins) > 0 and len(losses) > 0:
    avg_win = wins['pnl'].mean()
    avg_loss = abs(losses['pnl'].mean())
    rr_ratio = avg_win / avg_loss
    print(f"\n  📐 Risk:Reward:   1:{rr_ratio:.2f}")
    if rr_ratio < 1:
        print(f"     ⚠️  WARNING: Avg WIN < Avg LOSS — sangat sulit profit!")
    elif rr_ratio < 1.5:
        print(f"     ⚠️  R:R sub-optimal, butuh win rate >50% untuk profit")

# Expectancy
if total > 0:
    win_rate = len(wins) / total
    avg_win_amt = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss_amt = abs(losses['pnl'].mean()) if len(losses) > 0 else 0
    expectancy = (win_rate * avg_win_amt) - ((1 - win_rate) * avg_loss_amt)
    print(f"\n  💰 Expectancy/trade: ${expectancy:+.3f}")
    if expectancy < 0:
        print(f"     ❌ NEGATIVE — bot ini secara matematis akan MERUGI long-term")
    else:
        print(f"     ✅ POSITIVE — bot profitable secara expectancy")

# ============================================
# 4. BREAKDOWN BUY vs SELL
# ============================================
print("\n" + "=" * 75)
print("📈 BREAKDOWN PER ARAH")
print("=" * 75)

for dir_name in ['BUY', 'SELL']:
    sub = trades_df[trades_df['direction'] == dir_name]
    if len(sub) == 0:
        continue
    
    sub_wins = sub[sub['pnl'] > 0]
    sub_losses = sub[sub['pnl'] <= 0]
    
    print(f"\n  {dir_name}:")
    print(f"    Trades:    {len(sub)}")
    print(f"    Win rate:  {len(sub_wins)/len(sub)*100:.1f}%")
    print(f"    Total P/L: ${sub['pnl'].sum():+.2f}")
    if len(sub_wins) > 0:
        print(f"    Avg win:   ${sub_wins['pnl'].mean():+.2f}")
    if len(sub_losses) > 0:
        print(f"    Avg loss:  ${sub_losses['pnl'].mean():+.2f}")

# ============================================
# 5. ANALISIS LOSING STREAK (BERUNTUN LOSS!)
# ============================================
print("\n" + "=" * 75)
print("🔴 ANALISIS BERUNTUN LOSS (LOSING STREAK)")
print("=" * 75)

trades_sorted = trades_df.sort_values('entry_time').reset_index(drop=True)
trades_sorted['is_loss'] = trades_sorted['pnl'] <= 0

# Find streaks
current_streak = 0
max_streak = 0
streak_start = None
all_streaks = []

for idx, row in trades_sorted.iterrows():
    if row['is_loss']:
        if current_streak == 0:
            streak_start = row['entry_time']
        current_streak += 1
    else:
        if current_streak >= 2:
            all_streaks.append({
                'start': streak_start,
                'length': current_streak,
                'total_loss': trades_sorted.iloc[idx-current_streak:idx]['pnl'].sum()
            })
        max_streak = max(max_streak, current_streak)
        current_streak = 0

if current_streak >= 2:
    all_streaks.append({
        'start': streak_start,
        'length': current_streak,
        'total_loss': trades_sorted.iloc[-current_streak:]['pnl'].sum()
    })
    max_streak = max(max_streak, current_streak)

print(f"\n  Max losing streak: {max_streak} trades berturut-turut")
if all_streaks:
    print(f"  Total losing streaks (≥2): {len(all_streaks)}")
    print(f"\n  📋 Detail losing streaks:")
    for s in all_streaks:
        print(f"     {s['start']} | {s['length']} trades | Total loss: ${s['total_loss']:+.2f}")

# ============================================
# 6. ANALISIS DURASI TRADE
# ============================================
print("\n" + "=" * 75)
print("⏱️  ANALISIS DURASI TRADE")
print("=" * 75)

print(f"\n  Avg duration:  {trades_df['duration_min'].mean():.1f} menit")
print(f"  Min duration:  {trades_df['duration_min'].min():.1f} menit")
print(f"  Max duration:  {trades_df['duration_min'].max():.1f} menit")

# Duration vs result
fast_trades = trades_df[trades_df['duration_min'] < 30]
slow_trades = trades_df[trades_df['duration_min'] >= 30]

if len(fast_trades) > 0:
    fast_wr = len(fast_trades[fast_trades['pnl'] > 0]) / len(fast_trades) * 100
    print(f"\n  Fast trades (<30 min):  {len(fast_trades)} trades, win rate {fast_wr:.1f}%, "
          f"P/L ${fast_trades['pnl'].sum():+.2f}")

if len(slow_trades) > 0:
    slow_wr = len(slow_trades[slow_trades['pnl'] > 0]) / len(slow_trades) * 100
    print(f"  Slow trades (>30 min):  {len(slow_trades)} trades, win rate {slow_wr:.1f}%, "
          f"P/L ${slow_trades['pnl'].sum():+.2f}")

# ============================================
# 7. ANALISIS SL/TP DISTANCE
# ============================================
print("\n" + "=" * 75)
print("📏 ANALISIS PRICE MOVEMENT (Loss vs Win)")
print("=" * 75)

if len(losses) > 0:
    avg_loss_dist = losses.assign(diff=abs(losses['exit_price'] - losses['entry_price']))['diff'].mean()
    print(f"\n  LOSS:")
    print(f"    Avg price movement: {avg_loss_dist:.2f} points")
    print(f"    → Estimasi SL: ~{avg_loss_dist*100:.0f} points (0.01 lot = ~${avg_loss_dist:.2f})")

if len(wins) > 0:
    avg_win_dist = wins.assign(diff=abs(wins['exit_price'] - wins['entry_price']))['diff'].mean()
    print(f"\n  WIN:")
    print(f"    Avg price movement: {avg_win_dist:.2f} points")
    print(f"    → Capture: ~{avg_win_dist*100:.0f} points")
    
    if len(losses) > 0:
        ratio = avg_win_dist / avg_loss_dist
        print(f"\n  📊 WIN distance vs LOSS distance: 1:{ratio:.2f}")
        if ratio < 1:
            print(f"     ❌ WIN cuma capture {ratio*100:.0f}% dari LOSS distance")
            print(f"     → TS TERLALU MEPET! Profit dipotong terlalu cepat")

# ============================================
# 8. DETAIL SEMUA LOSS TRADES
# ============================================
print("\n" + "=" * 75)
print("🔴 DETAIL SEMUA LOSS TRADES")
print("=" * 75)

losses_sorted = losses.sort_values('entry_time')
print(f"\n  {'Entry Time':<20} {'Dir':<5} {'Entry':<10} {'Exit':<10} {'Diff':<8} {'P/L':<10} {'Duration':<10}")
print(f"  {'-'*20} {'-'*5} {'-'*10} {'-'*10} {'-'*8} {'-'*10} {'-'*10}")
for _, t in losses_sorted.iterrows():
    et = t['entry_time'].strftime('%m-%d %H:%M')
    print(f"  {et:<20} {t['direction']:<5} "
          f"{t['entry_price']:<10.2f} {t['exit_price']:<10.2f} "
          f"{t['price_diff']:<8.2f} ${t['pnl']:<+8.2f} "
          f"{t['duration_min']:<6.1f} min")

# ============================================
# 9. SAVE TO CSV
# ============================================
trades_df.to_csv('trade_history_analysis.csv', index=False)
print(f"\n💾 Saved to: trade_history_analysis.csv")

# ============================================
# 10. KESIMPULAN & REKOMENDASI
# ============================================
print("\n" + "=" * 75)
print("💡 KESIMPULAN & REKOMENDASI AWAL")
print("=" * 75)

issues = []
if len(losses) > len(wins):
    issues.append(f"❌ Win rate rendah ({len(wins)/total*100:.0f}%)")

if len(wins) > 0 and len(losses) > 0:
    if abs(losses['pnl'].mean()) > wins['pnl'].mean():
        issues.append(f"❌ Avg LOSS > Avg WIN (R:R buruk)")

if max_streak >= 3:
    issues.append(f"❌ Pernah {max_streak}x loss berturut-turut")

if len(losses) > 0 and len(wins) > 0:
    avg_loss_dist = losses.assign(d=abs(losses['exit_price'] - losses['entry_price']))['d'].mean()
    avg_win_dist = wins.assign(d=abs(wins['exit_price'] - wins['entry_price']))['d'].mean()
    if avg_win_dist < avg_loss_dist * 0.7:
        issues.append(f"❌ TS TERLALU MEPET — win distance hanya {avg_win_dist/avg_loss_dist*100:.0f}% dari loss distance")

print()
if issues:
    print("  🚨 MASALAH TERDETEKSI:")
    for i in issues:
        print(f"     {i}")
    
    print("\n  🎯 SARAN AKSI:")
    print("     1. Lonjakkan trailing stop (kasih napas profit)")
    print("     2. Tambah filter EMA+RSI untuk kurangi entry buruk")
    print("     3. Analisis time-of-day untuk hindari sesi loss")
    print("     4. Pertimbangkan break setelah 2x loss berturut")
else:
    print("  ✅ Tidak ada masalah kritis terdeteksi")

print("\n" + "=" * 75)

mt5.shutdown()