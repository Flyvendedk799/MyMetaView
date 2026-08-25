'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { renderMetaTags, renderSnippetTag, toNextMetadata } = require('../src/tags');
const { isCrawler } = require('../src/crawlers');
const { PREVIEW } = require('./helpers');

test('a title with quotes and angle brackets cannot break out of the attribute', () => {
  const html = renderMetaTags(
    { ...PREVIEW, title: 'He said "<script>alert(1)</script>" & left' },
    PREVIEW.url
  );
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('&quot;&lt;script&gt;'));
  assert.ok(html.includes('&amp; left'));
});

test('a preview without a title renders nothing', () => {
  assert.equal(renderMetaTags(null, PREVIEW.url), '');
  assert.equal(renderMetaTags({ url: PREVIEW.url }, PREVIEW.url), '');
});

test('the OG type follows the preview type', () => {
  assert.ok(renderMetaTags({ ...PREVIEW, type: 'blog' }, PREVIEW.url).includes('"article"'));
  assert.ok(renderMetaTags({ ...PREVIEW, type: 'product' }, PREVIEW.url).includes('"product"'));
  assert.ok(renderMetaTags({ ...PREVIEW, type: 'nonsense' }, PREVIEW.url).includes('"website"'));
});

test('an imageless preview downgrades the Twitter card', () => {
  const html = renderMetaTags({ ...PREVIEW, image_url: null }, PREVIEW.url);
  assert.ok(html.includes('content="summary"'));
  assert.ok(!html.includes('twitter:image'));
});

test('empty fields are skipped rather than emitted blank', () => {
  const html = renderMetaTags({ ...PREVIEW, description: '', site_name: null }, PREVIEW.url);
  assert.ok(!html.includes('og:description'));
  assert.ok(!html.includes('og:site_name'));
});

test('the snippet tag carries the site only when there is one', () => {
  assert.equal(
    renderSnippetTag('https://mymetaview.com/snippet.js', 'example.com'),
    '<script src="https://mymetaview.com/snippet.js" data-site="example.com" defer></script>'
  );
  assert.equal(
    renderSnippetTag('https://mymetaview.com/snippet.js', ''),
    '<script src="https://mymetaview.com/snippet.js" defer></script>'
  );
});

test('the Next metadata mirrors the tags', () => {
  const metadata = toNextMetadata(PREVIEW, PREVIEW.url);
  assert.equal(metadata.title, PREVIEW.title);
  assert.equal(metadata.openGraph.images[0], PREVIEW.image_url);
  assert.equal(metadata.openGraph.siteName, 'Example');
  assert.equal(metadata.twitter.card, 'summary_large_image');
  assert.deepEqual(toNextMetadata(null, PREVIEW.url), {});
});

test('crawlers are recognised and browsers are not', () => {
  for (const agent of [
    'facebookexternalhit/1.1',
    'Twitterbot/1.0',
    'LinkedInBot/1.0 (compatible; Mozilla/5.0)',
    'Slackbot-LinkExpanding 1.0',
    'Discordbot/2.0',
    'WhatsApp/2.21',
    'TelegramBot (like TwitterBot)',
    'Mozilla/5.0 (compatible; Applebot/0.1)',
  ]) {
    assert.ok(isCrawler(agent), `${agent} should be a crawler`);
  }

  assert.equal(isCrawler('Mozilla/5.0 (Macintosh) Chrome/122 Safari/537.36'), false);
  assert.equal(isCrawler(''), false);
  assert.equal(isCrawler(undefined), false);
});
