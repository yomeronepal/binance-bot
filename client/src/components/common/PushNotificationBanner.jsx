import React, { useState, useEffect } from 'react';
import { Bell, X, Loader2, AlertTriangle, Check } from 'lucide-react';
import {
  isPushSubscribed,
  isPushSupported,
  setupForegroundNotifications,
  checkAndResubscribe,
} from '../../services/pushNotification';

const PushNotificationBanner = () => {
  const [subscribed, setSubscribed] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [supported, setSupported] = useState(true);
  const [errorMsg, setErrorMsg] = useState(null);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const sup = isPushSupported();
    setSupported(sup);
    setSubscribed(isPushSubscribed());
    setDismissed(localStorage.getItem('push_banner_dismissed') === 'true');

    if (isPushSubscribed() && sup) {
      const initPush = async () => {
        await checkAndResubscribe();
        await setupForegroundNotifications(handleForegroundMessage);
        console.log('[PUSH] Foreground listener registered');
      };
      initPush();
    }
  }, []);

  const handleForegroundMessage = (payload) => {
    setToast({
      title: payload.notification?.title || 'New Signal',
      body: payload.notification?.body || '',
      data: payload.data,
    });
    setTimeout(() => setToast(null), 8000);
  };

  const handleSubscribe = async () => {
    setLoading(true);
    setErrorMsg(null);

    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setErrorMsg('Notification permission denied. Check browser settings.');
        setLoading(false);
        return;
      }

      const { requestNotificationPermission } = await import('../../services/firebase');
      const token = await requestNotificationPermission();

      if (!token) {
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        if (isIOS) {
          setErrorMsg('Push notifications are not yet supported on iOS Safari. Use Chrome on desktop or Android for push alerts.');
        } else {
          setErrorMsg('Failed to enable notifications. Try refreshing the page or use Chrome/Edge.');
        }
        setLoading(false);
        return;
      }

      const api = (await import('../../services/api')).default;
      const deviceName = `${navigator.userAgent.includes('Mobile') ? 'Mobile' : 'Desktop'} - ${navigator.platform}`;

      const response = await api.post('/public/push/subscribe/', {
        fcm_token: token,
        device_name: deviceName,
      });

      localStorage.setItem('push_subscribed', 'true');
      localStorage.setItem('fcm_token', token);
      setSubscribed(true);
      await setupForegroundNotifications(handleForegroundMessage);
      console.log('[PUSH] Subscribed and foreground listener registered');

    } catch (err) {
      console.error('Push subscribe error:', err);
      setErrorMsg(`Failed: ${err.message || 'Unknown error'}`);
    }

    setLoading(false);
  };

  const handleUnsubscribe = async () => {
    setLoading(true);
    const token = localStorage.getItem('fcm_token');
    if (token) {
      try {
        const api = (await import('../../services/api')).default;
        await api.post('/push/unsubscribe/', { fcm_token: token });
      } catch (e) {
        console.error('Unsubscribe error:', e);
      }
    }
    localStorage.removeItem('push_subscribed');
    localStorage.removeItem('fcm_token');
    setSubscribed(false);
    setLoading(false);
  };

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem('push_banner_dismissed', 'true');
  };

  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;

  if (!supported) {
    if (isIOS && !isStandalone) {
      return (
        <div className="bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30 rounded-lg p-3 text-sm text-indigo-600 dark:text-indigo-400 flex items-start gap-2">
          <Bell className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Install app for push notifications</p>
            <p className="text-xs mt-1 opacity-80">
              Tap the share button <span className="inline-block align-middle">⬆️</span> then "Add to Home Screen" to enable notifications.
            </p>
          </div>
          <button onClick={handleDismiss} className="p-1 text-gray-400 hover:text-gray-600 flex-shrink-0">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      );
    }
    return null;
  }

  if (dismissed && !subscribed) return null;

  return (
    <>
      {!subscribed && (
        <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-200 dark:border-indigo-500/30 rounded-lg p-3 sm:p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <Bell className="w-5 h-5 text-indigo-500 flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white">
                  Enable push notifications
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 hidden sm:block">
                  Get instant alerts for new trading signals
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={handleSubscribe}
                disabled={loading}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs sm:text-sm font-medium rounded-lg transition-colors disabled:opacity-50 flex items-center gap-1.5"
              >
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Bell className="w-3.5 h-3.5" />}
                Enable
              </button>
              <button
                onClick={handleDismiss}
                className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          {errorMsg && (
            <div className="mt-2 text-xs text-red-500 dark:text-red-400 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3 flex-shrink-0" />
              {errorMsg}
            </div>
          )}
        </div>
      )}

      {subscribed && !dismissed && (
        <div className="bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30 rounded-lg p-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Check className="w-4 h-4 text-green-500" />
            <span className="text-sm text-green-700 dark:text-green-400">Push notifications enabled</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleUnsubscribe}
              disabled={loading}
              className="text-xs text-gray-500 hover:text-red-500 transition-colors"
            >
              Disable
            </button>
            <button onClick={handleDismiss} className="p-1 text-gray-400 hover:text-gray-600">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed top-4 right-4 z-50 max-w-sm">
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-2xl p-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 bg-indigo-100 dark:bg-indigo-500/20 rounded-full flex items-center justify-center flex-shrink-0">
                <Bell className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-gray-900 dark:text-white">{toast.title}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{toast.body}</p>
              </div>
              <button onClick={() => setToast(null)} className="text-gray-400 hover:text-gray-600">
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default PushNotificationBanner;
