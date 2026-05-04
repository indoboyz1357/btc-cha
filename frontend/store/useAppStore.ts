import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  Timeframe,
  Candle,
  CrystalHACandle,
  TrendCard,
  Position,
  PendingOrder,
  AIAnalysis,
  AutoTradingState,
  TradeSetup,
  Toast,
} from "@/types";
import { calculateTrendCard } from "@/utils/trendCalculator";

interface AppState {
  // ── Connection ──────────────────────────────────────────────────────────────
  bridgeUrl: string;
  isConnected: boolean;
  reconnectAttempts: number;
  setBridgeUrl: (url: string) => void;
  setConnected: (v: boolean) => void;

  // ── Market data ─────────────────────────────────────────────────────────────
  currentPrice: number;
  prevPrice: number;
  priceChange: number;
  priceChangePercent: number;
  currentSession: string;
  updatePrice: (bid: number, ask: number) => void;

  // ── Candles & Crystal HA ────────────────────────────────────────────────────
  candles: Partial<Record<Timeframe, Candle[]>>;
  crystalHA: Partial<Record<Timeframe, CrystalHACandle[]>>;
  trendCards: Partial<Record<Timeframe, TrendCard>>;
  updateCandles: (tf: Timeframe, data: Candle[]) => void;
  updateCrystalHA: (tf: Timeframe, data: CrystalHACandle[]) => void;

  // ── Chart ───────────────────────────────────────────────────────────────────
  activeTimeframe: Timeframe;
  setActiveTimeframe: (tf: Timeframe) => void;
  activeIndicators: string[];
  toggleIndicator: (name: string) => void;

  // ── AI config ───────────────────────────────────────────────────────────────
  openRouterKey: string;
  selectedModel: string;
  setOpenRouterKey: (k: string) => void;
  setSelectedModel: (m: string) => void;

  // ── AI Analysis ─────────────────────────────────────────────────────────────
  isAnalyzing: boolean;
  lastAnalysis: AIAnalysis | null;
  analysisHistory: AIAnalysis[];
  setAnalyzing: (v: boolean) => void;
  setAnalysis: (a: AIAnalysis) => void;

  // ── Auto trading ────────────────────────────────────────────────────────────
  autoTrading: AutoTradingState;
  updateAutoStatus: (data: Partial<AutoTradingState>) => void;
  clearAutoLog: () => void;

  // ── Execution ───────────────────────────────────────────────────────────────
  pendingSetup: TradeSetup | null;
  openPositions: Position[];
  pendingOrders: PendingOrder[];
  setPendingSetup: (s: TradeSetup | null) => void;
  updatePositions: (data: Position[]) => void;
  updateOrders: (data: PendingOrder[]) => void;

  // ── Toasts ──────────────────────────────────────────────────────────────────
  toasts: Toast[];
  addToast: (type: Toast["type"], message: string) => void;
  removeToast: (id: string) => void;

  // ── MT5 config ──────────────────────────────────────────────────────────────
  mt5Login: string;
  mt5Password: string;
  mt5Server: string;
  setMt5Config: (login: string, password: string, server: string) => void;

  // ── WebSocket send ──────────────────────────────────────────────────────────
  _ws: WebSocket | null;
  setWs: (ws: WebSocket | null) => void;
  sendCommand: (cmd: object) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // ── Connection ────────────────────────────────────────────────────────
      bridgeUrl: "ws://localhost:8765",
      isConnected: false,
      reconnectAttempts: 0,
      setBridgeUrl: (url) => set({ bridgeUrl: url }),
      setConnected: (v) => set({ isConnected: v }),

      // ── Market ────────────────────────────────────────────────────────────
      currentPrice: 0,
      prevPrice: 0,
      priceChange: 0,
      priceChangePercent: 0,
      currentSession: "—",
      updatePrice: (bid, ask) => {
        const mid  = (bid + ask) / 2;
        const prev = get().currentPrice || mid;
        const chg  = mid - prev;
        const pct  = prev > 0 ? (chg / prev) * 100 : 0;
        const hour = new Date().getUTCHours();
        let session = "Sydney";
        if (hour >= 7 && hour < 16) session = "London";
        else if (hour >= 12 && hour < 21) session = "New York";
        else if (hour >= 0 && hour < 9) session = "Tokyo";
        set({ currentPrice: mid, prevPrice: prev, priceChange: chg, priceChangePercent: pct, currentSession: session });
      },

      // ── Candles & HA ─────────────────────────────────────────────────────
      candles: {},
      crystalHA: {},
      trendCards: {},
      updateCandles: (tf, data) =>
        set((s) => ({ candles: { ...s.candles, [tf]: data } })),
      updateCrystalHA: (tf, data) =>
        set((s) => {
          const cards = { ...s.trendCards, [tf]: calculateTrendCard(tf, data) };
          return { crystalHA: { ...s.crystalHA, [tf]: data }, trendCards: cards };
        }),

      // ── Chart ─────────────────────────────────────────────────────────────
      activeTimeframe: "M15",
      setActiveTimeframe: (tf) => set({ activeTimeframe: tf }),
      activeIndicators: ["ema20"],
      toggleIndicator: (name) =>
        set((s) => ({
          activeIndicators: s.activeIndicators.includes(name)
            ? s.activeIndicators.filter((x) => x !== name)
            : [...s.activeIndicators, name],
        })),

      // ── AI config ─────────────────────────────────────────────────────────
      openRouterKey: "",
      selectedModel: "deepseek/deepseek-chat-v3-5",
      setOpenRouterKey: (k) => set({ openRouterKey: k }),
      setSelectedModel: (m) => set({ selectedModel: m }),

      // ── AI Analysis ───────────────────────────────────────────────────────
      isAnalyzing: false,
      lastAnalysis: null,
      analysisHistory: [],
      setAnalyzing: (v) => set({ isAnalyzing: v }),
      setAnalysis: (a) =>
        set((s) => ({
          lastAnalysis: a,
          analysisHistory: [a, ...s.analysisHistory].slice(0, 100),
        })),

      // ── Auto Trading ──────────────────────────────────────────────────────
      autoTrading: {
        enabled: false,
        scan_interval: 30,
        min_confidence: 70,
        lot_size: 0.01,
        max_positions: 2,
        max_daily_loss: 10,
        session_filter: ["london", "new_york"],
        allow_buy: true,
        allow_sell: true,
        daily_loss: 0,
        trades_today: 0,
        last_scan: "",
        last_signal: "",
        log: [],
      },
      updateAutoStatus: (data) =>
        set((s) => ({ autoTrading: { ...s.autoTrading, ...data } })),
      clearAutoLog: () =>
        set((s) => ({ autoTrading: { ...s.autoTrading, log: [] } })),

      // ── Execution ─────────────────────────────────────────────────────────
      pendingSetup: null,
      openPositions: [],
      pendingOrders: [],
      setPendingSetup: (s) => set({ pendingSetup: s }),
      updatePositions: (data) => set({ openPositions: data }),
      updateOrders: (data) => set({ pendingOrders: data }),

      // ── Toasts ────────────────────────────────────────────────────────────
      toasts: [],
      addToast: (type, message) => {
        const id = Math.random().toString(36).slice(2);
        set((s) => ({ toasts: [...s.toasts, { id, type, message }] }));
        setTimeout(() => get().removeToast(id), 5000);
      },
      removeToast: (id) =>
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

      // ── MT5 config ────────────────────────────────────────────────────────
      mt5Login: "430207633",
      mt5Password: "",
      mt5Server: "XMGlobal-MT5 18",
      setMt5Config: (login, password, server) =>
        set({ mt5Login: login, mt5Password: password, mt5Server: server }),

      // ── WebSocket ─────────────────────────────────────────────────────────
      _ws: null,
      setWs: (ws) => set({ _ws: ws }),
      sendCommand: (cmd) => {
        const ws = get()._ws;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(cmd));
        }
      },
    }),
    {
      name: "omega-v2-store",
      partialize: (s) => ({
        bridgeUrl: s.bridgeUrl,
        openRouterKey: s.openRouterKey,
        selectedModel: s.selectedModel,
        mt5Login: s.mt5Login,
        mt5Password: s.mt5Password,
        mt5Server: s.mt5Server,
        analysisHistory: s.analysisHistory,
        autoTrading: {
          scan_interval: s.autoTrading.scan_interval,
          min_confidence: s.autoTrading.min_confidence,
          lot_size: s.autoTrading.lot_size,
          max_positions: s.autoTrading.max_positions,
          max_daily_loss: s.autoTrading.max_daily_loss,
          session_filter: s.autoTrading.session_filter,
          allow_buy: s.autoTrading.allow_buy,
          allow_sell: s.autoTrading.allow_sell,
        },
      }),
    }
  )
);
