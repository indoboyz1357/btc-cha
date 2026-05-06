"use client";

import { useState } from "react";
import { Zap, Plug, BarChart2, Wifi, WifiOff } from "lucide-react";
import { useAppStore } from "@/store/useAppStore";
import { useShallow } from "zustand/react/shallow";
import { formatPrice, formatChange } from "@/utils/formatters";
import MT5ConfigModal from "./modals/MT5ConfigModal";

interface HeaderProps {
  onHistoryClick: () => void;
}

export default function Header({ onHistoryClick }: HeaderProps) {
  const [showMT5, setShowMT5] = useState(false);

  // ✅ Hanya subscribe field yang dipakai Header — tick update tidak trigger re-render komponen lain
  const { currentPrice, priceChange, priceChangePercent, currentSession, isConnected, autoTrading } =
    useAppStore(
      useShallow((s) => ({
        currentPrice:        s.currentPrice,
        priceChange:         s.priceChange,
        priceChangePercent:  s.priceChangePercent,
        currentSession:      s.currentSession,
        isConnected:         s.isConnected,
        autoTrading:         s.autoTrading,
      }))
    );

  const priceDir = priceChange >= 0 ? "price-up" : "price-down";

  return (
    <>
      <header style={{
        height: 60,
        background: "var(--bg-surface)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        padding: "0 16px",
        gap: 12,
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginRight: 8 }}>
          <Zap size={16} color="var(--accent-yellow)" />
          <span style={{ fontWeight: 700, fontSize: 13, letterSpacing: "0.04em", whiteSpace: "nowrap" }}>
            SIGNAL OMEGA V2
          </span>
        </div>

        {/* Price block */}
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginRight: 12 }}>
          <span className={`mono ${priceDir}`} style={{ fontSize: 18, fontWeight: 700 }}>
            ${formatPrice(currentPrice, 2)}
          </span>
          <span className={`mono ${priceDir}`} style={{ fontSize: 11 }}>
            {formatChange(priceChange, priceChangePercent)}
          </span>
        </div>

        {/* Session */}
        <div style={{
          padding: "3px 10px",
          background: "rgba(59,130,246,0.1)",
          border: "1px solid rgba(59,130,246,0.3)",
          borderRadius: "99px",
          fontSize: 11,
          color: "var(--accent-blue)",
          whiteSpace: "nowrap",
        }}>
          🕐 {currentSession}
        </div>

        {/* Connection */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {isConnected
            ? <><Wifi size={12} color="var(--accent-green)" /> <span className="pulse" style={{ color: "var(--accent-green)", fontSize: 10 }}>CONNECTED</span></>
            : <><WifiOff size={12} color="var(--accent-red)" /> <span style={{ color: "var(--accent-red)", fontSize: 10 }}>DISCONNECTED</span></>
          }
        </div>

        {/* Auto trading indicator */}
        {autoTrading.enabled && (
          <div style={{
            padding: "2px 8px",
            background: "rgba(0,208,132,0.1)",
            border: "1px solid var(--accent-green)",
            borderRadius: "99px",
            fontSize: 10,
            color: "var(--accent-green)",
            fontWeight: 600,
          }}>
            🤖 AUTO: ON
          </div>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Action buttons */}
        <button id="btn-mt5-config" className="btn btn-ghost" onClick={() => setShowMT5(true)}
          style={{ fontSize: 11 }}>
          <Plug size={13} /> MT5
        </button>

        <button id="btn-history" className="btn btn-ghost" onClick={onHistoryClick}
          style={{ fontSize: 11 }}>
          <BarChart2 size={13} /> HISTORY
        </button>
      </header>

      {showMT5 && <MT5ConfigModal onClose={() => setShowMT5(false)} />}
    </>
  );
}
