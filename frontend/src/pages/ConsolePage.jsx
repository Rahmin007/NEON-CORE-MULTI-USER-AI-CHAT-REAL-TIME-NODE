import { useCallback, useEffect, useState } from 'react';
import OnlineUsers from '../components/OnlineUsers';
import { Button, Eyebrow, Field, Modal, Panel, Spinner } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useChat } from '../context/ChatContext';
import { useToast } from '../context/ToastContext';
import { api } from '../lib/api';
import { formatDateTime } from '../lib/format';

const LOG_ACTIONS = ['', 'LOGIN_SUCCESS', 'LOGIN_FAILED', 'REGISTER', 'CHAT_MESSAGE', 'MOD_DELETE_MESSAGE', 'MOD_WARN_USER', 'MOD_MUTE_USER', 'MOD_UNMUTE_USER', 'ADMIN_CREATE_USER', 'ADMIN_CHANGE_ROLE', 'ADMIN_CHANGE_STATUS'];

/** Moderators see the moderation tab; admins also get stats, user management and the activity log. */
export default function ConsolePage() {
  const { user } = useAuth();
  const isAdmin = user.role === 'ADMIN';
  const tabs = isAdmin ? ['overview', 'moderation', 'users', 'activity'] : ['moderation'];
  const [tab, setTab] = useState(tabs[0]);

  return (
    <Panel className="flex h-full min-h-0 flex-col">
      <header className="border-b border-line px-5 pt-4">
        <Eyebrow>{isAdmin ? 'ADMIN CONTROL CENTER' : 'MODERATOR CONSOLE'}</Eyebrow>
        <div className="mt-3 flex gap-1 overflow-x-auto" role="tablist" aria-label="Console sections">
          {tabs.map((name) => (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={tab === name}
              onClick={() => setTab(name)}
              className={`whitespace-nowrap px-4 py-2.5 font-display text-[11px] font-bold tracking-widest ${tab === name ? 'border-b-2 border-cyan text-cyan' : 'text-muted hover:text-ink'}`}
            >
              {name.toUpperCase()}
            </button>
          ))}
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {tab === 'overview' && <Overview />}
        {tab === 'moderation' && <Moderation />}
        {tab === 'users' && <Users />}
        {tab === 'activity' && <ActivityLog />}
      </div>
    </Panel>
  );
}

function Moderation() {
  const { user } = useAuth();
  const { online } = useChat();
  return (
    <div className="max-w-2xl">
      <h2 className="font-display text-sm font-bold tracking-widest text-cyan">ONLINE NOW · {online.length}</h2>
      <p className="mt-1 text-sm text-muted">
        Warn or mute users here. Delete a message by hovering it in the lobby. Moderators can act on regular users only.
      </p>
      <div className="mt-4">
        <OnlineUsers me={user} users={online} showActions />
      </div>
    </div>
  );
}

function Overview() {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    api('/admin/stats').then(setStats).catch(() => setStats(false));
  }, []);
  if (stats === null) return <Spinner />;
  if (!stats) return <p className="text-danger">Could not load statistics.</p>;
  const cards = [
    ['Registered users', stats.users],
    ['Active accounts', stats.active_users],
    ['Online now', stats.online],
    ['Messages', stats.messages],
    ['Moderators', stats.moderators],
    ['Admins', stats.admins],
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 md:grid-cols-3">
      {cards.map(([label, value]) => (
        <div key={label} className="border border-line bg-panel2 p-4">
          <dt className="font-display text-[10px] tracking-widest text-muted">{label.toUpperCase()}</dt>
          <dd className="mt-1 font-display text-3xl font-bold text-cyan">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Users() {
  const { user: me } = useAuth();
  const { notify } = useToast();
  const [users, setUsers] = useState(null);
  const [query, setQuery] = useState('');
  const [creating, setCreating] = useState(false);

  const load = useCallback(() => {
    api(`/admin/users?q=${encodeURIComponent(query)}`)
      .then(setUsers)
      .catch((error) => notify(error.message, 'error'));
  }, [query, notify]);

  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  const patch = async (target, path, body, done) => {
    try {
      const updated = await api(`/admin/users/${target.id}/${path}`, { method: 'PATCH', body });
      setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
      notify(done, 'success');
    } catch (error) {
      notify(error.message, 'error');
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Search users" className="w-full max-w-xs" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="username or email" />
        <Button variant="outline" onClick={() => setCreating(true)}>
          + New user
        </Button>
      </div>
      {!users ? (
        <div className="mt-6">
          <Spinner />
        </div>
      ) : (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="font-display text-[10px] tracking-widest text-muted">
              <tr className="border-b border-line">
                <th className="py-2 pr-3">USER</th>
                <th className="py-2 pr-3">ROLE</th>
                <th className="py-2 pr-3">STATUS</th>
                <th className="py-2 pr-3">JOINED</th>
                <th className="py-2">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const self = u.id === me.id;
                return (
                  <tr key={u.id} className="border-b border-line/60">
                    <td className="py-2.5 pr-3">
                      <p className="font-semibold">{u.username}{self && <span className="ml-1 text-muted">(you)</span>}</p>
                      <p className="text-xs text-muted">{u.email}</p>
                    </td>
                    <td className="py-2.5 pr-3">
                      <label className="sr-only" htmlFor={`role-${u.id}`}>Role for {u.username}</label>
                      <select
                        id={`role-${u.id}`}
                        value={u.role}
                        disabled={self}
                        onChange={(e) => patch(u, 'role', { role: e.target.value }, `${u.username} is now ${e.target.value}.`)}
                        className="border border-line bg-bg px-2 py-1 text-ink disabled:opacity-50"
                      >
                        <option value="USER">USER</option>
                        <option value="MODERATOR">MODERATOR</option>
                        <option value="ADMIN">ADMIN</option>
                      </select>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className={u.is_active ? 'text-lime' : 'text-danger'}>{u.is_active ? 'Active' : 'Disabled'}</span>
                    </td>
                    <td className="py-2.5 pr-3 text-muted">{formatDateTime(u.created_at)}</td>
                    <td className="py-2.5">
                      <Button
                        size="sm"
                        variant={u.is_active ? 'danger' : 'outline'}
                        disabled={self}
                        onClick={() => patch(u, 'status', { is_active: !u.is_active }, `${u.username} ${u.is_active ? 'disabled' : 'enabled'}.`)}
                      >
                        {u.is_active ? 'Disable' : 'Enable'}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {users.length === 0 && <p className="mt-4 text-muted">No users match “{query}”.</p>}
        </div>
      )}
      {creating && <CreateUserDialog onClose={() => setCreating(false)} onCreated={load} />}
    </div>
  );
}

function CreateUserDialog({ onClose, onCreated }) {
  const { notify } = useToast();
  const [form, setForm] = useState({ username: '', email: '', password: '', role: 'USER' });
  const [error, setError] = useState('');
  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    try {
      await api('/admin/users', { method: 'POST', body: form });
      notify(`User ${form.username} created.`, 'success');
      onCreated();
      onClose();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal title="CREATE USER" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Username" value={form.username} onChange={update('username')} required minLength={3} />
        <Field label="Email" type="email" value={form.email} onChange={update('email')} required />
        <Field label="Temporary password" type="password" value={form.password} onChange={update('password')} required minLength={8} />
        <div>
          <label htmlFor="new-role" className="mb-1.5 block font-display text-[10px] font-bold tracking-widest text-muted">ROLE</label>
          <select id="new-role" value={form.role} onChange={update('role')} className="h-11 w-full border border-line bg-bg px-3 text-ink">
            <option value="USER">USER</option>
            <option value="MODERATOR">MODERATOR</option>
            <option value="ADMIN">ADMIN</option>
          </select>
        </div>
        {error && <p className="text-sm text-danger" role="alert">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit">Create</Button>
        </div>
      </form>
    </Modal>
  );
}

function ActivityLog() {
  const { notify } = useToast();
  const [rows, setRows] = useState(null);
  const [action, setAction] = useState('');
  const [more, setMore] = useState(false);

  const load = useCallback(
    async (before) => {
      const params = new URLSearchParams({ limit: '100' });
      if (action) params.set('action', action);
      if (before) params.set('before', before);
      try {
        const page = await api(`/logs?${params}`);
        setRows((list) => (before ? [...list, ...page] : page));
        setMore(page.length === 100);
      } catch (error) {
        notify(error.message, 'error');
      }
    },
    [action, notify],
  );

  useEffect(() => {
    setRows(null);
    load();
  }, [load]);

  const details = (value) => (value && typeof value === 'object' ? Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(' · ') : value || '');

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="log-action" className="mb-1.5 block font-display text-[10px] font-bold tracking-widest text-muted">FILTER BY ACTION</label>
          <select id="log-action" value={action} onChange={(e) => setAction(e.target.value)} className="h-11 border border-line bg-bg px-3 text-ink">
            {LOG_ACTIONS.map((a) => (
              <option key={a} value={a}>{a || 'All actions'}</option>
            ))}
          </select>
        </div>
        <Button variant="ghost" onClick={() => { setRows(null); load(); }}>Refresh</Button>
      </div>
      {!rows ? (
        <div className="mt-6"><Spinner /></div>
      ) : (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="font-display text-[10px] tracking-widest text-muted">
              <tr className="border-b border-line">
                <th className="py-2 pr-3">TIME</th>
                <th className="py-2 pr-3">USER</th>
                <th className="py-2 pr-3">ACTION</th>
                <th className="py-2 pr-3">DETAILS</th>
                <th className="py-2">IP</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-line/60 align-top">
                  <td className="whitespace-nowrap py-2 pr-3 text-muted">{formatDateTime(row.created_at)}</td>
                  <td className="py-2 pr-3">{row.username || '—'}</td>
                  <td className="py-2 pr-3"><span className="font-mono text-xs text-cyan">{row.action}</span></td>
                  <td className="py-2 pr-3 text-muted">{details(row.details)}</td>
                  <td className="py-2 font-mono text-xs text-muted">{row.ip_address || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="mt-4 text-muted">No events yet.</p>}
          {more && (
            <div className="mt-4 text-center">
              <Button variant="ghost" onClick={() => load(rows[rows.length - 1].id)}>Load more</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
