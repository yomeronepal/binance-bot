importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

let messagingInitialized = false;

function initFirebase(config) {
  if (messagingInitialized) return;
  firebase.initializeApp(config);
  messagingInitialized = true;

  const messaging = firebase.messaging();

  messaging.onBackgroundMessage((payload) => {
    const { title, body } = payload.notification || {};
    const data = payload.data || {};

    const notificationTitle = title || 'RevX Trading Bot';
    const notificationOptions = {
      body: body || 'New trading signal received',
      icon: '/icon-192x192.png',
      badge: '/icon-192x192.png',
      vibrate: [200, 100, 200, 100, 200],
      silent: false,
      requireInteraction: true,
      tag: data.signal_id || 'revx-signal',
      renotify: true,
      data: {
        url: data.url || '/bot-performance',
        signal_id: data.signal_id,
        symbol: data.symbol,
        direction: data.direction,
      },
    };

    return self.registration.showNotification(notificationTitle, notificationOptions);
  });
}

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'FIREBASE_CONFIG') {
    initFirebase(event.data.config);
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const url = event.notification.data?.url || '/bot-performance';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
