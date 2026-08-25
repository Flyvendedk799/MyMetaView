'use strict';

/**
 * mymetaview
 *
 *   npm install mymetaview
 *
 *   const mymetaview = require('mymetaview')
 *   app.use(mymetaview())
 *
 * That is the whole integration. Nothing to start, no build step, no key: the
 * middleware answers social crawlers with server-rendered Open Graph tags for
 * the page they asked for, and leaves every other response untouched.
 */

const { DEFAULT_API_ORIGIN, resolveConfig } = require('./config');
const { PreviewClient, TtlCache } = require('./client');
const { isCrawler, CRAWLER_PATTERN } = require('./crawlers');
const {
  renderMetaTags,
  renderSnippetTag,
  toNextMetadata,
  escapeHtml,
} = require('./tags');
const { createMiddleware, requestUrl } = require('./middleware');

/** A shared client, so helper calls and the middleware share one cache. */
let sharedClient = null;

function getClient(options) {
  if (options && Object.keys(options).length > 0) {
    return new PreviewClient(resolveConfig(options));
  }
  if (!sharedClient) sharedClient = new PreviewClient(resolveConfig({}));
  return sharedClient;
}

/**
 * The preview for a URL, or null when there is not one worth serving.
 *
 * @param {string} url
 * @param {object} [options]
 * @returns {Promise<object|null>}
 */
function getPreview(url, options = {}) {
  const { variant, ...rest } = options;
  return getClient(rest).getPreview(url, { variant });
}

/**
 * The `<meta>` tags for a URL, ready to drop into a template.
 *
 * @param {string} url
 * @param {object} [options]
 * @returns {Promise<string>} HTML, or '' when there is no preview
 */
async function metaTags(url, options = {}) {
  const preview = await getPreview(url, options);
  return preview ? renderMetaTags(preview, url) : '';
}

/**
 * The browser snippet tag: install verification and social click analytics.
 *
 * @param {object} [options]
 * @returns {string} HTML
 */
function snippetTag(options = {}) {
  const config = resolveConfig(options);
  return renderSnippetTag(config.snippetUrl, config.site);
}

/**
 * A Next.js `Metadata` object for a URL, for `generateMetadata`.
 *
 * @param {string} url
 * @param {object} [options]
 * @returns {Promise<object>}
 */
async function metadataFor(url, options = {}) {
  const preview = await getPreview(url, options);
  return toNextMetadata(preview, url);
}

const mymetaview = (options) => createMiddleware(options);

module.exports = mymetaview;
module.exports.default = mymetaview;
module.exports.mymetaview = mymetaview;
module.exports.middleware = createMiddleware;
module.exports.createMiddleware = createMiddleware;
module.exports.express = createMiddleware;
module.exports.connect = createMiddleware;
module.exports.getPreview = getPreview;
module.exports.metaTags = metaTags;
module.exports.metadataFor = metadataFor;
module.exports.snippetTag = snippetTag;
module.exports.renderMetaTags = renderMetaTags;
module.exports.renderSnippetTag = renderSnippetTag;
module.exports.toNextMetadata = toNextMetadata;
module.exports.escapeHtml = escapeHtml;
module.exports.isCrawler = isCrawler;
module.exports.requestUrl = requestUrl;
module.exports.resolveConfig = resolveConfig;
module.exports.PreviewClient = PreviewClient;
module.exports.TtlCache = TtlCache;
module.exports.CRAWLER_PATTERN = CRAWLER_PATTERN;
module.exports.DEFAULT_API_ORIGIN = DEFAULT_API_ORIGIN;
