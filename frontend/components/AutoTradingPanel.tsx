"use client";

import { useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import Toggle from "./ui/Toggle";
import AutoTradingLog from "./AutoTradingLog";

const SESSIONS = ["london", "new_york", "sydney", "tokyo"];
const SESSION_LABEL: Record<string, string> = { london: "London", new_york: "New York", sydney: "Sydney", tokyo: "Tokyo" };

export default function AutoTradingPanel() {
  const { autoTrading, updateAutoStatus, sendCommand } = useAppStore();
  const [localCfg, setLocalCfg] = useState({
    scan_interval:   autoTrading.scan_interval,
    min_confidence:  autoTrading.min_confidence,
    lot_size:        autoTrading.lot_size,
    max_positions:   autoTrading.max_positions,
    max_daily_loss:  autoTrading.max_daily_loss,
  });

  const isOn       = autoTrading.enabled;
  const dailyColor = autoTrading.daily_loss >= autoTrading.max_daily_loss * 0.8
    ? "var(--accent-red)" : "var(--accent-green)";

  const toggleAuto = () => {
    const next = !isOn;
    updateAutoStatus({ enabled: next });
    sendCommand({ cmd: "set_auto_trading", enabled: next });
  };

  const handleSave = () => {
    updateAutoStatus(localCfg);
    sendCommand({ cmd: "set_auto_trading", ...localCfg });
  };

  const toggleSession = (s: string) => {
    const filter = autoTrading.session_filter.includes(s)
      ? autoTrading.session_filter.filter((x) => x !== s)
      : [...autoTrading.session_filter, s];
    updateAutoStatus({ session_filter: filter });
  };

  return (
    <div className="card" style={{ margin: 8 }}>
      <div className="section-header">
        <span>🤖 AUTO TRADING</span>
      </div>

      {/* Main toggle */}
      <div style={{ padding: "14px", display: "flex", flexDirection: "column", alignItems: "center", gap: 8, borderBottom: "1px solid var(--border)" }}>
        <div
          id="auto-trading-toggle-area"
          onClick={toggleAuto}
          style={{
            width: "100%",
            padding: "12px 20px",
            borderRadius: "var(--radius-md)",
            border: `2px solid ${isOn ? "var(--accent-green)" : "var(--border-light)"}`,
            background: isOn ? "rgba(0,208,132,0.08)" : "var(--bg-surface)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            cursor: "pointer",
            transition: "all 0.2s",
          }}
        >
          <span style={{ fontWeight: 700, fontSize: 13, color: isOn ? "var(--accent-green)" : "var(--text-secondary)" }}>
            {isOn ? "● AUTO TRADING ON" : "○ AUTO TRADING OFF"}
          </span>
          <Toggle checked={isOn} onChange={toggleAuto} id="toggle-auto" />
        </div>
        <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
          {isOn ? "Auto trading aktif — settings terkunci" : "Klik untuk mengaktifkan"}
        </span>
      </div>

      {/* Settings */}
      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8, borderBottom: "1px solid var(--border)" }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 2 }}>Settings</div>

        {[
          { key: "lot_size",        label: "Lot Size",        suffix: "lot",  step: 0.01 },
          { key: "scan_interval",   label: "Scan Interval",   suffix: "det",  step: 10 },
          { key: "min_confidence",  label: "Min Confidence",  suffix: "%",    step: 5 },
          { key: "max_positions",   label: "Max Posisi",      suffix: "",     step: 1 },
          { key: "max_daily_loss",  label: "Max Loss/Hari",   suffix: "$",    step: 1 },
        ].map(({ key, label, suffix, step }) => (
          <div key={key} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <label className="label" style={{ margin: 0, whiteSpace: "nowrap" }}>{label}</label>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <input
                id={`auto-${key}`}
                type="number"
                disabled={isOn}
                step={step}
                value={localCfg[key as keyof typeof localCfg]}
                onChange={(e) => setLocalCfg((p) => ({ ...p, [key]: parseFloat(e.target.value) || 0 }))}
                className="input"
                style={{ width: 72, textAlign: "right", opacity: isOn ? 0.5 : 1 }}
              />
              {suffix && <span style={{ fontSize: 10, color: "var(--text-muted)", whiteSpace: "nowrap" }}>{suffix}</span>}
            </div>
          </div>
        ))}

        {/* Direction */}
        <div>
          <div className="label">Arah Trading</div>
          <div style={{ display: "flex", gap: 8 }}>
            {[
              { key: "allow_buy",  label: "BUY",  color: "var(--accent-green)" },
              { key: "allow_sell", label: "SELL", color: "var(--accent-red)" },
            ].map(({ key, label, color }) => {
              const val = autoTrading[key as keyof typeof autoTrading] as boolean;
              return (
                <button key={key} id={`auto-${key}`}
                  disabled={isOn}
                  className="btn btn-ghost"
                  style={{
                    fontSize: 11, flex: 1,
                    borderColor: val ? color : "var(--border-light)",
                    color:       val ? color : "var(--text-muted)",
                    opacity:     isOn ? 0.6 : 1,
                  }}
                  onClick={() => updateAutoStatus({ [key]: !val })}
                >
                  {val ? "✓" : "○"} {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Session filter */}
        <div>
          <div className="label">Session Filter</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {SESSIONS.map((s) => {
              const active = autoTrading.session_filter.includes(s);
              return (
                <button key={s} id={`session-${s}`}
                  disabled={isOn}
                  className="btn btn-ghost"
                  style={{
                    fontSize: 10, padding: "3px 8px",
                    borderColor: active ? "var(--accent-blue)" : "var(--border-light)",
                    color:       active ? "var(--accent-blue)" : "var(--text-muted)",
                    opacity:     isOn ? 0.6 : 1,
                  }}
                  onClick={() => toggleSession(s)}
                >
                  {active ? "✓" : "○"} {SESSION_LABEL[s]}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Status */}
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 6 }}>Status</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <StatusRow label="Daily P/L" value={`-$${autoTrading.daily_loss.toFixed(2)} / $${autoTrading.max_daily_loss}`} color={dailyColor} />
          <StatusRow label="Auto trades" value={`${autoTrading.trades_today} hari ini`} />
          <StatusRow label="Last signal" value={autoTrading.last_signal || "—"} />
        </div>
      </div>

      {/* Save + Log */}
      <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
        <button id="btn-save-auto-settings" className="btn btn-primary" disabled={isOn} style={{ fontSize: 11 }} onClick={handleSave}>
          💾 SIMPAN SETTINGS
        </button>
      </div>

      <AutoTradingLog />
    </div>
  );
}

function StatusRow({ label, value, color = "var(--text-secondary)" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span className="mono" style={{ color }}>{value}</span>
    </div>
  );
}
