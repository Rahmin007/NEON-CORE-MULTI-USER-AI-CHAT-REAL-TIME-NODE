import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

const ToastContext = createContext(null);
const STYLES = {
  info: 'border-cyan text-ink',
  success: 'border-lime text-ink',
  warning: 'border-amber text-ink',
  error: 'border-danger text-ink',
};

/** Small notification pop-ups in the corner. */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), []);

  const notify = useCallback(
    (message, level = 'info', duration = 4500) => {
      const id = ++nextId.current;
      setToasts((list) => [...list.slice(-3), { id, message, level }]);
      setTimeout(() => dismiss(id), duration);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ notify }), [notify]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-[min(92vw,360px)] flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`flex items-start gap-3 border bg-panel2/95 px-4 py-3 text-sm shadow-glow backdrop-blur ${STYLES[toast.level]}`}>
            <p className="flex-1">{toast.message}</p>
            <button type="button" onClick={() => dismiss(toast.id)} className="text-muted hover:text-ink" aria-label="Dismiss notification">
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used inside <ToastProvider>');
  return context;
}
