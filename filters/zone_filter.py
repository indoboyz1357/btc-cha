"""
zone_filter.py - Detect Resistance & Support Zones
Block BUY kalau dekat resistance, block SELL kalau dekat support
"""
import MetaTrader5 as mt5
import pandas as pd

LOOKBACK_CANDLES = 200
SWING_WINDOW = 5
CLUSTER_TOLERANCE_PCT = 0.15
MIN_TOUCHES = 2
WARN_THRESHOLD_PCT = 0.003   # 0.3% dari harga = ~$250 kalau BTC $83k


def find_swing_points(df, window=SWING_WINDOW):
    swing_highs = []
    swing_lows = []
    for i in range(window, len(df) - window):
        left = df.iloc[i-window:i]
        right = df.iloc[i+1:i+window+1]
        current = df.iloc[i]
        if current['high'] > left['high'].max() and current['high'] > right['high'].max():
            swing_highs.append({'index': i, 'time': current['time'], 'price': current['high']})
        if current['low'] < left['low'].min() and current['low'] < right['low'].min():
            swing_lows.append({'index': i, 'time': current['time'], 'price': current['low']})
    return swing_highs, swing_lows


def cluster_levels(swing_points, tolerance_pct=CLUSTER_TOLERANCE_PCT, min_touches=MIN_TOUCHES):
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
    if len(current_cluster) >= min_touches:
        clusters.append(current_cluster)
    zones = []
    for cluster in clusters:
        prices = [p['price'] for p in cluster]
        zones.append({
            'price_min': min(prices),
            'price_max': max(prices),
            'price_avg': sum(prices) / len(prices),
            'touches': len(cluster),
        })
    return zones


def check_zone_filter(symbol, direction, current_price=None):
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, LOOKBACK_CANDLES)
        if rates is None or len(rates) < 50:
            return {
                'pass': True, 'reason': 'no_data_skip_filter',
                'nearest_resistance': None, 'nearest_support': None,
                'distance_to_resistance': None, 'distance_to_support': None,
            }

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        if current_price is None:
            current_price = df['close'].iloc[-1]

        # Threshold = 0.3% dari harga sekarang
        # Contoh: BTC $83,000 → threshold = $249
        warn_threshold = current_price * WARN_THRESHOLD_PCT

        swing_highs, swing_lows = find_swing_points(df)
        resistance_zones = cluster_levels(swing_highs)
        support_zones = cluster_levels(swing_lows)

        # Resistance terdekat DI ATAS harga
        nearest_resistance = None
        for zone in sorted(resistance_zones, key=lambda x: x['price_avg']):
            if zone['price_avg'] > current_price:
                nearest_resistance = zone
                break

        # Support terdekat DI BAWAH harga
        nearest_support = None
        for zone in sorted(support_zones, key=lambda x: -x['price_avg']):
            if zone['price_avg'] < current_price:
                nearest_support = zone
                break

        dist_to_r = (nearest_resistance['price_avg'] - current_price) if nearest_resistance else 9999
        dist_to_s = (current_price - nearest_support['price_avg']) if nearest_support else 9999

        result = {
            'nearest_resistance': nearest_resistance['price_avg'] if nearest_resistance else None,
            'nearest_support': nearest_support['price_avg'] if nearest_support else None,
            'distance_to_resistance': round(dist_to_r, 2),
            'distance_to_support': round(dist_to_s, 2),
        }

        # BUY → block kalau terlalu dekat RESISTANCE
        # SELL → block kalau terlalu dekat SUPPORT
        if direction.lower() == 'buy':
            if dist_to_r < warn_threshold:
                result['pass'] = False
                result['reason'] = f"buy_blocked_near_resistance(dist=${dist_to_r:.2f} threshold=${warn_threshold:.2f})"
            else:
                result['pass'] = True
                result['reason'] = f"buy_ok_room_to_resistance=${dist_to_r:.2f}"

        elif direction.lower() == 'sell':
            if dist_to_s < warn_threshold:
                result['pass'] = False
                result['reason'] = f"sell_blocked_near_support(dist=${dist_to_s:.2f} threshold=${warn_threshold:.2f})"
            else:
                result['pass'] = True
                result['reason'] = f"sell_ok_room_to_support=${dist_to_s:.2f}"

        else:
            result['pass'] = True
            result['reason'] = 'unknown_direction'

        return result

    except Exception as e:
        print(f"[ZONE FILTER ERROR] {e}")
        return {
            'pass': True, 'reason': f'error_skip:{str(e)[:50]}',
            'nearest_resistance': None, 'nearest_support': None,
            'distance_to_resistance': None, 'distance_to_support': None,
        }
