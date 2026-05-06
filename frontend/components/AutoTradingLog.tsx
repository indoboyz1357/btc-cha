"use client";

import { useAppStore } from "@/store/useAppStore";

const ICON: Record<string, string> = { TRADE: "🟢", SKIP: "⏭", ERROR: "🔴", PAUSE: "⚠" };

export default function AutoTradingLog() {
  const { autoTrading, clearAutoLog } = useAppStore();
  const log = autoTrading.log || [];

  return (
    <div style={{ borderTop: "1px solid var(--border)" }}>
      <div className="section-header">
        <span>📋 AUTO TRADING LOG</span>
        <button id="btn-clear-auto-log" className="btn-icon" onClick={clearAutoLog} title="Clear log">✕</button>
      </div>
      <div style={{ maxHeight: 180, overflowY: "auto", padding: "4px 0" }}>
        {log.length === 0 ? (
          <div style={{ padding: "12px 14px", color: "var(--text-muted)", fontSize: 11, textAlign: "center" }}>
            Belum ada aktivitas auto trading
          </div>
        ) : log.map((entry, i) => (
          <div key={i} style={{
            padding: "6px 12px",
            borderBottom: "1px solid var(--border)",
            fontSize: 10.5,
          }}>
            <div style={{ display: "flex", gap: 6, color: "var(--text-muted)", marginBottom: 2 }}>
              <span>{ICON[entry.action] || "•"}</span>
              <span className="mono">{entry.time}</span>
              <span style={{ color: "var(--text-secondary)", fontWeight: 600 }}>{entry.action}</span>
            </div>
            <div style={{ color: "var(--text-secondary)", paddingLeft: 16 }}>{entry.reason}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
