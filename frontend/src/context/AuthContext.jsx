import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, tokenStore } from '../lib/api';

const AuthContext = createContext(null);

/** Holds the logged-in user and exposes login / register / logout. */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => tokenStore.get());
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));

  const logout = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await api('/users/me'));
    } catch (error) {
      if (error.status === 401 || error.status === 403) logout();
      throw error;
    }
  }, [logout]);

  // Restore the session on page load.
  useEffect(() => {
    if (!token) return;
    refreshUser()
      .catch(() => {})
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (username, password) => {
    const { access_token: accessToken } = await api('/auth/login', { method: 'POST', form: { username, password }, auth: false });
    tokenStore.set(accessToken);
    setToken(accessToken);
    setUser(await api('/users/me'));
  }, []);

  const register = useCallback(
    async (username, email, password) => {
      await api('/auth/register', { method: 'POST', body: { username, email, password }, auth: false });
      await login(username, password);
    },
    [login],
  );

  const value = useMemo(
    () => ({ user, token, loading, login, register, logout, refreshUser, setUser }),
    [user, token, loading, login, register, logout, refreshUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
