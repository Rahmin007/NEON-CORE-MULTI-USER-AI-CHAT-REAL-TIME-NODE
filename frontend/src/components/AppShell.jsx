import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useChat } from '../context/ChatContext';
import { initials, isStaff } from '../lib/format';
import Brand from './Brand';
import WarningDialog from './WarningDialog';
import { Button, RoleBadge } from './ui';

const STATUS = {
  online: { label: 'LIVE', color: 'bg-lime shadow-[0_0_10px_#75ff68]', text: 'text-lime' },
  connecting: { label: 'CONNECTING', color: 'bg-amber animate-pulse', text: 'text-amber' },
  offline: { label: 'RECONNECTING', color: 'bg-danger animate-pulse', text: 'text-danger' },
};

export function ConnectionBadge() {
  const { status } = useChat();
  const s = STATUS[status];
  return (
    <span className={`inline-flex items-center gap-2 font-display text-[10px] font-bold tracking-widest ${s.text}`} role="status">
      <span className={`h-2 w-2 rounded-full ${s.color}`} aria-hidden="true" />
      {s.label}
    </span>
  );
}

const navClass = ({ isActive }) =>
  `px-3 py-2 font-display text-[11px] font-bold tracking-widest transition ${isActive ? 'text-cyan' : 'text-muted hover:text-ink'}`;

/** Top bar + page area for signed-in users. */
export default function AppShell() {
  const { user, logout } = useAuth();
  return (
    <div className="mx-auto flex h-[100dvh] max-w-[1500px] flex-col gap-3 p-3 sm:p-4">
      <header className="flex h-16 shrink-0 items-center gap-3 border border-line bg-panel/90 px-4 sm:px-5">
        <Brand compact />
        <nav aria-label="Main" className="ml-2 flex">
          <NavLink to="/" end className={navClass}>
            LOBBY
          </NavLink>
          {isStaff(user) && (
            <NavLink to="/console" className={navClass}>
              CONSOLE
            </NavLink>
          )}
        </nav>
        <div className="ml-auto flex items-center gap-4">
          <span className="hidden sm:inline-flex">
            <ConnectionBadge />
          </span>
          <div className="hidden items-center gap-2 md:flex">
            <span className="grid h-9 w-9 place-items-center border border-pink font-display text-[11px] text-pink">{initials(user.username)}</span>
            <div className="leading-tight">
              <p className="font-semibold">{user.username}</p>
              <RoleBadge role={user.role} />
            </div>
          </div>
          <Button variant="danger" size="sm" onClick={logout}>
            Log out
          </Button>
        </div>
      </header>
      <main id="main" className="min-h-0 flex-1">
        <Outlet />
      </main>
      <WarningDialog />
    </div>
  );
}
