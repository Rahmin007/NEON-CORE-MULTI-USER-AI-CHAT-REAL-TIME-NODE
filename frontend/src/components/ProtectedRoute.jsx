import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Spinner } from './ui';

/** Only renders children for signed-in users (optionally with one of `roles`). */
export default function ProtectedRoute({ roles, children }) {
  const { user, token, loading } = useAuth();
  const location = useLocation();
  if (loading || (token && !user)) {
    return (
      <div className="grid h-[100dvh] place-items-center">
        <Spinner label="Restoring session" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}
