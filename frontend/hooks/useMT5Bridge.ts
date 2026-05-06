"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/store/useAppStore";
import { BRIDGE_CONNECTED_EVENT } from "@/hooks/useSignalVoice";
import type { Timeframe, Candle, CrystalHACandle, Position, PendingOrder } from "@/types";

const HEARTBEAT_INTERVAL = 10_000;
const MAX_BACKOFF = 30_000;

export function useMT5Bridge() {
  const store         = useAppStore();
  const wsRef         = useRef<WebSocket | null>(null);
  const attemptRef    = useRef(0);
  const timerRef      = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingRef       = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef    = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    const url = store.bridgeUrl;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      store.setWs(ws);

      ws.onopen = () => {
        attemptRef.current = 0;
        store.setConnected(true);
        store.addToast("success", "Bridge terhubung!");
        // 🔊 Trigger welcome voice di useSignalVoice
        window.dispatchEvent(new Event(BRIDGE_CONNECTED_EVENT));

        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ cmd: "get_auto_status" }));
        }, HEARTBEAT_INTERVAL);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          handleMessage(msg);
        } catch {/* ignore parse errors */}
      };

      ws.onclose = () => {
        store.setConnected(false);
        store.setWs(null);
        if (pingRef.current) clearInterval(pingRef.current);
        if (!mountedRef.current) return;

        const delay = Math.min(1000 * 2 ** attemptRef.current, MAX_BACKOFF);
        attemptRef.current++;
        timerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      const delay = Math.min(1000 * 2 ** attemptRef.current, MAX_BACKOFF);
      attemptRef.current++;
      timerRef.current = setTimeout(connect, delay);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store.bridgeUrl]);

  function handleMessage(msg: Record<string, unknown>) {
    const type = msg.type as string;

    if (type === "tick") {
      // Throttle tick: hanya update kalau harga berubah minimal 0.01
      const newBid = msg.bid as number;
      const curPrice = useAppStore.getState().currentPrice;
      if (Math.abs(newBid - curPrice) >= 0.01) {
        store.updatePrice(newBid, msg.ask as number);
      }
    } else if (type === "candles") {
      store.updateCandles(msg.timeframe as Timeframe, msg.data as Candle[]);
    } else if (type === "crystal_ha") {
      const tf   = msg.timeframe as Timeframe;
      const data = msg.data as CrystalHACandle[];
      // Throttle: hanya update kalau candle terakhir berubah
      const existing = useAppStore.getState().crystalHA[tf];
      const lastNew  = data[data.length - 1];
      const lastOld  = existing?.[existing.length - 1];
      if (
        !lastOld ||
        lastNew?.time     !== lastOld?.time ||
        lastNew?.ha_close !== lastOld?.ha_close ||
        lastNew?.ha_open  !== lastOld?.ha_open
      ) {
        store.updateCrystalHA(tf, data);
      }
    } else if (type === "positions") {
      store.updatePositions(msg.data as Position[]);
    } else if (type === "orders") {
      store.updateOrders(msg.data as PendingOrder[]);
    } else if (type === "auto_trading_status") {
      store.updateAutoStatus({
        enabled:         msg.enabled as boolean,
        scan_interval:   msg.scan_interval as number,
        max_positions:   msg.max_positions as number,
        max_daily_loss:  msg.max_daily_loss as number,
        session_filter:  msg.session_filter as string[],
        daily_loss:      msg.daily_loss_current as number,
        trades_today:    msg.total_auto_trades_today as number,
        last_scan:       msg.last_scan as string,
        last_signal:     msg.last_signal as string,
        ha_trend:        (msg.ha_trend as string)  || "",
        status_text:     (msg.status_text as string) || "",
        equity:          (msg.equity as number)      || 0,
        balance:         (msg.balance as number)     || 0,
        free_margin:     (msg.free_margin as number) || 0,
        log:             (msg.auto_log as []) || [],
      });
    } else if (type === "trailing_update") {
      store.addToast("info", `📈 Trail SL updated → ${(msg.new_sl as number).toFixed(2)}`);
    } else if (type === "rejection_status") {
      const statusMap: Record<string, string> = {
        waiting_rejection: `🎯 Rejection trigger kena! Menunggu entry...`,
        executed:          `✅ Rejection entry tereksekusi @ ${msg.exec_price}`,
        timeout:           `❌ Rejection order timeout — dibatalkan`,
      };
      const toastMsg = statusMap[msg.status as string];
      if (toastMsg) store.addToast(msg.status === "timeout" ? "warning" : "success", toastMsg);
    } else if (type === "auto_trade_executed") {
      const dir = (msg.direction as string).toUpperCase();
      store.addToast("success", `🤖 AUTO ${dir} ${msg.volume} @ ${(msg.entry as number).toFixed(2)} (conf: ${msg.confidence}%)`);
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(`AUTO ${dir}`, { body: `${msg.volume} @ ${(msg.entry as number).toFixed(2)} | Conf: ${msg.confidence}%` });
      }
    } else if (type === "error") {
      store.addToast("error", msg.message as string);
    } else if (type === "disconnected") {
      store.addToast("warning", "🔴 Bridge terputus — mencoba reconnect...");
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
    connect();

    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (pingRef.current) clearInterval(pingRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return {
    isConnected: store.isConnected,
    sendCommand: store.sendCommand,
  };
}
