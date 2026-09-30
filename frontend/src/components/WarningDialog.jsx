import { useState } from 'react';
import { useChat } from '../context/ChatContext';
import { formatDateTime } from '../lib/format';
import { Button, Modal } from './ui';

/**
 * Shows moderator warnings one at a time. The user has to click "I understand",
 * which is saved on the server so the same warning isn't shown again.
 */
export default function WarningDialog() {
  const { warnings, acknowledgeWarning } = useChat();
  const [busy, setBusy] = useState(false);
  const warning = warnings[0];
  if (!warning) return null;

  const acknowledge = async () => {
    setBusy(true);
    await acknowledgeWarning(warning.id);
    setBusy(false);
  };

  return (
    <Modal title="⚠ WARNING FROM A MODERATOR" onClose={acknowledge}>
      <div className="border-l-4 border-amber bg-amber/10 px-4 py-3">
        <p className="text-lg text-ink">{warning.reason}</p>
      </div>
      <p className="mt-3 text-sm text-muted">
        From <span className="font-semibold text-amber">{warning.from_username}</span> · {formatDateTime(warning.created_at)}
      </p>
      <p className="mt-3 text-sm text-muted">Repeated warnings can lead to being muted or having your account disabled.</p>
      {warnings.length > 1 && <p className="mt-2 text-sm text-amber">You have {warnings.length - 1} more warning(s).</p>}
      <div className="mt-5 flex justify-end">
        <Button variant="warn" onClick={acknowledge} disabled={busy}>
          I understand
        </Button>
      </div>
    </Modal>
  );
}
