"""
timing_filter.py - Multi-TF Timing Filter (M5 + M1 alignment)
Wait sampai M5 + M1 candle color align dengan M15 signal direction
"""
import MetaTrader5 as mt5
import pandas as pd
import asyncio
from datetime import datetime

# CONFIG
M15_CANDLE_MINUTES = 15
SLOW_REFRESH_SEC = 15   # saat M5 belum align (dipercepat dari 30s)
FAST_REFRESH_SEC = 5    # saat M5 align tinggal M1
M1_CONFIRM_CANDLES = 0  # FIX: 0 = langsung entry begitu M5+M1 align, tidak nunggu lagi
MAX_WAIT_SECONDS = 900   # 15 menit max wait


def get_candle_color(symbol, timeframe):
    """
    Detect Crystal HA candle color untuk timeframe tertentu
    
    Returns: 'green', 'blue', 'orange', 'red', or 'unknown'
    
    Color logic (matching bot):
    - GREEN  = bullish_strong (BUY signal candle, reversal up)
    - BLUE   = bullish_weak (continuation up)
    - ORANGE = bearish_strong (SELL signal candle, reversal down)
    - RED    = bearish_weak (continuation down)
    """
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 50)
        if rates is None or len(rates) < 10:
            return 'unknown'
        
        df = pd.DataFrame(rates)
        
        # Calculate HA
        ha = pd.DataFrame(index=df.index)
        ha['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha['ha_open'] = 0.0
        ha.loc[ha.index[0], 'ha_open'] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
        
        for i in range(1, len(ha)):
            ha.loc[ha.index[i], 'ha_open'] = (ha['ha_open'].iloc[i-1] + ha['ha_close'].iloc[i-1]) / 2
        
        # Cek candle current (live)
        current_close = ha['ha_close'].iloc[-1]
        current_open = ha['ha_open'].iloc[-1]
        prev_close = ha['ha_close'].iloc[-2]
        prev_open = ha['ha_open'].iloc[-2]
        
        prev_was_bullish = prev_close > prev_open
        prev_was_bearish = prev_close < prev_open
        current_is_bullish = current_close > current_open
        current_is_bearish = current_close < current_open
        
        if current_is_bullish:
            if prev_was_bearish:
                return 'green'
            else:
                return 'blue'
        elif current_is_bearish:
            if prev_was_bullish:
                return 'orange'
            else:
                return 'red'
        else:
            return 'unknown'
            
    except Exception as e:
        print(f"[CANDLE COLOR ERROR {timeframe}] {e}")
        return 'unknown'


def is_color_aligned(direction, color):
    """Check if color align dengan direction"""
    bullish_colors = ['blue', 'green']
    bearish_colors = ['red', 'orange']
    
    if direction.lower() == 'buy':
        return color in bullish_colors
    elif direction.lower() == 'sell':
        return color in bearish_colors
    return False


def _get_current_m15_candle_start():
    """Get start time of current M15 candle"""
    now = datetime.now()
    minute_block = (now.minute // M15_CANDLE_MINUTES) * M15_CANDLE_MINUTES
    return now.replace(minute=minute_block, second=0, microsecond=0)


async def check_timing_filter_async(symbol, direction, signal_type="circle",
                                     max_wait_seconds=MAX_WAIT_SECONDS,
                                     wait_mode=True, callback=None):
    """
    ASYNC MAIN timing filter.

    ARROW  → langsung PASS, tidak perlu timing check.
             Arrow di M15 sudah konfirmasi kuat, nunggu M5+M1 justru terlambat.

    CIRCLE → cek M5 warna BERLAWANAN dengan direction (belum balik).
             Artinya momentum reversal baru mulai, belum terlambat masuk.
             Contoh: CIRCLE BUY → M5 masih orange/red (bearish) = harga baru
             mulai balik, entry di awal. Kalau M5 sudah hijau = sudah terlambat.
    """
    # ARROW: skip timing, langsung pass
    if signal_type == "arrow":
        return {
            'pass': True,
            'reason': 'arrow_skip_timing',
            'm5_color': '', 'm1_color': '',
            'wait_seconds': 0, 'expired': False
        }

    # CIRCLE: tunggu M5 masih berlawanan (konfirmasi baru mulai reversal)
    try:
        start_time = datetime.now()
        initial_m15_candle = _get_current_m15_candle_start()
        wait_count = 0

        while True:
            elapsed = (datetime.now() - start_time).total_seconds()

            # M15 candle expired
            current_m15 = _get_current_m15_candle_start()
            if current_m15 != initial_m15_candle:
                return {
                    'pass': False, 'reason': 'm15_candle_expired',
                    'm5_color': '', 'm1_color': '',
                    'wait_seconds': int(elapsed), 'expired': True
                }

            # Timeout
            if elapsed > max_wait_seconds:
                return {
                    'pass': False, 'reason': f'timeout_{int(elapsed)}s',
                    'm5_color': get_candle_color(symbol, mt5.TIMEFRAME_M5),
                    'm1_color': get_candle_color(symbol, mt5.TIMEFRAME_M1),
                    'wait_seconds': int(elapsed), 'expired': True
                }

            m5_color = get_candle_color(symbol, mt5.TIMEFRAME_M5)
            m1_color = get_candle_color(symbol, mt5.TIMEFRAME_M1)

            # Untuk CIRCLE BUY: M5 masih bearish (orange/red) = reversal baru mulai
            # Untuk CIRCLE SELL: M5 masih bullish (blue/green) = reversal baru mulai
            bearish_colors = {'red', 'orange'}
            bullish_colors = {'blue', 'green'}

            if direction == 'buy':
                # M5 masih bearish = entry di awal reversal, bagus
                m5_early = m5_color in bearish_colors
            else:
                # M5 masih bullish = entry di awal reversal, bagus
                m5_early = m5_color in bullish_colors

            if callback:
                try:
                    cb_data = {
                        'm5_color': m5_color, 'm1_color': m1_color,
                        'm5_ok': m5_early,
                        'wait_seconds': int(elapsed), 'wait_count': wait_count
                    }
                    if asyncio.iscoroutinefunction(callback):
                        await callback(cb_data)
                    else:
                        callback(cb_data)
                except:
                    pass

            if not wait_mode:
                if m5_early:
                    return {
                        'pass': True,
                        'reason': f'circle_early_entry_m5={m5_color}',
                        'm5_color': m5_color, 'm1_color': m1_color,
                        'wait_seconds': 0, 'expired': False
                    }
                else:
                    return {
                        'pass': False,
                        'reason': f'circle_too_late_m5={m5_color}',
                        'm5_color': m5_color, 'm1_color': m1_color,
                        'wait_seconds': 0, 'expired': False
                    }

            # WAIT MODE: tunggu kondisi early reversal terbentuk
            if m5_early:
                return {
                    'pass': True,
                    'reason': f'circle_early_entry_m5={m5_color}',
                    'm5_color': m5_color, 'm1_color': m1_color,
                    'wait_seconds': int(elapsed), 'expired': False
                }
            else:
                # M5 sudah searah = terlambat, tidak perlu nunggu lagi
                return {
                    'pass': False,
                    'reason': f'circle_too_late_m5={m5_color}_already_moved',
                    'm5_color': m5_color, 'm1_color': m1_color,
                    'wait_seconds': int(elapsed), 'expired': False
                }

    except Exception as e:
        import traceback
        print(f"[TIMING FILTER ERROR] {e}")
        traceback.print_exc()
        return {
            'pass': False, 'reason': f'error:{str(e)[:50]}',
            'm5_color': '', 'm1_color': '',
            'wait_seconds': 0, 'expired': True
        }
    """
    ASYNC MAIN timing filter - non-blocking wait
    
    Returns:
        dict {
            'pass': bool,
            'reason': str,
            'm5_color': str,
            'm1_color': str,
            'wait_seconds': int,
            'expired': bool
        }
    """
    try:
        start_time = datetime.now()
        initial_m15_candle = _get_current_m15_candle_start()
        wait_count = 0
        
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Check M15 expired
            current_m15 = _get_current_m15_candle_start()
            if current_m15 != initial_m15_candle:
                return {
                    'pass': False,
                    'reason': 'm15_candle_expired',
                    'm5_color': '', 'm1_color': '',
                    'wait_seconds': int(elapsed),
                    'expired': True
                }
            
            # Check timeout
            if elapsed > max_wait_seconds:
                return {
                    'pass': False,
                    'reason': f'timeout_{int(elapsed)}s',
                    'm5_color': get_candle_color(symbol, mt5.TIMEFRAME_M5),
                    'm1_color': get_candle_color(symbol, mt5.TIMEFRAME_M1),
                    'wait_seconds': int(elapsed),
                    'expired': True
                }
            
            # Get current colors
            m5_color = get_candle_color(symbol, mt5.TIMEFRAME_M5)
            m1_color = get_candle_color(symbol, mt5.TIMEFRAME_M1)
            
            m5_ok = is_color_aligned(direction, m5_color)
            m1_ok = is_color_aligned(direction, m1_color)
            
            # Callback for dashboard update
            if callback:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback({
                            'm5_color': m5_color, 'm1_color': m1_color,
                            'm5_ok': m5_ok, 'm1_ok': m1_ok,
                            'wait_seconds': int(elapsed), 'wait_count': wait_count
                        })
                    else:
                        callback({
                            'm5_color': m5_color, 'm1_color': m1_color,
                            'm5_ok': m5_ok, 'm1_ok': m1_ok,
                            'wait_seconds': int(elapsed), 'wait_count': wait_count
                        })
                except:
                    pass
            
            # Single check mode (no wait)
            if not wait_mode:
                if m5_ok and m1_ok:
                    return {
                        'pass': True,
                        'reason': f'aligned_m5={m5_color}_m1={m1_color}',
                        'm5_color': m5_color, 'm1_color': m1_color,
                        'wait_seconds': 0, 'expired': False
                    }
                else:
                    return {
                        'pass': False,
                        'reason': f'not_aligned_m5={m5_color}_m1={m1_color}',
                        'm5_color': m5_color, 'm1_color': m1_color,
                        'wait_seconds': 0, 'expired': False
                    }
            
            # WAIT MODE
            if m5_ok and m1_ok:
                # Kedua TF align — langsung pass, tidak perlu nunggu konfirmasi lagi
                return {
                    'pass': True,
                    'reason': f'aligned_m5={m5_color}_m1={m1_color}',
                    'm5_color': m5_color, 'm1_color': m1_color,
                    'wait_seconds': int(elapsed), 'expired': False
                }
            
            elif m5_ok and not m1_ok:
                # M5 align, tunggu M1 — fast refresh
                await asyncio.sleep(FAST_REFRESH_SEC)
                wait_count += 1
            
            else:
                # M5 belum align — slow refresh
                await asyncio.sleep(SLOW_REFRESH_SEC)
                wait_count += 1
                
    except Exception as e:
        import traceback
        print(f"[TIMING FILTER ERROR] {e}")
        traceback.print_exc()
        return {
            'pass': False,
            'reason': f'error:{str(e)[:50]}',
            'm5_color': '', 'm1_color': '',
            'wait_seconds': 0, 'expired': True
        }


def check_timing_filter(symbol, direction, max_wait_seconds=MAX_WAIT_SECONDS,
                        wait_mode=True, callback=None):
    """SYNC wrapper (non-async, single check only - for testing)"""
    if wait_mode:
        raise RuntimeError("Use check_timing_filter_async for wait_mode=True")
    
    # Single check tidak butuh async
    m5_color = get_candle_color(symbol, mt5.TIMEFRAME_M5)
    m1_color = get_candle_color(symbol, mt5.TIMEFRAME_M1)
    m5_ok = is_color_aligned(direction, m5_color)
    m1_ok = is_color_aligned(direction, m1_color)
    
    if m5_ok and m1_ok:
        return {'pass': True, 'reason': f'aligned_m5={m5_color}_m1={m1_color}',
                'm5_color': m5_color, 'm1_color': m1_color,
                'wait_seconds': 0, 'expired': False}
    else:
        return {'pass': False, 'reason': f'not_aligned_m5={m5_color}_m1={m1_color}',
                'm5_color': m5_color, 'm1_color': m1_color,
                'wait_seconds': 0, 'expired': False}
