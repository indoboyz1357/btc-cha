"use client";

import { useState } from "react";
import { useAppStore } from "@/store/useAppStore";
import { Eye, EyeOff } from "lucide-react";

const MODELS = [
  { id: "deepseek/deepseek-chat-v3-5",   label: "🔥 DeepSeek V3 Flash",    desc: "Tercepat & Termurah" },
  { id: "anthropic/claude-sonnet-4-6",   label: "🔴 Claude Sonnet 4.6",    desc: "Analisis Terbaik" },
  { id: "google/gemini-2.5-pro-preview", label: "⭐ Gemini 2.5 Pro",       desc: "Benchmark Tertinggi" },
  { id: "openai/gpt-4o",                 label: "💎 GPT-4o",               desc: "Serbaguna" },
];

export default function AISetupModal({ onClose }: { onClose: () => void }) {
  const { openRouterKey, selectedModel, setOpenRouterKey, setSelectedModel } = useAppStore();
  const [key, setKey]       = useState(openRouterKey);
  const [model, setModel]   = useState(selectedModel);
  const [showKey, setShow]  = useState(false);

  const save = () => {
    setOpenRouterKey(key);
    setSelectedModel(model);
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()} style={{ padding: 20 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: "var(--text-primary)" }}>
          ⚙ AI CONFIG — OpenRouter API
        </h2>

        <div style={{ marginBottom: 14 }}>
          <label className="label">OpenRouter API Key</label>
          <div style={{ position: "relative" }}>
            <input id="ai-api-key" className="input" type={showKey ? "text" : "password"}
              value={key} onChange={(e) => setKey(e.target.value)}
              placeholder="sk-or-v1-xxxxxxxxxxxx"
              style={{ paddingRight: 36 }}
            />
            <button className="btn-icon" style={{ position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)" }}
              onClick={() => setShow(!showKey)}>
              {showKey ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}>
            Daftar gratis di{" "}
            <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer" style={{ color: "var(--accent-blue)" }}>
              openrouter.ai/keys
            </a>
          </div>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label className="label">AI Model</label>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {MODELS.map((m) => (
              <div key={m.id} id={`model-opt-${m.id.replace(/\//g, "-")}`}
                onClick={() => setModel(m.id)}
                style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "8px 12px", borderRadius: "var(--radius-sm)", cursor: "pointer",
                  border: `1px solid ${model === m.id ? "var(--accent-blue)" : "var(--border)"}`,
                  background: model === m.id ? "rgba(59,130,246,0.08)" : "var(--bg-surface)",
                  transition: "all 0.15s",
                }}
              >
                <span style={{ fontSize: 12, fontWeight: model === m.id ? 600 : 400 }}>{m.label}</span>
                <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{m.desc}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button id="btn-ai-setup-cancel" className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>CANCEL</button>
          <button id="btn-ai-setup-save" className="btn btn-primary" style={{ flex: 1 }} onClick={save}>💾 SAVE</button>
        </div>
      </div>
    </div>
  );
}
