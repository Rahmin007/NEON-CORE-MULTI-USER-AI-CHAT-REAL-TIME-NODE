import { useEffect, useId, useRef } from 'react';

const VARIANTS = {
  primary: 'bg-cyan text-bg hover:brightness-110',
  outline: 'border border-cyan text-cyan hover:bg-cyan/10',
  danger: 'border border-danger text-danger hover:bg-danger/10',
  warn: 'border border-amber text-amber hover:bg-amber/10',
  ghost: 'text-muted hover:text-ink hover:bg-white/5',
};
const SIZES = { sm: 'h-8 px-3 text-[10px]', md: 'h-11 px-5 text-xs' };

export function Button({ variant = 'primary', size = 'md', className = '', type = 'button', ...props }) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 font-display font-bold uppercase tracking-wider transition disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    />
  );
}

export function Panel({ as: Tag = 'section', className = '', ...props }) {
  return <Tag className={`border border-line bg-panel/95 shadow-glow ${className}`} {...props} />;
}

export function Eyebrow({ children, className = '' }) {
  return <p className={`font-display text-[10px] font-bold uppercase tracking-[0.2em] text-pink ${className}`}>{children}</p>;
}

export function Field({ label, error, hint, className = '', ...inputProps }) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block font-display text-[10px] font-bold uppercase tracking-[0.18em] text-muted">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={`h-12 w-full border bg-[#050a12] px-4 text-base font-semibold text-ink outline-none transition placeholder:text-muted/60 focus:border-cyan focus:shadow-[0_0_14px_rgba(0,246,255,0.15)] ${error ? 'border-danger' : 'border-line'}`}
        {...inputProps}
      />
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-danger">
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={`${id}-hint`} className="mt-1.5 text-sm text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

const ROLE_STYLES = {
  ADMIN: 'border-pink/60 text-pink',
  MODERATOR: 'border-amber/60 text-amber',
  USER: 'border-line text-muted',
  AI: 'border-cyan/60 text-cyan',
};

export function RoleBadge({ role }) {
  return (
    <span className={`inline-block border px-1.5 py-px font-display text-[9px] font-bold tracking-wider ${ROLE_STYLES[role] || ROLE_STYLES.USER}`}>
      {role === 'MODERATOR' ? 'MOD' : role}
    </span>
  );
}

export function Spinner({ label = 'Loading' }) {
  return (
    <span className="inline-flex items-center gap-2 text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan border-t-transparent" aria-hidden="true" />
      <span className="text-sm">{label}…</span>
    </span>
  );
}

/** Accessible dialog: focuses the first field, closes on Escape or backdrop click. */
export function Modal({ title, children, onClose }) {
  const panelRef = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    panelRef.current?.querySelector('input, textarea, select, button')?.focus();
    const onKey = (event) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      previous?.focus?.();
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-black/70 p-4 backdrop-blur-sm">
      <button type="button" className="absolute inset-0 cursor-default" aria-label="Close dialog" onClick={onClose} tabIndex={-1} />
      <div ref={panelRef} role="dialog" aria-modal="true" aria-label={title} className="relative w-full max-w-md border border-line bg-panel p-6 shadow-glow">
        <h2 className="font-display text-sm font-bold tracking-widest text-cyan">{title}</h2>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}
