"use client";

import { useAppStore } from "@/store/useAppStore";
import type { AISignal } from "@/types";
import { formatPrice } from "@/utils/formatters";
import { TrendingUp, TrendingDown, Bot } from "lucide-react";

interface Props {
  id: string;
  title: string;
  signal: AISignal;
  label: string;
  isCounter?: boolean;
}

export default function SignalCard({ id, title, signal, label, isCounter }: Props) {
  const { setPendingSetup, sendCommand, autoTrading, updateAutoStatus } = useAppStore();

  const isBuy  = signal.direction === "buy";
  const isSell = signal.direction === "sell";

  const handleUse = () => {
    if (!signal.active || !signal.direction) return;
    setPendingSetup({
      label,
      direction: signal.direction,
      entry:     signal.entry ?? 0,
      sl:        signal.sl ?? 0,
    });
  };

  const handleAutoMode = () => {
    if (!signal.active || !signal.direction) return;
    const newEnabled = !autoTrading.enabled;
    updateAutoStatus({ enabled: newEnabled });
    sendCommand({
      cmd:     "set_auto_trading",
      enabled: newEnabled,
    });
  };

  if (!signal.active) {
    return (
      <div id={id} className="card" style={{ padding: "12px 14px", opacity: 0.5 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text-muted)", marginBottom: 6, textTransform: "uppercase" }}>{title}</div>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", fontStyle: "italic" }}>
          {signal.reasoning || "Tidak ada sinyal — tunggu kondisi lebih jelas"}
        </div>
      </div>
    );
  }

  const confColor = signal.confidence >= 70 ? "var(--accent-green)" : signal.confidence >= 50 ? "var(--accent-yellow)" : "var(--accent-red)";

  return (
    <div id={id} className="card fade-in" style={{
      border: `1px solid ${isBuy ? "rgba(0,208,132,0.4)" : "rgba(255,68,68,0.4)"}`,
      background: isBuy ? "rgba(0,208,132,0.04)" : "rgba(255,68,68,0.04)",
    }}>
      {isCounter && (
        <div style={{ background: "rgba(249,115,22,0.1)", borderBottom: "1px solid rgba(249,115,22,0.3)", padding: "3px 14px", fontSize: 10, color: "var(--accent-orange)", fontWeight: 600 }}>
          ⚠ COUNTER-TREND — RISIKO TINGGI
        </div>
      )}

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderBottom: "1px solid var(--border)" }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{title}</span>
        <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: confColor }}>CONF {signal.confidence}%</span>
      </div>

      {/* Direction + entry */}
      <div style={{ padding: "8px 14px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
          {isBuy ? <TrendingUp size={14} color="var(--accent-green)" /> : <TrendingDown size={14} color="var(--accent-red)" />}
          <span style={{ fontWeight: 700, fontSize: 12, color: isBuy ? "var(--accent-green)" : "var(--accent-red)" }}>
            {label} {signal.direction?.toUpperCase()} @ {formatPrice(signal.entry ?? 0)}
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div>
            <div className="label">ENTRY</div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
              {formatPrice(signal.entry ?? 0)}
            </div>
          </div>
          <div>
            <div className="label">STOP LOSS</div>
            <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--accent-red)" }}>
              {formatPrice(signal.sl ?? 0)}
            </div>
          </div>
        </div>

        <div style={{ marginTop: 6, fontSize: 10, color: "var(--text-muted)" }}>
          {signal.rr_note}
        </div>
      </div>

      {/* Reasoning */}
      {signal.reasoning && (
        <div style={{ padding: "8px 14px", borderBottom: "1px solid var(--border)", fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.6, fontStyle: "italic" }}>
          &ldquo;{signal.reasoning}&rdquo;
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 8, padding: "10px 14px" }}>
        <button id={`${id}-use`} className={`btn ${isBuy ? "btn-green" : "btn-red"}`} style={{ flex: 1, fontSize: 11 }} onClick={handleUse}>
          {isBuy ? <TrendingUp size={12} /> : <TrendingDown size={12} />} GUNAKAN SETUP INI
        </button>
        <button id={`${id}-auto`} className="btn btn-ghost" style={{ fontSize: 11 }} onClick={handleAutoMode}>
          <Bot size={12} /> AUTO MODE
        </button>
      </div>
    </div>
  );
}
