'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { PreviewClient, TtlCache } = require('../src/client');
const { resolveConfig } = require('../src/config');
const { PREVIEW } = require('./helpers');

function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

function clientWith(fetchImpl, overrides = {}) {
  return new PreviewClient(
    resolveConfig({ apiOrigin: 'https://api.test', fetch: fetchImpl, ...overrides })
  );
}

test('the endpoint carries the URL, and the site only when configured', () => {
  const plain = clientWith(async () => jsonResponse(PREVIEW));
  assert.equal(
    plain.endpoint('https://example.com/a?b=1'),
    'https://api.test/api/v1/public/preview?full_url=https%3A%2F%2Fexample.com%2Fa%3Fb%3D1'
  );

  const scoped = clientWith(async () => jsonResponse(PREVIEW), { site: 'Example.com' });
  assert.ok(scoped.endpoint('https://blog.example.com/a').includes('site=example.com'));
});

test('a hit is cached, so a second lookup makes no request', async () => {
  let calls = 0;
  const client = clientWith(async () => {
    calls += 1;
    return jsonResponse(PREVIEW);
  });

  assert.deepEqual(await client.getPreview('https://example.com/a'), PREVIEW);
  assert.deepEqual(await client.getPreview('https://example.com/a'), PREVIEW);
  assert.equal(calls, 1);
});

test('concurrent lookups of one URL share a single request', async () => {
  let calls = 0;
  const client = clientWith(async () => {
    calls += 1;
    await new Promise((resolve) => setTimeout(resolve, 10));
    return jsonResponse(PREVIEW);
  });

  const results = await Promise.all([
    client.getPreview('https://example.com/a'),
    client.getPreview('https://example.com/a'),
    client.getPreview('https://example.com/a'),
  ]);
  assert.equal(calls, 1);
  assert.equal(results.filter(Boolean).length, 3);
});

test('a miss is cached too, so a broken API is not re-dialled per request', async () => {
  let calls = 0;
  const client = clientWith(async () => {
    calls += 1;
    return jsonResponse({ detail: 'nope' }, 500);
  });

  assert.equal(await client.getPreview('https://example.com/a'), null);
  assert.equal(await client.getPreview('https://example.com/a'), null);
  assert.equal(calls, 1);
});

test('a fallback preview is treated as no preview', async () => {
  const client = clientWith(async () =>
    jsonResponse({ ...PREVIEW, status: 'fallback', description: null })
  );
  assert.equal(await client.getPreview('https://example.com/a'), null);
});

test('a thrown fetch is reported, not raised', async () => {
  const seen = [];
  const client = clientWith(
    async () => {
      throw new Error('connection refused');
    },
    { onError: (error, context) => seen.push([error.message, context.url]) }
  );

  assert.equal(await client.getPreview('https://example.com/a'), null);
  assert.deepEqual(seen, [['connection refused', 'https://example.com/a']]);
});

test('a hanging API is abandoned at the timeout', async () => {
  const client = clientWith(
    (_url, init) =>
      new Promise((_resolve, reject) => {
        init.signal.addEventListener('abort', () => reject(new Error('aborted')));
      }),
    { timeout: 20 }
  );

  const started = Date.now();
  assert.equal(await client.getPreview('https://example.com/a'), null);
  assert.ok(Date.now() - started < 1000);
});

test('an error handler that throws cannot take the request down', async () => {
  const client = clientWith(
    async () => {
      throw new Error('boom');
    },
    {
      onError: () => {
        throw new Error('handler exploded');
      },
    }
  );
  assert.equal(await client.getPreview('https://example.com/a'), null);
});

test('the cache expires entries and evicts the coldest key', () => {
  const cache = new TtlCache(2);
  cache.set('a', 1, 300);
  cache.set('b', 2, 300);
  cache.get('a');
  cache.set('c', 3, 300);

  assert.equal(cache.get('a'), 1);
  assert.equal(cache.get('b'), undefined);
  assert.equal(cache.get('c'), 3);

  cache.set('d', 4, -1);
  assert.equal(cache.get('d'), undefined);
});
