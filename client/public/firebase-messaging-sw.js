importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

self.addEventListener('install', function() { self.skipWaiting(); });
self.addEventListener('activate', function(event) { event.waitUntil(clients.claim()); });

var firebaseConfig = {"apiKey":"","authDomain":"","projectId":"","storageBucket":"","messagingSenderId":"","appId":""};
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
