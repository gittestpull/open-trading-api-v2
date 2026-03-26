"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { wsUrl } from "@/lib/api";

export type WsState = "disconnected" | "connecting" | "connected";

interface UseWebSocketOptions {
  path: string;
  onMessage: (data: unknown) => void;
  enabled?: boolean;
  reconnectMs?: number;
}

export function useWebSocket({
  path,
  onMessage,
  enabled = true,
  reconnectMs = 5000,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [state, setState] = useState<WsState>("disconnected");
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    setState("disconnected");
  }, []);

  const connect = useCallback(() => {
    disconnect();
    if (!path || !enabled) return;

    const url = wsUrl(path);
    if (!url) return;

    setState("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setState("connected");
    ws.onclose = () => {
      setState("disconnected");
      reconnectTimer.current = setTimeout(connect, reconnectMs);
    };
    ws.onerror = () => {};
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onMessageRef.current(data);
      } catch {
        // ignore parse errors
      }
    };
  }, [path, enabled, reconnectMs, disconnect]);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return { state, disconnect };
}
