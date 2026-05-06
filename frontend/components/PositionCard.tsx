"use client";

import { useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import { formatPrice } from "@/utils/formatters";
import type { Position } from "@/types";
import ModifySLModal from "./modals/ModifySLModal";

function formatDuration(iso: string): string {
  try {
    const ms = Date.now() - new Date(iso).getTime();
    if (ms < 0) return "0m";
    const h = Math.floor(ms / 3600000);
    const m = Math.floor((ms % 3600000) / 60000);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  } catch { return "—"; }
}

export default function PositionCard({ pos }: { pos: Position }) {
  const { sendCommand, currentPrice } = useAppStore();
  const [showModify, setShowModify] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);

  const isBuy       = pos.type === "buy";
  const profitPos   = pos.profit >= 0;
  const profitColor = profitPos ? "#00d084" : "#ff4444";
  const accent      = isBuy ? "#00d084" : "#ff4444";
  const accentRgb   = isBuy ? "0,208,132" : "255,68,68";
  const curPrice    = currentPrice || pos.open_price;
  const pctChange   = ((curPrice - pos.open_price) / pos.open_price * 100) * (isBuy ? 1 : -1);
  const tpDist      = pos.tp ? Math.abs(pos.tp - pos.open_price) : 0;
  const curDist     = Math.abs(curPrice - pos.open_price);
  const progressPct = tpDist > 0 ? Math.min(100, Math.max(0, (curDist / tpDist) * 100)) : 0;

  return (
    <>
      <div className="fade-in" style={{
        margin: "8px 10px",
        borderRadius: 12,
        overflow: "hidden",
        border: `1px solid rgba(${accentRgb},0.25)`,
        background: `linear-gradient(135deg, rgba(${accentRgb},0.05) 0%, rgba(0,0,0,0.4) 100%)`,
        boxShadow: `0 0 24px rgba(${accentRgb},0.08), inset 0 1px 0 rgba(255,255,255,0.04)`,
      }}>

        {/* HEADER */}
        <div style={{
          padding: "10px 14px 9px",
          borderBottom: `1px solid rgba(${accentRgb},0.15)`,
          background: `rgba(${accentRgb},0.06)`,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "4px 14px", borderRadius: 6,
              background: `rgba(${accentRgb},0.15)`,
              border: `1px solid rgba(${accentRgb},0.4)`,
              boxShadow: `0 0 12px rgba(${accentRgb},0.2)`,
            }}>
              <span style={{ fontSize: 10, color: accent }}>{isBuy ? "▲" : "▼"}</span>
              <span style={{
                fontSize: 16, fontWeight: 900, color: accent,
                letterSpacing: "0.1em",
                textShadow: `0 0 20px rgba(${accentRgb},0.8)`,
              }}>{isBuy ? "BUY" : "SELL"}</span>
            </div>
            <span style={{
              fontSize: 11, fontWeight: 600, color: "var(--text-muted)",
              background: "rgba(255,255,255,0.04)", padding: "3px 8px",
              borderRadius: 4, border: "1px solid var(--border)",
            }}>{pos.volume} lot</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 9, color: "var(--text-muted)" }}>⏱ {formatDuration(pos.open_time)}</span>
            <span style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>#{pos.ticket}</span>
          </div>
        </div>

        {/* PRICE GRID */}
        <div style={{ padding: "12px 14px 8px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 16px" }}>
          <div>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 3, letterSpacing: "0.08em" }}>ENTRY</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700 }}>{formatPrice(pos.open_price)}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 3, letterSpacing: "0.08em" }}>CURRENT</div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 5 }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700 }}>{formatPrice(curPrice)}</span>
              <span style={{
                fontSize: 9, fontWeight: 700,
                color: pctChange >= 0 ? "#00d084" : "#ff4444",
                background: pctChange >= 0 ? "rgba(0,208,132,0.1)" : "rgba(255,68,68,0.1)",
                padding: "1px 5px", borderRadius: 3,
              }}>{pctChange >= 0 ? "+" : ""}{pctChange.toFixed(2)}%</span>
            </div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 3, letterSpacing: "0.08em" }}>STOP LOSS</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "#ff6666" }}>{pos.sl ? formatPrice(pos.sl) : "—"}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 3, letterSpacing: "0.08em" }}>TAKE PROFIT</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "#00d084" }}>{pos.tp ? formatPrice(pos.tp) : "—"}</div>
          </div>
        </div>

        {/* PROGRESS */}
        {tpDist > 0 && (
          <div style={{ padding: "0 14px 10px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ fontSize: 9, color: "var(--text-muted)" }}>SL ←</span>
              <span style={{ fontSize: 9, fontWeight: 700, color: accent }}>{progressPct.toFixed(0)}% to TP</span>
              <span style={{ fontSize: 9, color: "var(--text-muted)" }}>→ TP</span>
            </div>
            <div style={{ height: 5, borderRadius: 99, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
              <div style={{
                height: "100%", width: `${progressPct}%`,
                background: `linear-gradient(90deg, rgba(${accentRgb},0.4), ${accent})`,
                borderRadius: 99, transition: "width 0.6s ease",
                boxShadow: `0 0 8px rgba(${accentRgb},0.6)`,
              }} />
            </div>
          </div>
        )}

        {/* FOOTER */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "10px 14px",
          borderTop: `1px solid rgba(${accentRgb},0.12)`,
          background: "rgba(0,0,0,0.25)",
        }}>
          <div>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginBottom: 2, letterSpacing: "0.08em" }}>UNREALIZED P/L</div>
            <div style={{
              fontFamily: "var(--font-mono)", fontSize: 20, fontWeight: 900, color: profitColor,
              textShadow: profitPos ? "0 0 20px rgba(0,208,132,0.6)" : "0 0 20px rgba(255,68,68,0.6)",
            }}>{pos.profit >= 0 ? "+" : ""}${pos.profit.toFixed(2)}</div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={() => setShowModify(true)} style={{
              fontSize: 10, padding: "7px 14px", borderRadius: 6, cursor: "pointer", fontWeight: 600,
              background: "rgba(59,130,246,0.1)", color: "#3b82f6",
              border: "1px solid rgba(59,130,246,0.3)",
            }}>✏ SL</button>
            {confirmClose ? (
              <>
                <button onClick={() => setConfirmClose(false)} style={{
                  fontSize: 10, padding: "7px 10px", borderRadius: 6, cursor: "pointer", fontWeight: 600,
                  background: "rgba(255,255,255,0.05)", color: "var(--text-muted)",
                  border: "1px solid var(--border)",
                }}>✕</button>
                <button onClick={() => { sendCommand({ cmd: "close_position", ticket: pos.ticket }); setConfirmClose(false); }} style={{
                  fontSize: 10, padding: "7px 12px", borderRadius: 6, cursor: "pointer", fontWeight: 800,
                  background: "rgba(255,68,68,0.25)", color: "#ff4444",
                  border: "2px solid #ff4444",
                  boxShadow: "0 0 10px rgba(255,68,68,0.4)",
                }}>⚠ YA, CLOSE!</button>
              </>
            ) : (
              <button onClick={() => setConfirmClose(true)} style={{
                fontSize: 10, padding: "7px 14px", borderRadius: 6, cursor: "pointer", fontWeight: 700,
                background: "rgba(255,68,68,0.12)", color: "#ff4444",
                border: "1px solid rgba(255,68,68,0.35)",
              }}>✕ CLOSE</button>
            )}
          </div>
        </div>
      </div>
      {showModify && <ModifySLModal ticket={pos.ticket} currentSL={pos.sl} onClose={() => setShowModify(false)} />}
    </>
  );
}
