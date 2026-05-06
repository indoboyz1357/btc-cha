"""
cek_zona.py - Auto-detect Resistance & Support Zones
=====================================================
Test: Apakah algoritma bisa "lihat" zona yang sama dengan mata Anda?

Cara pakai:
    python cek_zona.py

Tweaking parameter:
    - LOOKBACK_CANDLES : berapa candle history (default 200 = ~2 hari)
    - SWING_WINDOW     : sensitivity swing (3=sensitive, 7=strict)
    - CLUSTER_TOLERANCE: berapa % beda harga = 1 zona (default 0.15%)
    - MIN_TOUCHES      : minimum sentuhan untuk dianggap zona valid
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============================================
# CONFIGURATION (BISA DI-TWEAK)
# ============================================
SYMBOL = "BTCUSD"
TIMEFRAME = mt5.TIMEFRAME_M15
LOOKBACK_CANDLES = 200        # ~2 hari di M15
SWING_WINDOW = 5              # window untuk detect swing (3=sensitive, 7=strict)
CLUSTER_TOLERANCE = 0.15      # % tolerance untuk cluster (0.15% ~ 120pts di BTC 80K)
MIN_TOUCHES = 2               # minimum touches untuk dianggap zona valid
NEAR_THRESHOLD_PTS = 100      # < 100 pts = "very close"
WARN_THRESHOLD_PTS = 200      # < 200 pts = "warning"


# ============================================
# INITIALIZE MT5
# ============================================
if not mt5.initialize():
    print(f"❌ MT5 init failed: {mt5.last_error()}")
    quit()


# ============================================
# AMBIL DATA CANDLE
# ============================================
rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, LOOKBACK_CANDLES)
if rates is None or len(rates) < 50:
    print("❌ Gagal ambil data candle")
    mt5.shutdown()
    quit()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

current_price = df['close'].iloc[-1]

print("=" * 80)
print(f"🔍 ANALISIS ZONA RESISTANCE & SUPPORT - {SYMBOL}")
print(f"   Lookback: {LOOKBACK_CANDLES} candles M15 (~{LOOKBACK_CANDLES*15/60:.1f} jam)")
print(f"   Current price: {current_price:.2f}")
print(f"   Time now: {df['time'].iloc[-1]}")
print(f"   Swing window: {SWING_WINDOW} | Cluster tolerance: {CLUSTER_TOLERANCE}% | Min touches: {MIN_TOUCHES}")
print("=" * 80)


# ============================================
# METHOD 1: SWING HIGH/LOW DETECTION
# ============================================
def find_swing_points(df, window=5):
    """
    Cari swing high/low.
    Swing high = candle dengan high tertinggi dalam window kiri+kanan
    Swing low = sebaliknya
    """
    swing_highs = []
    swing_lows = []
    
    for i in range(window, len(df) - window):
        left = df.iloc[i-window:i]
        right = df.iloc[i+1:i+window+1]
        current = df.iloc[i]
        
        # Swing High
        if current['high'] > left['high'].max() and current['high'] > right['high'].max():
            swing_highs.append({
                'index': i,
                'time': current['time'],
                'price': current['high'],
            })
        
        # Swing Low
        if current['low'] < left['low'].min() and current['low'] < right['low'].min():
            swing_lows.append({
                'index': i,
                'time': current['time'],
                'price': current['low'],
            })
    
    return swing_highs, swing_lows


swing_highs, swing_lows = find_swing_points(df, window=SWING_WINDOW)

print(f"\n📍 SWING POINTS DITEMUKAN:")
print(f"   Swing Highs: {len(swing_highs)}")
print(f"   Swing Lows:  {len(swing_lows)}")


# ============================================
# METHOD 2: CLUSTER NEARBY SWING POINTS
# ============================================
def cluster_levels(swing_points, tolerance_pct=0.15, min_touches=2):
    """
    Group swing points yang HARGA-NYA mirip-mirip.
    """
    if not swing_points:
        return []
    
    sorted_points = sorted(swing_points, key=lambda x: x['price'])
    
    clusters = []
    current_cluster = [sorted_points[0]]
    
    for point in sorted_points[1:]:
        last_price = current_cluster[-1]['price']
        diff_pct = abs(point['price'] - last_price) / last_price * 100
        
        if diff_pct <= tolerance_pct:
            current_cluster.append(point)
        else:
            if len(current_cluster) >= min_touches:
                clusters.append(current_cluster)
            current_cluster = [point]
    
    # Last cluster
    if len(current_cluster) >= min_touches:
        clusters.append(current_cluster)
    
    # Convert to zone format
    zones = []
    for cluster in clusters:
        prices = [p['price'] for p in cluster]
        zones.append({
            'price_min': min(prices),
            'price_max': max(prices),
            'price_avg': sum(prices) / len(prices),
            'touches': len(cluster),
            'last_touch': max(p['time'] for p in cluster),
        })
    
    return zones


resistance_zones = cluster_levels(swing_highs, 
                                   tolerance_pct=CLUSTER_TOLERANCE, 
                                   min_touches=MIN_TOUCHES)
support_zones = cluster_levels(swing_lows, 
                                tolerance_pct=CLUSTER_TOLERANCE, 
                                min_touches=MIN_TOUCHES)


# ============================================
# DISPLAY ZONES
# ============================================
print(f"\n" + "=" * 80)
print(f"🔴 RESISTANCE ZONES (Swing Highs Cluster)")
print(f"=" * 80)

if not resistance_zones:
    print("   (Tidak ada zona resistance terdeteksi)")
else:
    resistance_zones_sorted = sorted(resistance_zones, key=lambda x: -x['price_avg'])
    
    print(f"\n   {'Zona':<8} {'Range':<25} {'Avg':<12} {'Touches':<10} {'Last Touch':<18} {'Distance'}")
    print(f"   {'-'*8} {'-'*25} {'-'*12} {'-'*10} {'-'*18} {'-'*25}")
    
    for i, zone in enumerate(resistance_zones_sorted, 1):
        distance = zone['price_avg'] - current_price
        if distance > 0:
            marker = f"⬆️ +{distance:.0f} pts above"
        else:
            marker = f"⬇️ {distance:.0f} pts below (BROKEN)"
        
        print(f"   R-{i:<6} {zone['price_min']:.2f} - {zone['price_max']:.2f}     "
              f"{zone['price_avg']:<12.2f} {zone['touches']}x         "
              f"{zone['last_touch'].strftime('%m-%d %H:%M'):<18} {marker}")


print(f"\n" + "=" * 80)
print(f"🟢 SUPPORT ZONES (Swing Lows Cluster)")
print(f"=" * 80)

if not support_zones:
    print("   (Tidak ada zona support terdeteksi)")
else:
    support_zones_sorted = sorted(support_zones, key=lambda x: -x['price_avg'])
    
    print(f"\n   {'Zona':<8} {'Range':<25} {'Avg':<12} {'Touches':<10} {'Last Touch':<18} {'Distance'}")
    print(f"   {'-'*8} {'-'*25} {'-'*12} {'-'*10} {'-'*18} {'-'*25}")
    
    for i, zone in enumerate(support_zones_sorted, 1):
        distance = current_price - zone['price_avg']
        if distance > 0:
            marker = f"⬇️ -{distance:.0f} pts below"
        else:
            marker = f"⬆️ {-distance:.0f} pts above (BROKEN)"
        
        print(f"   S-{i:<6} {zone['price_min']:.2f} - {zone['price_max']:.2f}     "
              f"{zone['price_avg']:<12.2f} {zone['touches']}x         "
              f"{zone['last_touch'].strftime('%m-%d %H:%M'):<18} {marker}")


# ============================================
# CURRENT POSITION ANALYSIS
# ============================================
print(f"\n" + "=" * 80)
print(f"📍 CURRENT PRICE POSITION: {current_price:.2f}")
print(f"=" * 80)

# Find nearest above (resistance)
nearest_resistance = None
for zone in sorted(resistance_zones, key=lambda x: x['price_avg']):
    if zone['price_avg'] > current_price:
        nearest_resistance = zone
        break

# Find nearest below (support)
nearest_support = None
for zone in sorted(support_zones, key=lambda x: -x['price_avg']):
    if zone['price_avg'] < current_price:
        nearest_support = zone
        break

print(f"\n🎯 ZONA TERDEKAT:")

if nearest_resistance:
    dist_r = nearest_resistance['price_avg'] - current_price
    pct_r = dist_r / current_price * 100
    print(f"\n   ⬆️ RESISTANCE TERDEKAT (di ATAS):")
    print(f"      Range:    {nearest_resistance['price_min']:.2f} - {nearest_resistance['price_max']:.2f}")
    print(f"      Avg:      {nearest_resistance['price_avg']:.2f}")
    print(f"      Distance: +{dist_r:.0f} points ({pct_r:+.2f}%)")
    print(f"      Touches:  {nearest_resistance['touches']}x")
    
    if dist_r < NEAR_THRESHOLD_PTS:
        print(f"      🚨 SANGAT DEKAT RESISTANCE — BAHAYA BUY!")
    elif dist_r < WARN_THRESHOLD_PTS:
        print(f"      ⚠️  Cukup dekat resistance — hati-hati BUY")
    else:
        print(f"      ✅ Masih ada room ke resistance")
else:
    print(f"\n   ⬆️ RESISTANCE: (Tidak ada di atas current price)")

if nearest_support:
    dist_s = current_price - nearest_support['price_avg']
    pct_s = dist_s / current_price * 100
    print(f"\n   ⬇️ SUPPORT TERDEKAT (di BAWAH):")
    print(f"      Range:    {nearest_support['price_min']:.2f} - {nearest_support['price_max']:.2f}")
    print(f"      Avg:      {nearest_support['price_avg']:.2f}")
    print(f"      Distance: -{dist_s:.0f} points (-{pct_s:.2f}%)")
    print(f"      Touches:  {nearest_support['touches']}x")
    
    if dist_s < NEAR_THRESHOLD_PTS:
        print(f"      🚨 SANGAT DEKAT SUPPORT — BAHAYA SELL!")
    elif dist_s < WARN_THRESHOLD_PTS:
        print(f"      ⚠️  Cukup dekat support — hati-hati SELL")
    else:
        print(f"      ✅ Masih ada room ke support")
else:
    print(f"\n   ⬇️ SUPPORT: (Tidak ada di bawah current price)")


# ============================================
# TRADING VERDICT
# ============================================
print(f"\n" + "=" * 80)
print(f"💡 VERDICT TRADING (Berdasarkan ZONA):")
print(f"=" * 80)

# BUY recommendation
print(f"\n🟢 KALAU MAU BUY:")
if nearest_resistance:
    dist_r = nearest_resistance['price_avg'] - current_price
    if dist_r < NEAR_THRESHOLD_PTS:
        print(f"   ❌ JANGAN BUY! Resistance hanya {dist_r:.0f} pts di atas")
        print(f"   📍 Target maksimal: {nearest_resistance['price_avg']:.2f}")
        print(f"   ⚠️  Risk:Reward sangat jelek")
    elif dist_r < WARN_THRESHOLD_PTS:
        print(f"   ⚠️  Hati-hati. Resistance {dist_r:.0f} pts di atas")
        print(f"   📍 Target maksimal: {nearest_resistance['price_avg']:.2f}")
        print(f"   📊 Pertimbangkan SL ketat")
    else:
        print(f"   ✅ OK, ada room {dist_r:.0f} pts ke resistance")
        print(f"   📍 Target potensial: {nearest_resistance['price_avg']:.2f}")
else:
    print(f"   ✅ Free room ke atas (no resistance detected nearby)")

# SELL recommendation
print(f"\n🔴 KALAU MAU SELL:")
if nearest_support:
    dist_s = current_price - nearest_support['price_avg']
    if dist_s < NEAR_THRESHOLD_PTS:
        print(f"   ❌ JANGAN SELL! Support hanya {dist_s:.0f} pts di bawah")
        print(f"   📍 Target maksimal: {nearest_support['price_avg']:.2f}")
        print(f"   ⚠️  Risk:Reward sangat jelek")
    elif dist_s < WARN_THRESHOLD_PTS:
        print(f"   ⚠️  Hati-hati. Support {dist_s:.0f} pts di bawah")
        print(f"   📍 Target maksimal: {nearest_support['price_avg']:.2f}")
        print(f"   📊 Pertimbangkan SL ketat")
    else:
        print(f"   ✅ OK, ada room {dist_s:.0f} pts ke support")
        print(f"   📍 Target potensial: {nearest_support['price_avg']:.2f}")
else:
    print(f"   ✅ Free room ke bawah (no support detected nearby)")


# ============================================
# ALL ZONES SUMMARY (TABLE)
# ============================================
print(f"\n" + "=" * 80)
print(f"📊 SEMUA ZONA (URUTAN HARGA TERTINGGI → TERENDAH):")
print(f"=" * 80)

all_zones = []
for zone in resistance_zones:
    all_zones.append({**zone, 'type': 'R'})
for zone in support_zones:
    all_zones.append({**zone, 'type': 'S'})

all_zones_sorted = sorted(all_zones, key=lambda x: -x['price_avg'])

if not all_zones_sorted:
    print("   (Tidak ada zona terdeteksi)")
else:
    print(f"\n   {'Type':<8} {'Range':<25} {'Avg':<12} {'Touches':<10} {'Distance':<20} {'Note'}")
    print(f"   {'-'*8} {'-'*25} {'-'*12} {'-'*10} {'-'*20} {'-'*15}")
    
    for zone in all_zones_sorted:
        type_label = "🔴 RES" if zone['type'] == 'R' else "🟢 SUP"
        distance = zone['price_avg'] - current_price
        
        if distance > 0:
            dist_str = f"⬆️ +{distance:.0f} pts above"
        elif distance < 0:
            dist_str = f"⬇️ {distance:.0f} pts below"
        else:
            dist_str = "🎯 AT current"
        
        marker = ""
        if abs(distance) < NEAR_THRESHOLD_PTS:
            marker = "⚠️ VERY CLOSE"
        elif abs(distance) < WARN_THRESHOLD_PTS:
            marker = "⚡ close"
        
        print(f"   {type_label:<8} {zone['price_min']:.2f} - {zone['price_max']:.2f}     "
              f"{zone['price_avg']:<12.2f} {zone['touches']}x         "
              f"{dist_str:<20} {marker}")


# ============================================
# VISUAL ASCII MAP
# ============================================
print(f"\n" + "=" * 80)
print(f"🗺️  VISUAL MAP (Price Levels relative to CURRENT):")
print(f"=" * 80)

if all_zones_sorted:
    # Build full list dengan current price
    levels_to_show = sorted(
        all_zones_sorted + [{'price_avg': current_price, 'type': 'CURRENT', 'touches': 0,
                             'price_min': current_price, 'price_max': current_price}],
        key=lambda x: -x['price_avg']
    )
    
    print()
    for level in levels_to_show:
        price = level['price_avg']
        
        if level.get('type') == 'CURRENT':
            print(f"   ▶▶▶  {price:>10.2f}  ◄══════ 🎯 CURRENT PRICE ══════◄")
        elif level.get('type') == 'R':
            distance = price - current_price
            sign = '+' if distance > 0 else ''
            broken = " ❌ BROKEN" if distance < 0 else ""
            print(f"        {price:>10.2f}  ─── 🔴 RESISTANCE ({level['touches']}x) "
                  f"[{sign}{distance:.0f}pts]{broken}")
        elif level.get('type') == 'S':
            distance = price - current_price
            sign = '+' if distance > 0 else ''
            broken = " ❌ BROKEN" if distance > 0 else ""
            print(f"        {price:>10.2f}  ─── 🟢 SUPPORT ({level['touches']}x) "
                  f"[{sign}{distance:.0f}pts]{broken}")


# ============================================
# SUMMARY STATISTICS
# ============================================
print(f"\n" + "=" * 80)
print(f"📈 SUMMARY:")
print(f"=" * 80)

print(f"\n   Total Resistance Zones: {len(resistance_zones)}")
print(f"   Total Support Zones:    {len(support_zones)}")

# Active vs Broken
active_resistance = [z for z in resistance_zones if z['price_avg'] > current_price]
broken_resistance = [z for z in resistance_zones if z['price_avg'] <= current_price]
active_support = [z for z in support_zones if z['price_avg'] < current_price]
broken_support = [z for z in support_zones if z['price_avg'] >= current_price]

print(f"\n   Active Resistance (above price): {len(active_resistance)}")
print(f"   Broken Resistance (below price): {len(broken_resistance)}")
print(f"   Active Support (below price):    {len(active_support)}")
print(f"   Broken Support (above price):    {len(broken_support)}")


# ============================================
# CLEANUP
# ============================================
print(f"\n" + "=" * 80)
print(f"✅ Analysis complete!")
print(f"=" * 80)
print(f"\n💡 TIP: Bandingkan output di atas dengan chart MT5 Anda.")
print(f"   - Apakah zona terdeteksi sama dengan yang Anda lihat?")
print(f"   - Ada zona penting yang ke-miss?")
print(f"   - Ada zona false positive?")
print(f"\n   Adjust parameter di top file kalau perlu:")
print(f"   - SWING_WINDOW (lebih kecil = lebih banyak swing)")
print(f"   - CLUSTER_TOLERANCE (lebih besar = zona lebih lebar)")
print(f"   - MIN_TOUCHES (lebih besar = zona lebih ketat)")
print()

mt5.shutdown()