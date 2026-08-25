'use strict';

/**
 * Next.js adapter.
 *
 * Next renders its own <head>, so filtering the response is the wrong layer
 * here: the framework would rather be told what the metadata is.
 *
 *   // app/layout.tsx  (or any page)
 *   export { generateMetadata } from 'mymetaview/next'
 *
 *   // middleware.ts  (so the metadata knows which URL is being rendered)
 *   export { middleware, config } from 'mymetaview/next'
 *
 * Both files are one line. Without the middleware, `generateMetadata` still
 * works when you pass the URL yourself via `metadataForUrl(url)`.
 */

const { resolveConfig } = require('./config');
const { PreviewClient } = require('./client');
const { toNextMetadata } = require('./tags');

/** The request header the middleware below sets, and metadata reads back. */
const URL_HEADER = 'x-mymetaview-url';

let sharedClient = null;

function clientFor(options) {
  if (options && Object.keys(options).length > 0) {
    return new PreviewClient(resolveConfig(options));
  }
  if (!sharedClient) sharedClient = new PreviewClient(resolveConfig({}));
  return sharedClient;
}

/**
 * Metadata for an explicit URL.
 *
 * @param {string} url
 * @param {object} [options]
 * @returns {Promise<object>} a Next `Metadata` object, `{}` when there is none
 */
async function metadataForUrl(url, options = {}) {
  if (!url) return {};
  const preview = await clientFor(options).getPreview(url);
  return toNextMetadata(preview, url);
}

async function readHeaders() {
  try {
    const mod = await import('next/headers');
    // `headers()` is sync in Next 13/14 and a promise in Next 15+.
    return await mod.headers();
  } catch {
    return null;
  }
}

function headerValue(store, name) {
  try {
    return store.get(name) || '';
  } catch {
    return '';
  }
}

/** Rebuild the URL being rendered from the request headers. */
async function urlFromHeaders() {
  const store = await readHeaders();
  if (!store) return null;

  const explicit = headerValue(store, URL_HEADER);
  if (explicit) return explicit;

  const host = String(
    headerValue(store, 'x-forwarded-host') || headerValue(store, 'host') || ''
  )
    .split(',')[0]
    .trim();
  if (!host) return null;

  // Next exposes the rendered path under different names across routers and
  // versions; without one of them we would be guessing, and a card for the
  // wrong URL is worse than no card.
  const path =
    headerValue(store, 'x-invoke-path') ||
    headerValue(store, 'x-matched-path') ||
    headerValue(store, 'x-pathname') ||
    '';
  if (!path) return null;

  const protocol =
    String(headerValue(store, 'x-forwarded-proto') || '').split(',')[0].trim() || 'https';

  try {
    return new URL(path, `${protocol}://${host}`).href;
  } catch {
    return null;
  }
}

async function metadataForCurrentUrl(options) {
  const url = await urlFromHeaders();
  if (!url) return {};
  return metadataForUrl(url, options);
}

/**
 * `generateMetadata` for the page being rendered.
 *
 * Next calls this with the route props; they are deliberately ignored, because
 * the URL comes from the request headers. For options, use
 * `mymetaviewMetadata({...})` instead.
 */
async function generateMetadata() {
  return metadataForCurrentUrl({});
}

/** Curried form, for when you want to pass options. */
function mymetaviewMetadata(options = {}) {
  return async function generateMetadataWithOptions() {
    return metadataForCurrentUrl(options);
  };
}

/**
 * Request headers with the current URL added, for an app that already has a
 * middleware of its own:
 *
 *   return NextResponse.next({ request: { headers: withMyMetaViewUrl(request) } })
 */
function withMyMetaViewUrl(request) {
  const headers = new Headers(request.headers);
  headers.set(URL_HEADER, request.url);
  return headers;
}

/**
 * Next middleware that records the request URL for `generateMetadata`.
 * Re-export it from `middleware.ts`.
 */
async function middleware(request) {
  const { NextResponse } = await import('next/server');
  return NextResponse.next({ request: { headers: withMyMetaViewUrl(request) } });
}

/** Matcher that skips Next's own assets — the default for the export above. */
const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};

module.exports = {
  URL_HEADER,
  config,
  generateMetadata,
  metadataForUrl,
  middleware,
  mymetaviewMetadata,
  withMyMetaViewUrl,
};
