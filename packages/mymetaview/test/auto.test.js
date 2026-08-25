'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawn } = require('node:child_process');

const { CRAWLER_UA, PREVIEW, stubApi } = require('./helpers');

const AUTO = path.join(__dirname, '..', 'src', 'auto.js');
const FIXTURE = path.join(__dirname, 'fixtures', 'plain-server.js');

/** Start the fixture server under `--require`, and wait for its port. */
function startServer(env) {
  const child = spawn(process.execPath, ['--require', AUTO, FIXTURE], {
    env: { ...process.env, ...env },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  const stdout = [];
  const stderr = [];
  child.stderr.on('data', (chunk) => stderr.push(chunk.toString()));

  const ready = new Promise((resolve, reject) => {
    child.stdout.on('data', (chunk) => {
      stdout.push(chunk.toString());
      const match = /port=(\d+)/.exec(stdout.join(''));
      if (match) resolve(Number(match[1]));
    });
    child.on('exit', (code) =>
      reject(new Error(`fixture exited with ${code}: ${stderr.join('')}`))
    );
    setTimeout(
      () => reject(new Error(`fixture never started: ${stderr.join('')}`)),
      10000
    ).unref();
  });

  return { child, ready, stdout };
}

test('--require mymetaview/auto instruments a server that never imported it', async (t) => {
  const api = await stubApi(() => PREVIEW);
  t.after(() => api.close());

  const { child, ready, stdout } = startServer({ MYMETAVIEW_API_ORIGIN: api.origin });
  t.after(() => child.kill());
  const port = await ready;

  const page = await fetch(`http://127.0.0.1:${port}/pricing`, {
    headers: { 'user-agent': CRAWLER_UA },
  });
  const body = await page.text();
  assert.ok(body.includes(PREVIEW.title), 'the crawler sees the preview tags');
  assert.ok(body.includes('<body>hi</body>'), 'the page is otherwise unchanged');
  assert.equal(api.calls.length, 1);

  const json = await fetch(`http://127.0.0.1:${port}/data.json`, {
    headers: { 'user-agent': CRAWLER_UA },
  });
  assert.equal(await json.text(), '{"ok":true}');

  assert.ok(stdout.join('').includes('[mymetaview]'), 'it says so on startup');
});

test('MYMETAVIEW_ENABLED=0 leaves the process completely alone', async (t) => {
  const api = await stubApi(() => PREVIEW);
  t.after(() => api.close());

  const { child, ready } = startServer({
    MYMETAVIEW_API_ORIGIN: api.origin,
    MYMETAVIEW_ENABLED: '0',
  });
  t.after(() => child.kill());
  const port = await ready;

  const page = await fetch(`http://127.0.0.1:${port}/pricing`, {
    headers: { 'user-agent': CRAWLER_UA },
  });
  const body = await page.text();
  assert.ok(!body.includes(PREVIEW.title));
  assert.equal(api.calls.length, 0);
});
