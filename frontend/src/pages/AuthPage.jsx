import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import Brand from '../components/Brand';
import { Button, Eyebrow, Field, Panel } from '../components/ui';
import { useAuth } from '../context/AuthContext';

const USERNAME_RULE = /^[A-Za-z0-9_.-]{3,30}$/;

function validate(mode, form) {
  const errors = {};
  if (mode === 'register') {
    if (!USERNAME_RULE.test(form.username)) errors.username = '3–30 characters: letters, numbers, . _ or -';
    if (!/^\S+@\S+\.\S+$/.test(form.email)) errors.email = 'Enter a valid email address.';
    if (form.password.length < 8) errors.password = 'Use at least 8 characters.';
  } else {
    if (!form.username.trim()) errors.username = 'Enter your username.';
    if (!form.password) errors.password = 'Enter your password.';
  }
  return errors;
}

export default function AuthPage() {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={location.state?.from?.pathname || '/'} replace />;

  const update = (field) => (event) => {
    setForm((f) => ({ ...f, [field]: event.target.value }));
    if (errors[field]) setErrors((e) => ({ ...e, [field]: undefined }));
  };

  const switchMode = (next) => {
    setMode(next);
    setErrors({});
    setServerError('');
  };

  const submit = async (event) => {
    event.preventDefault();
    const found = validate(mode, form);
    setErrors(found);
    setServerError('');
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      if (mode === 'login') await login(form.username.trim(), form.password);
      else await register(form.username.trim(), form.email.trim(), form.password);
      navigate('/', { replace: true });
    } catch (error) {
      setServerError(error.message);
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-[100dvh] place-items-center p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="inline-block text-left">
            <Brand />
          </div>
        </div>
        <Panel className="p-6 sm:p-8">
          <Eyebrow>SECURE ACCESS NODE</Eyebrow>
          <h1 className="mt-2 font-display text-2xl font-extrabold text-cyan sm:text-3xl">
            {mode === 'login' ? 'ENTER THE GRID' : 'CREATE IDENTITY'}
          </h1>
          <p className="mt-1 text-muted">A public, real-time chat room with an AI you can summon with @ai.</p>

          <div className="mt-6 grid grid-cols-2 border-b border-line" role="tablist" aria-label="Account">
            {['login', 'register'].map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={mode === tab}
                onClick={() => switchMode(tab)}
                className={`py-3 font-display text-[11px] font-bold tracking-widest ${mode === tab ? 'border-b-2 border-cyan text-cyan' : 'text-muted hover:text-ink'}`}
              >
                {tab === 'login' ? 'LOG IN' : 'REGISTER'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} noValidate className="mt-6 space-y-4">
            <Field label="Username" autoComplete="username" value={form.username} onChange={update('username')} error={errors.username} autoFocus />
            {mode === 'register' && (
              <Field label="Email" type="email" autoComplete="email" value={form.email} onChange={update('email')} error={errors.email} />
            )}
            <Field
              label="Password"
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              value={form.password}
              onChange={update('password')}
              error={errors.password}
              hint={mode === 'register' ? 'At least 8 characters.' : undefined}
            />
            {serverError && (
              <p className="border border-danger/50 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
                {serverError}
              </p>
            )}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? 'Connecting…' : mode === 'login' ? 'Log in' : 'Create account'}
            </Button>
          </form>
        </Panel>
        <p className="mt-4 text-center text-xs text-muted">FastAPI · WebSockets · MongoDB · JWT · Role-based access</p>
      </div>
    </main>
  );
}
