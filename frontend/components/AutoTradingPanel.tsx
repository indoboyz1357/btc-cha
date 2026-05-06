"use client";

import { useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import Toggle from "./ui/Toggle";
import AutoTradingLog from "./AutoTradingLog";

const SESSIONS = ["london", "new_york", "sydney", "tokyo"];
const SESSION_LABEL: Record<string, string> = {
  london: "London", new_york: "New York", sydney: "Sydney", tokyo: "Tokyo",
};

export default function AutoTradingPanel() {
  const { autoTrading, updateAutoStatus, sendCommand } = useAppStore();

  const [openSection, setOpenSection] = useState<string>("strategy");
  const [localCfg, setLocalCfg] = useState({
    scan_interval:        autoTrading.scan_interval,
    lot_size:             autoTrading.lot_size,
    max_positions:        autoTrading.max_positions,
    max_daily_loss:       autoTrading.max_daily_loss,
  });

  const isOn = autoTrading.enabled;
  const dailyPct = autoTrading.max_daily_loss > 0
    ? Math.min((autoTrading.daily_loss / autoTrading.max_daily_loss) * 100, 100)
    : 0;
  const dailyColor = dailyPct >= 80 ? "var(--accent-red)" : dailyPct >= 50 ? "var(--accent-yellow)" : "var(--accent-green)";

  const toggleAuto = () => {
    const next = !isOn;
    updateAutoStatus({ enabled: next });
    sendCommand({ cmd: "set_auto_trading", enabled: next });
  };

  const handleSave = () => {
    updateAutoStatus(localCfg);
    sendCommand({
      cmd: "set_auto_trading",
      ...localCfg,
      logic_timeframe:      autoTrading.logic_timeframe,
      allow_buy:            autoTrading.allow_buy,
      allow_sell:           autoTrading.allow_sell,
      follow_trend:         autoTrading.follow_trend,
      session_filter:       autoTrading.session_filter,
    });
  };

  const setEnum = (key: string, val: unknown) => {
    if (isOn) return;
    updateAutoStatus({ [key]: val } as Partial<typeof autoTrading>);
  };

  const toggleSession = (s: string) => {
    if (isOn) return;
    const filter = autoTrading.session_filter.includes(s)
      ? autoTrading.session_filter.filter((x) => x !== s)
      : [...autoTrading.session_filter, s];
    updateAutoStatus({ session_filter: filter });
  };

  const allSessionsActive = SESSIONS.every((s) => autoTrading.session_filter.includes(s));

  const SectionHead = ({ id, icon, label }: { id: string; icon: string; label: string }) => (
    <button
      onClick={() => setOpenSection(openSection === id ? "" : id)}
      style={{
        width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "8px 12px", background: openSection === id ? "rgba(38,165,228,0.08)" : "rgba(0,0,0,0.2)",
        border: "none", borderBottom: "1px solid var(--border)",
        color: openSection === id ? "#26a5e4" : "var(--text-muted)",
        fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const,
        letterSpacing: "0.07em", cursor: "pointer",
      }}
    >
      <span>{icon} {label}</span>
      <span style={{ fontSize: 11, opacity: 0.7 }}>{openSection === id ? "▲" : "▼"}</span>
    </button>
  );

  const OptBtn = ({
    active, label, desc, color = "#26a5e4", onClick,
  }: { active: boolean; label: string; desc?: string; color?: string; onClick: () => void }) => (
    <button
      disabled={isOn}
      onClick={onClick}
      style={{
        flex: 1, padding: "7px 6px", borderRadius: 5,
        border: `1px solid ${active ? color : "var(--border)"}`,
        background: active ? `${color}18` : "transparent",
        color: active ? color : "var(--text-muted)",
        cursor: isOn ? "not-allowed" : "pointer",
        opacity: isOn ? 0.55 : 1,
        textAlign: "center" as const,
      }}
    >
      <div style={{ fontSize: 11, fontWeight: active ? 700 : 400 }}>{active ? "● " : "○ "}{label}</div>
      {desc && <div style={{ fontSize: 9, marginTop: 2, color: active ? color : "var(--text-muted)", opacity: 0.8 }}>{desc}</div>}
    </button>
  );

  return (
    <div className="card" style={{ margin: 8 }}>
      <div className="section-header"><span>🤖 AUTO TRADING</span></div>

      {/* ── MASTER TOGGLE ────────────────────────────────────── */}
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border)" }}>
        <div
          onClick={toggleAuto}
          style={{
            padding: "11px 16px", borderRadius: 6, cursor: "pointer",
            border: `2px solid ${isOn ? "var(--accent-green)" : "var(--border-light)"}`,
            background: isOn ? "rgba(0,208,132,0.08)" : "var(--bg-surface)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            transition: "all 0.2s",
          }}
        >
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: isOn ? "var(--accent-green)" : "var(--text-secondary)" }}>
              {isOn ? "● AUTO TRADING ON" : "○ AUTO TRADING OFF"}
            </div>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>
              {isOn ? `Scanning tiap ${autoTrading.scan_interval}s — settings terkunci` : "Klik untuk aktifkan"}
            </div>
          </div>
          <Toggle checked={isOn} onChange={toggleAuto} id="toggle-auto-main" />
        </div>

        {/* Daily loss progress */}
        <div style={{ marginTop: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3, fontSize: 10 }}>
            <span style={{ color: "var(--text-muted)" }}>Daily Loss</span>
            <span style={{ color: dailyColor, fontWeight: 700 }}>
              ${(autoTrading.daily_loss || 0).toFixed(2)} / ${(autoTrading.max_daily_loss || 5).toFixed(0)}
            </span>
          </div>
          <div style={{ height: 4, borderRadius: 99, background: "var(--border-light)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${dailyPct}%`, background: dailyColor, borderRadius: 99, transition: "width 0.4s" }} />
          </div>
        </div>

        {/* Status row */}
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 10 }}>
          <span style={{ color: "var(--text-muted)" }}>
            HA Trend: <span style={{ color: autoTrading.ha_trend === "BULLISH" ? "var(--accent-green)" : autoTrading.ha_trend === "BEARISH" ? "var(--accent-red)" : "var(--text-muted)", fontWeight: 700 }}>
              {autoTrading.ha_trend || "—"}
            </span>
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            Trades: <span style={{ color: "var(--text-secondary)", fontWeight: 700 }}>{autoTrading.trades_today || 0}</span>
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            Equity: <span style={{ color: "#e8eaed", fontWeight: 700 }}>
              {autoTrading.equity > 0 ? `$${autoTrading.equity.toFixed(0)}` : "—"}
            </span>
          </span>
        </div>
      </div>

      {/* SECTION 1: STRATEGY */}
      <SectionHead id="strategy" icon="📐" label="1. Strategy" />
      {openSection === "strategy" && (
        <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 10 }}>

          {/* Trading Direction */}
          <div>
            <div className="label">Trading Direction</div>
            <div style={{ display: "flex", gap: 6 }}>
              <OptBtn
                active={autoTrading.follow_trend}
                label="Follow Trend" desc="Circle searah tren — langsung entry" color="var(--accent-green)"
                onClick={() => setEnum("follow_trend", true)}
              />
              <OptBtn
                active={!autoTrading.follow_trend}
                label="Both" desc="Circle searah=entry, Melawan=butuh Arrow" color="#26a5e4"
                onClick={() => { setEnum("follow_trend", false); updateAutoStatus({ allow_buy: true, allow_sell: true }); }}
              />
            </div>
          </div>

          {/* Session filter */}
          <div>
            <div className="label">Session Filter</div>
            <div style={{ display: "flex", flexWrap: "wrap" as const, gap: 5 }}>
              <button key="24h" disabled={isOn}
                onClick={() => {
                  if (isOn) return;
                  if (allSessionsActive) {
                    updateAutoStatus({ session_filter: [] });
                  } else {
                    updateAutoStatus({ session_filter: [...SESSIONS] });
                  }
                }}
                style={{
                  padding: "4px 10px", fontSize: 10, borderRadius: 4,
                  border: `1px solid ${allSessionsActive ? "var(--accent-green)" : "var(--border-light)"}`,
                  background: allSessionsActive ? "rgba(0,208,132,0.1)" : "transparent",
                  color: allSessionsActive ? "var(--accent-green)" : "var(--text-muted)",
                  cursor: isOn ? "not-allowed" : "pointer", opacity: isOn ? 0.55 : 1,
                  fontWeight: 700,
                }}>
                {allSessionsActive ? "✓ 24H" : "○ 24H"}
              </button>
              {SESSIONS.map((s) => {
                const active = autoTrading.session_filter.includes(s);
                return (
                  <button key={s} disabled={isOn}
                    onClick={() => toggleSession(s)}
                    style={{
                      padding: "4px 10px", fontSize: 10, borderRadius: 4,
                      border: `1px solid ${active ? "#26a5e4" : "var(--border-light)"}`,
                      background: active ? "rgba(38,165,228,0.12)" : "transparent",
                      color: active ? "#26a5e4" : "var(--text-muted)",
                      cursor: isOn ? "not-allowed" : "pointer", opacity: isOn ? 0.55 : 1,
                    }}>
                    {active ? "✓" : "○"} {SESSION_LABEL[s]}
                  </button>
                );
              })}
            </div>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 4 }}>
              {allSessionsActive ? "24 jam non-stop — semua sesi aktif" : "Kustom: hanya sesi terpilih"}
            </div>
          </div>

          {/* Scan interval */}
          <div>
            <div className="label">Scan Interval (detik)</div>
            <input type="number" disabled={isOn} step={10} min={10} max={300}
              value={localCfg.scan_interval}
              onChange={(e) => setLocalCfg(p => ({ ...p, scan_interval: parseInt(e.target.value) || 30 }))}
              className="input" style={{ opacity: isOn ? 0.5 : 1 }} />
          </div>
        </div>
      )}

      {/* SECTION 2: RISK */}
      <SectionHead id="risk" icon="🎯" label="2. Risk Management" />
      {openSection === "risk" && (
        <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: 10 }}>

          {/* Lot + Max positions */}
          <div style={{ display: "flex", gap: 8 }}>
            <div style={{ flex: 1 }}>
              <div className="label">Lot Size</div>
              <input type="number" disabled={isOn} step={0.01} min={0.01}
                value={localCfg.lot_size}
                onChange={(e) => setLocalCfg(p => ({ ...p, lot_size: parseFloat(e.target.value) || 0.01 }))}
                className="input" style={{ opacity: isOn ? 0.5 : 1 }} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="label">Max Posisi</div>
              <input type="number" disabled={isOn} step={1} min={1} max={10}
                value={localCfg.max_positions}
                onChange={(e) => setLocalCfg(p => ({ ...p, max_positions: parseInt(e.target.value) || 2 }))}
                className="input" style={{ opacity: isOn ? 0.5 : 1 }} />
            </div>
          </div>

          {/* Max daily loss */}
          <div>
            <div className="label">Max Daily Loss ($)</div>
            <input type="number" disabled={isOn} step={1} min={1}
              value={localCfg.max_daily_loss}
              onChange={(e) => setLocalCfg(p => ({ ...p, max_daily_loss: parseFloat(e.target.value) || 5 }))}
              className="input" style={{ opacity: isOn ? 0.5 : 1 }} />
          </div>
        </div>
      )}

      {/* ── SAVE BUTTON ──────────────────────────────────────── */}
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border)" }}>
        <button
          className="btn btn-primary"
          disabled={isOn}
          style={{ width: "100%", fontSize: 11, opacity: isOn ? 0.5 : 1 }}
          onClick={handleSave}
        >
          💾 SIMPAN SETTINGS
        </button>
        {isOn && (
          <div style={{ fontSize: 9, color: "var(--text-muted)", textAlign: "center", marginTop: 4 }}>
            Matikan Auto Trading untuk mengubah settings
          </div>
        )}
      </div>

      {/* ── LOG ──────────────────────────────────────────────── */}
      <AutoTradingLog />
    </div>
  );
}
