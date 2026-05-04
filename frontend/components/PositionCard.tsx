"use client";

import { useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import { formatPrice } from "@/utils/formatters";
import type { Position } from "@/types";
import ModifySLModal from "./modals/ModifySLModal";

export default function PositionCard({ pos }: { pos: Position }) {
  const { sendCommand } = useAppStore();
  const [showModify, setShowModify] = useState(false);

  const isBuy      = pos.type === "buy";
  const profitColor = pos.profit >= 0 ? "var(--accent-green)" : "var(--accent-red)";
  const trailLabel = pos.trailing_status === "active" ? "TRAIL: AKTIF 🔥" : "TRAIL: STANDBY";
  const trailColor = pos.trailing_status === "active" ? "var(--accent-green)" : "var(--text-muted)";

  return (
    <>
      <div className="card fade-in" style={{
        margin: "4px 8px",
        border: `1px solid ${isBuy ? "rgba(0,208,132,0.25)" : "rgba(255,68,68,0.25)"}`,
        background: isBuy ? "rgba(0,208,132,0.03)" : "rgba(255,68,68,0.03)",
      }}>
        <div style={{ padding: "8px 12px" }}>
          {/* Top row */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <span className="mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>#{pos.ticket}</span>
              <span className={`badge ${isBuy ? "badge-green" : "badge-red"}`} style={{ fontSize: 10 }}>
                {isBuy ? "▲ BUY" : "▼ SELL"}
              </span>
              <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{pos.volume} lot</span>
            </div>
            <span style={{ fontSize: 9, color: trailColor }}>{trailLabel}</span>
          </div>

          {/* Prices */}
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <div>
              <div className="label">OPEN</div>
              <div className="mono" style={{ fontSize: 12 }}>{formatPrice(pos.open_price)}</div>
            </div>
            <div>
              <div className="label">SL</div>
              <div className="mono" style={{ fontSize: 12, color: "var(--accent-red)" }}>{formatPrice(pos.sl)}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="label">P/L</div>
              <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: profitColor }}>
                {pos.profit >= 0 ? "+" : ""}${pos.profit.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: "flex", gap: 6 }}>
            <button id={`btn-modify-sl-${pos.ticket}`} className="btn btn-ghost" style={{ flex: 1, fontSize: 10 }}
              onClick={() => setShowModify(true)}>
              Modify SL
            </button>
            <button id={`btn-close-${pos.ticket}`} className="btn btn-red" style={{ flex: 1, fontSize: 10 }}
              onClick={() => sendCommand({ cmd: "close_position", ticket: pos.ticket })}>
              Close
            </button>
          </div>
        </div>
      </div>

      {showModify && <ModifySLModal ticket={pos.ticket} currentSL={pos.sl} onClose={() => setShowModify(false)} />}
    </>
  );
}
