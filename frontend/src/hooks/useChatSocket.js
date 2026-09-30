import { useCallback, useEffect, useRef, useState } from 'react';
import { socketUrl } from '../lib/api';

// Close codes sent by the server when reconnecting would not help.
const CLOSE_AUTH_FAILED = 4401;
const CLOSE_ACCOUNT_DISABLED = 4403;

/**
 * Keeps one WebSocket open to the chat server.
 * - Reconnects with increasing delays (1s, 2s, 4s ... 30s) after network drops.
 * - Stops reconnecting when the server says the login is invalid or the account is disabled.
 * - Sends a ping every 25s so proxies don't close an idle connection.
 */
export function useChatSocket(token, { onEvent, onFatalClose }) {
  const [status, setStatus] = useState('connecting'); // connecting | online | offline
  const socketRef = useRef(null);
  const handlers = useRef({ onEvent, onFatalClose });
  handlers.current = { onEvent, onFatalClose };

  useEffect(() => {
    if (!token) return undefined;
    let stopped = false;
    let attempt = 0;
    let retryTimer;
    let pingTimer;

    const connect = () => {
      setStatus('connecting');
      const socket = new WebSocket(socketUrl(token));
      socketRef.current = socket;

      socket.onopen = () => {
        attempt = 0;
        setStatus('online');
        pingTimer = setInterval(() => socket.readyState === WebSocket.OPEN && socket.send(JSON.stringify({ type: 'ping' })), 25000);
      };
      socket.onmessage = (event) => {
        try {
          handlers.current.onEvent(JSON.parse(event.data));
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = (event) => {
        clearInterval(pingTimer);
        // Only forget this socket if it is still the current one: an old socket closing
        // late must not wipe out the reference to its replacement.
        if (socketRef.current === socket) socketRef.current = null;
        if (stopped) return;
        setStatus('offline');
        if (event.code === CLOSE_AUTH_FAILED || event.code === CLOSE_ACCOUNT_DISABLED) {
          handlers.current.onFatalClose?.(event.code);
          return;
        }
        const delay = Math.min(30000, 1000 * 2 ** attempt++);
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      clearInterval(pingTimer);
      socketRef.current?.close();
    };
  }, [token]);

  /** Returns false if the socket is not open (so the caller can keep the draft). */
  const send = useCallback((message) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify({ type: 'message', message }));
    return true;
  }, []);

  return { status, send };
}
