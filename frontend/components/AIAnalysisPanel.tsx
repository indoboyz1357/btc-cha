"use client";

import { useAppStore } from "@/store/useAppStore";
import { useAIAnalysis } from "@/hooks/useAIAnalysis";
import { Bot, Loader2 } from "lucide-react";
import SignalCard from "./SignalCard";
import MarketSummary from "./MarketSummary";

export default function AIAnalysisPanel() {
  const { lastAnalysis, isAnalyzing } = useAppStore();
  const { analyze }                   = useAIAnalysis();

  if (isAnalyzing) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, padding: 40, height: "100%" }}>
        <Loader2 size={32} color="var(--accent-blue)" style={{ animation: "spin 1s linear infinite" }} />
        <span style={{ color: "var(--text-secondary)", fontSize: 12 }}>Menganalisis pasar…</span>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!lastAnalysis) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, padding: 40, height: "100%" }}>
        <Bot size={40} color="var(--text-muted)" />
        <div style={{ textAlign: "center" }}>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Analisis AI Belum Dijalankan</p>
          <p style={{ color: "var(--text-muted)", fontSize: 11 }}>Klik tombol AI ANALYZE di header untuk memulai</p>
        </div>
        <button className="btn btn-primary" onClick={analyze} style={{ fontSize: 12 }}>
          <Bot size={14} /> Mulai Analisis
        </button>
      </div>
    );
  }

  const { primary_swing, scalp_trend, scalp_counter, market_summary, reversal_risk, overall_confidence, trend_bias } = lastAnalysis;

  return (
    <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Overall bias */}
      <div style={{
        padding: "8px 12px",
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>BIAS KESELURUHAN</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className={`badge badge-${trend_bias === "bullish" ? "green" : trend_bias === "bearish" ? "red" : "gray"}`}
            style={{ fontSize: 11, fontWeight: 700 }}>
            {trend_bias?.toUpperCase()}
          </span>
          <span className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            {overall_confidence}%
          </span>
        </div>
      </div>

      <SignalCard
        id="signal-primary"
        title="🎯 PRIMARY ENTRY (SWING)"
        signal={primary_swing}
        label="PRIMARY SWING"
      />
      <SignalCard
        id="signal-scalp-trend"
        title="⚡ SCALP TREND"
        signal={scalp_trend}
        label="SCALP TREND"
      />
      <SignalCard
        id="signal-scalp-counter"
        title="↩ SCALP COUNTER"
        signal={scalp_counter}
        label="SCALP COUNTER"
        isCounter
      />
      <MarketSummary summary={market_summary} reversalRisk={reversal_risk} />
    </div>
  );
}
