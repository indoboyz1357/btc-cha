"use client";

import { useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import { formatPrice } from "@/utils/formatters";

interface Props {
  ticket: number;
  currentSL: number;
  onClose: () => void;
}

export default function ModifySLModal({ ticket, currentSL, onClose }: Props) {
  const { sendCommand } = useAppStore();
  const [newSL, setNewSL] = useState(currentSL.toString());

  const apply = () => {
    sendCommand({ cmd: "modify_sl", ticket, sl: parseFloat(newSL) });
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()} style={{ padding: 20, maxWidth: 340 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Modify Stop Loss</h2>
        <div style={{ marginBottom: 6, fontSize: 11, color: "var(--text-muted)" }}>
          Ticket #{ticket} · SL saat ini: <span className="mono" style={{ color: "var(--accent-red)" }}>{formatPrice(currentSL)}</span>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label className="label">SL Baru</label>
          <input id="modify-sl-input" className="input" type="number" step="0.01" value={newSL}
            onChange={(e) => setNewSL(e.target.value)} autoFocus />
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button id="btn-modify-sl-cancel" className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>CANCEL</button>
          <button id="btn-modify-sl-apply" className="btn btn-primary" style={{ flex: 1 }} onClick={apply}>✓ APPLY</button>
        </div>
      </div>
    </div>
  );
}
