'use strict';

/**
 * A server that knows nothing about mymetaview: the fixture for
 * `node --require mymetaview/auto`. It prints its port so the test can find it.
 */

const http = require('node:http');

const PAGE = '<!doctype html><html><head><title>Pricing</title></head><body>hi</body></html>';

const server = http.createServer();

server.on('request', (req, res) => {
  if (req.url === '/data.json') {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end('{"ok":true}');
    return;
  }
  res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
  res.end(PAGE);
});

server.listen(0, '127.0.0.1', () => {
  process.stdout.write(`port=${server.address().port}\n`);
});
