import type { Timeframe, CrystalHACandle, TrendCard } from "@/types";

export function calculateTrendCard(
  timeframe: Timeframe,
  candles: CrystalHACandle[]
): TrendCard {
  if (!candles || candles.length === 0) {
    return {
      timeframe,
      direction: "sideways",
      label: "SIDEWAYS",
      strength: 0,
      momentum: 0,
      reversalRisk: 0,
      aligned: 0,
    };
  }

  const lastCandle = candles[candles.length - 1];
  const { ema20, ema50, close } = lastCandle;

  let direction: TrendCard["direction"] = "sideways";
  let label = "SIDEWAYS";

  if (ema20 > ema50) {
    direction = close > ema20 ? "bullish_strong" : "bullish_weak";
    label = "BULLISH";
  } else if (ema20 < ema50) {
    direction = close < ema20 ? "bearish_strong" : "bearish_weak";
    label = "BEARISH";
  }

  const emaDist = Math.abs(ema20 - ema50) / ema50 * 100;
  const strength = direction === "sideways" ? 0 : Math.min(Math.round(emaDist * 100), 100);

  return { timeframe, direction, label, strength, momentum: strength, reversalRisk: 0, aligned: direction !== "sideways" ? 10 : 0 };
}

export function calculateConfluence(trendCards: Partial<Record<Timeframe, TrendCard>>) {
  // Bobot TF (M1 = 0 diabaikan)
  const weights: Record<string, number> = {
    H4: 4,
    H1: 3,
    M15: 2,
    M5: 1,
    M1: 0,
  };

  let weightedBull = 0;
  let weightedBear = 0;

  for (const [tf, card] of Object.entries(trendCards)) {
    const w = weights[tf] || 0;
    if (card?.direction?.includes("bullish")) {
      weightedBull += w;
    } else if (card?.direction?.includes("bearish")) {
      weightedBear += w;
    }
  }

  let dominantTrend: "UP" | "DOWN" | "SIDEWAYS" = "SIDEWAYS";

  if (weightedBull > weightedBear + 2) {
    dominantTrend = "UP";
  } else if (weightedBear > weightedBull + 2) {
    dominantTrend = "DOWN";
  }

  return { dominantTrend, weightedBull, weightedBear };
}

