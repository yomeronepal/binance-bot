/**
 * Main App Component
 * Root component that initializes the application
 */
import { useEffect } from 'react';
import AppRouter from './routes/AppRouter';
import { useAuthStore } from './store/useAuthStore';

function App() {
  const { loadUser } = useAuthStore();

  useEffect(() => {
    // Load user on app mount
    loadUser();
  }, []);

  return <AppRouter />;
}

export default App;
