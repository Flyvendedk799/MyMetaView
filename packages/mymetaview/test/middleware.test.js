'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const zlib = require('node:zlib');

const { createMiddleware } = require('../src/middleware');
const { BROWSER_UA, CRAWLER_UA, PAGE, PREVIEW, serve, stubApi } = require('./helpers');

/** An app with the middleware in front of it, and the stub API behind it. */
async function app(handler, options = {}, previewFor = () => PREVIEW) {
  const api = await stubApi(previewFor);
  const middleware = createMiddleware({ apiOrigin: api.origin, ...options });
  const server = await serve((req, res) => {
    middleware(req, res, () => handler(req, res));
  });

  return {
    api,
    origin: server.origin,
    async get(path, headers = {}) {
      const response = await fetch(`${server.origin}${path}`, { headers });
      return { response, body: await response.text() };
    },
    async close() {
      await server.close();
      await api.close();
    },
  };
}

function html(res, body) {
  res.setHeader('content-type', 'text/html; charset=utf-8');
  res.end(body);
}

test('a crawler gets the preview tags, ahead of the page\'s own', async (t) => {
  const fixture = await app((req, res) => html(res, PAGE));
  t.after(() => fixture.close());

  const { response, body } = await fixture.get('/pricing', { 'user-agent': CRAWLER_UA });

  assert.equal(response.status, 200);
  assert.ok(body.includes(`content="${PREVIEW.title}"`));
  assert.ok(body.includes(`content="${PREVIEW.image_url}"`));
  assert.ok(body.includes('twitter:card'));
  assert.ok(body.indexOf('og:title') < body.indexOf('<title>'), 'ours must come first');
  assert.ok(body.includes('<body><h1>Pricing</h1></body>'), 'the page survives intact');
  assert.equal(fixture.api.calls.length, 1);
  assert.equal(
    fixture.api.calls[0].query.full_url,
    `${fixture.origin}/pricing`
  );
});

test('a browser gets the snippet and no preview lookup at all', async (t) => {
  const fixture = await app((req, res) => html(res, PAGE));
  t.after(() => fixture.close());

  const { body } = await fixture.get('/pricing', { 'user-agent': BROWSER_UA });

  assert.ok(body.includes('snippet.js'));
  assert.ok(!body.includes('og:title'));
  assert.equal(fixture.api.calls.length, 0, 'humans must not put the API in the path');
});

test('crawlersOnly: false serves tags to everyone', async (t) => {
  const fixture = await app((req, res) => html(res, PAGE), { crawlersOnly: false });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/pricing', { 'user-agent': BROWSER_UA });
  assert.ok(body.includes('og:title'));
  assert.ok(body.includes('snippet.js'));
});

test('a body written in many chunks is reassembled correctly', async (t) => {
  const fixture = await app((req, res) => {
    res.setHeader('content-type', 'text/html');
    for (const chunk of PAGE.match(/[\s\S]{1,7}/g)) res.write(chunk);
    res.end();
  });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/pricing', { 'user-agent': CRAWLER_UA });
  assert.ok(body.includes(PREVIEW.title));
  assert.equal(body.replace(/<!-- MyMetaView -->[\s\S]*?<!-- \/MyMetaView -->/, ''), PAGE);
});

test('a Content-Length set by the app does not truncate the response', async (t) => {
  const fixture = await app((req, res) => {
    const buffer = Buffer.from(PAGE, 'utf8');
    res.setHeader('content-type', 'text/html');
    res.setHeader('content-length', String(buffer.length));
    res.end(buffer);
  });
  t.after(() => fixture.close());

  const { response, body } = await fixture.get('/pricing', { 'user-agent': CRAWLER_UA });
  assert.ok(body.includes(PREVIEW.title));
  assert.ok(body.includes('</html>'));
  assert.equal(response.headers.get('content-length'), null);
});

test('an injected response drops the stale ETag and varies on the agent', async (t) => {
  const fixture = await app((req, res) => {
    res.setHeader('content-type', 'text/html');
    res.setHeader('etag', '"page-v1"');
    res.setHeader('vary', 'Accept-Encoding');
    res.end(PAGE);
  });
  t.after(() => fixture.close());

  const { response } = await fixture.get('/pricing', { 'user-agent': CRAWLER_UA });
  assert.equal(response.headers.get('etag'), null);
  assert.equal(response.headers.get('vary'), 'Accept-Encoding, User-Agent');
});

test('headers passed straight to writeHead are handled too', async (t) => {
  const fixture = await app((req, res) => {
    const buffer = Buffer.from(PAGE, 'utf8');
    res.writeHead(200, {
      'content-type': 'text/html; charset=utf-8',
      'content-length': String(buffer.length),
    });
    res.end(buffer);
  });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/pricing', { 'user-agent': CRAWLER_UA });
  assert.ok(body.includes(PREVIEW.title));
  assert.ok(body.includes('</html>'));
});

test('a non-HTML response is never touched', async (t) => {
  const fixture = await app((req, res) => {
    res.setHeader('content-type', 'application/json');
    res.end('{"ok":true}');
  });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/api/thing', { 'user-agent': CRAWLER_UA });
  assert.equal(body, '{"ok":true}');
});

test('an already-compressed response is left alone', async (t) => {
  const fixture = await app((req, res) => {
    res.setHeader('content-type', 'text/html');
    res.setHeader('content-encoding', 'gzip');
    res.end(zlib.gzipSync(Buffer.from(PAGE)));
  });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/pricing', { 'user-agent': CRAWLER_UA });
  assert.equal(body, PAGE, 'the gzip round-trip must be byte-identical');
});

test('a non-200 response is left alone', async (t) => {
  const fixture = await app((req, res) => {
    res.writeHead(404, { 'content-type': 'text/html' });
    res.end(PAGE);
  });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/missing', { 'user-agent': CRAWLER_UA });
  assert.equal(body, PAGE);
});

test('static paths and non-GET methods skip the lookup entirely', async (t) => {
  const fixture = await app((req, res) => html(res, PAGE));
  t.after(() => fixture.close());

  await fixture.get('/assets/app.js', { 'user-agent': CRAWLER_UA });
  await fetch(`${fixture.origin}/pricing`, {
    method: 'POST',
    headers: { 'user-agent': CRAWLER_UA },
  });
  assert.equal(fixture.api.calls.length, 0);
});

test('a URL with no preview ships the page unchanged', async (t) => {
  const fixture = await app((req, res) => html(res, PAGE), {}, () => null);
  t.after(() => fixture.close());

  const { body } = await fixture.get('/pricing', { 'user-agent': CRAWLER_UA });
  assert.equal(body, PAGE);
});

test('skip() takes a request out of the path', async (t) => {
  const fixture = await app((req, res) => html(res, PAGE), {
    skip: (url) => url.includes('/admin/'),
  });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/admin/settings', { 'user-agent': CRAWLER_UA });
  assert.equal(body, PAGE);
  assert.equal(fixture.api.calls.length, 0);
});

test('enabled: false is a complete no-op', async (t) => {
  const fixture = await app((req, res) => html(res, PAGE), { enabled: false });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/pricing', { 'user-agent': BROWSER_UA });
  assert.equal(body, PAGE);
});

test('a document with no </head> in range still ships whole', async (t) => {
  const filler = '<p>x</p>'.repeat(2000);
  const page = `<!doctype html><html><head><title>a</title>${filler}`;
  const fixture = await app((req, res) => html(res, page), { maxHeadBytes: 512 });
  t.after(() => fixture.close());

  const { body } = await fixture.get('/long', { 'user-agent': CRAWLER_UA });
  assert.ok(body.includes(PREVIEW.title));
  assert.ok(body.endsWith(filler.slice(-8)), 'the tail of the document still arrives');
  assert.equal(body.replace(/<!-- MyMetaView -->[\s\S]*?<!-- \/MyMetaView -->/, ''), page);
});

test('the proxy headers decide the URL that is looked up', async (t) => {
  const fixture = await app((req, res) => html(res, PAGE));
  t.after(() => fixture.close());

  await fixture.get('/pricing', {
    'user-agent': CRAWLER_UA,
    'x-forwarded-host': 'example.com',
    'x-forwarded-proto': 'https',
  });
  assert.equal(fixture.api.calls[0].query.full_url, 'https://example.com/pricing');
});

test('an unreachable API does not hold the page hostage', async (t) => {
  // Port 1 refuses instantly on some systems and hangs on others; either way
  // the page must come back, and come back whole.
  const middleware = createMiddleware({ apiOrigin: 'http://127.0.0.1:1', timeout: 50 });
  const server = await serve((req, res) => {
    middleware(req, res, () => html(res, PAGE));
  });
  t.after(() => server.close());

  const response = await fetch(`${server.origin}/pricing`, {
    headers: { 'user-agent': CRAWLER_UA },
  });
  assert.equal(await response.text(), PAGE);
});
