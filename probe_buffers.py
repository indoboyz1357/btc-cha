"""
Probe Crystal Heikin Ashi indicator buffers.
Jalankan script ini untuk tahu ada berapa buffer dan isinya apa.
MT5 harus sudah terbuka dan connected.
"""
import MetaTrader5 as mt5
import json

LOGIN    = 430207633
PASSWORD = "Pierre@136"
SERVER   = "XMGlobal-MT5 18"
SYMBOL   = "BTCUSD"
TF       = mt5.TIMEFRAME_M15
COUNT    = 10
INDICATOR = "Crystal Heikin Ashi"

terminal_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"

if not mt5.initialize(path=terminal_path):
    mt5.initialize()

mt5.login(LOGIN, password=PASSWORD, server=SERVER)

print(f"MT5 connected: {mt5.account_info() is not None}")
print(f"\nProbing indicator: {INDICATOR}")
print("=" * 60)

# Coba baca buffer 0 sampai 15
for buf_idx in range(16):
    try:
        data = mt5.copy_buffer(SYMBOL, TF, 0, COUNT, buf_idx, INDICATOR)
        if data is not None and len(data) > 0:
            # Filter nilai yang bukan empty/EMPTY_VALUE
            valid = [v for v in data if v != 2147483647.0 and v != -2147483648.0 and abs(v) < 1e15]
            if valid:
                print(f"\nBuffer [{buf_idx}]: {len(data)} values")
                print(f"  Sample (last {min(5,len(valid))}): {valid[-5:]}")
                print(f"  Min={min(valid):.4f}, Max={max(valid):.4f}")
                # Cek apakah ini color buffer (nilai 0,1,2,3)
                unique = sorted(set(round(v) for v in valid))
                if all(u in [0,1,2,3,4,5,6,7,8,9,10] for u in unique):
                    print(f"  *** KEMUNGKINAN COLOR BUFFER! Unique values: {unique}")
            else:
                print(f"Buffer [{buf_idx}]: ada data tapi semua EMPTY")
        else:
            print(f"Buffer [{buf_idx}]: NULL / tidak ada data")
    except Exception as e:
        print(f"Buffer [{buf_idx}]: ERROR - {e}")

mt5.shutdown()
print("\nDone.")
