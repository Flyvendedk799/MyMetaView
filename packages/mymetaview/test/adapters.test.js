'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const fastifyPlugin = require('../src/fastify');
const { metadataForUrl, withMyMetaViewUrl, URL_HEADER } = require('../src/next');
const { PREVIEW, CRAWLER_UA, BROWSER_UA } = require('./helpers');

/** Just enough Fastify to exercise the onSend hook. */
function fakeFastify() {
  const hooks = {};
  return {
    hooks,
    addHook(name, handler) {
      hooks[name] = handler;
    },
  };
}

function fakeReply(headers, statusCode = 200) {
  const store = { ...headers };
  return {
    statusCode,
    getHeader: (name) => store[name.toLowerCase()],
    header: (name, value) => {
      store[name.toLowerCase()] = value;
    },
    removeHeader: (name) => {
      delete store[name.toLowerCase()];
    },
    headers: store,
  };
}

async function onSendWith(options, request, reply, payload) {
  const fastify = fakeFastify();
  await new Promise((resolve) => fastifyPlugin(fastify, options, resolve));
  return fastify.hooks.onSend(request, reply, payload);
}

const HTML = '<!doctype html><html><head><title>a</title></head><body>b</body></html>';

const previewFetch = async () => ({
  ok: true,
  status: 200,
  json: async () => PREVIEW,
});

test('the Fastify hook injects tags for a crawler and fixes the headers', async () => {
  const reply = fakeReply({
    'content-type': 'text/html',
    'content-length': String(HTML.length),
    etag: '"abc"',
    vary: 'Accept-Encoding',
  });
  const out = await onSendWith(
    { apiOrigin: 'https://api.test', fetch: previewFetch },
    { method: 'GET', url: '/pricing', headers: { host: 'example.com', 'user-agent': CRAWLER_UA } },
    reply,
    HTML
  );

  const body = out.toString();
  assert.ok(body.includes(PREVIEW.title));
  assert.ok(body.includes('</html>'));
  assert.equal(reply.headers['content-length'], String(Buffer.byteLength(body)));
  assert.equal(reply.headers.etag, undefined, 'the app\'s ETag no longer describes this body');
  assert.equal(reply.headers.vary, 'Accept-Encoding, User-Agent');
});

test('the Fastify hook gives a browser the snippet, not the tags', async () => {
  const out = await onSendWith(
    { apiOrigin: 'https://api.test', fetch: previewFetch },
    { method: 'GET', url: '/pricing', headers: { host: 'example.com', 'user-agent': BROWSER_UA } },
    fakeReply({ 'content-type': 'text/html' }),
    HTML
  );

  const body = out.toString();
  assert.ok(body.includes('snippet.js'));
  assert.ok(!body.includes('og:title'));
});

test('the Fastify hook passes through anything it should not rewrite', async () => {
  const base = { apiOrigin: 'https://api.test', fetch: previewFetch };
  const request = {
    method: 'GET',
    url: '/pricing',
    headers: { host: 'example.com', 'user-agent': CRAWLER_UA },
  };

  assert.equal(
    await onSendWith(base, request, fakeReply({ 'content-type': 'application/json' }), '{}'),
    '{}'
  );
  assert.equal(
    await onSendWith(base, request, fakeReply({ 'content-type': 'text/html' }, 404), HTML),
    HTML
  );
  assert.equal(
    await onSendWith(
      base,
      { ...request, method: 'POST' },
      fakeReply({ 'content-type': 'text/html' }),
      HTML
    ),
    HTML
  );
  assert.equal(
    await onSendWith(
      base,
      request,
      fakeReply({ 'content-type': 'text/html', 'content-encoding': 'br' }),
      HTML
    ),
    HTML
  );
  // A stream payload is not ours to rewrite.
  const stream = { pipe() {} };
  assert.equal(
    await onSendWith(base, request, fakeReply({ 'content-type': 'text/html' }), stream),
    stream
  );
});

test('the Next helper builds metadata for an explicit URL', async () => {
  const metadata = await metadataForUrl('https://example.com/pricing', {
    apiOrigin: 'https://api.test',
    fetch: previewFetch,
  });
  assert.equal(metadata.title, PREVIEW.title);
  assert.equal(metadata.openGraph.url, PREVIEW.url);
  assert.deepEqual(await metadataForUrl('', {}), {});
});

test('the Next middleware records the URL it is rendering', () => {
  const headers = withMyMetaViewUrl({
    url: 'https://example.com/pricing',
    headers: new Headers({ 'user-agent': BROWSER_UA }),
  });
  assert.equal(headers.get(URL_HEADER), 'https://example.com/pricing');
  assert.equal(headers.get('user-agent'), BROWSER_UA);
});
