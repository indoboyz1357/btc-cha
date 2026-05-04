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

  const last10 = candles.slice(-10);
  const last5  = candles.slice(-5);

  const bs = last10.filter((c) => c.color === "bullish_strong").length;
  const bw = last10.filter((c) => c.color === "bullish_weak").length;
  const rs = last10.filter((c) => c.color === "bearish_strong").length;
  const rw = last10.filter((c) => c.color === "bearish_weak").length;

  const totalBull = bs + bw;
  const totalBear = rs + rw;

  let direction: TrendCard["direction"] = "sideways";
  let label = "SIDEWAYS";
  let aligned = 0;

  if (bs >= 6) { direction = "bullish_strong"; label = "BULLISH KUAT"; aligned = bs; }
  else if (totalBull >= 6) { direction = "bullish_weak"; label = "BULLISH LEMAH"; aligned = totalBull; }
  else if (rs >= 6) { direction = "bearish_strong"; label = "BEARISH KUAT"; aligned = rs; }
  else if (totalBear >= 6) { direction = "bearish_weak"; label = "BEARISH LEMAH"; aligned = totalBear; }
  else { direction = "sideways"; label = "SIDEWAYS"; aligned = 0; }

  const strength = Math.round((aligned / 10) * 100);

  // Momentum from last5: bullish_strong weight=2, bullish_weak=1 etc.
  const momScore = last5.reduce((acc, c) => {
    if (c.color === "bullish_strong") return acc + 2;
    if (c.color === "bullish_weak")   return acc + 1;
    if (c.color === "bearish_weak")   return acc - 1;
    if (c.color === "bearish_strong") return acc - 2;
    return acc;
  }, 0);
  const momentum = Math.round(((momScore + 10) / 20) * 100);

  // Reversal risk: weak candles at tail
  const weakTail = last5.filter(
    (c) => c.color === "bullish_weak" || c.color === "bearish_weak"
  ).length;
  const reversalSignals = last5.filter((c) => c.reversal_signal).length;
  const reversalRisk = Math.min(
    Math.round(((weakTail * 15 + reversalSignals * 20) / 100) * 100),
    100
  );

  return { timeframe, direction, label, strength, momentum, reversalRisk, aligned };
}
