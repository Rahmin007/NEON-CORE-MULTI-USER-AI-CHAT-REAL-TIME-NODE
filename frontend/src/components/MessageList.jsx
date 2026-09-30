import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { formatDay, isStaff } from '../lib/format';
import ChatMessage from './ChatMessage';
import { Button, Spinner } from './ui';

/**
 * Scrollable message history with day separators, "load older", and smart auto-scroll:
 * it only jumps to new messages when you're already near the bottom.
 */
export default function MessageList({ me, messages, hasMore, loaded, aiTyping, onLoadOlder, onDelete }) {
  const scrollRef = useRef(null);
  const atBottomRef = useRef(true);
  const prevHeightRef = useRef(null);
  const [unseen, setUnseen] = useState(0);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const lastId = messages[messages.length - 1]?.id;

  const scrollToBottom = (smooth = false) => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
    setUnseen(0);
  };

  // Keep the reading position when older messages are added on top.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && prevHeightRef.current !== null) {
      el.scrollTop += el.scrollHeight - prevHeightRef.current;
      prevHeightRef.current = null;
    }
  }, [messages]);

  useEffect(() => {
    if (!lastId) return;
    const last = messages[messages.length - 1];
    if (atBottomRef.current || last.user_id === me.id) scrollToBottom(loaded);
    else setUnseen((n) => n + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastId]);

  useEffect(() => {
    if (aiTyping && atBottomRef.current) scrollToBottom(true);
  }, [aiTyping]);

  const onScroll = () => {
    const el = scrollRef.current;
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (atBottomRef.current) setUnseen(0);
  };

  const loadOlder = async () => {
    setLoadingOlder(true);
    prevHeightRef.current = scrollRef.current.scrollHeight;
    try {
      await onLoadOlder();
    } catch {
      prevHeightRef.current = null;
    } finally {
      setLoadingOlder(false);
    }
  };

  let lastDay = null;
  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="h-full overflow-y-auto px-4 py-4 sm:px-6"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {!loaded && (
          <div className="grid h-full place-items-center">
            <Spinner label="Loading messages" />
          </div>
        )}
        {loaded && hasMore && (
          <div className="mb-3 text-center">
            <Button variant="ghost" size="sm" onClick={loadOlder} disabled={loadingOlder}>
              {loadingOlder ? 'Loading…' : 'Load older messages'}
            </Button>
          </div>
        )}
        {loaded && messages.length === 0 && (
          <div className="grid h-full place-items-center text-center">
            <div>
              <p className="font-display text-sm tracking-widest text-muted">NO TRANSMISSIONS YET</p>
              <p className="mt-2 text-muted">Say hello, or ask the AI something with <b className="text-cyan">@ai</b>.</p>
            </div>
          </div>
        )}
        {messages.map((message) => {
          const day = formatDay(message.created_at);
          const divider = day !== lastDay;
          lastDay = day;
          return (
            <div key={message.id}>
              {divider && (
                <div className="my-4 flex items-center gap-3 text-[10px] font-display tracking-widest text-muted" role="separator">
                  <span className="h-px flex-1 bg-line" />
                  {day.toUpperCase()}
                  <span className="h-px flex-1 bg-line" />
                </div>
              )}
              <ChatMessage message={message} isOwn={message.user_id === me.id && message.sender_role !== 'AI'} canDelete={isStaff(me)} onDelete={onDelete} />
            </div>
          );
        })}
        {aiTyping && (
          <p className="my-3 flex items-center gap-2 text-sm text-cyan" aria-live="polite">
            <span className="flex gap-1" aria-hidden="true">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan [animation-delay:120ms]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan [animation-delay:240ms]" />
            </span>
            AI CORE is answering {aiTyping}…
          </p>
        )}
      </div>
      {unseen > 0 && (
        <button
          type="button"
          onClick={() => scrollToBottom(true)}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 border border-cyan bg-panel px-3 py-1.5 font-display text-[10px] font-bold tracking-wider text-cyan shadow-glow"
        >
          {unseen} NEW MESSAGE{unseen > 1 ? 'S' : ''} ↓
        </button>
      )}
    </div>
  );
}
