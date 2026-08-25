'use strict';

/**
 * Putting tags into an HTML response someone else is writing.
 *
 * The rules this has to respect, in order of how badly they bite:
 *
 * 1. Never corrupt a body. Scanning happens on bytes (latin1, which is
 *    byte-preserving), so a multi-byte character split across two chunks can
 *    never be mangled, and the splice happens on the Buffer at a byte offset.
 * 2. Never hold a response open. We buffer only until `</head>`, and give up
 *    at `maxBytes` rather than growing without bound.
 * 3. Never inject twice. A site running both this and the snippet tag (or
 *    sitting behind the Cloudflare Worker) must not get two sets of tags.
 * 4. Win over the page's own tags. Crawlers take the first occurrence of a
 *    property, so ours go at the very top of <head>.
 */

const { OPEN_MARKER } = require('./tags');

const HEAD_OPEN = /<head(?:\s[^>]*)?>/;
const HTML_OPEN = /<html(?:\s[^>]*)?>/;
const HEAD_CLOSE = '</head';

/** Byte-preserving lowercase view of a buffer, so offsets stay byte offsets. */
function scanText(buffer) {
  return buffer.toString('latin1').toLowerCase();
}

/**
 * Where our tags go: straight after <head>, else after <html>, else the top.
 *
 * @param {string} scan lowercased latin1 view of the document so far
 * @returns {number} byte offset
 */
function findInsertIndex(scan) {
  const head = HEAD_OPEN.exec(scan);
  if (head) return head.index + head[0].length;

  const html = HTML_OPEN.exec(scan);
  if (html) return html.index + html[0].length;

  return 0;
}

/** True once the head is fully buffered, so de-duplication can be trusted. */
function hasHeadClose(scan) {
  return scan.includes(HEAD_CLOSE);
}

function alreadyInjected(scan) {
  return scan.includes(OPEN_MARKER.toLowerCase());
}

/**
 * True when the document already loads the browser snippet, from any source:
 * a pasted tag, a tag manager, or another copy of this middleware.
 */
function hasSnippet(scan, snippetUrl) {
  let path = '/snippet.js';
  try {
    path = new URL(snippetUrl).pathname.toLowerCase();
  } catch {
    // A relative or malformed snippet URL still has a recognisable tail.
    path = snippetUrl.toLowerCase();
  }
  return scan.includes(path);
}

/**
 * Splice HTML into a buffer at a byte offset.
 *
 * @param {Buffer} buffer
 * @param {number} index
 * @param {string} html
 * @returns {Buffer}
 */
function spliceAt(buffer, index, html) {
  if (!html) return buffer;
  const clamped = Math.max(0, Math.min(index, buffer.length));
  return Buffer.concat([
    buffer.subarray(0, clamped),
    Buffer.from(html, 'utf8'),
    buffer.subarray(clamped),
  ]);
}

/**
 * Streaming head accumulator.
 *
 * Feed it chunks; it tells you when it has seen enough to decide (the whole
 * <head>, or `maxBytes` of document, whichever comes first). Once it has
 * released its buffer, later chunks pass straight through untouched.
 */
class HeadScanner {
  constructor(maxBytes) {
    this.maxBytes = maxBytes;
    this.chunks = [];
    this.size = 0;
    this.scanned = 0;
    this.done = false;
  }

  /**
   * @param {Buffer} chunk
   * @returns {boolean} true when the buffered prefix is ready to be decided on
   */
  push(chunk) {
    if (this.done) return false;
    this.chunks.push(chunk);
    this.size += chunk.length;
    if (this.size >= this.maxBytes) return true;

    // Rescan only the new bytes, backing up far enough that a `</head` split
    // across two chunks is still found.
    const buffer = this.buffer();
    const from = Math.max(0, this.scanned - HEAD_CLOSE.length);
    const found = hasHeadClose(scanText(buffer.subarray(from)));
    this.scanned = buffer.length;
    return found;
  }

  buffer() {
    if (this.chunks.length > 1) {
      this.chunks = [Buffer.concat(this.chunks)];
    }
    return this.chunks[0] || Buffer.alloc(0);
  }

  /** Hand back everything buffered and stop intercepting. */
  release() {
    const buffer = this.buffer();
    this.done = true;
    this.chunks = [];
    this.size = 0;
    return buffer;
  }
}

/**
 * Decide what to add to a buffered document prefix.
 *
 * @param {Buffer} buffer document prefix
 * @param {{metaHtml?: string, snippetHtml?: string, snippetUrl?: string}} parts
 * @returns {Buffer} the prefix, with whatever was missing spliced in
 */
function applyInjection(buffer, parts) {
  const scan = scanText(buffer);
  let html = '';

  if (parts.metaHtml && !alreadyInjected(scan)) {
    html += parts.metaHtml;
  }
  if (parts.snippetHtml && !hasSnippet(scan, parts.snippetUrl || '/snippet.js')) {
    html += parts.snippetHtml;
  }
  if (!html) return buffer;

  return spliceAt(buffer, findInsertIndex(scan), html);
}

module.exports = {
  HeadScanner,
  alreadyInjected,
  applyInjection,
  findInsertIndex,
  hasHeadClose,
  hasSnippet,
  scanText,
  spliceAt,
};
