#!/usr/bin/env node
'use strict';

/**
 * `npx mymetaview check http://localhost:3000`
 *
 * The install is one line of app code, so the thing worth shipping a CLI for
 * is the question right after it: did it actually work? `check` asks the app
 * for a page exactly the way Facebook's crawler would, and reports what came
 * back.
 */

const { resolveConfig } = require('../src/config');
const { getPreview, renderMetaTags, snippetTag } = require('../src/index');
const { OPEN_MARKER } = require('../src/tags');

const CRAWLER_UA =
  'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php) mymetaview-cli';

const USAGE = `mymetaview <command> [url]

Commands:
  check <url>     Fetch a page as a social crawler and report the tags it sees
  preview <url>   Print the MyMetaView preview for a URL as JSON
  tags <url>      Print the meta tags for a URL
  snippet         Print the browser snippet tag

Environment:
  MYMETAVIEW_API_ORIGIN   API to talk to (default https://mymetaview.com)
  MYMETAVIEW_SITE         Registered domain, when it differs from the URL host
`;

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
}

function normalizeUrl(value) {
  if (!value) return null;
  const candidate = /^https?:\/\//i.test(value) ? value : `https://${value}`;
  try {
    return new URL(candidate).href;
  } catch {
    return null;
  }
}

function readMeta(html, key) {
  const pattern = new RegExp(
    `<meta[^>]+(?:property|name)=["']${key}["'][^>]*content=["']([^"']*)["']`,
    'i'
  );
  const alternate = new RegExp(
    `<meta[^>]+content=["']([^"']*)["'][^>]*(?:property|name)=["']${key}["']`,
    'i'
  );
  const match = pattern.exec(html) || alternate.exec(html);
  return match ? match[1] : null;
}

async function check(url) {
  const config = resolveConfig({});
  let response;
  try {
    response = await fetch(url, {
      headers: { 'user-agent': CRAWLER_UA, accept: 'text/html' },
      redirect: 'follow',
    });
  } catch (error) {
    return fail(`Could not reach ${url}: ${error.message}`);
  }

  const html = await response.text();
  const injected = html.includes(OPEN_MARKER);
  const title = readMeta(html, 'og:title');
  const image = readMeta(html, 'og:image');
  const snippetPath = new URL(config.snippetUrl).pathname;

  const lines = [
    `Checked   ${response.url} (HTTP ${response.status})`,
    `Tags      ${injected ? 'served by mymetaview' : 'not from mymetaview'}`,
    `og:title  ${title || '(none)'}`,
    `og:image  ${image || '(none)'}`,
    `snippet   ${html.includes(snippetPath) ? 'present' : 'absent'}`,
  ];
  process.stdout.write(`${lines.join('\n')}\n`);

  if (!injected) {
    process.exitCode = 1;
    process.stdout.write(
      '\nNo MyMetaView tags in this response. Things worth checking:\n' +
        '  - is app.use(mymetaview()) registered before the route that renders HTML?\n' +
        '  - does the response come back as text/html, uncompressed at that point?\n' +
        '  - is the domain connected and verified in your MyMetaView dashboard?\n'
    );
  }
}

async function preview(url) {
  const result = await getPreview(url);
  if (!result) {
    return fail(`No preview available for ${url}.`);
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

async function tags(url) {
  const result = await getPreview(url);
  if (!result) {
    return fail(`No preview available for ${url}.`);
  }
  process.stdout.write(`${renderMetaTags(result, url).split('><').join('>\n<')}\n`);
}

async function main(argv) {
  const [command, target] = argv;

  if (!command || command === '-h' || command === '--help' || command === 'help') {
    process.stdout.write(USAGE);
    return;
  }
  if (command === '-v' || command === '--version') {
    process.stdout.write(`${require('../package.json').version}\n`);
    return;
  }
  if (command === 'snippet') {
    process.stdout.write(`${snippetTag()}\n`);
    return;
  }

  const url = normalizeUrl(target);
  if (!url) {
    return fail(`Usage: mymetaview ${command} <url>`);
  }

  if (command === 'check') return check(url);
  if (command === 'preview') return preview(url);
  if (command === 'tags') return tags(url);

  fail(`Unknown command "${command}".\n\n${USAGE}`);
}

main(process.argv.slice(2)).catch((error) => {
  fail(error && error.stack ? error.stack : String(error));
});
