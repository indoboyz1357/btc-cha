"use client";

import { useState } from "react";
import { useMT5Bridge } from "@/hooks/useMT5Bridge";
import { useAppStore } from "@/store/useAppStore";
import Header from "@/components/Header";
import TrendCard from "@/components/TrendCard";
import ChartPanel from "@/components/ChartPanel";
import AIAnalysisPanel from "@/components/AIAnalysisPanel";
import AutoTradingPanel from "@/components/AutoTradingPanel";
import ManualOrderPanel from "@/components/ManualOrderPanel";
import PositionCard from "@/components/PositionCard";
import PendingOrderCard from "@/components/PendingOrderCard";
import ToastContainer from "@/components/ui/Toast";
import { useRouter } from "next/navigation";
import type { Timeframe } from "@/types";

const TIMEFRAMES: Timeframe[] = ["H4", "H1", "M15", "M5", "M1"];

export default function HomePage() {
  useMT5Bridge(); // Connect to bridge on mount
  const router = useRouter();

  const { trendCards, openPositions, pendingOrders, sendCommand, isConnected } = useAppStore();

  const totalPL   = openPositions.reduce((s, p) => s + p.profit, 0);
  const plColor   = totalPL >= 0 ? "var(--accent-green)" : "var(--accent-red)";

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

        {/* ── COL 1: Trend Cards + Chart ── */}
        <div className="terminal-col terminal-col-1" style={{ display: "flex", flexDirection: "column" }}>
          {/* Trend cards */}
          <div style={{ padding: 8, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {TIMEFRAMES.map((tf) => {
              const card = trendCards[tf] || {
                timeframe: tf, direction: "sideways" as const, label: "—",
                strength: 0, momentum: 50, reversalRisk: 0, aligned: 0,
              };
              return <TrendCard key={tf} card={card} />;
            })}
            {/* 5th card full width */}
          </div>

          {/* Chart */}
          <div style={{ flex: 1, borderTop: "1px solid var(--border)", minHeight: 280 }}>
            <ChartPanel />
          </div>
        </div>

        {/* ── COL 2: AI Analysis ── */}
        <div className="terminal-col" style={{ overflowY: "auto" }}>
          <div style={{
            padding: "8px 10px",
            borderBottom: "1px solid var(--border)",
            fontSize: 10,
            fontWeight: 700,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}>
            AI Signal Analysis
          </div>
          <AIAnalysisPanel />
        </div>

        {/* ── COL 3: Execution Panel ── */}
        <div className="terminal-col" style={{ overflowY: "auto" }}>
          {/* Auto Trading */}
          <AutoTradingPanel />

          {/* Manual Order */}
          <ManualOrderPanel />

          {/* Open Positions */}
          <div className="section-header" style={{ margin: "0 8px" }}>
            <span>📂 POSISI TERBUKA ({openPositions.length})</span>
            {openPositions.length > 0 && (
              <span className="mono" style={{ fontSize: 11, color: plColor }}>
                {totalPL >= 0 ? "+" : ""}${totalPL.toFixed(2)}
              </span>
            )}
          </div>

          {openPositions.length === 0 ? (
            <div style={{ padding: "12px 16px", fontSize: 11, color: "var(--text-muted)", textAlign: "center" }}>
              Tidak ada posisi terbuka
            </div>
          ) : (
            <>
              {openPositions.map((p) => <PositionCard key={p.ticket} pos={p} />)}
              <div style={{ padding: "6px 8px" }}>
                <button id="btn-close-all" className="btn btn-red" style={{ width: "100%", fontSize: 11 }}
                  onClick={() => sendCommand({ cmd: "close_all" })}>
                  🔴 CLOSE ALL POSITIONS
                </button>
              </div>
            </>
          )}

          {/* Pending Orders */}
          {pendingOrders.length > 0 && (
            <>
              <div className="section-header" style={{ margin: "8px 8px 0" }}>
                <span>⏳ ORDER PENDING ({pendingOrders.length})</span>
              </div>
              {pendingOrders.map((o) => <PendingOrderCard key={o.ticket} order={o} />)}
            </>
          )}

          <div style={{ height: 20 }} />
        </div>
      </div>

      <ToastContainer />
    </div>
  );
}
