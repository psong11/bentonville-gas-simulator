/**
 * WebSocket Hook for Real-time Updates
 * Manages connection, reconnection, and message handling
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './useApi';

export type WSMessageType =
  | 'SET_PRESSURE'
  | 'SET_DEMAND_MULTIPLIER'
  | 'INJECT_LEAK'
  | 'CLEAR_LEAKS'
  | 'HIGHLIGHT_PIPE'
  | 'SIMULATION_UPDATE'
  | 'NETWORK_UPDATE'
  | 'LEAK_ALERT'
  | 'ERROR';

interface WSMessage {
  type: WSMessageType;
  payload: Record<string, unknown>;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastUpdate: Date | null;
  sendMessage: (type: WSMessageType, payload: Record<string, unknown>) => void;
  setPressure: (value: number) => void;
  setDemandMultiplier: (value: number) => void;
  injectLeak: (count: number) => void;
  clearLeaks: () => void;
  highlightPipe: (pipeId: number | null) => void;
}

export function useWebSocket(): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const queryClient = useQueryClient();

  // Send message through WebSocket
  const sendMessage = useCallback((type: WSMessageType, payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }, []);

  // Convenience methods
  const setPressure = useCallback((value: number) => {
    sendMessage('SET_PRESSURE', { value });
  }, [sendMessage]);

  const setDemandMultiplier = useCallback((value: number) => {
    sendMessage('SET_DEMAND_MULTIPLIER', { value });
  }, [sendMessage]);

  const injectLeak = useCallback((count: number) => {
    sendMessage('INJECT_LEAK', { count });
  }, [sendMessage]);

  const clearLeaks = useCallback(() => {
    sendMessage('CLEAR_LEAKS', {});
  }, [sendMessage]);

  const highlightPipe = useCallback((pipeId: number | null) => {
    sendMessage('HIGHLIGHT_PIPE', { pipeId });
  }, [sendMessage]);

  // Handle incoming messages
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WSMessage = JSON.parse(event.data);
      
      switch (message.type) {
        case 'SIMULATION_UPDATE':
          // Update simulation cache with fresh data
          queryClient.setQueryData(queryKeys.simulation, message.payload);
          setLastUpdate(new Date());
          break;
          
        case 'NETWORK_UPDATE':
          // Invalidate network cache to refetch
          queryClient.invalidateQueries({ queryKey: queryKeys.network });
          setLastUpdate(new Date());
          break;
          
        case 'LEAK_ALERT':
          // Invalidate both to get updated state
          queryClient.invalidateQueries({ queryKey: queryKeys.network });
          queryClient.invalidateQueries({ queryKey: queryKeys.simulation });
          setLastUpdate(new Date());
          break;
          
        case 'ERROR':
          console.error('WebSocket error from server:', message.payload);
          break;
          
        default:
          console.log('Unknown WebSocket message type:', message.type);
      }
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err);
    }
  }, [queryClient]);

  // Connect to WebSocket
  useEffect(() => {
    const connect = () => {
      // Determine WebSocket URL
      // In production: use VITE_WS_URL environment variable (Railway backend)
      // In development: auto-detect based on current location
      let wsUrl: string;
      
      if (import.meta.env.VITE_WS_URL) {
        // Production: use configured WebSocket URL
        wsUrl = `${import.meta.env.VITE_WS_URL}/ws`;
      } else {
        // Development: connect to local backend
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = import.meta.env.DEV ? '8000' : window.location.port;
        wsUrl = `${protocol}//${host}:${port}/ws`;
      }
      
      console.log('Connecting to WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        // Clear any pending reconnect
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);
        wsRef.current = null;
        
        // Reconnect after delay (unless intentionally closed)
        if (event.code !== 1000) {
          reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };

    connect();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting');
      }
    };
  }, [handleMessage]);

  return {
    isConnected,
    lastUpdate,
    sendMessage,
    setPressure,
    setDemandMultiplier,
    injectLeak,
    clearLeaks,
    highlightPipe,
  };
}
