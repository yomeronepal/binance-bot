import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, onMessage } from 'firebase/messaging';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || 'AIzaSyC8aVRYOzcPHhohpNzFRUGItaiTBohQMjU',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'binance-bot-cb351.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'binance-bot-cb351',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || 'binance-bot-cb351.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '932493851566',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '1:932493851566:web:9a3cdbfafce203eee6663f',
};

let app = null;
let messaging = null;

function getFirebaseApp() {
  if (!app) {
    app = initializeApp(firebaseConfig);
  }
  return app;
}

function getFirebaseMessaging() {
  if (!messaging) {
    messaging = getMessaging(getFirebaseApp());
  }
  return messaging;
}

async function getServiceWorkerRegistration() {
  await navigator.serviceWorker.ready;

  const regs = await navigator.serviceWorker.getRegistrations();
  for (const reg of regs) {
    if (reg.active) {
      reg.active.postMessage({ type: 'FIREBASE_CONFIG', config: firebaseConfig });
      return reg;
    }
  }

  const fbReg = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
  await navigator.serviceWorker.ready;
  if (fbReg.active) {
    fbReg.active.postMessage({ type: 'FIREBASE_CONFIG', config: firebaseConfig });
  }
  return fbReg;
}

export async function requestNotificationPermission() {
  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      console.warn('[PUSH] Notification permission denied');
      return null;
    }

    const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY || 'BFIkedelUGPFVfvl_Yr-G0ZXzZ2KHchARgeS_7AYVpMTWenj-2EN2a7wKjiM9VNU4qaYJ5NzUMQN3Jkl-7JC5Ts';
    const swRegistration = await getServiceWorkerRegistration();
    const msg = getFirebaseMessaging();

    const token = await getToken(msg, {
      vapidKey,
      serviceWorkerRegistration: swRegistration,
    });

    console.log('[PUSH] FCM Token:', token?.substring(0, 30) + '...');
    return token;
  } catch (error) {
    console.error('[PUSH] Failed to get FCM token:', error);
    return null;
  }
}

export function onForegroundMessage(callback) {
  try {
    const msg = getFirebaseMessaging();
    return onMessage(msg, (payload) => {
      console.log('[PUSH] Foreground message received:', payload);
      callback(payload);
    });
  } catch (error) {
    console.error('[PUSH] onForegroundMessage error:', error);
  }
}

export async function getFCMToken() {
  try {
    if (Notification.permission !== 'granted') return null;

    const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY || 'BFIkedelUGPFVfvl_Yr-G0ZXzZ2KHchARgeS_7AYVpMTWenj-2EN2a7wKjiM9VNU4qaYJ5NzUMQN3Jkl-7JC5Ts';
    const swRegistration = await getServiceWorkerRegistration();
    const msg = getFirebaseMessaging();

    return await getToken(msg, {
      vapidKey,
      serviceWorkerRegistration: swRegistration,
    });
  } catch (error) {
    console.error('[PUSH] Failed to get FCM token:', error);
    return null;
  }
}
