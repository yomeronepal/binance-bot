importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

let messagingInitialized = false;

function initFirebase(config) {
  if (messagingInitialized) return;
  firebase.initializeApp(config);
  messagingInitialized = true;
  setupMessaging();
}

function setupMessaging() {
  const messaging = firebase.messaging();
  messaging.onBackgroundMessage((payload) => {
    const ntf = payload.notification || {};
    const data = payload.data || {};
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
}

var buildConfig = {"apiKey":"AIzaSyC8aVRYOzcPHhohpNzFRUGItaiTBohQMjU","authDomain":"binance-bot-cb351.firebaseapp.com","projectId":"binance-bot-cb351","storageBucket":"binance-bot-cb351.firebasestorage.app","messagingSenderId":"932493851566","appId":"1:932493851566:web:9a3cdbfafce203eee6663f"};
if (buildConfig.projectId) {
  initFirebase(buildConfig);
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'FIREBASE_CONFIG') {
    initFirebase(event.data.config);
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  var url = event.notification.data?.url || '/bot-performance';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (var i = 0; i < clientList.length; i++) {
        if (clientList[i].url.includes(self.location.origin) && 'focus' in clientList[i]) {
          clientList[i].navigate(url);
          return clientList[i].focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
