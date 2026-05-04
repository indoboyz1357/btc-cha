"use client";

import { useAppStore } from "@/store/useAppStore";
import { formatPrice } from "@/utils/formatters";
import type { PendingOrder } from "@/types";

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  waiting_trigger:    { label: "⏳ MENUNGGU TRIGGER...", color: "var(--text-muted)" },
  waiting_rejection:  { label: "🎯 TRIGGER KENA! MENUNGGU REJECTION...", color: "var(--accent-yellow)" },
  executed:           { label: "✅ ORDER TEREKSEKUSI", color: "var(--accent-green)" },
  timeout:            { label: "❌ TIMEOUT — dibatalkan", color: "var(--accent-red)" },
};

export default function PendingOrderCard({ order }: { order: PendingOrder }) {
  const { sendCommand } = useAppStore();
  const status = STATUS_MAP[order.status] || { label: order.status, color: "var(--text-muted)" };
  const isSell = order.type.includes("sell");

  return (
    <div className="card fade-in" style={{ margin: "4px 8px" }}>
      <div style={{ padding: "8px 12px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span className="mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>#{order.ticket}</span>
            <span className={`badge ${isSell ? "badge-red" : "badge-green"}`} style={{ fontSize: 10 }}>
              REJECTION {isSell ? "SELL" : "BUY"}
            </span>
          </div>
          <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{order.volume} lot</span>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 11 }}>
          <span style={{ color: "var(--text-muted)" }}>
            Trigger: <span className="mono" style={{ color: "var(--text-secondary)" }}>{formatPrice(order.trigger_price)}</span>
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            Entry: <span className="mono" style={{ color: "var(--text-secondary)" }}>{formatPrice(order.entry_price)}</span>
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            SL: <span className="mono" style={{ color: "var(--accent-red)" }}>{formatPrice(order.sl)}</span>
          </span>
        </div>

        <div style={{ fontSize: 10.5, color: status.color, marginBottom: 8 }}>{status.label}</div>

        <button id={`btn-cancel-order-${order.ticket}`} className="btn btn-ghost" style={{ width: "100%", fontSize: 10 }}
          onClick={() => sendCommand({ cmd: "cancel_order", ticket: order.ticket })}>
          Cancel Order
        </button>
      </div>
    </div>
  );
}
