"use client";

import { useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import { formatPrice } from "@/utils/formatters";

export default function ManualOrderPanel() {
  const { pendingSetup, setPendingSetup, sendCommand, currentPrice } = useAppStore();

  const [orderType, setOrderType]   = useState<"market" | "rejection">("market");
  const [direction, setDirection]   = useState<"buy" | "sell">(pendingSetup?.direction || "buy");
  const [entry, setEntry]           = useState(pendingSetup?.entry?.toString() || "");
  const [sl, setSl]                 = useState(pendingSetup?.sl?.toString() || "");
  const [volume, setVolume]         = useState("0.01");
  const [triggerPrice, setTrigger]  = useState("");
  const [rejEntry, setRejEntry]     = useState("");
  const [timeout, setTimeout]       = useState("5");

  // Confirm state: null = idle, "buy" = waiting confirm buy, "sell" = waiting confirm sell
  const [confirmDir, setConfirmDir] = useState<"buy" | "sell" | null>(null);

  const label = pendingSetup?.label ? `Setup: ${pendingSetup.label} ${direction.toUpperCase()}` : "Order Manual";

  const execMarket = (dir: "buy" | "sell") => {
    sendCommand({
      cmd:    "order_market",
      type:   dir,
      volume: parseFloat(volume),
      sl:     parseFloat(sl),
    });
    setPendingSetup(null);
    setConfirmDir(null);
  };

  const execRejection = (dir: "buy" | "sell") => {
    sendCommand({
      cmd:             "order_pending_rejection",
      direction:       dir,
      volume:          parseFloat(volume),
      trigger_price:   parseFloat(triggerPrice),
      entry_price:     parseFloat(rejEntry),
      sl:              parseFloat(sl),
      timeout_minutes: parseInt(timeout),
    });
    setPendingSetup(null);
    setConfirmDir(null);
  };

  const handleFirstClick = (dir: "buy" | "sell") => {
    setDirection(dir);
    setConfirmDir(dir);
  };

  const handleConfirm = (dir: "buy" | "sell") => {
    orderType === "market" ? execMarket(dir) : execRejection(dir);
  };

  const handleCancel = () => {
    setConfirmDir(null);
  };

  return (
    <div className="card" style={{ margin: "0 8px 8px" }}>
      <div className="section-header">
        <span>⚡ {label}</span>
        {pendingSetup && (
          <button className="btn-icon" onClick={() => setPendingSetup(null)} title="Clear setup">✕</button>
        )}
      </div>

      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 10 }}>
        {/* Order type radio */}
        <div style={{ display: "flex", gap: 8 }}>
          {(["market", "rejection"] as const).map((t) => (
            <button key={t} id={`order-type-${t}`}
              className={`btn ${orderType === t ? "btn-primary" : "btn-ghost"}`}
              style={{ flex: 1, fontSize: 11 }}
              onClick={() => setOrderType(t)}
            >
              {t === "market" ? "● MARKET" : "○ REJECTION"}
            </button>
          ))}
        </div>

        {/* Entry / SL / Volume */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {orderType === "market" && (
            <div>
              <label className="label">Entry (saat ini)</label>
              <input className="input" id="order-entry" placeholder={formatPrice(currentPrice)} value={entry}
                onChange={(e) => setEntry(e.target.value)} />
            </div>
          )}
          <div>
            <label className="label">Stop Loss</label>
            <input className="input" id="order-sl" placeholder="0.00" value={sl}
              onChange={(e) => setSl(e.target.value)} />
          </div>
          <div>
            <label className="label">Volume (lot)</label>
            <input className="input" id="order-volume" type="number" step="0.01" value={volume}
              onChange={(e) => setVolume(e.target.value)} />
          </div>
        </div>

        {/* Trailing info */}
        <div style={{ padding: "6px 10px", background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.2)", borderRadius: "var(--radius-sm)", fontSize: 10, color: "var(--accent-blue)" }}>
          📈 SL/TP dikelola Crystal HA Pro EA — isi SL manual jika ingin override (0 = pakai EA)
        </div>

        {/* Rejection fields */}
        {orderType === "rejection" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "8px 10px", background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: "var(--radius-sm)" }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--accent-yellow)" }}>⚙ Rejection Entry Config</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div>
                <label className="label">Harga Trigger</label>
                <input className="input" id="rej-trigger" placeholder="0.00" value={triggerPrice}
                  onChange={(e) => setTrigger(e.target.value)} />
              </div>
              <div>
                <label className="label">Entry Setelah</label>
                <input className="input" id="rej-entry" placeholder="0.00" value={rejEntry}
                  onChange={(e) => setRejEntry(e.target.value)} />
              </div>
              <div>
                <label className="label">Timeout (menit)</label>
                <select className="input" id="rej-timeout" value={timeout} onChange={(e) => setTimeout(e.target.value)}>
                  {[3, 5, 10, 15, 30].map((m) => <option key={m} value={m}>{m} menit</option>)}
                </select>
              </div>
            </div>
            <div style={{ fontSize: 10, color: "var(--text-muted)", fontStyle: "italic" }}>
              Harga menyentuh trigger → tunggu rejection → eksekusi otomatis
            </div>
          </div>
        )}

        {/* ── Execute buttons ── */}
        {confirmDir === null ? (
          /* STEP 1: Tombol BUY & SELL sejajar */
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <button
              id="btn-exec-buy"
              className="btn btn-green"
              style={{ fontSize: 12, padding: "10px", borderRadius: 8 }}
              onClick={() => handleFirstClick("buy")}
            >
              ▲ BUY
            </button>
            <button
              id="btn-exec-sell"
              className="btn btn-red"
              style={{ fontSize: 12, padding: "10px", borderRadius: 8 }}
              onClick={() => handleFirstClick("sell")}
            >
              ▼ SELL
            </button>
          </div>
        ) : (
          /* STEP 2: Konfirmasi */
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{
              padding: "8px 12px",
              borderRadius: 8,
              background: confirmDir === "buy" ? "rgba(0,208,132,0.08)" : "rgba(255,68,68,0.08)",
              border: `1px solid ${confirmDir === "buy" ? "rgba(0,208,132,0.4)" : "rgba(255,68,68,0.4)"}`,
              fontSize: 11,
              fontWeight: 700,
              color: confirmDir === "buy" ? "#00d084" : "#ff4444",
              textAlign: "center",
              letterSpacing: "0.05em",
            }}>
              ⚠ Konfirmasi {confirmDir === "buy" ? "▲ BUY" : "▼ SELL"} — Yakin?
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <button
                onClick={handleCancel}
                style={{
                  fontSize: 12, padding: "10px", borderRadius: 8, cursor: "pointer", fontWeight: 700,
                  background: "rgba(255,255,255,0.05)", color: "var(--text-muted)",
                  border: "1px solid var(--border)",
                }}
              >
                ✕ Batal
              </button>
              <button
                id={`btn-confirm-${confirmDir}`}
                onClick={() => handleConfirm(confirmDir)}
                style={{
                  fontSize: 12, padding: "10px", borderRadius: 8, cursor: "pointer", fontWeight: 800,
                  background: confirmDir === "buy" ? "rgba(0,208,132,0.25)" : "rgba(255,68,68,0.25)",
                  color: confirmDir === "buy" ? "#00d084" : "#ff4444",
                  border: `2px solid ${confirmDir === "buy" ? "#00d084" : "#ff4444"}`,
                  boxShadow: confirmDir === "buy" ? "0 0 12px rgba(0,208,132,0.4)" : "0 0 12px rgba(255,68,68,0.4)",
                }}
              >
                ✔ YA, {confirmDir === "buy" ? "BUY" : "SELL"}!
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
