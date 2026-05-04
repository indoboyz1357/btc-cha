export type Timeframe = "M1" | "M5" | "M15" | "H1" | "H4";

export type CandleColor =
  | "bullish_strong"
  | "bullish_weak"
  | "bearish_weak"
  | "bearish_strong";

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  tick_volume: number;
}

export interface CrystalHACandle {
  time: number;
  ha_open: number;
  ha_high: number;
  ha_low: number;
  ha_close: number;
  color: CandleColor;
  reversal_signal: boolean;
}

export interface TrendCard {
  timeframe: Timeframe;
  direction: "bullish_strong" | "bullish_weak" | "bearish_strong" | "bearish_weak" | "sideways";
  label: string;
  strength: number;      // 0–100
  momentum: number;      // 0–100
  reversalRisk: number;  // 0–100
  aligned: number;       // aligned candles out of 10
}

export interface Position {
  ticket: number;
  type: "buy" | "sell";
  volume: number;
  open_price: number;
  sl: number;
  tp: number;
  profit: number;
  open_time: string;
  trailing_status: "active" | "standby" | "off";
  trailing_high: number;
  source?: "auto" | "manual";
}

export interface PendingOrder {
  ticket: string;
  type: string;
  volume: number;
  trigger_price: number;
  entry_price: number;
  sl: number;
  status: string;
  created_at: string;
}

export interface AISignal {
  active: boolean;
  direction: "buy" | "sell" | null;
  entry: number | null;
  sl: number | null;
  confidence: number;
  rr_note: string;
  reasoning: string;
}

export interface AIAnalysis {
  id: string;
  timestamp: string;
  btcPrice: number;
  model: string;
  trend_bias: "bullish" | "bearish" | "sideways";
  overall_confidence: number;
  primary_swing: AISignal;
  scalp_trend: AISignal;
  scalp_counter: AISignal;
  market_summary: {
    title: string;
    situation: string;
    key_levels: string;
    action: string;
    avoid: string;
    invalidation: string;
  };
  reversal_risk: {
    percentage: number;
    description: string;
  };
}

export interface AutoTradeLog {
  time: string;
  action: string;
  reason: string;
  result: string;
}

export interface AutoTradingSettings {
  enabled: boolean;
  scan_interval: number;
  min_confidence: number;
  lot_size: number;
  max_positions: number;
  max_daily_loss: number;
  session_filter: string[];
  allow_buy: boolean;
  allow_sell: boolean;
}

export interface AutoTradingState extends AutoTradingSettings {
  daily_loss: number;
  trades_today: number;
  last_scan: string;
  last_signal: string;
  log: AutoTradeLog[];
}

export interface TradeSetup {
  label: string;
  direction: "buy" | "sell";
  entry: number;
  sl: number;
}

export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
}
