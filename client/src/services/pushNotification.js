import api from './api';
import { requestNotificationPermission, getFCMToken, onForegroundMessage } from './firebase';

const PUSH_SUBSCRIBE_URL = '/public/push/subscribe/';

export async function subscribeToPush() {
  const token = await requestNotificationPermission();
  if (!token) return { success: false, reason: 'permission_denied' };

  try {
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

export function setupForegroundNotifications(onNotification) {
  return onForegroundMessage((payload) => {
    const { title, body } = payload.notification || {};
    if (title) {
      new Notification(title, {
        body,
        icon: '/icon-192x192.png',
        badge: '/icon-192x192.png',
        data: payload.data,
      });
    }
    if (onNotification) onNotification(payload);
  });
}

export async function checkAndResubscribe() {
  if (!isPushSupported()) return;
  if (!isPushSubscribed()) return;
  if (Notification.permission !== 'granted') return;

  const currentToken = await getFCMToken();
  const storedToken = localStorage.getItem('fcm_token');

  if (currentToken && currentToken !== storedToken) {
    const deviceName = `${navigator.userAgent.includes('Mobile') ? 'Mobile' : 'Desktop'} - ${navigator.platform}`;
    try {
      await api.post(PUSH_SUBSCRIBE_URL, {
        fcm_token: currentToken,
        device_name: deviceName,
      });
      localStorage.setItem('fcm_token', currentToken);
      console.log('FCM token refreshed');
    } catch (error) {
      console.error('FCM token refresh failed:', error);
    }
  }
}
