"use client";

/**
 * useSignalVoice
 * =============
 * Voice alert elegan untuk sinyal BUY/SELL dari M15.
 *
 * Welcome: dipanggil langsung dari useMT5Bridge via window event
 * BUY/SELL: hanya untuk sinyal BARU (tidak fire saat loading)
 * Cooldown: 10 detik antar alert sinyal
 */

import { useEffect, useRef } from "react";
import { useAppStore } from "@/store/useAppStore";
import { useShallow } from "zustand/react/shallow";

// ────────────────────────────────────────────────────────────
// Voice Engine
// ────────────────────────────────────────────────────────────

function pickBestVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  const priority = [
    "Microsoft Ryan Online (Natural) - English (United Kingdom)",
    "Microsoft Guy Online (Natural) - English (United States)",
    "Microsoft Davis Online (Natural) - English (United States)",
    "Google UK English Male",
    "Microsoft Mark - English (United States)",
    "Microsoft David Desktop - English (United States)",
    "Alex",
    "Daniel",
    "Google US English",
  ];
  for (const name of priority) {
    const v = voices.find((vx) => vx.name === name);
    if (v) return v;
  }
  return voices.find((v) => v.lang.startsWith("en")) ?? voices[0];
}

function speak(text: string, opts: { pitch?: number; rate?: number; volume?: number }) {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utter    = new SpeechSynthesisUtterance(text);
  utter.pitch    = opts.pitch  ?? 0.82;
  utter.rate     = opts.rate   ?? 0.84;
  utter.volume   = opts.volume ?? 1.0;
  const voice    = pickBestVoice(window.speechSynthesis.getVoices());
  if (voice) utter.voice = voice;
  window.speechSynthesis.speak(utter);
}

function playTone(type: "buy" | "sell") {
  try {
    const ctx  = new (window.AudioContext || (window as any).webkitAudioContext)();
    const freq = type === "buy" ? 528 : 340;
    const playBeep = (t: number) => {
      const osc  = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(0.35, t + 0.05);
      gain.gain.linearRampToValueAtTime(0, t + 0.22);
      osc.start(t); osc.stop(t + 0.3);
    };
    const now = ctx.currentTime;
    playBeep(now);
    playBeep(now + 0.28);
    setTimeout(() => ctx.close(), 2000);
  } catch { /* silent */ }
}

// ────────────────────────────────────────────────────────────
// Custom event — dipanggil dari useMT5Bridge saat ws.onopen
// ────────────────────────────────────────────────────────────
export const BRIDGE_CONNECTED_EVENT = "bridge:connected";

// ────────────────────────────────────────────────────────────
const COOLDOWN_MS        = 10_000;
const COOLDOWN_CIRCLE_MS =  8_000; // circle lebih pendek cooldown-nya

// Tipe sinyal lebih granular
type SignalState =
  | "init"
  | "none"
  | "circle_buy"
  | "circle_sell"
  | "arrow_buy"
  | "arrow_sell";

// ────────────────────────────────────────────────────────────
export function useSignalVoice() {
  const { crystalHA, trendCards } = useAppStore(
    useShallow((s) => ({
      crystalHA:  s.crystalHA,
      trendCards: s.trendCards,
    }))
  );

  const lastSignalRef    = useRef<SignalState>("init");
  const lastAlertRef     = useRef<number>(0);
  const welcomePlayedRef = useRef(false);

  // ── Load voices async ──────────────────────────────────
  useEffect(() => {
    if (typeof window === "undefined") return;
    const tryLoad = () => { window.speechSynthesis.getVoices(); };
    tryLoad();
    window.speechSynthesis.addEventListener("voiceschanged", tryLoad);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", tryLoad);
  }, []);

  // ── Welcome: play saat user pertama interaksi + bridge sudah connect ──
  // Browser Chrome/Edge BLOCK audio sampai ada gesture (klik/keydown).
  // Strategi: simpan flag "bridge connected", lalu play di gesture pertama.
  const bridgeReadyRef = useRef(false);

  useEffect(() => {
    // Saat bridge connect → set flag
    const onBridgeConnect = () => {
      bridgeReadyRef.current = true;
      // Coba langsung play (works kalau user sudah pernah interaksi sebelumnya)
      if (!welcomePlayedRef.current) {
        welcomePlayedRef.current = true;
        setTimeout(() => {
          speak("Welcome to Signal Omega V2", { pitch: 0.80, rate: 0.95, volume: 1.0 });
        }, 600);
      }
    };

    // Saat user pertama kali klik/keydown → play welcome kalau bridge sudah ready
    const onFirstGesture = () => {
      if (!bridgeReadyRef.current || welcomePlayedRef.current) return;
      welcomePlayedRef.current = true;
      speak("Welcome to Signal Omega V2", { pitch: 0.80, rate: 0.95, volume: 1.0 });
      // Hapus listener setelah pertama kali
      window.removeEventListener("click",   onFirstGesture);
      window.removeEventListener("keydown", onFirstGesture);
    };

    window.addEventListener(BRIDGE_CONNECTED_EVENT, onBridgeConnect);
    window.addEventListener("click",   onFirstGesture);
    window.addEventListener("keydown", onFirstGesture);

    return () => {
      window.removeEventListener(BRIDGE_CONNECTED_EVENT, onBridgeConnect);
      window.removeEventListener("click",   onFirstGesture);
      window.removeEventListener("keydown", onFirstGesture);
    };
  }, []);

  // ── Monitor M15 signal ─────────────────────────────────
  useEffect(() => {
    const m15Data = crystalHA["M15"];
    if (!m15Data || m15Data.length === 0) return;

    const latest = m15Data[m15Data.length - 1];
    if (!latest) return;

    // Baca semua flag dari candle M15 terbaru
    const hasArrowBuy    = !!latest.arrow_buy;
    const hasArrowSell   = !!latest.arrow_sell;
    const hasCircleBuy   = !!latest.circle_buy;
    const hasCircleSell  = !!latest.circle_sell;

    // Priority: arrow > circle > none
    const currentSignal: SignalState =
      hasArrowBuy   ? "arrow_buy"   :
      hasArrowSell  ? "arrow_sell"  :
      hasCircleBuy  ? "circle_buy"  :
      hasCircleSell ? "circle_sell" :
      "none";

    // Pertama kali load → simpan state tanpa alert
    if (lastSignalRef.current === "init") {
      lastSignalRef.current = currentSignal;
      console.log(`[SignalVoice] Init → ${currentSignal} (no alert)`);
      return;
    }

    if (currentSignal === "none") {
      lastSignalRef.current = "none";
      return;
    }

    // Cek apakah sinyal benar-benar BARU
    const now        = Date.now();
    const isNew      = currentSignal !== lastSignalRef.current;
    const cooldown   = currentSignal.startsWith("circle") ? COOLDOWN_CIRCLE_MS : COOLDOWN_MS;
    const cooldownOk = (now - lastAlertRef.current) > cooldown;

    // Upgrade boleh langsung (circle_buy → arrow_buy): bypass cooldown
    const isUpgrade =
      (currentSignal === "arrow_buy"  && lastSignalRef.current === "circle_buy")  ||
      (currentSignal === "arrow_sell" && lastSignalRef.current === "circle_sell");

    if (!isNew) return;
    if (!cooldownOk && !isUpgrade) return;

    lastSignalRef.current = currentSignal;
    lastAlertRef.current  = now;

    console.log(`[SignalVoice] 🔊 ${currentSignal}`);

    // ── Teks berbeda per level ──
    let text = "";
    let pitch = 0.83;

    if (currentSignal === "circle_buy") {
      text  = "Buy setup forming. Standby.";
      pitch = 0.85;
    } else if (currentSignal === "circle_sell") {
      text  = "Sell setup forming. Standby.";
      pitch = 0.80;
    } else if (currentSignal === "arrow_buy") {
      text  = "Buy signal confirmed.";
      pitch = 0.87;
    } else if (currentSignal === "arrow_sell") {
      text  = "Sell signal confirmed.";
      pitch = 0.78;
    }

    if (window.speechSynthesis) {
      speak(text, { pitch, rate: 0.95 });
    } else {
      playTone(currentSignal.includes("buy") ? "buy" : "sell");
    }

  }, [crystalHA, trendCards]);
}
