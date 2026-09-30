import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { useChatSocket } from '../hooks/useChatSocket';
import { useAuth } from './AuthContext';
import { useToast } from './ToastContext';

const ChatContext = createContext(null);
const PAGE_SIZE = 50;

/**
 * Owns the live chat state for the whole signed-in app, so the lobby and the
 * console share one connection and one list of online users.
 */
export function ChatProvider({ children }) {
  const { token, logout, refreshUser } = useAuth();
  const { notify } = useToast();
  const [messages, setMessages] = useState([]);
  const [online, setOnline] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [aiTyping, setAiTyping] = useState(null); // username who asked, or null
  const [mutedUntil, setMutedUntil] = useState(0); // epoch ms
  const [warnings, setWarnings] = useState([]); // unacknowledged moderator warnings

  const onEvent = useCallback(
    (event) => {
      switch (event.type) {
        case 'message':
          setMessages((list) => (list.some((m) => m.id === event.message.id) ? list : [...list, event.message]));
          break;
        case 'message_deleted':
          setMessages((list) => list.filter((m) => m.id !== event.message_id));
          break;
        case 'presence':
          setOnline(event.users || []);
          break;
        case 'ai_typing':
          setAiTyping(event.active ? event.requested_by : null);
          break;
        case 'session':
          setMutedUntil(event.muted_seconds ? Date.now() + event.muted_seconds * 1000 : 0);
          if (event.muted_seconds === 0 && mutedUntil) notify('You can chat again.', 'success');
          break;
        case 'warning':
          setWarnings((list) => (list.some((w) => w.id === event.warning.id) ? list : [...list, event.warning]));
          break;
        case 'role_changed':
          notify(`Your role is now ${event.role}.`, 'info');
          refreshUser().catch(() => {});
          break;
        case 'notice':
          notify(event.message, event.level || 'info');
          break;
        case 'error':
          notify(event.message, 'error');
          break;
        default:
          break;
      }
    },
    [notify, refreshUser, mutedUntil],
  );

  const onFatalClose = useCallback(
    (code) => {
      notify(code === 4403 ? 'Your account has been disabled.' : 'Your session has expired. Please log in again.', 'error', 8000);
      logout();
    },
    [logout, notify],
  );

  const { status, send } = useChatSocket(token, { onEvent, onFatalClose });

  // Load the latest messages once per login.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api(`/chat/history?limit=${PAGE_SIZE}`)
      .then((rows) => {
        if (cancelled) return;
        setMessages(rows);
        setHasMore(rows.length === PAGE_SIZE);
      })
      .catch((error) => notify(error.message, 'error'))
      .finally(() => !cancelled && setHistoryLoaded(true));
    return () => {
      cancelled = true;
    };
  }, [token, notify]);

  const loadOlder = useCallback(async () => {
    if (!messages.length) return;
    const rows = await api(`/chat/history?limit=${PAGE_SIZE}&before=${messages[0].id}`);
    setMessages((list) => [...rows, ...list]);
    setHasMore(rows.length === PAGE_SIZE);
  }, [messages]);

  const deleteMessage = useCallback(
    async (id) => {
      try {
        await api(`/chat/messages/${id}`, { method: 'DELETE' });
        notify('Message deleted.', 'success');
      } catch (error) {
        notify(error.message, 'error');
      }
    },
    [notify],
  );

  /** Marks a warning as read on the server, then removes it from the screen. */
  const acknowledgeWarning = useCallback(
    async (id) => {
      try {
        await api(`/users/me/warnings/${id}/acknowledge`, { method: 'POST' });
      } catch (error) {
        if (error.status !== 404) {
          notify(error.message, 'error');
          return;
        }
      }
      setWarnings((list) => list.filter((w) => w.id !== id));
    },
    [notify],
  );

  const value = useMemo(
    () => ({ messages, online, hasMore, historyLoaded, aiTyping, mutedUntil, warnings, status, send, loadOlder, deleteMessage, acknowledgeWarning }),
    [messages, online, hasMore, historyLoaded, aiTyping, mutedUntil, warnings, status, send, loadOlder, deleteMessage, acknowledgeWarning],
  );
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) throw new Error('useChat must be used inside <ChatProvider>');
  return context;
}
