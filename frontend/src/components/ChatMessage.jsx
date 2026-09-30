import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { formatTime } from '../lib/format';
import { RoleBadge } from './ui';

/** Links from AI answers open in a new tab; raw HTML is never rendered. */
const markdownComponents = {
  // eslint-disable-next-line no-unused-vars
  a: ({ node, children, ...props }) => (
    <a {...props} target="_blank" rel="noopener noreferrer" className="text-cyan underline">
      {children}
    </a>
  ),
};

function ChatMessage({ message, isOwn, canDelete, onDelete }) {
  const isAi = message.sender_role === 'AI';
  const tone = isAi ? 'border-cyan/50 bg-cyan/[0.04]' : isOwn ? 'ml-auto border-pink/45 bg-pink/[0.04]' : 'border-line bg-panel2';
  const nameColor = isAi ? 'text-cyan' : isOwn ? 'text-pink' : 'text-ink';

  return (
    <article className={`group relative my-2 w-fit max-w-[88%] border px-4 py-2.5 sm:max-w-[78%] ${tone}`} data-message-id={message.id}>
      <header className="mb-1 flex flex-wrap items-center gap-2">
        <span className={`font-display text-[11px] font-bold tracking-wider ${nameColor}`}>{isAi ? 'AI CORE' : message.username}</span>
        {!isAi && message.sender_role !== 'USER' && <RoleBadge role={message.sender_role} />}
        {isOwn && <span className="font-display text-[9px] tracking-wider text-muted">YOU</span>}
        <time className="text-xs text-muted" dateTime={message.created_at}>
          {formatTime(message.created_at)}
        </time>
        {canDelete && (
          <button
            type="button"
            onClick={() => onDelete(message.id)}
            className="ml-auto font-display text-[9px] font-bold tracking-wider text-danger opacity-0 transition focus:opacity-100 group-hover:opacity-100"
            aria-label={`Delete message from ${isAi ? 'AI CORE' : message.username}`}
          >
            DELETE
          </button>
        )}
      </header>
      {isAi ? (
        <div className="markdown text-[15px] leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {message.message}
          </ReactMarkdown>
        </div>
      ) : (
        <p className="whitespace-pre-wrap break-words text-[15px] leading-relaxed">
          {message.message.toLowerCase().startsWith('@ai') ? (
            <>
              <span className="font-bold text-cyan">{message.message.slice(0, 3)}</span>
              {message.message.slice(3)}
            </>
          ) : (
            message.message
          )}
        </p>
      )}
    </article>
  );
}

export default memo(ChatMessage);
