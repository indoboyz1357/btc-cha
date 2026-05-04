"use client";

import type { TrendCard as ITrendCard } from "@/types";

const DIR_CLASS: Record<string, string> = {
  bullish_strong: "trend-bullish-strong",
  bullish_weak:   "trend-bullish-weak",
  bearish_strong: "trend-bearish-strong",
  bearish_weak:   "trend-bearish-weak",
  sideways:       "trend-sideways",
};

const DIR_ICON: Record<string, string> = {
  bullish_strong: "▲",
  bullish_weak:   "△",
  bearish_strong: "▼",
  bearish_weak:   "▽",
  sideways:       "━",
};

const PROGRESS_COLOR: Record<string, string> = {
  bullish_strong: "var(--accent-green)",
  bullish_weak:   "rgba(0,208,132,0.5)",
  bearish_strong: "var(--accent-red)",
  bearish_weak:   "rgba(255,68,68,0.5)",
  sideways:       "var(--text-muted)",
};

export default function TrendCard({ card }: { card: ITrendCard }) {
  const cls   = DIR_CLASS[card.direction];
  const icon  = DIR_ICON[card.direction];
  const color = PROGRESS_COLOR[card.direction];
  const isBull = card.direction.startsWith("bullish");
  const isBear = card.direction.startsWith("bearish");

  return (
    <div className={`card ${cls} fade-in`} style={{ padding: "10px 12px" }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", letterSpacing: "0.06em" }}>
          {card.timeframe}
        </span>
        <span className="mono" style={{
          fontSize: 13, fontWeight: 700,
          color: isBull ? "var(--accent-green)" : isBear ? "var(--accent-red)" : "var(--text-muted)",
        }}>
          {card.strength}%
        </span>
      </div>

      {/* Direction label */}
      <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 8 }}>
        <span style={{ fontSize: 13, color: isBull ? "var(--accent-green)" : isBear ? "var(--accent-red)" : "var(--text-muted)" }}>
          {icon}
        </span>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-primary)", letterSpacing: "0.04em" }}>
          {card.label}
        </span>
      </div>

      {/* Momentum bar */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
          <span style={{ fontSize: 10, color: "var(--text-muted)" }}>Momentum</span>
          <span className="mono" style={{ fontSize: 10, color: "var(--text-secondary)" }}>{card.momentum}%</span>
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${card.momentum}%`, background: color }} />
        </div>
      </div>

      {/* Bottom stats */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-muted)" }}>
        <span>Searah: <span className="mono" style={{ color: "var(--text-secondary)" }}>{card.aligned}/10</span></span>
        <span style={{ color: card.reversalRisk > 40 ? "var(--accent-orange)" : "var(--text-muted)" }}>
          ⚠ Rev: <span className="mono">{card.reversalRisk}%</span>
        </span>
      </div>
    </div>
  );
}
