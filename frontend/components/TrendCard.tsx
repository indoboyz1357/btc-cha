"use client";

import type { TrendCard as ITrendCard } from "@/types";

const DIR_ICON: Record<string, string> = {
  bullish_strong: "▲",
  bullish_weak:   "△",
  bearish_strong: "▼",
  bearish_weak:   "▽",
  sideways:       "━",
};

const DIR_COLOR: Record<string, string> = {
  bullish_strong: "var(--accent-green)",
  bullish_weak:   "rgba(0,208,132,0.65)",
  bearish_strong: "var(--accent-red)",
  bearish_weak:   "rgba(255,68,68,0.65)",
  sideways:       "var(--text-muted)",
};

const BG_COLOR: Record<string, string> = {
  bullish_strong: "rgba(0,208,132,0.08)",
  bullish_weak:   "rgba(0,208,132,0.04)",
  bearish_strong: "rgba(255,68,68,0.08)",
  bearish_weak:   "rgba(255,68,68,0.04)",
  sideways:       "transparent",
};

export default function TrendCard({ card }: { card: ITrendCard }) {
  const icon  = DIR_ICON[card.direction];
  const color = DIR_COLOR[card.direction];
  const bg    = BG_COLOR[card.direction];
  const isSide = card.direction === "sideways";

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: 4,
      padding: "7px 10px",
      background: bg,
      border: "1px solid",
      borderColor: isSide ? "var(--border)" : color.replace(")", ", 0.25)").replace("rgba", "rgba").replace("var(--accent-green)", "rgba(0,208,132,0.25)").replace("var(--accent-red)", "rgba(255,68,68,0.25)"),
      borderRadius: 6,
      minWidth: 0,
      flex: 1,
    }}>
      {/* Row 1: TF + strength */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
          {card.timeframe}
        </span>
        <span className="mono" style={{ fontSize: 11, fontWeight: 700, color }}>
          {card.strength}%
        </span>
      </div>

      {/* Row 2: Icon + Label */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <span style={{ fontSize: 10, color }}>{icon}</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: "var(--text-primary)", letterSpacing: "0.03em", whiteSpace: "nowrap" }}>
          {card.label}
        </span>
      </div>

      {/* Row 3: Thin momentum bar */}
      <div style={{ height: 2, borderRadius: 2, background: "var(--border)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${card.momentum}%`, background: color, borderRadius: 2, transition: "width 0.4s ease" }} />
      </div>
    </div>
  );
}

