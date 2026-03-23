import api from './api';

const PUSH_SUBSCRIBE_URL = '/public/push/subscribe/';

export async function subscribeToPush() {
  try {
    const { requestNotificationPermission } = await import('./firebase');
    const token = await requestNotificationPermission();
    if (!token) return { success: false, reason: 'permission_denied' };

    const deviceName = `${navigator.userAgent.includes('Mobile') ? 'Mobile' : 'Desktop'} - ${navigator.platform}`;
    const response = await api.post(PUSH_SUBSCRIBE_URL, {
      fcm_token: token,
      device_name: deviceName,
    });
    localStorage.setItem('push_subscribed', 'true');
    localStorage.setItem('fcm_token', token);
    return { success: true, data: response.data };
  } catch (error) {
    console.error('Push subscribe failed:', error);
    return { success: false, reason: 'api_error', error };
  }
}

export async function unsubscribeFromPush() {
  const token = localStorage.getItem('fcm_token');
  if (!token) return { success: true };

  try {
    await api.post('/push/unsubscribe/', { fcm_token: token });
    localStorage.removeItem('push_subscribed');
    localStorage.removeItem('fcm_token');
    return { success: true };
  } catch (error) {
    console.error('Push unsubscribe failed:', error);
    return { success: false, error };
  }
}

export function isPushSubscribed() {
  return localStorage.getItem('push_subscribed') === 'true';
}

export function isPushSupported() {
  return 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window;
}

export async function setupForegroundNotifications(onNotification) {
  try {
    const { onForegroundMessage } = await import('./firebase');
    return onForegroundMessage((payload) => {
      console.log('[PUSH] Foreground message received:', payload);
      const { title, body } = payload.notification || {};
      if (title && Notification.permission === 'granted') {
        new Notification(title, {
          body,
          icon: '/icon-192x192.png',
          badge: '/icon-192x192.png',
          data: payload.data,
        });
      }
      if (onNotification) onNotification(payload);
    });
  } catch (error) {
    console.error('[PUSH] Failed to setup foreground notifications:', error);
  }
}

export async function checkAndResubscribe() {
  if (!isPushSupported()) return;
  if (!isPushSubscribed()) return;
  if (Notification.permission !== 'granted') return;

  try {
    const { getFCMToken } = await import('./firebase');
    const currentToken = await getFCMToken();
    const storedToken = localStorage.getItem('fcm_token');

    if (currentToken && currentToken !== storedToken) {
      const deviceName = `${navigator.userAgent.includes('Mobile') ? 'Mobile' : 'Desktop'} - ${navigator.platform}`;
      await api.post(PUSH_SUBSCRIBE_URL, {
        fcm_token: currentToken,
        device_name: deviceName,
      });
      localStorage.setItem('fcm_token', currentToken);
      console.log('[PUSH] FCM token refreshed');
    }
  } catch (error) {
    console.error('[PUSH] Token refresh failed:', error);
  }
}
