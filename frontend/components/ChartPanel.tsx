"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart, CandlestickSeries, ColorType, CrosshairMode,
  LineSeries, createSeriesMarkers, Time,
} from "lightweight-charts";
import type { IChartApi, ISeriesApi, ISeriesMarkersPluginApi } from "lightweight-charts";
import { useAppStore } from "@/store/useAppStore";
import type { Timeframe } from "@/types";

const TIMEFRAMES: Timeframe[] = ["M1", "M5", "M15", "H1", "H4"];

const DRAW_TOOLS = [
  { id: "hline",  label: "━━", title: "Horizontal Line" },
  { id: "tline",  label: "╱",  title: "Trend Line" },
  { id: "ray",    label: "→",  title: "Ray" },
  { id: "rect",   label: "▭",  title: "Rectangle" },
  { id: "fib",    label: "ƒ",  title: "Fibonacci" },
  { id: "eraser", label: "✕",  title: "Hapus semua" },
] as const;

type DrawTool = typeof DRAW_TOOLS[number]["id"] | null;

// ── Warna Crystal HA Pro ──────────────────────────────────────────────────────
// Sama persis dengan screenshot versi berbayar
const HA_COLORS = {
  bullish_strong: "#00E676",   // Hijau terang — uptrend kuat (seperti Pro: biru muda → kita pakai hijau)
  bullish_weak:   "#1565C0",   // Biru gelap — uptrend normal
  bearish_weak:   "#FF1744",   // Merah — downtrend normal
  bearish_strong: "#FF6D00",   // Oranye — downtrend kuat
};

export default function ChartPanel() {
  const activeTimeframe    = useAppStore((s) => s.activeTimeframe);
  const setActiveTimeframe = useAppStore((s) => s.setActiveTimeframe);
  const crystalHAData      = useAppStore((s) => s.crystalHA[s.activeTimeframe]);
  const candlesData        = useAppStore((s) => s.candles[s.activeTimeframe]);
  const autoTrading        = useAppStore((s) => s.autoTrading);
  const tfSettings         = useAppStore((s) => s.tfSettings);
  const setTfSetting       = useAppStore((s) => s.setTfSetting);

  // Per-TF settings — ambil setting khusus TF aktif
  const currentTfSettings = tfSettings[activeTimeframe] || { activeTA: [], chartMode: "omega" as const };
  const activeTA    = currentTfSettings.activeTA;
  const chartMode   = currentTfSettings.chartMode;
  const setActiveTA = (val: string[] | ((prev: string[]) => string[])) => {
    const next = typeof val === "function" ? val(activeTA) : val;
    setTfSetting(activeTimeframe, "activeTA", next);
  };
  const setChartMode = (mode: "omega" | "normal") => {
    setTfSetting(activeTimeframe, "chartMode", mode);
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<IChartApi | null>(null);
  const haRef        = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema20Ref     = useRef<ISeriesApi<"Line"> | null>(null);
  const ema50Ref     = useRef<ISeriesApi<"Line"> | null>(null);
  const markersRef   = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const linesRef     = useRef<ISeriesApi<any>[]>([]);
  const currentTfRef   = useRef<Timeframe | null>(null);
  const currentModeRef = useRef<"omega" | "normal">("omega");

  // Simpan posisi chart (zoom+scroll) per-TF supaya gak ke-reset waktu ganti TF
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tfVisibleRangeRef = useRef<Partial<Record<Timeframe, any>>>({});

  const [chartShift, setChartShift] = useState(true);
  const [drawTool, setDrawTool]   = useState<DrawTool>(null);

  // Apply chart shift ke timeScale
  useEffect(() => {
    if (!chartRef.current) return;
    chartRef.current.timeScale().applyOptions({ rightOffset: chartShift ? 10 : 0 });
  }, [chartShift]);

  // ── Init chart ────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0d1117" },
        textColor: "#8b8d91",
        fontSize: 11,
        fontFamily: "'JetBrains Mono', monospace",
      },
      grid: {
        vertLines: { color: "#161b22" },
        horzLines: { color: "#161b22" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#21262d" },
      timeScale: { borderColor: "#21262d", timeVisible: true, secondsVisible: false, rightOffset: 10 },
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    const haSeries = chart.addSeries(CandlestickSeries, {
      upColor:          HA_COLORS.bullish_weak,
      downColor:        HA_COLORS.bearish_strong,
      borderUpColor:    HA_COLORS.bullish_weak,
      borderDownColor:  HA_COLORS.bearish_strong,
      wickUpColor:      "rgba(21,101,192,0.6)",
      wickDownColor:    "rgba(255,109,0,0.6)",
      priceLineVisible: true,
      priceLineColor:   "rgba(21,101,192,0.4)",
    });

    const ema20 = chart.addSeries(LineSeries, {
      color: "#f59e0b", lineWidth: 1,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    const ema50 = chart.addSeries(LineSeries, {
      color: "#3b82f6", lineWidth: 2,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    chartRef.current = chart;
    haRef.current    = haSeries;
    ema20Ref.current = ema20;
    ema50Ref.current = ema50;
    markersRef.current = createSeriesMarkers(haSeries, []);

    const ro = new ResizeObserver((entries) => {
      if ((ro as unknown as { _timer: ReturnType<typeof setTimeout> })._timer)
        clearTimeout((ro as unknown as { _timer: ReturnType<typeof setTimeout> })._timer);
      (ro as unknown as { _timer: ReturnType<typeof setTimeout> })._timer = setTimeout(() => {
        const entry = entries[0];
        if (!entry) return;
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) chart.applyOptions({ width, height });
      }, 100);
    });
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  // ── Feed data ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!haRef.current) return;

    if (chartMode === "omega" && crystalHAData?.length) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const mapped = crystalHAData.map((c: any) => {
        const color = HA_COLORS[c.color as keyof typeof HA_COLORS] || HA_COLORS.bullish_weak;
        return {
          time: c.time as Time,
          open: c.ha_open, high: c.ha_high, low: c.ha_low, close: c.ha_close,
          color, borderColor: color, wickColor: color,
        };
      });

      const isTfChange   = currentTfRef.current !== activeTimeframe;
      const isModeChange = currentModeRef.current !== "omega";
      if (isTfChange || isModeChange) {
        // Simpan posisi chart TF lama sebelum ganti
        if (currentTfRef.current && chartRef.current) {
          try {
            const range = chartRef.current.timeScale().getVisibleRange();
            if (range) tfVisibleRangeRef.current[currentTfRef.current] = range;
          } catch { /* ignore */ }
        }

        haRef.current.setData(mapped);

        // Restore posisi TF baru kalau ada, kalau belum pernah baru scrollToRealTime
        const savedRange = tfVisibleRangeRef.current[activeTimeframe];
        if (savedRange) {
          try {
            chartRef.current?.timeScale().setVisibleRange(savedRange);
          } catch {
            chartRef.current?.timeScale().scrollToRealTime();
          }
        } else {
          chartRef.current?.timeScale().scrollToRealTime();
        }

        // Reset vertical scale supaya auto-fit ke data TF ini (tidak sharing zoom vertikal)
        chartRef.current?.priceScale("right").applyOptions({ autoScale: true });

        currentTfRef.current   = activeTimeframe;
        currentModeRef.current = "omega";
      } else {
        const last = mapped[mapped.length - 1];
        if (last) haRef.current.update(last);
      }

      // ── Signal markers: circles + arrows ──────────────────────────
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const markers: { time: Time; position: string; color: string; shape: string; text?: string; size?: number }[] = [];
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      crystalHAData.forEach((c: any) => {
        if (c.circle_buy) {
          markers.push({
            time: c.time as Time,
            position: "belowBar",
            color: "#1E90FF",      // Dodger Blue — BUY circle
            shape: "circle",
            text: "●",
            size: 1,
          });
        }
        if (c.circle_sell) {
          markers.push({
            time: c.time as Time,
            position: "aboveBar",
            color: "#FF6D00",      // Orange — SELL circle
            shape: "circle",
            text: "●",
            size: 1,
          });
        }
        if (c.arrow_buy) {
          markers.push({
            time: c.time as Time,
            position: "belowBar",
            color: "#00E676",      // Hijau — BUY confirmed arrow
            shape: "arrowUp",
            text: "BUY",
            size: 2,
          });
        }
        if (c.arrow_sell) {
          markers.push({
            time: c.time as Time,
            position: "aboveBar",
            color: "#FF1744",      // Merah — SELL confirmed arrow
            shape: "arrowDown",
            text: "SELL",
            size: 2,
          });
        }
      });
      // Sort markers by time (required by lightweight-charts)
      markers.sort((a, b) => (a.time as number) - (b.time as number));
      markersRef.current?.setMarkers(markers);

    } else if (chartMode === "normal" && candlesData?.length) {
      haRef.current.applyOptions({
        upColor: "#26a69a", downColor: "#ef5350",
        borderUpColor: "#26a69a", borderDownColor: "#ef5350",
        wickUpColor: "rgba(38,166,154,0.7)", wickDownColor: "rgba(239,83,80,0.7)",
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const mapped = candlesData.map((c: any) => ({
        time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close,
      }));
      const isTfChange   = currentTfRef.current !== activeTimeframe;
      const isModeChange = currentModeRef.current !== "normal";
      if (isTfChange || isModeChange) {
        // Simpan posisi TF lama
        if (currentTfRef.current && chartRef.current) {
          try {
            const range = chartRef.current.timeScale().getVisibleRange();
            if (range) tfVisibleRangeRef.current[currentTfRef.current] = range;
          } catch { /* ignore */ }
        }
        haRef.current.setData(mapped);
        // Restore posisi TF baru
        const savedRange = tfVisibleRangeRef.current[activeTimeframe];
        if (savedRange) {
          try {
            chartRef.current?.timeScale().setVisibleRange(savedRange);
          } catch {
            chartRef.current?.timeScale().scrollToRealTime();
          }
        } else {
          chartRef.current?.timeScale().scrollToRealTime();
        }
        // Reset vertical scale supaya auto-fit
        chartRef.current?.priceScale("right").applyOptions({ autoScale: true });
        currentTfRef.current   = activeTimeframe;
        currentModeRef.current = "normal";
      } else {
        const last = mapped[mapped.length - 1];
        if (last) haRef.current.update(last);
      }
      markersRef.current?.setMarkers([]);
    }

    // EMAs
    if (crystalHAData?.length) {
      if (ema20Ref.current)
        ema20Ref.current.setData(
          activeTA.includes("ema20")
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ? crystalHAData.map((c: any) => ({ time: c.time as Time, value: c.ema20 }))
            : []
        );
      if (ema50Ref.current)
        ema50Ref.current.setData(
          activeTA.includes("ema50")
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ? crystalHAData.map((c: any) => ({ time: c.time as Time, value: c.ema50 }))
            : []
        );
    }
  }, [crystalHAData, candlesData, activeTimeframe, chartMode, activeTA]);

  // ── Latest signal summary untuk header bar ──────────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const latestHA     = (crystalHAData as any[])?.[crystalHAData?.length ? crystalHAData.length - 1 : -1];
  const hasCircleBuy  = latestHA?.circle_buy  || false;
  const hasCircleSell = latestHA?.circle_sell || false;
  const hasArrowBuy   = latestHA?.arrow_buy   || false;
  const hasArrowSell  = latestHA?.arrow_sell  || false;

  // ── Pro dashboard overlay (pojok kiri atas chart, seperti Pro EA) ──
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const haTrend = autoTrading.ha_trend || ((crystalHAData as any[])?.[crystalHAData?.length ? crystalHAData.length - 1 : -1]?.color?.includes("bullish") ? "BULLISH" : crystalHAData?.length ? "BEARISH" : "—");
  const statusText = autoTrading.status_text || (hasArrowBuy ? "Arrow Confirmed↑" : hasArrowSell ? "Arrow Confirmed↓" : hasCircleBuy ? "Waiting Breakout..." : hasCircleSell ? "Waiting Breakout..." : "Scanning...");
  const haTrendColor = haTrend === "BULLISH" ? "#00E676" : haTrend === "BEARISH" ? "#FF1744" : "#8b8d91";

  // ── Drawing ────────────────────────────────────────────────────────
  const handleChartClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (drawTool !== "hline" || !chartRef.current || !haRef.current) return;
    if (!crystalHAData || crystalHAData.length < 2) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const price = (haRef.current as any).coordinateToPrice(e.nativeEvent.offsetY);
    if (price == null) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const line = chartRef.current.addSeries(LineSeries as any, {
      color: "#f59e0b", lineWidth: 1, lineStyle: 1,
      priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
    });
    line.setData([
      { time: crystalHAData[0].time as Time, value: price },
      { time: crystalHAData[crystalHAData.length - 1].time as Time, value: price },
    ]);
    linesRef.current.push(line);
  }, [drawTool, crystalHAData]);

  const handleEraser = () => {
    linesRef.current.forEach((l) => {
      try { chartRef.current?.removeSeries(l); } catch { /* */ }
    });
    linesRef.current = [];
    setDrawTool(null);
  };

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 320 }}>
      {/* Draw tools sidebar */}
      <div style={{
        width: 36, borderRight: "1px solid var(--border)",
        display: "flex", flexDirection: "column",
        alignItems: "center", padding: "8px 0", gap: 4, background: "#0d1117",
      }}>
        {DRAW_TOOLS.map((tool) => (
          <button key={tool.id} title={tool.title}
            onClick={() => tool.id === "eraser"
              ? handleEraser()
              : setDrawTool(drawTool === tool.id ? null : tool.id)}
            style={{
              width: 28, height: 28, border: "1px solid",
              borderColor: drawTool === tool.id ? "#1e90ff" : "var(--border)",
              borderRadius: 4,
              background:  drawTool === tool.id ? "rgba(30,144,255,0.15)" : "transparent",
              color:       drawTool === tool.id ? "#1e90ff" : "var(--text-muted)",
              fontSize: 12, cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >{tool.label}</button>
        ))}
      </div>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Toolbar */}
        <div style={{
          display: "flex", alignItems: "center", gap: 4,
          padding: "5px 10px", borderBottom: "1px solid var(--border)", flexWrap: "wrap",
        }}>
          {TIMEFRAMES.map((tf) => (
            <button key={tf}
              className={activeTimeframe === tf ? "btn btn-primary" : "btn btn-ghost"}
              style={{ padding: "3px 10px", fontSize: 11, minWidth: 36 }}
              onClick={() => setActiveTimeframe(tf)}
            >{tf}</button>
          ))}
          <div style={{ flex: 1 }} />
          {[
            { id: "ema20",  label: "EMA20",  color: "#f59e0b" },
            { id: "ema50",  label: "EMA50",  color: "#3b82f6" },
          ].map((ind) => (
            <button key={ind.id} className="btn btn-ghost"
              style={{
                padding: "2px 8px", fontSize: 10,
                borderColor: activeTA.includes(ind.id) ? ind.color : "var(--border-light)",
                color:       activeTA.includes(ind.id) ? ind.color : "var(--text-muted)",
              }}
              onClick={() => setActiveTA((prev) =>
                prev.includes(ind.id) ? prev.filter((x) => x !== ind.id) : [...prev, ind.id]
              )}
            >{ind.label}</button>
          ))}

          {/* Chart Shift toggle — ruang kosong kanan chart */}
          <button
            title={chartShift ? "Chart Shift ON — klik untuk OFF" : "Chart Shift OFF — klik untuk ON"}
            onClick={() => setChartShift((v) => !v)}
            style={{
              width: 28, height: 24, fontSize: 13,
              display: "flex", alignItems: "center", justifyContent: "center",
              border: "1px solid",
              borderColor: chartShift ? "rgba(38,165,228,0.5)" : "var(--border-light)",
              borderRadius: 4,
              background: chartShift ? "rgba(38,165,228,0.12)" : "transparent",
              color: chartShift ? "#26a5e4" : "var(--text-muted)",
              cursor: "pointer",
            }}
          >⇥</button>

          {/* Mode toggle */}
          <div style={{ display: "flex", gap: 2, background: "var(--bg-surface)", padding: 2, borderRadius: 4, marginLeft: 8 }}>
            <button onClick={() => setChartMode("omega")} style={{
              fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 3,
              background: chartMode === "omega" ? "rgba(38,165,228,0.15)" : "transparent",
              color: chartMode === "omega" ? "#26a5e4" : "var(--text-muted)",
              border: "1px solid",
              borderColor: chartMode === "omega" ? "rgba(38,165,228,0.3)" : "transparent",
              cursor: "pointer",
            }}>OMEGA</button>
            <button onClick={() => setChartMode("normal")} style={{
              fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 3,
              background: chartMode === "normal" ? "rgba(0,208,132,0.15)" : "transparent",
              color: chartMode === "normal" ? "#00d084" : "var(--text-muted)",
              border: "1px solid",
              borderColor: chartMode === "normal" ? "rgba(0,208,132,0.3)" : "transparent",
              cursor: "pointer",
            }}>NORMAL</button>
          </div>

          {/* Live signal badges di toolbar */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, marginLeft: 4 }}>
            {hasArrowBuy  && <span style={{ fontSize: 10, color: "#00E676", fontWeight: 700, background: "rgba(0,230,118,0.12)", padding: "1px 6px", borderRadius: 4, border: "1px solid rgba(0,230,118,0.3)" }}>▲ BUY</span>}
            {hasArrowSell && <span style={{ fontSize: 10, color: "#FF1744", fontWeight: 700, background: "rgba(255,23,68,0.12)", padding: "1px 6px", borderRadius: 4, border: "1px solid rgba(255,23,68,0.3)" }}>▼ SELL</span>}
            {hasCircleBuy  && !hasArrowBuy  && <span style={{ fontSize: 10, color: "#1E90FF", background: "rgba(30,144,255,0.12)", padding: "1px 6px", borderRadius: 4, border: "1px solid rgba(30,144,255,0.3)" }}>● Watch BUY</span>}
            {hasCircleSell && !hasArrowSell && <span style={{ fontSize: 10, color: "#FF6D00", background: "rgba(255,109,0,0.12)", padding: "1px 6px", borderRadius: 4, border: "1px solid rgba(255,109,0,0.3)" }}>● Watch SELL</span>}
            {!hasArrowBuy && !hasArrowSell && !hasCircleBuy && !hasCircleSell &&
              <span style={{ fontSize: 9, color: "var(--text-muted)" }}>no signal</span>}
          </div>
        </div>

        {/* Chart area */}
        <div style={{ flex: 1, position: "relative", minHeight: 260 }}>
          <div ref={containerRef}
            style={{
              position: "absolute", inset: 0,
              cursor: drawTool && drawTool !== "eraser" ? "crosshair" : "default",
            }}
            onClick={handleChartClick}
          />

          {/* Crystal HA Pro Dashboard Overlay — dihapus */}
        </div>
      </div>
    </div>
  );
}

function DashRow({ label, value, color = "#8b8d91" }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 16, fontSize: 11 }}>
      <span style={{ color: "#6b7280", whiteSpace: "nowrap", minWidth: 80 }}>{label}:</span>
      <span style={{ color, fontWeight: 600, whiteSpace: "nowrap", textAlign: "right" }}>{value}</span>
    </div>
  );
}
