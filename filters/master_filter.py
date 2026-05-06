"""
master_filter.py - Combine semua filter
Main entry point untuk filter system
"""
from dataclasses import dataclass
from typing import Optional
import MetaTrader5 as mt5

from .zone_filter import check_zone_filter
from .sideways_filter import check_sideways_filter
from .timing_filter import check_timing_filter_async, check_timing_filter
from .filter_logger import log_filter_decision, print_filter_status


@dataclass
class FilterResult:
    final_decision: str  # 'ENTRY', 'BLOCKED', 'EXPIRED'
    blocked_by: Optional[str]
    zone_pass: bool
    sideways_pass: bool
    timing_pass: bool
    details: dict


async def check_all_filters_async(
    symbol: str,
    direction: str,
    signal_type: str,
    candle_time: str,
    enable_zone: bool = True,
    enable_sideways: bool = True,
    enable_timing: bool = True,
    timing_wait_mode: bool = True,
    max_timing_wait: int = 900,
    timing_callback=None,
    shadow_mode: bool = False,
):
    """
    ASYNC main function: Run all filters in sequence
    
    Args:
        symbol: e.g. "BTCUSD"
        direction: "buy" or "sell"
        signal_type: "circle" or "arrow"
        candle_time: timestamp candle M15
        enable_*: toggle individual filters
        timing_wait_mode: True = wait for alignment, False = single check
        max_timing_wait: max wait time for timing filter (seconds)
        timing_callback: optional async callback for dashboard updates
        shadow_mode: if True, log but don't block (override to ENTRY)
    
    Returns:
        FilterResult object
    """
    
    decision_data = {
        'm15_candle_time': str(candle_time),
        'symbol': symbol,
        'direction': direction,
        'signal_type': signal_type,
        'final_decision': 'UNKNOWN',
        'blocked_by_filter': None,
        'zone_pass': True,
        'zone_reason': 'disabled',
        'sideways_pass': True,
        'sideways_reason': 'disabled',
        'timing_pass': True,
        'timing_reason': 'disabled',
        'm5_color': '',
        'm1_color': '',
        'nearest_resistance': '',
        'nearest_support': '',
        'wait_seconds': 0,
        'final_action': '',
    }
    
    # ════════════════════════════════════
    # GATE #7: ZONE FILTER
    # ════════════════════════════════════
    if enable_zone:
        zone_result = check_zone_filter(symbol, direction)
        decision_data['zone_pass'] = zone_result['pass']
        decision_data['zone_reason'] = zone_result['reason']
        decision_data['nearest_resistance'] = zone_result['nearest_resistance']
        decision_data['nearest_support'] = zone_result['nearest_support']
        
        if not zone_result['pass']:
            decision_data['final_decision'] = 'BLOCKED'
            decision_data['blocked_by_filter'] = 'zone'
            decision_data['final_action'] = 'skip_no_entry'
            
            log_filter_decision(decision_data)
            print_filter_status(decision_data)
            
            final_decision = 'ENTRY' if shadow_mode else 'BLOCKED'
            return FilterResult(
                final_decision=final_decision,
                blocked_by='zone',
                zone_pass=False,
                sideways_pass=True,
                timing_pass=True,
                details=decision_data
            )
    
    # ════════════════════════════════════
    # GATE #8: SIDEWAYS FILTER
    # ════════════════════════════════════
    if enable_sideways:
        sideways_result = check_sideways_filter(symbol)
        decision_data['sideways_pass'] = sideways_result['pass']
        decision_data['sideways_reason'] = sideways_result['reason']
        
        if not sideways_result['pass']:
            decision_data['final_decision'] = 'BLOCKED'
            decision_data['blocked_by_filter'] = 'sideways'
            decision_data['final_action'] = 'skip_no_entry'
            
            log_filter_decision(decision_data)
            print_filter_status(decision_data)
            
            final_decision = 'ENTRY' if shadow_mode else 'BLOCKED'
            return FilterResult(
                final_decision=final_decision,
                blocked_by='sideways',
                zone_pass=True,
                sideways_pass=False,
                timing_pass=True,
                details=decision_data
            )
    
    # ════════════════════════════════════
    # GATE #9: TIMING FILTER (M5 + M1)
    # ════════════════════════════════════
    if enable_timing:
        timing_result = await check_timing_filter_async(
            symbol, direction,
            max_wait_seconds=max_timing_wait,
            wait_mode=timing_wait_mode,
            callback=timing_callback
        )
        
        decision_data['timing_pass'] = timing_result['pass']
        decision_data['timing_reason'] = timing_result['reason']
        decision_data['m5_color'] = timing_result['m5_color']
        decision_data['m1_color'] = timing_result['m1_color']
        decision_data['wait_seconds'] = timing_result['wait_seconds']
        
        if not timing_result['pass']:
            if timing_result['expired']:
                decision_data['final_decision'] = 'EXPIRED'
                decision_data['blocked_by_filter'] = 'timing_timeout'
            else:
                decision_data['final_decision'] = 'BLOCKED'
                decision_data['blocked_by_filter'] = 'timing'
            decision_data['final_action'] = 'skip_no_entry'
            
            log_filter_decision(decision_data)
            print_filter_status(decision_data)
            
            final_decision = 'ENTRY' if shadow_mode else decision_data['final_decision']
            return FilterResult(
                final_decision=final_decision,
                blocked_by=decision_data['blocked_by_filter'],
                zone_pass=True,
                sideways_pass=True,
                timing_pass=False,
                details=decision_data
            )
    
    # ════════════════════════════════════
    # ALL PASSED!
    # ════════════════════════════════════
    decision_data['final_decision'] = 'ENTRY'
    decision_data['final_action'] = 'execute_order'
    
    log_filter_decision(decision_data)
    print_filter_status(decision_data)
    
    return FilterResult(
        final_decision='ENTRY',
        blocked_by=None,
        zone_pass=True,
        sideways_pass=True,
        timing_pass=True,
        details=decision_data
    )


# Sync wrapper (for test_filters.py)
def check_all_filters(
    symbol: str,
    direction: str,
    signal_type: str,
    candle_time: str,
    enable_zone: bool = True,
    enable_sideways: bool = True,
    enable_timing: bool = True,
    timing_wait_mode: bool = False,
    max_timing_wait: int = 900,
    timing_callback=None,
    shadow_mode: bool = False,
) -> FilterResult:
    """
    Sync wrapper - timing filter runs in single-check mode (no long wait)
    Used by test_filters.py
    """
    import asyncio
    # Force wait_mode=False for sync call
    return asyncio.run(check_all_filters_async(
        symbol, direction, signal_type, candle_time,
        enable_zone, enable_sideways, enable_timing,
        timing_wait_mode=False,  # Force no-wait for sync
        max_timing_wait=max_timing_wait,
        timing_callback=timing_callback,
        shadow_mode=shadow_mode,
    ))
