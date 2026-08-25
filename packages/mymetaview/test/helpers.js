'use strict';

const http = require('node:http');

/**
 * A stand-in for the public preview API.
 *
 * Tests that exercise the middleware end to end need a real origin to talk to,
 * and a call counter is the only honest way to prove the cache works.
 */
async function stubApi(handler) {
  const calls = [];
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://stub');
    calls.push({ path: url.pathname, query: Object.fromEntries(url.searchParams) });

    const result = handler(url.searchParams.get('full_url'), url.searchParams);
    if (!result) {
      res.writeHead(404, { 'content-type': 'application/json' });
      res.end('{"detail":"not found"}');
      return;
    }
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify(result));
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();

  return {
    calls,
    origin: `http://127.0.0.1:${port}`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

/** Serve `handler` through an http server and hand back its origin. */
async function serve(handler) {
  const server = http.createServer(handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  return {
    server,
    port,
    origin: `http://127.0.0.1:${port}`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

const CRAWLER_UA = 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)';
const BROWSER_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36';

const PREVIEW = {
  url: 'https://example.com/pricing',
  title: 'Pricing that scales with you',
  description: 'Start free. Pay when it pays for itself.',
  image_url: 'https://cdn.example.com/card.png',
  site_name: 'Example',
  type: 'landing',
  status: 'fully_generated',
};

const PAGE = [
  '<!doctype html>',
  '<html lang="en">',
  '<head>',
  '<meta charset="utf-8">',
  '<title>Pricing</title>',
  '</head>',
  '<body><h1>Pricing</h1></body>',
  '</html>',
].join('\n');

module.exports = { BROWSER_UA, CRAWLER_UA, PAGE, PREVIEW, serve, stubApi };
