'use strict';

/**
 * The Express/Connect middleware, and the response filter behind it.
 *
 * What it does, in one sentence: when a social crawler asks for an HTML page,
 * the page it gets back has this site's MyMetaView card in its <head>, put
 * there server-side, which is the only kind of tag most crawlers ever see.
 *
 * The preview lookup starts the moment the request arrives and is awaited only
 * when the <head> has been buffered, so the app renders in parallel with the
 * API call rather than after it. Every failure path ends in "ship the page
 * exactly as the app wrote it".
 */

const { STATIC_EXTENSION, resolveConfig } = require('./config');
const { PreviewClient } = require('./client');
const { isCrawler } = require('./crawlers');
const { renderMetaTags, renderSnippetTag } = require('./tags');
const { HeadScanner, applyInjection } = require('./inject');
const { mergeVary } = require('./headers');

function header(req, name) {
  const value = req.headers ? req.headers[name] : undefined;
  return Array.isArray(value) ? value[0] : value;
}

/** Reconstruct the URL the visitor actually asked for, proxies included. */
function requestUrl(req) {
  const forwardedHost = header(req, 'x-forwarded-host');
  const host = (forwardedHost || header(req, 'host') || '').split(',')[0].trim();
  if (!host) return null;

  const forwardedProto = (header(req, 'x-forwarded-proto') || '').split(',')[0].trim();
  const secure = req.socket && req.socket.encrypted;
  const protocol = forwardedProto || (secure ? 'https' : 'http');

  try {
    const url = new URL(req.originalUrl || req.url || '/', `${protocol}://${host}`);
    url.hash = '';
    return url;
  } catch {
    return null;
  }
}

function toBuffer(chunk, encoding) {
  if (chunk == null) return null;
  if (Buffer.isBuffer(chunk)) return chunk;
  return Buffer.from(chunk, typeof encoding === 'string' ? encoding : 'utf8');
}

function headerName(headers, name) {
  if (!headers || typeof headers !== 'object' || Array.isArray(headers)) return undefined;
  return Object.keys(headers).find((key) => key.toLowerCase() === name);
}

/**
 * Patch a response so the buffered head comes back through `render`.
 *
 * @param {import('http').ServerResponse} res
 * @param {{maxHeadBytes: number, render: (buffer: Buffer) => Promise<Buffer>}} options
 */
function filterResponse(res, options) {
  const originalWrite = res.write;
  const originalEnd = res.end;
  const originalWriteHead = res.writeHead;

  const scanner = new HeadScanner(options.maxHeadBytes);
  const callbacks = [];
  const queued = [];

  let eligibility = null;
  let contentTypeHint = '';
  let contentEncodingHint = '';
  let passthrough = false;
  let flushing = false;

  function restore() {
    res.write = originalWrite;
    res.end = originalEnd;
    res.writeHead = originalWriteHead;
  }

  function giveUp() {
    passthrough = true;
    restore();
  }

  /** HTML, 200, and nobody has compressed it yet. */
  function eligible() {
    if (eligibility !== null) return eligibility;
    const type = String(contentTypeHint || res.getHeader('content-type') || '');
    const encoding = String(contentEncodingHint || res.getHeader('content-encoding') || '');
    eligibility =
      res.statusCode === 200 &&
      /text\/html/i.test(type) &&
      (encoding === '' || /^identity$/i.test(encoding));
    if (!eligibility) giveUp();
    return eligibility;
  }

  function runCallbacks() {
    while (callbacks.length) {
      const callback = callbacks.shift();
      try {
        callback();
      } catch {
        // A write callback that throws is the app's problem, not the response's.
      }
    }
  }

  function drainQueue() {
    while (queued.length) {
      const op = queued.shift();
      if (op.type === 'end') {
        originalEnd.call(res, op.chunk, op.callback);
        return;
      }
      originalWrite.call(res, op.chunk, op.callback);
    }
  }

  async function flush(endOp) {
    flushing = true;
    if (endOp && endOp.chunk) scanner.push(endOp.chunk);
    if (endOp && endOp.callback) callbacks.push(endOp.callback);

    const buffered = scanner.release();
    let out = buffered;
    try {
      out = await options.render(buffered);
    } catch {
      out = buffered;
    }

    if (!res.headersSent) {
      // This URL now answers differently per user agent, whether or not this
      // particular response was rewritten.
      res.setHeader('Vary', mergeVary(res.getHeader('Vary')));

      if (out.length !== buffered.length) {
        // We cannot know the final length while the rest of the document is
        // still being written, so it goes out chunked — and an ETag computed
        // over the app's body no longer describes what we are sending.
        res.removeHeader('Content-Length');
        res.removeHeader('ETag');
      }
    }

    giveUp();
    flushing = false;

    if (endOp) {
      originalEnd.call(res, out, () => runCallbacks());
      return;
    }

    originalWrite.call(res, out, () => runCallbacks());
    drainQueue();
  }

  res.writeHead = function patchedWriteHead(statusCode, statusMessage, headers) {
    const provided = typeof statusMessage === 'object' ? statusMessage : headers;
    const typeKey = headerName(provided, 'content-type');
    if (typeKey) contentTypeHint = String(provided[typeKey]);
    const encodingKey = headerName(provided, 'content-encoding');
    if (encodingKey) contentEncodingHint = String(provided[encodingKey]);

    if (typeof statusCode === 'number') res.statusCode = statusCode;

    // Strip the length here too: by the time we know whether we injected, a
    // header passed straight to writeHead is already out of reach.
    const lengthKey = !passthrough && eligible() ? headerName(provided, 'content-length') : undefined;
    if (lengthKey) {
      const copy = { ...provided };
      delete copy[lengthKey];
      return typeof statusMessage === 'object'
        ? originalWriteHead.call(res, statusCode, copy)
        : originalWriteHead.call(res, statusCode, statusMessage, copy);
    }

    return originalWriteHead.apply(res, arguments);
  };

  res.write = function patchedWrite(chunk, encoding, callback) {
    if (typeof encoding === 'function') {
      callback = encoding;
      encoding = undefined;
    }
    if (passthrough) return originalWrite.call(res, chunk, encoding, callback);
    if (!eligible()) return originalWrite.call(res, chunk, encoding, callback);

    const buffer = toBuffer(chunk, encoding);
    if (flushing) {
      queued.push({ type: 'write', chunk: buffer, callback });
      return true;
    }
    if (callback) callbacks.push(callback);

    const ready = buffer ? scanner.push(buffer) : false;
    if (ready) flush(null);
    return true;
  };

  res.end = function patchedEnd(chunk, encoding, callback) {
    if (typeof chunk === 'function') {
      callback = chunk;
      chunk = undefined;
      encoding = undefined;
    } else if (typeof encoding === 'function') {
      callback = encoding;
      encoding = undefined;
    }
    if (passthrough) return originalEnd.call(res, chunk, encoding, callback);
    if (!eligible()) return originalEnd.call(res, chunk, encoding, callback);

    const buffer = toBuffer(chunk, encoding);
    if (flushing) {
      queued.push({ type: 'end', chunk: buffer, callback });
      return res;
    }

    flush({ chunk: buffer, callback });
    return res;
  };
}

/**
 * Create the middleware.
 *
 * @param {object} [options] see README; every field also reads from the env
 * @returns {Function} an Express/Connect middleware `(req, res, next)`
 */
function createMiddleware(options = {}) {
  const config = resolveConfig(options);
  const client = options.client instanceof PreviewClient ? options.client : new PreviewClient(config);

  function mymetaview(req, res, next) {
    const done = typeof next === 'function' ? next : () => {};
    try {
      if (!config.enabled) return done();
      if ((req.method || 'GET').toUpperCase() !== 'GET') return done();

      const url = requestUrl(req);
      if (!url || !/^https?:$/.test(url.protocol)) return done();
      if (STATIC_EXTENSION.test(url.pathname)) return done();
      if (config.skip && config.skip(url.href, req)) return done();

      const crawler = isCrawler(header(req, 'user-agent'));
      const wantsTags = crawler || !config.crawlersOnly;
      // The snippet is for browsers: it reports the install heartbeat and
      // attributes social clicks. A crawler would never run it.
      const wantsSnippet = config.snippet && !crawler;
      if (!wantsTags && !wantsSnippet) return done();

      // Started now, awaited later: the app renders while this is in flight.
      const pending = wantsTags ? client.getPreview(url.href) : null;

      filterResponse(res, {
        maxHeadBytes: config.maxHeadBytes,
        render: async (buffer) => {
          const preview = pending ? await pending : null;
          return applyInjection(buffer, {
            metaHtml: preview ? renderMetaTags(preview, url.href) : '',
            snippetHtml: wantsSnippet ? renderSnippetTag(config.snippetUrl, config.site) : '',
            snippetUrl: config.snippetUrl,
          });
        },
      });
    } catch (error) {
      if (config.onError) {
        try {
          config.onError(error, { stage: 'middleware' });
        } catch {
          // Reporting must not be able to fail a request either.
        }
      }
    }
    return done();
  }

  mymetaview.config = config;
  mymetaview.client = client;
  return mymetaview;
}

module.exports = { createMiddleware, filterResponse, requestUrl };
