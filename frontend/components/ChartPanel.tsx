"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries, ColorType, CrosshairMode } from "lightweight-charts";
import type { IChartApi, ISeriesApi } from "lightweight-charts";
import { useAppStore } from "@/store/useAppStore";
import type { Timeframe } from "@/types";

const TIMEFRAMES: Timeframe[] = ["M1", "M5", "M15", "H1", "H4"];

export default function ChartPanel() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const candleRef    = useRef<ISeriesApi<"Candlestick"> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const haRef        = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const [activeTA, setActiveTA] = useState<string[]>([]);
  const { activeTimeframe, setActiveTimeframe, candles, crystalHA } = useAppStore();

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#161a22" },
        textColor: "#8b8d91",
        fontSize: 11,
        fontFamily: "'JetBrains Mono', monospace",
      },
      grid: {
        vertLines: { color: "#1e2329" },
        horzLines: { color: "#1e2329" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#1e2329" },
      timeScale: { borderColor: "#1e2329", timeVisible: true, secondsVisible: false },
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    // v5 API: chart.addSeries(SeriesType, options)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00d084", downColor: "#ff4444",
      borderUpColor: "#00d084", borderDownColor: "#ff4444",
      wickUpColor: "#00d084", wickDownColor: "#ff4444",
    });

    const haSeries = chart.addSeries(CandlestickSeries, {
      upColor: "rgba(0,208,132,0.7)", downColor: "rgba(255,68,68,0.7)",
      borderUpColor: "rgba(0,208,132,0.9)", borderDownColor: "rgba(255,68,68,0.9)",
      wickUpColor: "rgba(0,208,132,0.9)", wickDownColor: "rgba(255,68,68,0.9)",
      priceLineVisible: false,
    });

    chartRef.current  = chart;
    candleRef.current = candleSeries;
    haRef.current     = haSeries;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width:  containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  useEffect(() => {
    const data = candles[activeTimeframe];
    if (!candleRef.current || !data?.length) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    candleRef.current.setData(data.map((c) => ({ time: c.time as any, open: c.open, high: c.high, low: c.low, close: c.close })));
    chartRef.current?.timeScale().scrollToRealTime();
  }, [candles, activeTimeframe]);

  useEffect(() => {
    const data = crystalHA[activeTimeframe];
    if (!haRef.current || !data?.length) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    haRef.current.setData(data.map((c) => ({ time: c.time as any, open: c.ha_open, high: c.ha_high, low: c.ha_low, close: c.ha_close })));
  }, [crystalHA, activeTimeframe]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 320 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "8px 10px", borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
        {TIMEFRAMES.map((tf) => (
          <button key={tf} id={`btn-tf-${tf}`}
            className={activeTimeframe === tf ? "btn btn-primary" : "btn btn-ghost"}
            style={{ padding: "3px 10px", fontSize: 11, minWidth: 36 }}
            onClick={() => setActiveTimeframe(tf)}
          >
            {tf}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        {[{ id: "ema20", label: "EMA20", color: "#f59e0b" }, { id: "ema50", label: "EMA50", color: "#3b82f6" }, { id: "ema200", label: "EMA200", color: "#e8eaed" }, { id: "vol", label: "VOL", color: "#8b8d91" }]
          .map((ind) => (
            <button key={ind.id}
              className="btn btn-ghost"
              style={{ padding: "2px 8px", fontSize: 10, borderColor: activeTA.includes(ind.id) ? ind.color : "var(--border-light)", color: activeTA.includes(ind.id) ? ind.color : "var(--text-muted)" }}
              onClick={() => setActiveTA((prev) => prev.includes(ind.id) ? prev.filter((x) => x !== ind.id) : [...prev, ind.id])}
            >
              {ind.label}
            </button>
          ))}
      </div>
      <div ref={containerRef} style={{ flex: 1, minHeight: 260 }} />
    </div>
  );
}
