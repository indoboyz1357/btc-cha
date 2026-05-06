"""
filter_logger.py - Logging untuk semua filter decisions
Save ke CSV untuk analysis nanti
"""
import csv
import os
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
LOG_FILE = ROOT_DIR / "filter_decisions.csv"

CSV_HEADERS = [
    'timestamp', 'm15_candle_time', 'symbol', 'direction',
    'signal_type', 'final_decision', 'blocked_by_filter',
    'zone_pass', 'zone_reason',
    'sideways_pass', 'sideways_reason',
    'timing_pass', 'timing_reason',
    'm5_color', 'm1_color',
    'nearest_resistance', 'nearest_support',
    'wait_seconds', 'final_action'
]


def _ensure_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(CSV_HEADERS)


def log_filter_decision(decision_data: dict):
    """
    Log filter decision ke CSV
    """
    try:
        _ensure_log_file()
        
        row = [
            datetime.now().isoformat(timespec='seconds'),
            decision_data.get('m15_candle_time', ''),
            decision_data.get('symbol', 'BTCUSD'),
            decision_data.get('direction', ''),
            decision_data.get('signal_type', ''),
            decision_data.get('final_decision', ''),
            decision_data.get('blocked_by_filter', ''),
            decision_data.get('zone_pass', ''),
            decision_data.get('zone_reason', ''),
            decision_data.get('sideways_pass', ''),
            decision_data.get('sideways_reason', ''),
            decision_data.get('timing_pass', ''),
            decision_data.get('timing_reason', ''),
            decision_data.get('m5_color', ''),
            decision_data.get('m1_color', ''),
            decision_data.get('nearest_resistance', ''),
            decision_data.get('nearest_support', ''),
            decision_data.get('wait_seconds', 0),
            decision_data.get('final_action', ''),
        ]
        
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(row)
            
    except Exception as e:
        print(f"[FILTER LOGGER ERROR] {e}")


def print_filter_status(decision_data: dict):
    """
    Print compact status ke console
    """
    direction = decision_data.get('direction', '?').upper()
    signal_type = decision_data.get('signal_type', '?')
    final = decision_data.get('final_decision', '?')
    
    emoji = "✅" if final == "ENTRY" else "🚫" if final == "BLOCKED" else "⏸️"
    
    zone = "✓" if decision_data.get('zone_pass') else "✗"
    side = "✓" if decision_data.get('sideways_pass') else "✗"
    timing = "✓" if decision_data.get('timing_pass') else "✗"
    
    blocked_by = decision_data.get('blocked_by_filter', '')
    
    print(f"[FILTER] {emoji} {direction} {signal_type} | "
          f"Zone{zone} Side{side} Timing{timing} | "
          f"{blocked_by if final == 'BLOCKED' else final}")
