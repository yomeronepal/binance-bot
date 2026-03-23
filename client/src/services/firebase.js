import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage, isSupported } from 'firebase/messaging';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || 'AIzaSyC8aVRYOzcPHhohpNzFRUGItaiTBohQMjU',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'binance-bot-cb351.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'binance-bot-cb351',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || 'binance-bot-cb351.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '932493851566',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '1:932493851566:web:9a3cdbfafce203eee6663f',
};

const VAPID_KEY = import.meta.env.VITE_FIREBASE_VAPID_KEY || 'BFIkedelUGPFVfvl_Yr-G0ZXzZ2KHchARgeS_7AYVpMTWenj-2EN2a7wKjiM9VNU4qaYJ5NzUMQN3Jkl-7JC5Ts';

const IS_IOS = /iPad|iPhone|iPod/.test(navigator.userAgent);

let app = null;
let messaging = null;

function getFirebaseApp() {
  if (!app) app = initializeApp(firebaseConfig);
  return app;
}

async function getFirebaseMessaging() {
  if (IS_IOS) return null;
  if (messaging) return messaging;
  const supported = await isSupported();
  if (!supported) return null;
  messaging = getMessaging(getFirebaseApp());
  return messaging;
}

async function getServiceWorkerRegistration() {
  let reg = await navigator.serviceWorker.getRegistration('/');
  if (!reg) {
    reg = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
  }
  await navigator.serviceWorker.ready;
  if (reg.active) {
    reg.active.postMessage({ type: 'FIREBASE_CONFIG', config: firebaseConfig });
  }
  return reg;
}

export async function requestNotificationPermission() {
  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      console.warn('[PUSH] Permission denied');
      return null;
    }

    const swReg = await getServiceWorkerRegistration();

    if (!IS_IOS) {
      const token = await tryFirebaseToken(swReg);
      if (token) return token;
    }

    const nativeToken = await tryNativePush(swReg);
    if (nativeToken) return nativeToken;

    console.error('[PUSH] All token methods failed');
    return null;
  } catch (error) {
    console.error('[PUSH] requestNotificationPermission error:', error);
    return null;
  }
}

async function tryFirebaseToken(swReg) {
  try {
    const msg = await getFirebaseMessaging();
    if (!msg) return null;
    const token = await getToken(msg, { vapidKey: VAPID_KEY, serviceWorkerRegistration: swReg });
    console.log('[PUSH] FCM token:', token?.substring(0, 30) + '...');
    return token;
  } catch (error) {
    console.warn('[PUSH] Firebase getToken failed:', error.message);
    return null;
  }
}

async function tryNativePush(swReg) {
  try {
    if (!swReg.pushManager) {
      console.warn('[PUSH] PushManager not available');
      return null;
    }

    let subscription = await swReg.pushManager.getSubscription();
    if (!subscription) {
      subscription = await swReg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_KEY),
      });
    }

    const token = btoa(JSON.stringify(subscription.toJSON()));
    console.log('[PUSH] Native push token created');
    return 'native:' + token;
  } catch (error) {
    console.warn('[PUSH] Native push subscribe failed:', error.message);
    return null;
  }
}

export async function onForegroundMessage(callback) {
  try {
    const msg = await getFirebaseMessaging();
    if (msg) {
      return onMessage(msg, (payload) => {
        console.log('[PUSH] Foreground message:', payload);
        callback(payload);
      });
    }

    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'PUSH_RECEIVED') {
        console.log('[PUSH] Foreground message (native):', event.data);
        callback({ notification: event.data.notification, data: event.data.data });
      }
    });
  } catch (error) {
    console.error('[PUSH] onForegroundMessage error:', error);
  }
}

export async function getFCMToken() {
  try {
    if (Notification.permission !== 'granted') return null;
    const swReg = await getServiceWorkerRegistration();
    if (!IS_IOS) {
      const token = await tryFirebaseToken(swReg);
      if (token) return token;
    }
    return await tryNativePush(swReg);
  } catch (error) {
    console.error('[PUSH] getFCMToken error:', error);
    return null;
  }
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
