"use client";

interface Props {
  summary: {
    title: string;
    situation: string;
    key_levels: string;
    action: string;
    avoid: string;
    invalidation: string;
  };
  reversalRisk: { percentage: number; description: string };
}

export default function MarketSummary({ summary, reversalRisk }: Props) {
  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div className="section-header">
        <span>📊 ANALISIS MARKET — AI POWERED</span>
      </div>
      <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
        {/* Title */}
        <div style={{ fontWeight: 700, fontSize: 12, color: "var(--accent-blue)" }}>
          📌 {summary.title}
        </div>

        {/* Situation */}
        <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.6 }}>
          💬 {summary.situation}
        </div>

        {row("📍 Level Penting", summary.key_levels)}
        {row("✅ Yang Harus Dilakukan", summary.action, "var(--accent-green)")}
        {row("❌ Yang Harus Dihindari", summary.avoid, "var(--accent-red)")}
        {row("⚠️ Invalidasi", summary.invalidation, "var(--accent-orange)")}

        {/* Reversal risk */}
        <div style={{
          padding: "8px 10px",
          background: reversalRisk.percentage > 50 ? "rgba(255,68,68,0.08)" : "rgba(75,85,99,0.2)",
          borderRadius: "var(--radius-sm)",
          border: `1px solid ${reversalRisk.percentage > 50 ? "rgba(255,68,68,0.3)" : "var(--border)"}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>🔄 REVERSAL RISK</span>
            <span className="mono" style={{ fontSize: 11, fontWeight: 700, color: reversalRisk.percentage > 50 ? "var(--accent-red)" : "var(--accent-yellow)" }}>
              {reversalRisk.percentage}%
            </span>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>{reversalRisk.description}</div>
        </div>
      </div>
    </div>
  );
}

function row(label: string, value: string, color = "var(--text-secondary)") {
  return (
    <div>
      <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 11, color, lineHeight: 1.5 }}>{value}</div>
    </div>
  );
}
