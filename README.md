# BTCUSD Signal Omega V2

> Professional-grade BTC/USD trading terminal — Crystal Heikin Ashi + AI Multi-Model + Auto Trading Engine

![Stack](https://img.shields.io/badge/Stack-Python%20%7C%20Next.js%20%7C%20MT5-blue)
![Status](https://img.shields.io/badge/Status-Production%20Ready-green)

---

## Arsitektur

```
MT5 Desktop (PC Trader)
        ↓
Python WebSocket Bridge (localhost:8765)
        ↓
Cloudflare Tunnel (URL permanen)
        ↓
Next.js Frontend (Vercel) ←→ OpenRouter API (AI)
```

---

## Prerequisites

- **Python 3.8+** — [python.org](https://python.org)
- **MetaTrader 5** dengan Crystal Heikin Ashi indicator terpasang
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Git** — [git-scm.com](https://git-scm.com)
- Akun **OpenRouter** — [openrouter.ai](https://openrouter.ai) (gratis)
- Akun **Vercel** — [vercel.com](https://vercel.com) (gratis)
- Akun **GitHub** untuk deployment otomatis

---

## Setup Bridge (PC Trading)

### 1. Clone repository

```bash
git clone https://github.com/USERNAME/signal-omega-v2.git
cd signal-omega-v2
```

### 2. Isi config.json

Edit file `config.json` (JANGAN commit file ini):

```json
{
  "mt5_login": 430207633,
  "mt5_password": "PASSWORD_MT5_KAMU",
  "mt5_server": "XMGlobal-MT5 18",
  "websocket_port": 8765,
  "symbol": "BTCUSD",
  "trailing_trigger_points": 500,
  "trailing_stop_points": 250,
  "auto_trading": {
    "enabled": false,
    "scan_interval_seconds": 30,
    "min_confidence": 70,
    "lot_size": 0.01,
    "max_positions": 2,
    "max_daily_loss_usd": 10.0,
    "session_filter": ["london", "new_york"],
    "allow_buy": true,
    "allow_sell": true
  }
}
```

### 3. Pastikan Crystal Heikin Ashi aktif di MT5

- Buka MT5 → Chart BTCUSD M15
- Navigator → Market → Crystal Heikin Ashi → double-click (attach ke chart)
- Pastikan indicator terlihat di chart

### 4. Jalankan Bridge

Double-click `start.bat` atau:

```bash
pip install MetaTrader5 websockets
python bridge.py
```

Output yang benar:
```
=======================================================
  BTCUSD SIGNAL OMEGA V2 — BRIDGE
=======================================================
15:00:00 [INFO] MT5 connected — account 430207633 @ XMGlobal-MT5 18
15:00:00 [INFO] WebSocket server listening on ws://0.0.0.0:8765
```

---

## Setup Cloudflare Tunnel (Akses Remote)

Agar frontend di Vercel bisa terhubung ke bridge di PC kamu:

### 1. Download cloudflared

Download dari: https://github.com/cloudflare/cloudflared/releases/latest
→ `cloudflared-windows-amd64.exe` → rename jadi `cloudflared.exe`

### 2. Login Cloudflare

```bash
cloudflared.exe login
```

### 3. Buat Tunnel

```bash
cloudflared.exe tunnel create signal-omega
cloudflared.exe tunnel route dns signal-omega omega.yourdomain.com
```

### 4. Config tunnel

Buat file `cloudflared-config.yml`:

```yaml
tunnel: signal-omega
credentials-file: C:\Users\USERNAME\.cloudflared\<tunnel-id>.json
ingress:
  - hostname: omega.yourdomain.com
    service: ws://localhost:8765
  - service: http_status:404
```

### 5. Jalankan Tunnel

```bash
cloudflared.exe tunnel --config cloudflared-config.yml run
```

URL kamu: `wss://omega.yourdomain.com`

**Alternatif cepat (tanpa domain):**
```bash
cloudflared.exe tunnel --url ws://localhost:8765
```
→ Dapat URL sementara seperti `https://xxx-xxx.trycloudflare.com`

---

## Setup Frontend (Vercel)

### 1. Push ke GitHub

```bash
git add .
git commit -m "Initial Signal Omega V2"
git remote add origin https://github.com/USERNAME/signal-omega-v2.git
git push -u origin main
```

### 2. Import ke Vercel

1. Buka [vercel.com](https://vercel.com) → New Project
2. Import GitHub repository
3. **Root Directory:** `frontend`
4. Deploy!

### 3. Set Bridge URL di App

1. Buka URL Vercel kamu
2. Klik **MT5** di header
3. Masukkan Bridge URL:
   - Lokal: `ws://localhost:8765`
   - Remote: `wss://omega.yourdomain.com`
4. Masukkan kredensial MT5
5. Klik **SAVE & CONNECT**

---

## Cara Pakai

### Basic Flow

1. Jalankan `start.bat` di PC trading
2. Buka URL Vercel di browser (atau `npm run dev` untuk lokal)
3. Tunggu status **CONNECTED** di header
4. Lihat **5 Trend Cards** di kolom kiri — data real-time dari Crystal HA
5. Klik **AI ANALYZE** → pilih model → lihat sinyal di kolom tengah

### Manual Trading

1. Klik **GUNAKAN SETUP INI** di salah satu signal card
2. Form di kolom kanan otomatis terisi
3. Pilih **MARKET ORDER** atau **REJECTION ENTRY**
4. Klik **EKSEKUSI BUY** atau **EKSEKUSI SELL**
5. Trailing stop 500pt otomatis aktif dari bridge

### Auto Trading

1. Panel **AUTO TRADING** di kolom kanan
2. Set: lot size, scan interval, min confidence, max loss
3. Centang session filter (London/New York recommended)
4. Klik toggle besar **AUTO TRADING ON**
5. Engine scan Crystal HA setiap 30 detik, eksekusi otomatis jika confluence >= confidence

> **⚠ PERHATIAN:** Auto trading menggunakan uang riil. Test di demo account dulu!

### Rejection Entry

Contoh SELL rejection:
1. Set Harga Trigger: `80,150` (harga harus naik ke sini dulu)
2. Set Entry Setelah: `80,050` (kalau harga turun ke sini → eksekusi SELL)
3. Set SL dan timeout
4. Bridge monitor price action server-side, tidak perlu browser terbuka

---

## Fitur Lengkap

| Fitur | Deskripsi |
|-------|-----------|
| Real-time tick | Bid/ask update setiap 1 detik dari MT5 |
| Crystal HA data | Buffer langsung dari indicator MT5 |
| 5 Trend Cards | H4, H1, M15, M5, M1 confluence visual |
| AI Analysis | OpenRouter multi-model (DeepSeek/Claude/Gemini/GPT-4o) |
| Auto Trading | Rule-based Crystal HA engine, safety checks |
| Trailing Stop | 500pt trigger, 250pt trail — dikelola Python bridge |
| Rejection Entry | Server-side price monitoring |
| Daily Loss Limit | Auto pause saat limit tercapai |
| Session Filter | London, New York, Tokyo, Sydney |
| History | Semua analisis AI tersimpan di localStorage |

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Bridge disconnect | Cek MT5 berjalan, jalankan start.bat lagi |
| Crystal HA not found | Pastikan indicator attached ke chart BTCUSD |
| AI error | Cek API key di AI Setup, pastikan ada balance OpenRouter |
| Order failed | Cek account balance, min margin, lot size |
| Auto trading tidak eksekusi | Cek session filter, min confidence, daily loss limit |

---

## Security

- `config.json` ada di `.gitignore` — TIDAK pernah di-commit
- API key OpenRouter tersimpan di `localStorage` browser — tidak ke server
- MT5 password hanya ada di local `config.json`

---

## License

MIT — untuk penggunaan pribadi. Selalu test di demo account sebelum live trading.

> **Disclaimer:** Aplikasi ini adalah alat bantu analisis teknikal. Bukan saran finansial. Trading mengandung risiko kehilangan modal. Gunakan dengan bijak dan selalu terapkan manajemen risiko.
