"use client";

import { useAppStore } from "@/store/useAppStore";
import type { AIAnalysis, Timeframe } from "@/types";

const MODELS = {
  "deepseek/deepseek-chat-v3-5":          "DeepSeek V3 Flash",
  "anthropic/claude-sonnet-4-6":          "Claude Sonnet 4.6",
  "google/gemini-2.5-pro-preview":        "Gemini 2.5 Pro",
  "openai/gpt-4o":                        "GPT-4o",
};

const SYSTEM_PROMPT = `Kamu adalah AI trading analyst profesional untuk BTC/USD.

Kamu menerima data Crystal Heikin Ashi (HA) dari MetaTrader 5 untuk 5 timeframe: H4, H1, M15, M5, M1.
Crystal HA candle memiliki 4 jenis: bullish_strong, bullish_weak, bearish_weak, bearish_strong.

ATURAN WAJIB:
1. Tren H4 adalah penentu arah — TIDAK BOLEH dilanggar
2. SEMUA sinyal harus SEARAH dengan H4
3. Confidence berdasarkan jumlah TF yang searah:
   - H4+H1+M15+M5+M1 searah = 85-95%
   - H4+H1+M15+M5 searah = 70-84%
   - H4+H1+M15 searah = 55-69%
   - H4+H1 searah = 40-54%
   - Hanya H4 = < 40% → JANGAN kasih entry
4. Kalau kondisi tidak jelas = kosongkan entry, jangan asal kasih sinyal
5. TIDAK ADA TP — sistem pakai trailing stop (500pt trigger, 250pt trail)
6. Bahasa summary = bahasa anak SMP, sederhana, tidak pakai jargon

RESPONSE: Kembalikan HANYA JSON berikut, tidak ada teks lain:
{
  "trend_bias": "bullish|bearish|sideways",
  "overall_confidence": 75,
  "primary_swing": {
    "active": true,
    "direction": "buy",
    "entry": 79500.0,
    "sl": 78900.0,
    "confidence": 72,
    "rr_note": "Trailing stop aktif setelah +500pt",
    "reasoning": "Penjelasan singkat bahasa Indonesia"
  },
  "scalp_trend": {
    "active": false,
    "direction": null,
    "entry": null,
    "sl": null,
    "confidence": 0,
    "rr_note": "",
    "reasoning": "Alasan tidak ada sinyal"
  },
  "scalp_counter": {
    "active": false,
    "direction": null,
    "entry": null,
    "sl": null,
    "confidence": 0,
    "rr_note": "",
    "reasoning": "H4 masih bullish kuat, counter-trend tidak disarankan"
  },
  "market_summary": {
    "title": "Judul kondisi market",
    "situation": "Penjelasan kondisi dalam 2-3 kalimat",
    "key_levels": "Level penting",
    "action": "Saran konkret",
    "avoid": "Yang harus dihindari",
    "invalidation": "Kondisi yang membatalkan semua setup"
  },
  "reversal_risk": {
    "percentage": 25,
    "description": "Alasan reversal risk"
  }
}`;

export function useAIAnalysis() {
  const store = useAppStore();

  async function analyze() {
    if (!store.openRouterKey) {
      store.addToast("error", "OpenRouter API Key belum diisi — buka ⚙ AI Setup");
      return;
    }
    if (store.isAnalyzing) return;

    store.setAnalyzing(true);

    try {
      // Build Crystal HA context for all TFs
      const tfs: Timeframe[] = ["H4", "H1", "M15", "M5", "M1"];
      const haContext = tfs.map((tf) => {
        const data = store.crystalHA[tf]?.slice(-50) || [];
        return `\n### ${tf} Crystal HA (last ${data.length} candles)\n${JSON.stringify(data, null, 0)}`;
      }).join("\n");

      const userMessage = `Current BTC price: $${store.currentPrice.toFixed(2)}\n\nCrystal Heikin Ashi Data:\n${haContext}`;

      const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${store.openRouterKey}`,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://signal-omega-v2.vercel.app",
          "X-Title": "BTCUSD Signal Omega V2",
        },
        body: JSON.stringify({
          model: store.selectedModel,
          messages: [
            { role: "system", content: SYSTEM_PROMPT },
            { role: "user",   content: userMessage },
          ],
          temperature: 0.3,
          max_tokens:  2048,
        }),
      });

      if (!response.ok) {
        const err = await response.text();
        throw new Error(`OpenRouter error ${response.status}: ${err}`);
      }

      const json  = await response.json();
      const raw   = json.choices?.[0]?.message?.content || "";

      // Extract JSON block
      const match = raw.match(/\{[\s\S]*\}/);
      if (!match) throw new Error("AI returned invalid JSON");

      const parsed = JSON.parse(match[0]);
      const analysis: AIAnalysis = {
        id:              crypto.randomUUID(),
        timestamp:       new Date().toISOString(),
        btcPrice:        store.currentPrice,
        model:           MODELS[store.selectedModel as keyof typeof MODELS] || store.selectedModel,
        ...parsed,
      };

      store.setAnalysis(analysis);
      store.addToast("success", `🤖 AI signal ready — ${parsed.trend_bias?.toUpperCase()} (conf: ${parsed.overall_confidence}%)`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "AI analysis failed";
      store.addToast("error", msg);
    } finally {
      store.setAnalyzing(false);
    }
  }

  return { analyze, isAnalyzing: store.isAnalyzing };
}
