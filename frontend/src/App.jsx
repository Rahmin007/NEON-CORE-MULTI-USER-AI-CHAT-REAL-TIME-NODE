import { Route, Routes } from 'react-router-dom';
import AppShell from './components/AppShell';
import ProtectedRoute from './components/ProtectedRoute';
import { ChatProvider } from './context/ChatContext';
import AuthPage from './pages/AuthPage';
import ChatPage from './pages/ChatPage';
import ConsolePage from './pages/ConsolePage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route
        element={
          <ProtectedRoute>
            <ChatProvider>
              <AppShell />
            </ChatProvider>
          </ProtectedRoute>
        }
      >
        <Route index element={<ChatPage />} />
        <Route
          path="console"
          element={
            <ProtectedRoute roles={['MODERATOR', 'ADMIN']}>
              <ConsolePage />
            </ProtectedRoute>
          }
        />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
