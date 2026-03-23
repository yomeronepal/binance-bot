import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { writeFileSync } from 'fs'
import { resolve } from 'path'

function generateCombinedSW(envVars) {
  return {
    name: 'generate-combined-sw',
    buildStart() {
      const env = { ...process.env, ...envVars }
      const config = {
        apiKey: env.VITE_FIREBASE_API_KEY || '',
        authDomain: env.VITE_FIREBASE_AUTH_DOMAIN || '',
        projectId: env.VITE_FIREBASE_PROJECT_ID || '',
        storageBucket: env.VITE_FIREBASE_STORAGE_BUCKET || '',
        messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
        appId: env.VITE_FIREBASE_APP_ID || '',
      }

      const sw = `importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

self.addEventListener('install', function() { self.skipWaiting(); });
self.addEventListener('activate', function(event) { event.waitUntil(clients.claim()); });

var firebaseConfig = ${JSON.stringify(config)};
var messagingInitialized = false;

function initFirebase(config) {
  if (messagingInitialized) return;
  try {
    firebase.initializeApp(config);
    messagingInitialized = true;

    var messaging = firebase.messaging();
    messaging.onBackgroundMessage(function(payload) {
      var ntf = payload.notification || {};
      var data = payload.data || {};
      return self.registration.showNotification(ntf.title || 'RevX Trading Bot', {
        body: ntf.body || 'New trading signal received',
        icon: '/icon-192x192.png',
        badge: '/icon-192x192.png',
        vibrate: [200, 100, 200, 100, 200],
        silent: false,
        requireInteraction: true,
        tag: data.signal_id || 'revx-signal',
        renotify: true,
        data: { url: data.url || '/bot-performance', signal_id: data.signal_id, symbol: data.symbol, direction: data.direction },
      });
    });
  } catch(e) {
    console.error('[SW] Firebase init error:', e);
  }
}

if (firebaseConfig.projectId) {
  initFirebase(firebaseConfig);
}

self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'FIREBASE_CONFIG') {
    initFirebase(event.data.config);
  }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  var url = event.notification.data && event.notification.data.url ? event.notification.data.url : '/bot-performance';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (var i = 0; i < clientList.length; i++) {
        if (clientList[i].url.indexOf(self.location.origin) !== -1 && 'focus' in clientList[i]) {
          clientList[i].navigate(url);
          return clientList[i].focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});

self.addEventListener('push', function(event) {
  if (messagingInitialized) return;
  var data = {};
  try { data = event.data.json(); } catch(e) {}
  var ntf = data.notification || {};
  var pushData = data.data || {};

  event.waitUntil(
    Promise.all([
      self.registration.showNotification(ntf.title || 'RevX Trading Bot', {
        body: ntf.body || 'New signal received',
        icon: '/icon-192x192.png',
        badge: '/icon-192x192.png',
        vibrate: [200, 100, 200, 100, 200],
        requireInteraction: true,
        tag: pushData.signal_id || 'revx-signal',
        renotify: true,
        data: { url: pushData.url || '/bot-performance' },
      }),
      clients.matchAll({ type: 'window' }).then(function(cls) {
        cls.forEach(function(client) {
          client.postMessage({ type: 'PUSH_RECEIVED', notification: ntf, data: pushData });
        });
      })
    ])
  );
});
`
      writeFileSync(resolve('public', 'firebase-messaging-sw.js'), sw)
    }
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
  plugins: [
    generateCombinedSW(env),
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      devOptions: {
        enabled: true,
        type: 'module',
      },
      includeAssets: ['revx-logo.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'RevX - Binance Trading Bot',
        short_name: 'RevX',
        description: 'Advanced cryptocurrency trading bot with AI-powered signals',
        theme_color: '#0f172a',
        background_color: '#0f172a',
        display: 'standalone',
        icons: [
          {
            src: '/icon-192x192.png?v=2',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any maskable'
          },
          {
            src: '/icon-512x512.png?v=2',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable'
          }
        ]
      },
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}'],
        globIgnores: ['firebase-messaging-sw.js'],
      }
    })
  ],
}
})
