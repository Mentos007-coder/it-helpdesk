self.addEventListener('install', e => {
    e.waitUntil(
      caches.open('helpdesk-v1').then(cache =>
        cache.addAll(['/', '/static/css/style.css', '/static/js/main.js'])
      )
    );
  });
  self.addEventListener('fetch', e => {
    e.respondWith(
      caches.match(e.request).then(resp => resp || fetch(e.request))
    );
  });