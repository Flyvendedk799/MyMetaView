/*!
 * MyMetaView preview snippet
 *
 * Adds Open Graph / Twitter Card meta tags to pages that are missing them, using
 * the preview generated for the page in MyMetaView.
 *
 * Install:
 *   <script src="https://mymetaview.com/snippet.js" defer></script>
 *
 * Optional configuration, set as data-* attributes on the script tag:
 *   data-api="https://mymetaview.com"  Override the API origin (defaults to the
 *                                      origin the script itself was served from).
 *   data-mode="fill" | "replace"       "fill" (default) only adds tags that are
 *                                      missing. "replace" overwrites existing ones.
 *   data-spa="on" | "off"              Re-run on client-side route changes.
 *                                      Defaults to "on".
 *   data-cache="600"                   Seconds to cache a response in sessionStorage.
 *                                      0 disables caching. Defaults to 600.
 *   data-timeout="4000"                Milliseconds before the request is aborted.
 *   data-debug="on"                    Log what the snippet did to the console.
 *                                      Also enabled by adding ?mmv_debug=1 to any URL.
 *
 * The snippet never throws, never blocks rendering, and never overwrites tags
 * you already control unless you ask it to.
 */
(function (window, document) {
  'use strict';

  var VERSION = '2.1.0';
  var GUARD = '__mymetaview__';

  // Only ever run once per document, even if the tag is included twice.
  if (window[GUARD]) return;

  // ---------------------------------------------------------------------------
  // Locate our own <script> tag so we can read configuration off it.
  // ---------------------------------------------------------------------------

  function findSelf() {
    if (document.currentScript) return document.currentScript;
    // `defer`/`async` scripts lose document.currentScript by the time they run,
    // and tag managers inject the tag without it entirely.
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      var src = scripts[i].src || '';
      if (/\/(snippet|s)\.js(\?|$)/.test(src) || scripts[i].hasAttribute('data-mymetaview')) {
        return scripts[i];
      }
    }
    return null;
  }

  var self = findSelf();

  function attr(name, fallback) {
    if (!self) return fallback;
    var value = self.getAttribute('data-' + name);
    return value === null || value === '' ? fallback : value;
  }

  // ---------------------------------------------------------------------------
  // Configuration
  // ---------------------------------------------------------------------------

  function defaultApiOrigin() {
    // Prefer the origin the snippet was served from: that keeps staging and
    // self-hosted installs working without any extra configuration.
    try {
      if (self && self.src) return new URL(self.src, window.location.href).origin;
    } catch (e) { /* fall through */ }
    return 'https://mymetaview.com';
  }

  var config = {
    api: String(attr('api', defaultApiOrigin())).replace(/\/+$/, ''),
    site: attr('site', null),
    mode: attr('mode', 'fill') === 'replace' ? 'replace' : 'fill',
    spa: attr('spa', 'on') !== 'off',
    cacheSeconds: Math.max(0, parseInt(attr('cache', '600'), 10) || 0),
    timeout: Math.max(250, parseInt(attr('timeout', '4000'), 10) || 4000),
    ping: attr('ping', 'on') !== 'off'
  };

  var debug = attr('debug', 'off') === 'on' ||
    /[?&]mmv_debug=1(&|$)/.test(window.location.search);

  function log() {
    if (!debug || !window.console || !window.console.log) return;
    var args = Array.prototype.slice.call(arguments);
    args.unshift('[mymetaview]');
    window.console.log.apply(window.console, args);
  }

  window[GUARD] = { version: VERSION, config: config, applied: [], skipped: [] };
  var state = window[GUARD];

  log('v' + VERSION + ' starting', config);

  // ---------------------------------------------------------------------------
  // URL handling
  // ---------------------------------------------------------------------------

  // Params that identify a campaign or a click, never a distinct page. Dropping
  // them means /pricing?utm_source=x and /pricing share one cache entry and one
  // preview lookup.
  var NOISE_PARAMS = /^(utm_[a-z_]+|fbclid|gclid|dclid|msclkid|twclid|igshid|mc_cid|mc_eid|ref|referrer|_hs(enc|mi)|vero_(id|conv)|yclid|s_kwcid|mmv_debug)$/i;

  function canonicalUrl() {
    try {
      var url = new URL(window.location.href);
      url.hash = '';
      if (url.searchParams && url.searchParams.forEach) {
        var drop = [];
        url.searchParams.forEach(function (_value, key) {
          if (NOISE_PARAMS.test(key)) drop.push(key);
        });
        for (var i = 0; i < drop.length; i++) url.searchParams.delete(drop[i]);
      }
      return url.href;
    } catch (e) {
      return window.location.href;
    }
  }

  // ---------------------------------------------------------------------------
  // Meta tag helpers
  // ---------------------------------------------------------------------------

  function selectorFor(key, isName) {
    return isName ? 'meta[name="' + key + '"]' : 'meta[property="' + key + '"]';
  }

  function existingContent(key, isName) {
    var el = document.querySelector(selectorFor(key, isName));
    if (!el) return null;
    var content = el.getAttribute('content');
    return content && content.trim() !== '' ? content : null;
  }

  function setMeta(key, content, isName) {
    if (!content) return false;

    if (config.mode === 'fill' && existingContent(key, isName) !== null) {
      state.skipped.push(key);
      log('skip ' + key + ' (already set by the page)');
      return false;
    }

    var el = document.querySelector(selectorFor(key, isName));

    if (!el) {
      el = document.createElement('meta');
      el.setAttribute(isName ? 'name' : 'property', key);
      el.setAttribute('data-mymetaview', '');
      // Insert at the top of <head>: some crawlers only read the first few KB.
      var head = document.head || document.getElementsByTagName('head')[0];
      if (!head) return false;
      if (head.firstChild) {
        head.insertBefore(el, head.firstChild);
      } else {
        head.appendChild(el);
      }
    }

    el.setAttribute('content', content);
    state.applied.push(key);
    log('set ' + key + ' = ' + content);
    return true;
  }

  // MyMetaView categorises previews as product/blog/article/landing. Open Graph
  // accepts a different, fixed vocabulary — send a value crawlers understand.
  var OG_TYPES = { product: 'product', blog: 'article', article: 'article', landing: 'website' };

  function applyPreview(data, url) {
    if (!data || !data.title) {
      log('no preview available for', url);
      return 0;
    }

    var before = state.applied.length;

    setMeta('og:url', data.url || url, false);
    setMeta('og:title', data.title, false);
    setMeta('og:description', data.description || '', false);
    setMeta('og:type', OG_TYPES[data.type] || 'website', false);
    setMeta('og:image', data.image_url, false);
    setMeta('og:site_name', data.site_name, false);

    setMeta('twitter:card', 'summary_large_image', true);
    setMeta('twitter:title', data.title, true);
    setMeta('twitter:description', data.description || '', true);
    setMeta('twitter:image', data.image_url, true);

    var count = state.applied.length - before;
    log('applied ' + count + ' tag(s) for ' + url, data);
    return count;
  }

  // ---------------------------------------------------------------------------
  // Response cache (per tab). Avoids a network round trip on repeat views.
  // ---------------------------------------------------------------------------

  function cacheKey(url) {
    return 'mmv:preview:' + VERSION + ':' + url;
  }

  function readCache(url) {
    if (!config.cacheSeconds) return null;
    try {
      var raw = window.sessionStorage.getItem(cacheKey(url));
      if (!raw) return null;
      var entry = JSON.parse(raw);
      if (!entry || (Date.now() - entry.t) > config.cacheSeconds * 1000) {
        window.sessionStorage.removeItem(cacheKey(url));
        return null;
      }
      return entry.d;
    } catch (e) {
      return null;
    }
  }

  function writeCache(url, data) {
    if (!config.cacheSeconds) return;
    try {
      window.sessionStorage.setItem(cacheKey(url), JSON.stringify({ t: Date.now(), d: data }));
    } catch (e) { /* storage full or blocked — caching is optional */ }
  }

  // ---------------------------------------------------------------------------
  // Network
  // ---------------------------------------------------------------------------

  function fetchPreview(url) {
    var endpoint = config.api + '/api/v1/public/preview?full_url=' + encodeURIComponent(url);
    if (config.site) endpoint += '&site=' + encodeURIComponent(config.site);

    var controller = typeof window.AbortController === 'function' ? new window.AbortController() : null;
    var timer = controller ? window.setTimeout(function () { controller.abort(); }, config.timeout) : null;

    return window.fetch(endpoint, {
      method: 'GET',
      credentials: 'omit',
      mode: 'cors',
      cache: 'default',
      signal: controller ? controller.signal : undefined
    }).then(function (res) {
      if (timer) window.clearTimeout(timer);
      if (!res.ok) throw new Error('preview request failed: ' + res.status);
      return res.json();
    }, function (err) {
      if (timer) window.clearTimeout(timer);
      throw err;
    });
  }

  // Tell the dashboard the snippet is live on this domain, so "Verify
  // installation" can succeed even for pages a crawler cannot reach.
  function ping() {
    if (!config.ping) return;
    var key = 'mmv:pinged:' + window.location.host;
    try {
      if (window.sessionStorage.getItem(key)) return;
      window.sessionStorage.setItem(key, '1');
    } catch (e) { /* private mode — ping once per page instead */ }

    var endpoint = config.api + '/api/v1/public/install/ping' +
      '?host=' + encodeURIComponent(window.location.host) +
      '&v=' + encodeURIComponent(VERSION);

    try {
      if (navigator.sendBeacon && navigator.sendBeacon(endpoint)) {
        log('install ping sent (beacon)');
        return;
      }
    } catch (e) { /* fall through to fetch */ }

    try {
      window.fetch(endpoint, { method: 'GET', mode: 'no-cors', cache: 'no-store', keepalive: true });
      log('install ping sent (fetch)');
    } catch (e) { /* nothing else to try; pings are best-effort */ }
  }

  // When a visitor lands here from a social platform, that is a preview click:
  // the share card did its job. Reported once per URL per tab, best-effort.
  var SOCIAL_REFERRERS = /(^|\.)(facebook\.com|fb\.com|m\.facebook\.com|l\.facebook\.com|instagram\.com|l\.instagram\.com|twitter\.com|x\.com|t\.co|linkedin\.com|lnkd\.in|slack\.com|discord\.com|discordapp\.com|reddit\.com|out\.reddit\.com|pinterest\.[a-z.]+|t\.me|telegram\.(me|org)|api\.whatsapp\.com|wa\.me|news\.ycombinator\.com|bsky\.app|mastodon\.[a-z.]+|threads\.net)$/i;

  function reportSocialVisit(url) {
    try {
      var ref = document.referrer;
      if (!ref) return;
      var refHost = new URL(ref).hostname;
      if (!SOCIAL_REFERRERS.test(refHost)) return;

      var key = 'mmv:visit:' + url;
      try {
        if (window.sessionStorage.getItem(key)) return;
        window.sessionStorage.setItem(key, '1');
      } catch (e) { /* private mode — report once per page load */ }

      var endpoint = config.api + '/api/v1/track/social-visit' +
        '?url=' + encodeURIComponent(url) +
        '&ref=' + encodeURIComponent(refHost) +
        (config.site ? '&site=' + encodeURIComponent(config.site) : '');

      if (navigator.sendBeacon && navigator.sendBeacon(endpoint)) {
        log('social visit reported (beacon):', refHost);
        return;
      }
      window.fetch(endpoint, { method: 'GET', mode: 'no-cors', cache: 'no-store', keepalive: true });
      log('social visit reported (fetch):', refHost);
    } catch (e) { /* analytics are optional; never disturb the host page */ }
  }

  // ---------------------------------------------------------------------------
  // Run
  // ---------------------------------------------------------------------------

  var lastUrl = null;

  function run() {
    var url = canonicalUrl();
    if (url === lastUrl) return;
    lastUrl = url;

    var cached = readCache(url);
    if (cached) {
      log('cache hit for', url);
      applyPreview(cached, url);
      return;
    }

    fetchPreview(url)
      .then(function (data) {
        writeCache(url, data);
        applyPreview(data, url);
      })
      .catch(function (err) {
        // Never surface an error to the host page. In debug mode the developer
        // asked to see it.
        log('request failed:', err && err.message ? err.message : err);
      });
  }

  function start() {
    if (!document.head) {
      // Head isn't parsed yet (script placed above it). Retry on the next tick.
      window.setTimeout(start, 10);
      return;
    }
    run();
    ping();
    reportSocialVisit(canonicalUrl());
  }

  // Single-page apps swap the URL without a page load, so re-run on navigation.
  function watchRouteChanges() {
    if (!config.spa || !window.history || !window.history.pushState) return;

    function onNavigate() {
      // Let the framework finish committing the new route before we read it.
      window.setTimeout(run, 0);
    }

    ['pushState', 'replaceState'].forEach(function (method) {
      var original = window.history[method];
      if (typeof original !== 'function') return;
      window.history[method] = function () {
        var result = original.apply(this, arguments);
        onNavigate();
        return result;
      };
    });

    window.addEventListener('popstate', onNavigate);
    log('watching client-side route changes');
  }

  try {
    if (typeof window.fetch !== 'function') {
      log('fetch is unavailable; snippet is a no-op in this browser');
      return;
    }
    start();
    watchRouteChanges();
  } catch (e) {
    // A broken snippet must never break the page it is embedded in.
    log('fatal:', e);
  }
})(window, document);
