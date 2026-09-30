import { useState } from 'react';
import { api } from '../lib/api';
import { useToast } from '../context/ToastContext';
import { Button, Modal } from './ui';

const DURATIONS = [5, 10, 30, 60, 1440];

/** Warn or mute a user, with a reason (replaces the old browser prompt()). */
export default function ModerationDialog({ target, action, onClose }) {
  const { notify } = useToast();
  const [reason, setReason] = useState('');
  const [minutes, setMinutes] = useState(10);
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const body = action === 'mute' ? { reason, minutes } : { reason };
      const res = await api(`/chat/moderation/${target.id}/${action}`, { method: 'POST', body });
      notify(
        action === 'mute'
          ? `${target.username} is muted for ${minutes} minutes.`
          : res.delivered
            ? `Warning sent to ${target.username}.`
            : `${target.username} is offline. They'll see the warning when they next log in.`,
        'success',
      );
      onClose();
    } catch (error) {
      notify(error.message, 'error');
      setBusy(false);
    }
  };

  return (
    <Modal title={`${action === 'mute' ? 'MUTE' : 'WARN'} ${target.username.toUpperCase()}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {action === 'mute' && (
          <fieldset>
            <legend className="mb-2 font-display text-[10px] font-bold tracking-widest text-muted">DURATION</legend>
            <div className="flex flex-wrap gap-2">
              {DURATIONS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMinutes(value)}
                  aria-pressed={minutes === value}
                  className={`border px-3 py-1.5 text-sm ${minutes === value ? 'border-cyan bg-cyan/10 text-cyan' : 'border-line text-muted hover:text-ink'}`}
                >
                  {value === 1440 ? '24 h' : value >= 60 ? `${value / 60} h` : `${value} min`}
                </button>
              ))}
            </div>
          </fieldset>
        )}
        <div>
          <label htmlFor="mod-reason" className="mb-1.5 block font-display text-[10px] font-bold tracking-widest text-muted">
            REASON {action === 'warn' ? '(shown to the user)' : '(optional)'}
          </label>
          <textarea
            id="mod-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={300}
            rows={3}
            placeholder="e.g. Please keep the chat respectful."
            className="w-full resize-none border border-line bg-[#050a12] px-3 py-2 text-ink outline-none focus:border-cyan"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant={action === 'mute' ? 'danger' : 'warn'} disabled={busy}>
            {action === 'mute' ? 'Mute user' : 'Send warning'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
