/**
 * Main application router
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import ErrorBoundary from '../components/ErrorBoundary';

// Layout
import Layout from '../components/layout/Layout';

// Pages
import Login from '../pages/auth/Login';
import Register from '../pages/auth/Register';
import Dashboard from '../pages/dashboard/Dashboard';
import SignalDetail from '../pages/signals/SignalDetail';
import SignalList from '../pages/signals/SignalList';
import Futures from '../pages/Futures';
import PaperTrading from '../pages/PaperTrading';
import AutoTrading from '../pages/AutoTrading';
import BotPerformance from '../pages/BotPerformance';

const AppRouter = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/bot-performance" element={
          <ErrorBoundary>
            <BotPerformance />
          </ErrorBoundary>
        } />

        {/* Protected routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="spot-signals" element={<SignalList />} />
          <Route path="spot-signals/:id" element={<SignalDetail />} />
          <Route path="signals" element={<Navigate to="/spot-signals" replace />} />
          <Route path="signals/:id" element={<Navigate to="/spot-signals/:id" replace />} />
          <Route path="futures" element={<Futures />} />
          <Route path="paper-trading" element={
            <ErrorBoundary>
              <PaperTrading />
            </ErrorBoundary>
          } />
          <Route path="auto-trading" element={
            <ErrorBoundary>
              <AutoTrading />
            </ErrorBoundary>
          } />
        </Route>

        {/* Catch all - redirect to dashboard */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default AppRouter;
