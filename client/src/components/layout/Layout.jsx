import { useState, useEffect } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import useThemeStore from '../../store/useThemeStore';
import {
  LayoutDashboard, Signal, TrendingUp, FileText, Bot,
  Calendar, BarChart3, Sun, Moon, LogOut, LogIn, Menu,
  X, ChevronLeft, ChevronRight, User
} from 'lucide-react';

const Layout = () => {
  const { user, logout } = useAuthStore();
  const { theme, toggleTheme, initTheme } = useThemeStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('sidebar_collapsed') === 'true';
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    initTheme();
  }, [initTheme]);

  useEffect(() => {
    localStorage.setItem('sidebar_collapsed', collapsed);
  }, [collapsed]);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navLinks = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/spot-signals', label: 'Spot Signals', icon: Signal },
    { to: '/futures', label: 'Futures', icon: TrendingUp },
    { to: '/paper-trading', label: 'Paper Trading', icon: FileText },
    { to: '/bot-performance', label: 'Bot Performance', icon: Bot },
    { to: '/trading-sessions', label: 'Trading Sessions', icon: Calendar },
    ...(user?.is_superuser ? [
      { to: '/futures-performance', label: 'Futures Trade', icon: BarChart3 }
    ] : [])
  ];

  const isActiveLink = (path) => location.pathname === path;

  const SidebarContent = ({ isMobile = false }) => (
    <div className="flex flex-col h-full">
      <div className={`flex items-center ${collapsed && !isMobile ? 'justify-center' : 'justify-between'} px-4 h-16 border-b border-gray-200 dark:border-gray-700`}>
        <Link to="/dashboard" className="flex items-center gap-2 overflow-hidden">
          <img src="/revx-logo.svg" alt="RevX" className="h-8 w-8 flex-shrink-0" />
          {(!collapsed || isMobile) && (
            <span className="text-xl font-bold bg-gradient-to-r from-primary-500 to-purple-500 bg-clip-text text-transparent whitespace-nowrap">
              RevX
            </span>
          )}
        </Link>
        {isMobile && (
          <button onClick={() => setMobileOpen(false)} className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700">
            <X className="w-5 h-5" />
          </button>
        )}
        {!isMobile && (
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="hidden md:flex p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        )}
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navLinks.map((link) => {
          const Icon = link.icon;
          const active = isActiveLink(link.to);
          return (
            <Link
              key={link.to}
              to={link.to}
              title={collapsed && !isMobile ? link.label : undefined}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
                active
                  ? 'bg-primary-500/10 text-primary-600 dark:text-primary-400 border-r-2 border-primary-500'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-700/50 dark:hover:text-white'
              }`}
            >
              <Icon className={`w-5 h-5 flex-shrink-0 ${active ? 'text-primary-500' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'}`} />
              {(!collapsed || isMobile) && <span className="truncate">{link.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 py-4 border-t border-gray-200 dark:border-gray-700 space-y-2">
        <button
          onClick={toggleTheme}
          title={collapsed && !isMobile ? (theme === 'dark' ? 'Light Mode' : 'Dark Mode') : undefined}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700/50 transition-colors"
        >
          {theme === 'dark'
            ? <Sun className="w-5 h-5 flex-shrink-0 text-yellow-400" />
            : <Moon className="w-5 h-5 flex-shrink-0 text-gray-400" />
          }
          {(!collapsed || isMobile) && <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
        </button>

        {user ? (
          <>
            <div className={`flex items-center gap-3 px-3 py-2 ${collapsed && !isMobile ? 'justify-center' : ''}`}>
              <div className="w-8 h-8 rounded-full bg-primary-500/10 flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4 text-primary-500" />
              </div>
              {(!collapsed || isMobile) && (
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{user.username}</p>
                  {user.is_premium && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-gradient-to-r from-yellow-400 to-orange-500 text-white">
                      Premium
                    </span>
                  )}
                </div>
              )}
            </div>
            <button
              onClick={handleLogout}
              title={collapsed && !isMobile ? 'Logout' : undefined}
              className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10 transition-colors"
            >
              <LogOut className="w-5 h-5 flex-shrink-0" />
              {(!collapsed || isMobile) && <span>Logout</span>}
            </button>
          </>
        ) : (
          <Link
            to="/login"
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 transition-colors justify-center"
          >
            <LogIn className="w-5 h-5 flex-shrink-0" />
            {(!collapsed || isMobile) && <span>Sign In</span>}
          </Link>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-gray-50 dark:bg-gray-900 overflow-x-hidden">
      <aside className={`hidden md:flex flex-col fixed inset-y-0 left-0 z-30 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all duration-300 ${
        collapsed ? 'w-[68px]' : 'w-64'
      }`}>
        <SidebarContent />
      </aside>

      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="fixed inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="fixed inset-y-0 left-0 w-72 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 z-50">
            <SidebarContent isMobile />
          </aside>
        </div>
      )}

      <div className={`flex-1 flex flex-col min-h-screen transition-all duration-300 overflow-x-hidden ${collapsed ? 'md:ml-[68px]' : 'md:ml-64'}`}>
        <header className="md:hidden sticky top-0 z-20 flex items-center justify-between h-14 px-4 bg-white/80 dark:bg-gray-800/90 backdrop-blur-lg border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 rounded-lg text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            <Menu className="w-5 h-5" />
          </button>
          <Link to="/dashboard" className="flex items-center gap-2">
            <img src="/revx-logo.svg" alt="RevX" className="h-7 w-7" />
            <span className="text-lg font-bold bg-gradient-to-r from-primary-500 to-purple-500 bg-clip-text text-transparent">RevX</span>
          </Link>
          <button onClick={toggleTheme} className="p-2 rounded-lg text-gray-600 dark:text-gray-300">
            {theme === 'dark' ? <Sun className="w-5 h-5 text-yellow-400" /> : <Moon className="w-5 h-5" />}
          </button>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>

        <footer className="border-t border-gray-200 dark:border-gray-700 bg-white/50 dark:bg-gray-800/50">
          <div className="py-4 px-4 sm:px-6 lg:px-8">
            <p className="text-center text-sm text-gray-500 dark:text-gray-400">
              &copy; 2025 RevX Trading Bot. All rights reserved.
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default Layout;
