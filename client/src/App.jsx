/**
 * Main App Component
 * Root component that initializes the application
 */
import { useEffect } from 'react';
import AppRouter from './routes/AppRouter';
import { useAuthStore } from './store/useAuthStore';
import useThemeStore from './store/useThemeStore';

function App() {
  const { loadUser } = useAuthStore();
  const { initTheme } = useThemeStore();

  useEffect(() => {
    // Initialize theme first (before loading user)
    initTheme();
    // Load user on app mount
    loadUser();
  }, []);

  return <AppRouter />;
}

export default App;
