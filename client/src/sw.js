import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { registerRoute, NavigationRoute } from 'workbox-routing'
import { createHandlerBoundToURL } from 'workbox-precaching'

cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)

registerRoute(
  new NavigationRoute(createHandlerBoundToURL('index.html'))
)

// NOTE: API responses are intentionally NOT cached. This is a trading app
// where stale prices / PnL would be misleading, and the previous
// NetworkFirst route (/^https:\/\/api.*/) never matched the real backend
// host anyway.

importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js')
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js')

let messagingInitialized = false

function initFirebase(config) {
  if (messagingInitialized) return
  try {
    firebase.initializeApp(config)
    messagingInitialized = true
    const messaging = firebase.messaging()
    messaging.onBackgroundMessage(function (payload) {
      const ntf = payload.notification || {}
      const data = payload.data || {}
      return self.registration.showNotification(ntf.title || 'RevX Trading Bot', {
        body: ntf.body || 'New signal received',
        icon: '/icon-192x192.png',
        badge: '/icon-192x192.png',
        vibrate: [200, 100, 200, 100, 200],
        requireInteraction: true,
        tag: data.signal_id || 'revx-signal',
        renotify: true,
        data: { url: data.url || '/bot-performance' },
      })
    })
  } catch (e) {
    console.warn('[SW] Firebase init error:', e.message)
  }
}

self.addEventListener('message', function (event) {
  if (event.data && event.data.type === 'FIREBASE_CONFIG') {
    initFirebase(event.data.config)
  }
})

self.addEventListener('push', function (event) {
  if (messagingInitialized) return
  let data = {}
  try { data = event.data.json() } catch (e) { /* empty */ }
  const ntf = data.notification || {}
  const pushData = data.data || {}

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
      clients.matchAll({ type: 'window' }).then(function (cls) {
        cls.forEach(function (client) {
          client.postMessage({ type: 'PUSH_RECEIVED', notification: ntf, data: pushData })
        })
      }),
    ])
  )
})

self.addEventListener('notificationclick', function (event) {
  event.notification.close()
  const url = event.notification.data?.url || '/bot-performance'
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (clientList) {
      for (const client of clientList) {
        if (client.url.includes(url) && 'focus' in client) return client.focus()
      }
      if (clients.openWindow) return clients.openWindow(url)
    })
  )
})
