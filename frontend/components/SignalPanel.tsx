"use client";

import { useMemo, useRef, useEffect, useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import { useShallow } from "zustand/react/shallow";
import { formatPrice } from "@/utils/formatters";
import type { Timeframe } from "@/types";
import { TrendingUp, TrendingDown, Clock, Target, AlertTriangle, Ban, Zap } from "lucide-react";

const TF_ORDER: Timeframe[] = ["H4", "H1", "M15", "M5", "M1"];

function calcTrend(trendCards: Record<string, any>): "buy" | "sell" | "none" {
  const h4Dir = trendCards["H4"]?.direction || "sideways";
  if (h4Dir.includes("bullish")) return "buy";
  if (h4Dir.includes("bearish")) return "sell";
  return "none";
}

export default function SignalPanel() {
  const { trendCards, crystalHA, currentPrice, autoTrading } = useAppStore(
    useShallow((s) => ({
      trendCards:   s.trendCards,
      crystalHA:    s.crystalHA,
      currentPrice: s.currentPrice,
      autoTrading:  s.autoTrading,
    }))
  );

  const allowCounter = (autoTrading as any)?.allow_counter_trend ?? false;
  const trend = useMemo(() => calcTrend(trendCards), [trendCards]);

  const m15Data = crystalHA["M15"] || [];
  const latest  = m15Data[m15Data.length - 1];
  const prev    = m15Data[m15Data.length - 2];

  const circleDir: "buy" | "sell" | null = latest?.circle_buy  ? "buy" : latest?.circle_sell ? "sell" : null;
  const arrowDir:  "buy" | "sell" | null = latest?.arrow_buy   ? "buy" : latest?.arrow_sell  ? "sell" : null;
  const activeDir = arrowDir ?? circleDir;

  const isCounter = !!(trend !== "none" && activeDir && activeDir !== trend);
  const isBlocked = isCounter && !allowCounter;

  const signalType: "arrow" | "circle" | "blocked" | "none" =
    isBlocked ? "blocked" :
    arrowDir  ? "arrow"   :
    circleDir ? "circle"  : "none";

  const signalDir = isBlocked ? null : activeDir;

  // Confidence: circle ~55%, arrow ~85%
  const confidence = signalType === "arrow" ? 85 : signalType === "circle" ? 55 : 0;

  // ── Entry & SL dari data nyata candle M15 ────────────────────────────────
  const entryCandle = latest;
  const entryZone = useMemo(() => {
    if (!signalDir || !entryCandle) return null;
    if (signalDir === "buy") {
      return {
        entryFrom: entryCandle.ha_low,
        entryTo:   currentPrice,
        sl:        entryCandle.ha_low,
        slLabel:   `Bawah HA Low ${formatPrice(entryCandle.ha_low)}`,
      };
    } else {
      return {
        entryFrom: currentPrice,
        entryTo:   entryCandle.ha_high,
        sl:        entryCandle.ha_high,
        slLabel:   `Atas HA High ${formatPrice(entryCandle.ha_high)}`,
      };
    }
  }, [signalDir, entryCandle, currentPrice]);

  // ── Riwayat sinyal ────────────────────────────────────────────────────────
  const historyRef = useRef<{ time: number; type: "circle" | "arrow"; dir: "buy" | "sell" }[]>([]);
  const [history, setHistory] = useState<typeof historyRef.current>([]);

  useEffect(() => {
    if (!latest) return;
    const last = historyRef.current[0];
    if (latest.arrow_buy || latest.arrow_sell) {
      const dir = latest.arrow_buy ? "buy" : "sell";
      if (!last || last.time !== latest.time || last.type !== "arrow") {
        historyRef.current = [{ time: latest.time, type: "arrow", dir }, ...historyRef.current.slice(0, 9)];
        setHistory([...historyRef.current]);
      }
    } else if (latest.circle_buy || latest.circle_sell) {
      const dir = latest.circle_buy ? "buy" : "sell";
      if (!last || last.time !== latest.time) {
        historyRef.current = [{ time: latest.time, type: "circle", dir }, ...historyRef.current.slice(0, 9)];
        setHistory([...historyRef.current]);
      }
    }
  }, [latest]);

  // ── Colors ────────────────────────────────────────────────────────────────
  const sigColor  = signalDir === "buy" ? "var(--accent-green)" : signalDir === "sell" ? "var(--accent-red)" : "var(--text-muted)";
  const sigBg     = signalDir === "buy" ? "rgba(0,208,132,0.06)" : signalDir === "sell" ? "rgba(255,68,68,0.06)" : "transparent";
  const sigBorder = signalDir === "buy" ? "rgba(0,208,132,0.5)" : signalDir === "sell" ? "rgba(255,68,68,0.5)" : "var(--border)";
  const trendLabel = trend === "buy" ? "BULLISH" : trend === "sell" ? "BEARISH" : "SIDEWAYS";
  const trendColor = trend === "buy" ? "var(--accent-green)" : trend === "sell" ? "var(--accent-red)" : "var(--text-muted)";
  const confColor  = confidence >= 80 ? "var(--accent-green)" : confidence >= 50 ? "var(--accent-yellow)" : "var(--text-muted)";

  return (
    <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 10 }}>

      {/* ── CARD 1: STATUS SINYAL ─────────────────────────────────────────── */}
      <div style={{
        border: `2px solid ${sigBorder}`,
        background: sigBg,
        borderRadius: "var(--radius-md)",
        overflow: "hidden",
      }} className="fade-in">

        <div style={{ padding: "6px 14px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Entry Signal — M15
          </span>
          <span style={{ fontSize: 10, color: trendColor, fontWeight: 600 }}>Tren: {trendLabel}</span>
        </div>

        <div style={{ padding: "16px 14px" }}>

          {/* Waiting */}
          {signalType === "none" && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "8px 0" }}>
              <div style={{ fontSize: 26 }}>⏳</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-muted)" }}>Menunggu Circle M15</div>
              <div style={{ fontSize: 10, color: "var(--text-muted)", textAlign: "center" }}>
                {trend !== "none" ? `Hanya arah ${trendLabel} yang diterima` : "Tren belum jelas"}
              </div>
            </div>
          )}

          {/* Blocked */}
          {signalType === "blocked" && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "8px 0" }}>
              <Ban size={26} color="var(--accent-yellow)" />
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--accent-yellow)" }}>
                Circle {activeDir?.toUpperCase()} — Counter Tren
              </div>
              <div style={{ fontSize: 10, color: "var(--text-muted)", textAlign: "center", lineHeight: 1.6 }}>
                Tren utama <span style={{ color: trendColor, fontWeight: 700 }}>{trendLabel}</span> — diblokir.<br />
                Centang <em>Allow Counter-Trend</em> di Auto Trading.
              </div>
            </div>
          )}

          {/* Circle atau Arrow */}
          {(signalType === "circle" || signalType === "arrow") && signalDir && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {isCounter && (
                <div style={{ padding: "4px 10px", background: "rgba(245,158,11,0.1)", borderRadius: 4, fontSize: 10, color: "var(--accent-yellow)", fontWeight: 600, textAlign: "center" }}>
                  ⚠ COUNTER-TREND — allow counter aktif
                </div>
              )}

              {/* Arah + confidence */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {signalDir === "buy"
                    ? <TrendingUp  size={30} color="var(--accent-green)" />
                    : <TrendingDown size={30} color="var(--accent-red)"  />}
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 900, color: sigColor, lineHeight: 1 }}>
                      {signalDir === "buy" ? "BUY" : "SELL"}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                      {signalType === "arrow" ? "▶ Arrow — Confirmed" : "○ Circle — Forming"}
                    </div>
                  </div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 18, fontWeight: 900, color: confColor }}>{confidence}%</div>
                  <div style={{ fontSize: 9, color: "var(--text-muted)" }}>confidence</div>
                </div>
              </div>

              {/* Progress bar confidence */}
              <div>
                <div style={{ height: 5, borderRadius: 99, background: "var(--border-light)", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${confidence}%`, borderRadius: 99, transition: "width 0.5s", background: confColor }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 3, fontSize: 9, color: "var(--text-muted)" }}>
                  <span>Circle forming</span>
                  <span style={{ color: signalType === "arrow" ? "var(--accent-green)" : "var(--text-muted)", fontWeight: signalType === "arrow" ? 700 : 400 }}>
                    {signalType === "arrow" ? "⚡ Arrow confirmed" : "Tunggu arrow..."}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── CARD 2: SETUP ENTRY ──────────────────────────────────────────── */}
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
        <div style={{ padding: "7px 14px", borderBottom: "1px solid var(--border)", fontSize: 10, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Setup Entry
        </div>

        {!entryZone ? (
          <div style={{ padding: "16px", fontSize: 11, color: "var(--text-muted)", textAlign: "center", fontStyle: "italic" }}>
            Tampil saat ada sinyal aktif
          </div>
        ) : (
          <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 9 }}>

            {/* Entry zone */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <Target size={12} color="var(--accent-blue)" />
                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>Entry Zone</span>
              </div>
              <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
                {formatPrice(entryZone.entryFrom)} – {formatPrice(entryZone.entryTo)}
              </span>
            </div>

            {/* SL reference */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
              <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
                <AlertTriangle size={12} color="var(--accent-red)" />
                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>SL Reference</span>
              </div>
              <span style={{ fontSize: 11, color: "var(--accent-red)", textAlign: "right" }}>
                {entryZone.slLabel}
              </span>
            </div>

            <div style={{ height: 1, background: "var(--border)" }} />

            {/* Sinyal sebelumnya (prev candle) */}
            {prev && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>Candle sebelumnya</span>
                <span style={{ fontSize: 11, color: prev.color?.includes("bullish") ? "var(--accent-green)" : "var(--accent-red)" }}>
                  {prev.color?.includes("bullish_strong") ? "▲ Bull Strong" :
                   prev.color?.includes("bullish_weak")   ? "△ Bull Weak"   :
                   prev.color?.includes("bearish_strong") ? "▼ Bear Strong" :
                                                            "▽ Bear Weak"}
                </span>
              </div>
            )}

            {/* Candle sekarang */}
            {latest && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>Candle M15 ini</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: latest.color?.includes("bullish") ? "var(--accent-green)" : "var(--accent-red)" }}>
                  {latest.color?.includes("bullish_strong") ? "▲ Bull Strong" :
                   latest.color?.includes("bullish_weak")   ? "△ Bull Weak"   :
                   latest.color?.includes("bearish_strong") ? "▼ Bear Strong" :
                                                              "▽ Bear Weak"}
                </span>
              </div>
            )}

            <div style={{ fontSize: 9, color: "var(--text-muted)", fontStyle: "italic", paddingTop: 2 }}>
              SL / TP / Trailing dikelola EA MT5
            </div>
          </div>
        )}
      </div>

      {/* ── CARD 3: RIWAYAT SINYAL M15 ──────────────────────────────────── */}
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
        <div style={{ padding: "7px 14px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 6 }}>
          <Clock size={11} color="var(--text-muted)" />
          <span style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Riwayat Sinyal M15
          </span>
        </div>

        {history.length === 0 ? (
          <div style={{ padding: "14px", fontSize: 11, color: "var(--text-muted)", textAlign: "center", fontStyle: "italic" }}>
            Belum ada sinyal sejak sesi dibuka
          </div>
        ) : (
          <div>
            {history.map((h, i) => {
              const d    = new Date(h.time * 1000);
              const time = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
              const col  = h.dir === "buy" ? "var(--accent-green)" : "var(--accent-red)";
              return (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "7px 14px",
                  borderBottom: i < history.length - 1 ? "1px solid var(--border)" : "none",
                  opacity: Math.max(1 - i * 0.1, 0.3),
                }}>
                  <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)", width: 38 }}>{time}</span>
                  <span style={{ fontSize: 10, color: h.type === "arrow" ? "var(--accent-blue)" : "var(--text-muted)", width: 60, fontWeight: h.type === "arrow" ? 700 : 400 }}>
                    {h.type === "arrow" ? "⚡ Arrow" : "○ Circle"}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: col }}>
                    {h.dir === "buy" ? "BUY" : "SELL"}
                  </span>
                  {i === 0 && (
                    <span style={{ marginLeft: "auto", fontSize: 9, padding: "2px 6px", background: "rgba(255,255,255,0.06)", borderRadius: 3, color: "var(--text-muted)" }}>
                      terbaru
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
