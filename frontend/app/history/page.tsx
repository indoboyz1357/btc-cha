"use client";

import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useAppStore";
import { formatDateTime, formatPrice } from "@/utils/formatters";
import { ArrowLeft, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import type { AIAnalysis } from "@/types";

export default function HistoryPage() {
  const router   = useRouter();
  const history  = useAppStore((s) => s.analysisHistory);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [search, setSearch]     = useState("");

  const filtered = history.filter((h) =>
    h.trend_bias?.toLowerCase().includes(search.toLowerCase()) ||
    h.market_summary?.title?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-primary)", padding: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <button className="btn-icon" onClick={() => router.push("/")} id="btn-back-home">
          <ArrowLeft size={16} />
        </button>
        <h1 style={{ fontSize: 16, fontWeight: 700 }}>📊 History Analisis AI</h1>
        <div style={{ flex: 1 }} />
        <input className="input" placeholder="Search..." value={search}
          onChange={(e) => setSearch(e.target.value)} style={{ maxWidth: 200 }} />
      </div>

      {filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}>
          <p style={{ fontSize: 14, marginBottom: 8 }}>Belum ada history analisis</p>
          <p style={{ fontSize: 11 }}>Klik AI ANALYZE di halaman utama untuk memulai</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {filtered.map((item) => (
            <HistoryItem key={item.id} item={item}
              expanded={expanded === item.id}
              onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function HistoryItem({ item, expanded, onToggle }: { item: AIAnalysis; expanded: boolean; onToggle: () => void }) {
  const biasColor = item.trend_bias === "bullish" ? "var(--accent-green)"
    : item.trend_bias === "bearish" ? "var(--accent-red)" : "var(--text-muted)";

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      {/* Summary row */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12, padding: "12px 14px",
        cursor: "pointer",
      }} onClick={onToggle}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{formatDateTime(item.timestamp)}</span>
            <span className="badge badge-gray" style={{ fontSize: 10 }}>{item.model}</span>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span className="mono" style={{ fontSize: 13, fontWeight: 700 }}>
              BTC ${formatPrice(item.btcPrice)}
            </span>
            <span style={{ fontWeight: 700, color: biasColor, fontSize: 12 }}>
              {item.trend_bias?.toUpperCase()}
            </span>
            <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
              Conf: {item.overall_confidence}%
            </span>
          </div>
          {item.market_summary?.title && (
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4 }}>
              {item.market_summary.title}
            </div>
          )}
        </div>

        {/* Signal summary */}
        <div style={{ display: "flex", gap: 6 }}>
          {item.primary_swing?.active && (
            <span className={`badge ${item.primary_swing.direction === "buy" ? "badge-green" : "badge-red"}`} style={{ fontSize: 10 }}>
              SWING {item.primary_swing.direction?.toUpperCase()} @ {formatPrice(item.primary_swing.entry ?? 0)}
            </span>
          )}
        </div>

        {expanded ? <ChevronUp size={14} color="var(--text-muted)" /> : <ChevronDown size={14} color="var(--text-muted)" />}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ borderTop: "1px solid var(--border)", padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            { title: "🎯 Primary Swing", signal: item.primary_swing },
            { title: "⚡ Scalp Trend",   signal: item.scalp_trend },
            { title: "↩ Scalp Counter", signal: item.scalp_counter },
          ].map(({ title, signal }) => signal?.active && (
            <div key={title} style={{ padding: "8px 10px", background: "var(--bg-surface)", borderRadius: "var(--radius-sm)", fontSize: 11 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>{title} — Conf {signal.confidence}%</div>
              <div style={{ color: "var(--text-muted)" }}>
                {signal.direction?.toUpperCase()} Entry: <span className="mono">{formatPrice(signal.entry ?? 0)}</span>
                {" · "} SL: <span className="mono" style={{ color: "var(--accent-red)" }}>{formatPrice(signal.sl ?? 0)}</span>
              </div>
              {signal.reasoning && <div style={{ color: "var(--text-secondary)", marginTop: 4, fontStyle: "italic" }}>{signal.reasoning}</div>}
            </div>
          ))}

          {item.market_summary && (
            <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>📊 {item.market_summary.title}</div>
              <p>{item.market_summary.situation}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
