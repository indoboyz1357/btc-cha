"""
test_filters.py - Test smart filters dengan trade history
Verifikasi filter akan BLOCK loss trades dari kemarin
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

SYMBOL = "BTCUSDm"   # FIX: sesuai config.json (Exness)
MAGIC = 20260505
DAYS_BACK = 30

from filters.zone_filter import check_zone_filter
from filters.sideways_filter import check_sideways_filter
from filters.timing_filter import check_timing_filter


def main():
    if not mt5.initialize():
        print("❌ MT5 init failed")
        return
    
    # Get trade history
    deals = mt5.history_deals_get(
        datetime.now() - timedelta(days=DAYS_BACK),
        datetime.now()
    )
    
    if not deals:
        print("⚠️  No deals found for testing")
        mt5.shutdown()
        return
    
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s')

    # DEBUG: kalau 0 trades ditemukan, tampilkan semua yang ada di history
    filtered = df[(df['symbol'] == SYMBOL) & (df['magic'] == MAGIC)]
    if len(filtered) == 0:
        print(f"\n⚠️  Tidak ada trade dengan symbol={SYMBOL} magic={MAGIC}")
        print(f"\n📋 Semua trade di history {DAYS_BACK} hari terakhir:")
        summary = df[df['entry'] == 0].groupby(['symbol', 'magic']).size().reset_index(name='count')
        if len(summary) == 0:
            print("   (tidak ada trade sama sekali)")
        else:
            for _, row in summary.iterrows():
                print(f"   symbol={row['symbol']}  magic={row['magic']}  trades={row['count']}")
        mt5.shutdown()
        return

    df = filtered
    
    entries = df[df['entry'] == 0].copy()
    exits = df[df['entry'] == 1].copy()
    
    print("=" * 80)
    print(f"🔬 TEST FILTERS - Magic ID: {MAGIC}")
    print(f"   Analyzing {len(entries)} trades from last {DAYS_BACK} days")
    print("=" * 80)
    
    blocked_count = 0
    passed_count = 0
    saved_amount = 0
    lost_opportunity = 0
    zone_blocked = 0
    timing_blocked = 0
    
    for _, entry in entries.iterrows():
        matches = exits[exits['position_id'] == entry['position_id']]
        if len(matches) == 0:
            continue
        exit_deal = matches.iloc[0]
        
        direction = 'buy' if entry['type'] == 0 else 'sell'
        pnl = exit_deal['profit']
        
        print(f"\n{'─'*80}")
        print(f"📍 {entry['time']} | {direction.upper()} @ {entry['price']:.2f} | "
              f"P/L: ${pnl:+.2f}")
        
        # Test Zone filter
        zone = check_zone_filter(SYMBOL, direction, entry['price'])
        zone_status = "✅ PASS" if zone['pass'] else "🚫 BLOCK"
        print(f"  Zone Filter:     {zone_status} - {zone['reason']}")
        
        # Test Timing filter (single check mode)
        timing = check_timing_filter(SYMBOL, direction, wait_mode=False)
        timing_status = "✅ PASS" if timing['pass'] else "🚫 BLOCK"
        print(f"  Timing Filter:   {timing_status} - {timing['reason']}")
        
        # Verdict
        zone_blocked_flag = not zone['pass']
        timing_blocked_flag = not timing['pass']
        would_block = zone_blocked_flag or timing_blocked_flag
        
        if would_block:
            blocked_count += 1
            if zone_blocked_flag:
                zone_blocked += 1
            if timing_blocked_flag:
                timing_blocked += 1
            if pnl < 0:
                saved_amount += abs(pnl)
                print(f"  🎯 VERDICT: BLOCKED ✅ (saved ${abs(pnl):.2f})")
            else:
                lost_opportunity += pnl
                print(f"  ⚠️  VERDICT: BLOCKED ❌ (lost opportunity ${pnl:.2f})")
        else:
            passed_count += 1
            print(f"  ➡️  VERDICT: PASSED")
    
    print(f"\n{'='*80}")
    print(f"📊 SUMMARY")
    print(f"{'='*80}")
    print(f"  Total trades analyzed: {blocked_count + passed_count}")
    print(f"  Would BLOCK:          {blocked_count} (zone:{zone_blocked}, timing:{timing_blocked})")
    print(f"  Would PASS:           {passed_count}")
    print(f"\n  💰 Saved from loss:        ${saved_amount:+.2f}")
    print(f"  💸 Lost opportunity:       ${lost_opportunity:+.2f}")
    if saved_amount > 0 or lost_opportunity > 0:
        print(f"  📈 NET BENEFIT:            ${saved_amount - lost_opportunity:+.2f}")
    
    mt5.shutdown()


if __name__ == "__main__":
    main()
