'use strict';

/**
 * Fastify plugin.
 *
 *   await fastify.register(require('mymetaview/fastify'))
 *
 * Fastify does not run Connect middleware, and its `onSend` hook is a better
 * fit anyway: the payload is right there, so there is no response patching at
 * all and Content-Length stays accurate.
 */

const { resolveConfig, STATIC_EXTENSION } = require('./config');
const { PreviewClient } = require('./client');
const { isCrawler } = require('./crawlers');
const { renderMetaTags, renderSnippetTag } = require('./tags');
const { applyInjection } = require('./inject');
const { mergeVary } = require('./headers');

function firstHeader(value) {
  return Array.isArray(value) ? value[0] : value;
}

function requestUrl(request) {
  const headers = request.headers || {};
  const host = String(
    firstHeader(headers['x-forwarded-host']) || firstHeader(headers.host) || ''
  )
    .split(',')[0]
    .trim();
  if (!host) return null;

  const forwardedProto = String(firstHeader(headers['x-forwarded-proto']) || '')
    .split(',')[0]
    .trim();
  const protocol = forwardedProto || request.protocol || 'http';

  try {
    const url = new URL(request.url || '/', `${protocol}://${host}`);
    url.hash = '';
    return url;
  } catch {
    return null;
  }
}

function mymetaviewFastify(fastify, options, done) {
  const config = resolveConfig(options);
  const client = new PreviewClient(config);

  fastify.addHook('onSend', async (request, reply, payload) => {
    if (!config.enabled) return payload;
    if (typeof payload !== 'string' && !Buffer.isBuffer(payload)) return payload;
    if (reply.statusCode !== 200) return payload;
    if ((request.method || 'GET').toUpperCase() !== 'GET') return payload;

    const contentType = String(reply.getHeader('content-type') || '');
    if (!/text\/html/i.test(contentType)) return payload;
    const contentEncoding = String(reply.getHeader('content-encoding') || '');
    if (contentEncoding && !/^identity$/i.test(contentEncoding)) return payload;

    const url = requestUrl(request);
    if (!url) return payload;
    if (STATIC_EXTENSION.test(url.pathname)) return payload;
    if (config.skip && config.skip(url.href, request)) return payload;

    const crawler = isCrawler(firstHeader((request.headers || {})['user-agent']));
    const wantsTags = crawler || !config.crawlersOnly;
    const wantsSnippet = config.snippet && !crawler;
    if (!wantsTags && !wantsSnippet) return payload;

    const preview = wantsTags ? await client.getPreview(url.href) : null;
    const buffer = Buffer.isBuffer(payload) ? payload : Buffer.from(payload, 'utf8');
    const out = applyInjection(buffer, {
      metaHtml: preview ? renderMetaTags(preview, url.href) : '',
      snippetHtml: wantsSnippet ? renderSnippetTag(config.snippetUrl, config.site) : '',
      snippetUrl: config.snippetUrl,
    });

    // This URL answers differently per user agent now, so caches in front of
    // the app have to know.
    reply.header('vary', mergeVary(reply.getHeader('vary')));

    if (out.length !== buffer.length) {
      reply.header('content-length', String(out.length));
      // An ETag computed over the app's payload no longer describes this one.
      if (reply.getHeader('etag')) reply.removeHeader('etag');
    }
    return out;
  });

  done();
}

// Fastify encapsulates plugins by default; this hook is meant to cover the
// whole app, so it opts out of the child scope.
mymetaviewFastify[Symbol.for('skip-override')] = true;
mymetaviewFastify[Symbol.for('fastify.display-name')] = 'mymetaview';

module.exports = mymetaviewFastify;
module.exports.default = mymetaviewFastify;
module.exports.mymetaviewFastify = mymetaviewFastify;
