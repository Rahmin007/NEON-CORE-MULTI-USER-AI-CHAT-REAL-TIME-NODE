import { useRef, useState } from 'react';
import { formatCountdown } from '../lib/format';
import { Button } from './ui';

const MAX = 2000;

/**
 * Message box. Enter sends, Shift+Enter adds a new line.
 * The draft is only cleared when the message was actually sent.
 */
export default function Composer({ onSend, disabledReason, mutedSeconds }) {
  const [text, setText] = useState('');
  const ref = useRef(null);
  const blocked = Boolean(disabledReason) || mutedSeconds > 0;
  const trimmed = text.trim();

  const resize = (el) => {
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const submit = (event) => {
    event?.preventDefault();
    if (!trimmed || blocked || trimmed.length > MAX) return;
    if (onSend(trimmed)) {
      setText('');
      if (ref.current) ref.current.style.height = 'auto';
    }
  };

  const onKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event);
  };

  const status = mutedSeconds > 0 ? `You are muted for ${formatCountdown(mutedSeconds)}.` : disabledReason;

  return (
    <form onSubmit={submit} className="border-t border-line p-3 sm:p-4">
      {status && (
        <p className="mb-2 text-sm text-amber" role="status">
          {status}
        </p>
      )}
      <div className="flex items-end gap-2">
        <label htmlFor="composer" className="sr-only">
          Message
        </label>
        <textarea
          id="composer"
          ref={ref}
          rows={1}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            resize(event.target);
          }}
          onKeyDown={onKeyDown}
          disabled={mutedSeconds > 0}
          placeholder={mutedSeconds > 0 ? 'You are muted' : 'Message everyone…  (start with @ai to ask the AI)'}
          className="max-h-40 min-h-[48px] flex-1 resize-none border border-line bg-[#050a12] px-4 py-3 text-base text-ink outline-none placeholder:text-muted/70 focus:border-cyan disabled:opacity-60"
        />
        <Button type="submit" className="h-12 min-w-[92px]" disabled={!trimmed || blocked || trimmed.length > MAX}>
          Send
        </Button>
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-muted">
        <span>
          <kbd className="font-mono">Enter</kbd> to send · <kbd className="font-mono">Shift+Enter</kbd> for a new line
        </span>
        <span className={trimmed.length > MAX ? 'text-danger' : ''}>{text.length > MAX - 300 ? `${trimmed.length}/${MAX}` : ''}</span>
      </div>
    </form>
  );
}
