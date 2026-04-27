/**
 * Main application router
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import ErrorBoundary from '../components/ErrorBoundary';
import { useAuthStore } from '../store/useAuthStore';

// Layout
import Layout from '../components/layout/Layout';

// Pages
import LandingPage from '../pages/LandingPage';
import Login from '../pages/auth/Login';
import Register from '../pages/auth/Register';
import Dashboard from '../pages/dashboard/Dashboard';
import SignalDetail from '../pages/signals/SignalDetail';
import SignalList from '../pages/signals/SignalList';
import Futures from '../pages/Futures';
import PaperTrading from '../pages/PaperTrading';
import AutoTrading from '../pages/AutoTrading';
import BotPerformance from '../pages/BotPerformance';
import FuturesPerformance from '../pages/FuturesPerformance';
import Backtesting from '../pages/Backtesting';
import StrategyDashboard from '../pages/StrategyDashboard';
import TradingSessions from '../pages/TradingSessions';
import ConnectBinance from '../pages/ConnectBinance';

const RootRedirect = () => {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <LandingPage />;
};

const AppRouter = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* Root - Landing page or Dashboard for authenticated users */}
        <Route path="/" element={<RootRedirect />} />

        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Public Routes with Layout */}
        <Route element={<Layout />}>
          <Route path="bot-performance" element={
            <ErrorBoundary>
              <BotPerformance />
            </ErrorBoundary>
          } />
        </Route>

        {/* Protected routes with Layout */}
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="spot-signals" element={<SignalList />} />
          <Route path="spot-signals/:id" element={<SignalDetail />} />
          <Route path="signals" element={<Navigate to="/spot-signals" replace />} />
          <Route path="signals/:id" element={<Navigate to="/spot-signals/:id" replace />} />
          <Route path="futures" element={<Futures />} />
          <Route path="futures-performance" element={
            <ErrorBoundary>
              <FuturesPerformance />
            </ErrorBoundary>
          } />
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
          <Route path="backtesting" element={
            <ErrorBoundary>
              <Backtesting />
            </ErrorBoundary>
          } />
          <Route path="strategy-dashboard" element={
            <ErrorBoundary>
              <StrategyDashboard />
            </ErrorBoundary>
          } />
          <Route path="trading-sessions" element={
            <ErrorBoundary>
              <TradingSessions />
            </ErrorBoundary>
          } />
          <Route path="connect-binance" element={
            <ErrorBoundary>
              <ConnectBinance />
            </ErrorBoundary>
          } />
        </Route>

        {/* Catch all - redirect to root */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default AppRouter;
