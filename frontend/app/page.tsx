"use client";


import { useMT5Bridge } from "@/hooks/useMT5Bridge";
import { useSignalVoice } from "@/hooks/useSignalVoice";
import { useAppStore } from "@/store/useAppStore";
import { useShallow } from "zustand/react/shallow";
import Header from "@/components/Header";
import TrendCard from "@/components/TrendCard";
import ChartPanel from "@/components/ChartPanel";
import AutoTradingPanel from "@/components/AutoTradingPanel";
import ManualOrderPanel from "@/components/ManualOrderPanel";
import PositionCard from "@/components/PositionCard";
import PendingOrderCard from "@/components/PendingOrderCard";
import ToastContainer from "@/components/ui/Toast";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Timeframe } from "@/types";

const TIMEFRAMES: Timeframe[] = ["H4", "H1", "M15", "M5", "M1"];

export default function HomePage() {
  useMT5Bridge();
  useSignalVoice(); // 🔊 Voice alert: "Buy Signal Detected" / "Sell Signal Detected"
  const router = useRouter();
  const [confirmCloseAll, setConfirmCloseAll] = useState(false);

  // ✅ useShallow: page HANYA re-render kalau field ini benar-benar berubah
  // tick/crystalHA update TIDAK akan trigger re-render page ini
  const { trendCards, openPositions, pendingOrders, sendCommand, isConnected, autoTrading } = useAppStore(
    useShallow((s) => ({
      trendCards:    s.trendCards,
      openPositions: s.openPositions,
      pendingOrders: s.pendingOrders,
      sendCommand:   s.sendCommand,
      isConnected:   s.isConnected,
      autoTrading:   s.autoTrading,
    }))
  );

  const totalPL     = openPositions.reduce((s, p) => s + p.profit, 0);
  const totalVol    = openPositions.reduce((s, p) => s + p.volume, 0);
  const plColor     = totalPL >= 0 ? "var(--accent-green)" : "var(--accent-red)";
  const equity      = autoTrading.equity || 0;
  const balance     = autoTrading.balance || 0;

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Header onHistoryClick={() => router.push("/history")} />

      {/* Disconnected banner */}
      {!isConnected && (
        <div style={{
          padding: "8px 16px",
          background: "rgba(255,68,68,0.1)",
          borderBottom: "1px solid rgba(255,68,68,0.3)",
          fontSize: 11,
          color: "var(--accent-red)",
          textAlign: "center",
        }}>
          🔴 Bridge terputus — Jalankan <code>start.bat</code> di PC trading kamu
        </div>
      )}

      {/* 3-column grid */}
      <div className="terminal-grid" style={{ flex: 1, overflow: "hidden" }}>

        {/* ── COL 1: Trend Cards (horizontal strip) + Chart ── */}
        <div className="terminal-col terminal-col-1" style={{ display: "flex", flexDirection: "column" }}>
          {/* Trend cards — inline horizontal strip */}
          <div style={{ padding: "6px 8px", display: "flex", gap: 5, borderBottom: "1px solid var(--border)" }}>
            {TIMEFRAMES.map((tf) => {
              const card = trendCards[tf] || {
                timeframe: tf, direction: "sideways" as const, label: "—",
                strength: 0, momentum: 50, reversalRisk: 0, aligned: 0,
              };
              return <TrendCard key={tf} card={card} />;
            })}
          </div>

          {/* Chart — takes all remaining space */}
          <div style={{ flex: 1, minHeight: 280 }}>
            <ChartPanel />
          </div>
        </div>

        {/* ── COL 2: LIVE COCKPIT ── */}
        <div className="terminal-col" style={{ overflowY: "auto" }}>
          {/* Live Cockpit Header */}
          <div style={{
            margin: "10px 10px 0",
            padding: "14px 16px",
            background: "linear-gradient(135deg, rgba(0,208,132,0.08), rgba(0,208,132,0.02))",
            borderRadius: "8px 8px 0 0",
            border: "1px solid rgba(0,208,132,0.25)",
            borderBottom: "none",
          }}>
            {/* Title */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{
                fontSize: 13, fontWeight: 800, color: "#00d084",
                letterSpacing: "0.1em", textTransform: "uppercase",
                textShadow: "0 0 20px rgba(0,208,132,0.4)",
              }}>
                ⚡ LIVE COCKPIT
              </span>
              <span style={{
                fontSize: 11, fontWeight: 700,
                color: openPositions.length > 0 ? "#00d084" : "var(--text-muted)",
                background: openPositions.length > 0 ? "rgba(0,208,132,0.12)" : "var(--bg-surface)",
                padding: "2px 10px", borderRadius: 20,
                border: `1px solid ${openPositions.length > 0 ? "rgba(0,208,132,0.3)" : "var(--border)"}`,
              }}>
                {openPositions.length} POSISI
              </span>
            </div>

            {/* Equity & Balance — BESAR */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
              <div style={{
                background: "rgba(0,0,0,0.3)", borderRadius: 6, padding: "10px 12px",
                border: "1px solid rgba(0,208,132,0.15)",
              }}>
                <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.08em" }}>EQUITY</div>
                <div className="mono" style={{
                  fontSize: 22, fontWeight: 800,
                  color: equity > balance ? "var(--accent-green)" : equity < balance ? "var(--accent-red)" : "#e8eaed",
                }}>
                  ${equity.toFixed(2)}
                </div>
              </div>
              <div style={{
                background: "rgba(0,0,0,0.3)", borderRadius: 6, padding: "10px 12px",
                border: "1px solid rgba(255,255,255,0.06)",
              }}>
                <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.08em" }}>BALANCE</div>
                <div className="mono" style={{ fontSize: 22, fontWeight: 800, color: "#e8eaed" }}>
                  ${balance.toFixed(2)}
                </div>
              </div>
            </div>

            {/* Total P/L & Vol */}
            {openPositions.length > 0 && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 2 }}>TOTAL P/L</div>
                  <div className="mono" style={{ fontSize: 20, fontWeight: 800, color: plColor }}>
                    {totalPL >= 0 ? "+" : ""}${totalPL.toFixed(2)}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 2 }}>VOLUME</div>
                  <div className="mono" style={{ fontSize: 16, fontWeight: 700, color: "#e8eaed" }}>
                    {totalVol.toFixed(2)} lot
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Position Cards */}
          {openPositions.length === 0 ? (
            <div style={{
              margin: "0 10px", padding: "24px 16px",
              border: "1px solid rgba(0,208,132,0.15)", borderTop: "none",
              borderRadius: "0 0 8px 8px",
              fontSize: 12, color: "var(--text-muted)", textAlign: "center",
            }}>
              Tidak ada posisi terbuka
            </div>
          ) : (
            <>
              <div style={{ margin: "0 10px", border: "1px solid rgba(0,208,132,0.15)", borderTop: "none", borderRadius: "0 0 8px 8px", paddingBottom: 8 }}>
                {openPositions.map((p) => <PositionCard key={p.ticket} pos={p} />)}
              </div>
              <div style={{ padding: "6px 10px" }}>
                {confirmCloseAll ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{
                      padding: "8px 12px", borderRadius: 8, textAlign: "center",
                      background: "rgba(255,68,68,0.1)", border: "1px solid rgba(255,68,68,0.5)",
                      fontSize: 11, fontWeight: 700, color: "#ff4444",
                    }}>
                      ⚠ Tutup SEMUA posisi? Yakin?
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      <button onClick={() => setConfirmCloseAll(false)} style={{
                        fontSize: 12, padding: "10px", borderRadius: 8, cursor: "pointer", fontWeight: 700,
                        background: "rgba(255,255,255,0.05)", color: "var(--text-muted)",
                        border: "1px solid var(--border)",
                      }}>✕ Batal</button>
                      <button onClick={() => { sendCommand({ cmd: "close_all" }); setConfirmCloseAll(false); }} style={{
                        fontSize: 12, padding: "10px", borderRadius: 8, cursor: "pointer", fontWeight: 800,
                        background: "rgba(255,68,68,0.25)", color: "#ff4444",
                        border: "2px solid #ff4444",
                        boxShadow: "0 0 12px rgba(255,68,68,0.4)",
                      }}>🔴 YA, CLOSE ALL!</button>
                    </div>
                  </div>
                ) : (
                  <button id="btn-close-all" className="btn btn-red" style={{ width: "100%", fontSize: 12, fontWeight: 700, padding: "10px" }}
                    onClick={() => setConfirmCloseAll(true)}>
                    🔴 CLOSE ALL POSITIONS
                  </button>
                )}
              </div>
            </>
          )}

          {/* Pending Orders */}
          {pendingOrders.length > 0 && (
            <>
              <div className="section-header" style={{ margin: "8px 10px 0" }}>
                <span>⏳ ORDER PENDING ({pendingOrders.length})</span>
              </div>
              {pendingOrders.map((o) => <PendingOrderCard key={o.ticket} order={o} />)}
            </>
          )}

          <div style={{ height: 20 }} />
        </div>

        {/* ── COL 3: Execution Panel ── */}
        <div className="terminal-col" style={{ overflowY: "auto" }}>
          <ManualOrderPanel />
          <AutoTradingPanel />
          <div style={{ height: 20 }} />
        </div>

      </div>{/* end terminal-grid */}

      <ToastContainer />
    </div>
  );
}
