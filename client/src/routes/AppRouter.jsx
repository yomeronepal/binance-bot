/**
 * Main application router
 */
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import ErrorBoundary from '../components/ErrorBoundary';
import { useAuthStore } from '../store/useAuthStore';

// Layout (kept eager - part of the app shell)
import Layout from '../components/layout/Layout';

// Pages (lazy-loaded so each route ships in its own chunk)
const LandingPage = lazy(() => import('../pages/LandingPage'));
const Login = lazy(() => import('../pages/auth/Login'));
const Register = lazy(() => import('../pages/auth/Register'));
const Dashboard = lazy(() => import('../pages/dashboard/Dashboard'));
const SignalDetail = lazy(() => import('../pages/signals/SignalDetail'));
const SignalList = lazy(() => import('../pages/signals/SignalList'));
const Futures = lazy(() => import('../pages/Futures'));
const PaperTrading = lazy(() => import('../pages/PaperTrading'));
const AutoTrading = lazy(() => import('../pages/AutoTrading'));
const BotPerformance = lazy(() => import('../pages/BotPerformance'));
const DayTradeBotPerformance = lazy(() => import('../pages/DayTradeBotPerformance'));
const SwingBotPerformance = lazy(() => import('../pages/SwingBotPerformance'));
const SwingSignals = lazy(() => import('../pages/SwingSignals'));
const OrderBlockBotPerformance = lazy(() => import('../pages/OrderBlockBotPerformance'));
const OrderBlockSignals = lazy(() => import('../pages/OrderBlockSignals'));
const DayTradeSignals = lazy(() => import('../pages/DayTradeSignals'));
const DayTradeSessions = lazy(() => import('../pages/DayTradeSessions'));
const FuturesPerformance = lazy(() => import('../pages/FuturesPerformance'));
const Backtesting = lazy(() => import('../pages/Backtesting'));
const StrategyDashboard = lazy(() => import('../pages/StrategyDashboard'));
const TradingSessions = lazy(() => import('../pages/TradingSessions'));

const RouteFallback = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-blue-500" />
  </div>
);

const RootRedirect = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <LandingPage />;
};

const AppRouter = () => {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
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
          <Route path="daytrade-performance" element={
            <ErrorBoundary>
              <DayTradeBotPerformance />
            </ErrorBoundary>
          } />
          <Route path="swing-performance" element={
            <ErrorBoundary>
              <SwingBotPerformance />
            </ErrorBoundary>
          } />
          <Route path="swing-signals" element={
            <ErrorBoundary>
              <SwingSignals />
            </ErrorBoundary>
          } />
          <Route path="order-block-performance" element={
            <ErrorBoundary>
              <OrderBlockBotPerformance />
            </ErrorBoundary>
          } />
          <Route path="order-block-signals" element={
            <ErrorBoundary>
              <OrderBlockSignals />
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
          <Route path="daytrade-sessions" element={
            <ErrorBoundary>
              <DayTradeSessions />
            </ErrorBoundary>
          } />
          <Route path="daytrade-signals" element={
            <ErrorBoundary>
              <DayTradeSignals />
            </ErrorBoundary>
          } />
        </Route>

        {/* Catch all - redirect to root */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  );
};

export default AppRouter;
