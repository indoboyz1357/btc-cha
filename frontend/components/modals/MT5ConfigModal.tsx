"use client";

import { useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import { Eye, EyeOff, Wifi, WifiOff } from "lucide-react";

export default function MT5ConfigModal({ onClose }: { onClose: () => void }) {
  const { bridgeUrl, setBridgeUrl, mt5Login, mt5Password, mt5Server, setMt5Config, sendCommand, isConnected } = useAppStore();

  const [url, setUrl]         = useState(bridgeUrl);
  const [login, setLogin]     = useState(mt5Login);
  const [password, setPass]   = useState(mt5Password);
  const [server, setServer]   = useState(mt5Server);
  const [showPass, setShowP]  = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTest] = useState<string | null>(null);

  const testConnection = async () => {
    setTesting(true);
    setTest(null);
    try {
      const ws = new WebSocket(url);
      await new Promise<void>((resolve, reject) => {
        ws.onopen    = () => { setTest("● Connected"); ws.close(); resolve(); };
        ws.onerror   = () => reject(new Error("Cannot connect"));
        setTimeout(() => reject(new Error("Timeout")), 5000);
      });
    } catch (e: unknown) {
      setTest(`● ${e instanceof Error ? e.message : "Failed"}`);
    } finally {
      setTesting(false);
    }
  };

  const saveConnect = () => {
    setBridgeUrl(url);
    setMt5Config(login, password, server);
    sendCommand({ cmd: "reconnect_mt5", login: parseInt(login), password, server });
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()} style={{ padding: 20 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>🔌 MT5 CONNECTION CONFIG</h2>

        <div style={{ marginBottom: 12 }}>
          <label className="label">Bridge URL (WebSocket)</label>
          <input id="mt5-bridge-url" className="input" value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="ws://localhost:8765" />
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}>
            Ganti dengan Cloudflare URL untuk akses remote
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <label className="label">MT5 Login ID</label>
          <input id="mt5-login" className="input" value={login} onChange={(e) => setLogin(e.target.value)} />
        </div>

        <div style={{ marginBottom: 12 }}>
          <label className="label">MT5 Password</label>
          <div style={{ position: "relative" }}>
            <input id="mt5-password" className="input" type={showPass ? "text" : "password"}
              value={password} onChange={(e) => setPass(e.target.value)} style={{ paddingRight: 36 }} />
            <button className="btn-icon" style={{ position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)" }}
              onClick={() => setShowP(!showPass)}>
              {showPass ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label className="label">MT5 Server</label>
          <input id="mt5-server" className="input" value={server} onChange={(e) => setServer(e.target.value)} />
        </div>

        <div style={{ marginBottom: 16 }}>
          <button id="btn-test-connection" className="btn btn-ghost" style={{ width: "100%" }}
            onClick={testConnection} disabled={testing}>
            {testing ? "Testing..." : "🔍 TEST CONNECTION"}
          </button>
          {testResult && (
            <div style={{ marginTop: 6, fontSize: 11, color: testResult.includes("Connected") ? "var(--accent-green)" : "var(--accent-red)" }}>
              {testResult.includes("Connected") ? <Wifi size={11} style={{ display: "inline", marginRight: 4 }} /> : <WifiOff size={11} style={{ display: "inline", marginRight: 4 }} />}
              {testResult}
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button id="btn-mt5-cancel" className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>CANCEL</button>
          <button id="btn-mt5-save" className="btn btn-primary" style={{ flex: 1 }} onClick={saveConnect}>💾 SAVE & CONNECT</button>
        </div>
      </div>
    </div>
  );
}
