import { useEffect, useState } from 'react';

/** Seconds left until `until` (epoch ms), updated every second. */
export function useCountdown(until) {
  const calc = () => Math.max(0, Math.ceil((until - Date.now()) / 1000));
  const [left, setLeft] = useState(calc);
  useEffect(() => {
    setLeft(calc());
    if (!until) return undefined;
    const timer = setInterval(() => {
      const next = calc();
      setLeft(next);
      if (next === 0) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [until]);
  return left;
}
