'use strict';

/**
 * Option resolution.
 *
 * The whole point of this package is that `npm install mymetaview` plus one
 * line is enough, so every option has a working default and every one of them
 * can also come from the environment — which is how you configure a container
 * you would rather not rebuild.
 */

const DEFAULT_API_ORIGIN = 'https://mymetaview.com';

/** Files that are never HTML, skipped before we touch the response at all. */
const STATIC_EXTENSION = /\.(?:js|mjs|cjs|css|map|json|xml|txt|ico|png|jpe?g|gif|svg|webp|avif|woff2?|ttf|otf|eot|mp4|webm|mp3|wasm|pdf|zip)$/i;

function envString(name) {
  const value = process.env[name];
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed === '' ? undefined : trimmed;
}

function envBool(name) {
  const value = envString(name);
  if (value === undefined) return undefined;
  return !/^(0|false|no|off)$/i.test(value);
}

function envInt(name) {
  const value = envString(name);
  if (value === undefined) return undefined;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function pick(...candidates) {
  for (const candidate of candidates) {
    if (candidate !== undefined && candidate !== null) return candidate;
  }
  return undefined;
}

function normalizeHost(value) {
  if (!value) return '';
  let candidate = String(value).trim().toLowerCase();
  if (candidate.includes('//')) {
    candidate = candidate.split('//')[1] || candidate;
  }
  candidate = candidate.split('/')[0].split('@').pop().split(':')[0].replace(/\.$/, '');
  return candidate.startsWith('www.') ? candidate.slice(4) : candidate;
}

/**
 * Merge explicit options with the environment and the defaults.
 *
 * @param {object} [options]
 * @returns {object} frozen, fully-populated config
 */
function resolveConfig(options = {}) {
  if (options && typeof options !== 'object') {
    throw new TypeError('mymetaview: options must be an object');
  }

  const apiOrigin = String(
    pick(options.apiOrigin, envString('MYMETAVIEW_API_ORIGIN'), DEFAULT_API_ORIGIN)
  ).replace(/\/+$/, '');

  const config = {
    apiOrigin,
    // Optional: only needed when previews are owned by a domain other than the
    // one serving the request (a subdomain served by the apex's account).
    site: normalizeHost(pick(options.site, envString('MYMETAVIEW_SITE'), '')),
    enabled: pick(options.enabled, envBool('MYMETAVIEW_ENABLED'), true),
    // The browser snippet powers install verification and click analytics; the
    // meta tags are what crawlers read. Both are on by default.
    snippet: pick(options.snippet, envBool('MYMETAVIEW_SNIPPET'), true),
    snippetUrl: pick(options.snippetUrl, envString('MYMETAVIEW_SNIPPET_URL'), `${apiOrigin}/snippet.js`),
    // A crawler is waiting on this fetch, so it is bounded hard. On timeout the
    // page ships with whatever tags it already had.
    timeout: pick(options.timeout, envInt('MYMETAVIEW_TIMEOUT_MS'), 1500),
    cacheTtl: pick(options.cacheTtl, envInt('MYMETAVIEW_CACHE_TTL'), 300),
    cacheMax: pick(options.cacheMax, envInt('MYMETAVIEW_CACHE_MAX'), 500),
    // A miss is cached too, briefly, so an unreachable API cannot be re-dialled
    // on every single crawler hit.
    negativeCacheTtl: pick(options.negativeCacheTtl, envInt('MYMETAVIEW_NEGATIVE_CACHE_TTL'), 60),
    // How much of the document we will hold while looking for </head>.
    maxHeadBytes: pick(options.maxHeadBytes, envInt('MYMETAVIEW_MAX_HEAD_BYTES'), 256 * 1024),
    // Serving previews to humans as well as crawlers is opt-in: it puts the API
    // in the path of every page view, which is not a trade most sites want.
    crawlersOnly: pick(options.crawlersOnly, envBool('MYMETAVIEW_CRAWLERS_ONLY'), true),
    // Called with (error, context) instead of throwing. A broken preview must
    // never be able to break a page.
    onError: typeof options.onError === 'function' ? options.onError : null,
    // (url, req) => boolean. Return true to leave a request completely alone.
    skip: typeof options.skip === 'function' ? options.skip : null,
    fetch: typeof options.fetch === 'function' ? options.fetch : null,
  };

  if (!/^https?:\/\//i.test(config.apiOrigin)) {
    throw new TypeError(`mymetaview: apiOrigin must be an http(s) URL, got "${config.apiOrigin}"`);
  }

  return Object.freeze(config);
}

module.exports = {
  DEFAULT_API_ORIGIN,
  STATIC_EXTENSION,
  normalizeHost,
  resolveConfig,
};
