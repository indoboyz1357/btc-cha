"""
sideways_filter.py - Detect Sideways/Chop Market
Block entry saat market choppy (BUY-SELL bergantian)
"""
import MetaTrader5 as mt5
import pandas as pd

# CONFIG
LOOKBACK_CANDLES = 15
MIN_BODY_TO_RANGE_RATIO = 0.15  # body < 15% range = small candle
MAX_CHOP_RATIO = 0.4             # if buy:sell ratio > 0.4, considered chop


def calculate_ha(df):
    """Hitung Heikin Ashi candles"""
    ha = pd.DataFrame(index=df.index)
    ha['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha['ha_open'] = 0.0
    ha.loc[ha.index[0], 'ha_open'] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
    
    for i in range(1, len(ha)):
        ha.loc[ha.index[i], 'ha_open'] = (ha['ha_open'].iloc[i-1] + ha['ha_close'].iloc[i-1]) / 2
    
    ha['ha_high'] = pd.concat([df['high'], ha['ha_open'], ha['ha_close']], axis=1).max(axis=1)
    ha['ha_low'] = pd.concat([df['low'], ha['ha_open'], ha['ha_close']], axis=1).min(axis=1)
    
    return ha


def detect_arrows(ha_df, df):
    """Detect arrow buy/sell pada HA candles"""
    arrows = {'buy': [], 'sell': []}
    
    for i in range(1, len(ha_df)):
        ha_close_prev = ha_df['ha_close'].iloc[i-1]
        ha_open_prev = ha_df['ha_open'].iloc[i-1]
        ha_close_now = ha_df['ha_close'].iloc[i]
        ha_open_now = ha_df['ha_open'].iloc[i]
        
        # Reversal patterns
        if ha_close_prev < ha_open_prev and ha_close_now > ha_open_now:
            arrows['buy'].append(i)
        elif ha_close_prev > ha_open_prev and ha_close_now < ha_open_now:
            arrows['sell'].append(i)
    
    return arrows


def check_sideways_filter(symbol, timeframe=mt5.TIMEFRAME_M15):
    """
    Main sideways detection
    
    Returns:
        dict {
            'pass': bool (True = bukan sideways, OK trade),
            'reason': str,
            'is_sideways': bool,
            'method': str
        }
    """
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, LOOKBACK_CANDLES + 5)
        if rates is None or len(rates) < LOOKBACK_CANDLES:
            return {
                'pass': True, 'reason': 'no_data_skip_filter',
                'is_sideways': False, 'method': 'na'
            }
        
        df = pd.DataFrame(rates).tail(LOOKBACK_CANDLES).reset_index(drop=True)
        
        # METHOD 1: Crystal HA arrow pattern
        ha = calculate_ha(df)
        arrows = detect_arrows(ha, df)
        
        buy_count = len(arrows['buy'])
        sell_count = len(arrows['sell'])
        total_arrows = buy_count + sell_count
        
        crystal_chop = False
        if total_arrows >= 4:
            ratio = min(buy_count, sell_count) / max(buy_count, sell_count) if max(buy_count, sell_count) > 0 else 0
            if ratio > 0.5:
                crystal_chop = True
        
        # METHOD 2: Candle body vs range
        total_range = df['high'].max() - df['low'].min()
        avg_body = (df['close'] - df['open']).abs().mean()
        body_ratio = avg_body / total_range if total_range > 0 else 0
        
        candle_chop = body_ratio < MIN_BODY_TO_RANGE_RATIO
        
        # COMBINE: Sideways jika MINIMAL 1 method detect
        if crystal_chop and candle_chop:
            return {
                'pass': False,
                'reason': f'sideways_strong(crystal={buy_count}buy/{sell_count}sell,body={body_ratio:.2f})',
                'is_sideways': True,
                'method': 'both'
            }
        elif crystal_chop:
            return {
                'pass': False,
                'reason': f'sideways_crystal({buy_count}buy/{sell_count}sell)',
                'is_sideways': True,
                'method': 'crystal'
            }
        elif candle_chop:
            return {
                'pass': False,
                'reason': f'sideways_candles(body_ratio={body_ratio:.2f})',
                'is_sideways': True,
                'method': 'candles'
            }
        
        return {
            'pass': True,
            'reason': f'trending({buy_count}b/{sell_count}s,body={body_ratio:.2f})',
            'is_sideways': False,
            'method': 'none'
        }
        
    except Exception as e:
        print(f"[SIDEWAYS FILTER ERROR] {e}")
        return {
            'pass': True, 'reason': f'error_skip:{str(e)[:50]}',
            'is_sideways': False, 'method': 'error'
        }
