import { useState } from 'react';
import Composer from '../components/Composer';
import MessageList from '../components/MessageList';
import OnlineUsers from '../components/OnlineUsers';
import { ConnectionBadge } from '../components/AppShell';
import { Button, Eyebrow, Panel } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useChat } from '../context/ChatContext';
import { useToast } from '../context/ToastContext';
import { useCountdown } from '../hooks/useCountdown';
import { isStaff } from '../lib/format';

export default function ChatPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const chat = useChat();
  const mutedSeconds = useCountdown(chat.mutedUntil);
  const [showUsers, setShowUsers] = useState(false);

  const send = (text) => {
    const sent = chat.send(text);
    if (!sent) notify('Not connected right now. Your message was kept; try again in a moment.', 'warning');
    return sent;
  };

  const confirmDelete = (id) => {
    if (window.confirm('Delete this message for everyone?')) chat.deleteMessage(id);
  };

  const usersPanel = (
    <>
      <Eyebrow>LIVE NETWORK</Eyebrow>
      <h2 className="mt-1 font-display text-sm font-bold tracking-widest text-cyan">ONLINE · {chat.online.length}</h2>
      <div className="mt-3 min-h-0 flex-1 overflow-y-auto">
        <OnlineUsers me={user} users={chat.online} showActions={isStaff(user)} />
      </div>
    </>
  );

  return (
    <div className="grid h-full min-h-0 grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_300px]">
      <Panel className="flex min-h-0 flex-col">
        <header className="flex items-center gap-3 border-b border-line px-4 py-3 sm:px-6">
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-sm font-bold tracking-widest text-cyan sm:text-base">PUBLIC LOBBY</h1>
            <p className="truncate text-sm text-muted">
              Everyone sees every message · start with <b className="text-cyan">@ai</b> to ask the AI
            </p>
          </div>
          <span className="sm:hidden">
            <ConnectionBadge />
          </span>
          <Button variant="outline" size="sm" className="lg:hidden" onClick={() => setShowUsers((v) => !v)} aria-expanded={showUsers}>
            Online {chat.online.length}
          </Button>
        </header>
        {showUsers && <div className="max-h-64 overflow-y-auto border-b border-line p-4 lg:hidden">{usersPanel}</div>}
        <MessageList
          me={user}
          messages={chat.messages}
          hasMore={chat.hasMore}
          loaded={chat.historyLoaded}
          aiTyping={chat.aiTyping}
          onLoadOlder={chat.loadOlder}
          onDelete={confirmDelete}
        />
        <Composer
          onSend={send}
          mutedSeconds={mutedSeconds}
          disabledReason={chat.status === 'online' ? '' : 'Connecting to the chat server…'}
        />
      </Panel>
      <Panel as="aside" className="hidden min-h-0 flex-col p-5 lg:flex" aria-label="Online users">
        {usersPanel}
      </Panel>
    </div>
  );
}
