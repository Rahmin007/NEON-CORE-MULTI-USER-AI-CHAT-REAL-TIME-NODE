import { useState } from 'react';
import { api } from '../lib/api';
import { initials, isStaff } from '../lib/format';
import { useToast } from '../context/ToastContext';
import ModerationDialog from './ModerationDialog';
import { Button, RoleBadge } from './ui';

/** Who's online. Staff also get warn / mute / unmute controls. */
export default function OnlineUsers({ me, users, showActions = false }) {
  const { notify } = useToast();
  const [dialog, setDialog] = useState(null);

  // Moderators can act on regular users; admins on everyone except themselves.
  const canModerate = (user) => isStaff(me) && user.id !== me.id && (me.role === 'ADMIN' || user.role === 'USER');

  const unmute = async (user) => {
    try {
      await api(`/chat/moderation/${user.id}/unmute`, { method: 'POST' });
      notify(`${user.username} can chat again.`, 'success');
    } catch (error) {
      notify(error.message, 'error');
    }
  };

  if (!users.length) return <p className="text-sm text-muted">Nobody is online right now.</p>;

  return (
    <>
      <ul className="divide-y divide-dashed divide-line">
        {users.map((user) => (
          <li key={user.id} className="py-2.5">
            <div className="flex items-center gap-2.5">
              <span className="relative grid h-8 w-8 shrink-0 place-items-center border border-line font-display text-[10px] text-cyan">
                {initials(user.username)}
                <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-lime shadow-[0_0_8px_#75ff68]" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1 truncate font-semibold">
                {user.username}
                {user.id === me.id && <span className="ml-1.5 text-xs font-normal text-muted">(you)</span>}
              </span>
              <RoleBadge role={user.role} />
            </div>
            {showActions && canModerate(user) && (
              <div className="mt-2 flex gap-1.5 pl-[42px]">
                <Button size="sm" variant="warn" onClick={() => setDialog({ user, action: 'warn' })}>
                  Warn
                </Button>
                <Button size="sm" variant="danger" onClick={() => setDialog({ user, action: 'mute' })}>
                  Mute
                </Button>
                <Button size="sm" variant="ghost" onClick={() => unmute(user)}>
                  Unmute
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {dialog && <ModerationDialog target={dialog.user} action={dialog.action} onClose={() => setDialog(null)} />}
    </>
  );
}
