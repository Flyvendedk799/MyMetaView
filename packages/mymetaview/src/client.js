'use strict';

/**
 * Preview lookups against the public API.
 *
 * Three properties matter here, because a crawler is blocked on this call:
 *
 * - bounded: an AbortController kills the request at `timeout`
 * - cached: including misses, so a down API costs one call per minute per URL
 * - de-duplicated: a burst of crawler hits on one URL makes one request
 */

const USER_AGENT_PREFIX = 'mymetaview-node';

class TtlCache {
  constructor(max) {
    this.max = Math.max(1, max);
    this.entries = new Map();
  }

  get(key) {
    const entry = this.entries.get(key);
    if (!entry) return undefined;
    if (entry.expires <= Date.now()) {
      this.entries.delete(key);
      return undefined;
    }
    // Refresh recency so the eviction below drops the coldest key.
    this.entries.delete(key);
    this.entries.set(key, entry);
    return entry.value;
  }

  set(key, value, ttlSeconds) {
    if (ttlSeconds <= 0) return;
    if (this.entries.has(key)) this.entries.delete(key);
    this.entries.set(key, { value, expires: Date.now() + ttlSeconds * 1000 });
    while (this.entries.size > this.max) {
      this.entries.delete(this.entries.keys().next().value);
    }
  }

  clear() {
    this.entries.clear();
  }
}

class PreviewClient {
  /** @param {object} config resolved config from `resolveConfig` */
  constructor(config) {
    this.config = config;
    this.cache = new TtlCache(config.cacheMax);
    this.inflight = new Map();
    this.version = packageVersion();
  }

  endpoint(url, variant) {
    const query = new URLSearchParams({ full_url: url });
    if (this.config.site) query.set('site', this.config.site);
    if (variant) query.set('variant', variant);
    return `${this.config.apiOrigin}/api/v1/public/preview?${query.toString()}`;
  }

  /**
   * Look up the preview for a URL.
   *
   * Never throws: a failure is reported through `onError` and returns null, so
   * the caller ships the page unchanged.
   *
   * @param {string} url
   * @param {{variant?: string}} [options]
   * @returns {Promise<object|null>}
   */
  async getPreview(url, options = {}) {
    if (!url) return null;
    const key = `${url} ${options.variant || ''}`;

    const cached = this.cache.get(key);
    if (cached !== undefined) return cached;

    const pending = this.inflight.get(key);
    if (pending) return pending;

    const request = this._fetchPreview(url, options.variant)
      .then((preview) => {
        this.cache.set(
          key,
          preview,
          preview ? this.config.cacheTtl : this.config.negativeCacheTtl
        );
        return preview;
      })
      .catch((error) => {
        this.cache.set(key, null, this.config.negativeCacheTtl);
        this._report(error, { url });
        return null;
      })
      .finally(() => {
        this.inflight.delete(key);
      });

    this.inflight.set(key, request);
    return request;
  }

  async _fetchPreview(url, variant) {
    const doFetch = this.config.fetch || globalThis.fetch;
    if (typeof doFetch !== 'function') {
      throw new Error('mymetaview: global fetch is unavailable (Node 18+ required)');
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.config.timeout);
    try {
      const response = await doFetch(this.endpoint(url, variant), {
        signal: controller.signal,
        headers: {
          accept: 'application/json',
          'user-agent': `${USER_AGENT_PREFIX}/${this.version}`,
        },
      });
      if (!response.ok) return null;

      const data = await response.json();
      if (!data || !data.title) return null;
      // A fallback carries no generated copy, and the page's own tags are
      // better than a card we would be inventing here.
      if (data.status === 'fallback') return null;
      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  _report(error, context) {
    if (this.config.onError) {
      try {
        this.config.onError(error, context);
      } catch {
        // An error handler that throws is not going to get a second chance to
        // take the response down with it.
      }
    }
  }
}

function packageVersion() {
  try {
    return require('../package.json').version;
  } catch {
    return '0.0.0';
  }
}

module.exports = { PreviewClient, TtlCache };
