'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  HeadScanner,
  applyInjection,
  findInsertIndex,
  hasSnippet,
  scanText,
  spliceAt,
} = require('../src/inject');
const { OPEN_MARKER } = require('../src/tags');

const META = '<meta property="og:title" content="x">';

test('tags go straight after the head opening tag', () => {
  const html = '<!doctype html><html><head><title>a</title></head><body></body></html>';
  const index = findInsertIndex(scanText(Buffer.from(html)));
  assert.equal(html.slice(index, index + 7), '<title>');
});

test('a head opening tag with attributes is still found', () => {
  const html = '<html><head data-x="1" ><meta charset="utf-8"></head></html>';
  const index = findInsertIndex(scanText(Buffer.from(html)));
  assert.equal(html.slice(index, index + 5), '<meta');
});

test('<header> is not mistaken for <head>', () => {
  const html = '<html><body><header>hi</header></body></html>';
  const index = findInsertIndex(scanText(Buffer.from(html)));
  assert.equal(html.slice(index, index + 5), '<body');
});

test('a document without a head falls back to after <html>', () => {
  const html = '<html><body>hi</body></html>';
  const index = findInsertIndex(scanText(Buffer.from(html)));
  assert.equal(index, '<html>'.length);
});

test('splicing preserves multi-byte characters on both sides', () => {
  const html = '<html><head><title>Grüße 😀</title></head></html>';
  const buffer = Buffer.from(html, 'utf8');
  const out = applyInjection(buffer, { metaHtml: META });
  const text = out.toString('utf8');
  assert.ok(text.includes('Grüße 😀'));
  assert.ok(text.includes(META));
  assert.ok(text.indexOf(META) < text.indexOf('<title>'));
});

test('tags are injected once, however many times the filter runs', () => {
  const once = applyInjection(Buffer.from('<html><head></head></html>'), {
    metaHtml: `${OPEN_MARKER}${META}`,
  });
  const twice = applyInjection(once, { metaHtml: `${OPEN_MARKER}${META}` });
  assert.equal(twice.toString(), once.toString());
});

test('the snippet is not added when the page already loads it', () => {
  const html =
    '<html><head><script src="https://mymetaview.com/snippet.js" defer></script></head></html>';
  const out = applyInjection(Buffer.from(html), {
    snippetHtml: '<script src="https://mymetaview.com/snippet.js" defer></script>',
    snippetUrl: 'https://mymetaview.com/snippet.js',
  });
  assert.equal(out.toString(), html);
});

test('a snippet served from a customer CDN path still counts as present', () => {
  const scan = scanText(Buffer.from('<script src="https://cdn.acme.com/snippet.js"></script>'));
  assert.equal(hasSnippet(scan, 'https://mymetaview.com/snippet.js'), true);
});

test('nothing to add means the buffer is returned untouched', () => {
  const buffer = Buffer.from('<html><head></head></html>');
  assert.equal(applyInjection(buffer, {}), buffer);
});

test('spliceAt clamps an out-of-range index', () => {
  const buffer = Buffer.from('abc');
  assert.equal(spliceAt(buffer, 99, 'X').toString(), 'abcX');
  assert.equal(spliceAt(buffer, -5, 'X').toString(), 'Xabc');
});

test('the scanner reports ready once </head> arrives, across chunks', () => {
  const scanner = new HeadScanner(1024);
  assert.equal(scanner.push(Buffer.from('<html><head><title>a</title></h')), false);
  assert.equal(scanner.push(Buffer.from('ead><body>')), true);
  assert.equal(scanner.release().toString(), '<html><head><title>a</title></head><body>');
});

test('the scanner gives up rather than buffering an unbounded document', () => {
  const scanner = new HeadScanner(32);
  assert.equal(scanner.push(Buffer.from('<html><head>')), false);
  assert.equal(scanner.push(Buffer.alloc(64, 0x61)), true);
  assert.equal(scanner.release().length, 12 + 64);
});

test('a released scanner ignores later chunks', () => {
  const scanner = new HeadScanner(1024);
  scanner.push(Buffer.from('<head></head>'));
  scanner.release();
  assert.equal(scanner.push(Buffer.from('more')), false);
});
