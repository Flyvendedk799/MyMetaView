'use strict';

/** The HTML we inject: Open Graph + Twitter tags, and the browser snippet. */

const OG_TYPES = {
  product: 'product',
  blog: 'article',
  article: 'article',
  landing: 'website',
};

const OPEN_MARKER = '<!-- MyMetaView -->';
const CLOSE_MARKER = '<!-- /MyMetaView -->';

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Render the meta tags for a preview.
 *
 * @param {object} preview public preview payload
 * @param {string} url the URL being served
 * @returns {string} HTML, or '' when the preview has nothing worth serving
 */
function renderMetaTags(preview, url) {
  if (!preview || !preview.title) return '';

  const properties = [
    ['og:url', preview.url || url],
    ['og:title', preview.title],
    ['og:description', preview.description],
    ['og:type', OG_TYPES[preview.type] || 'website'],
    ['og:image', preview.image_url],
    ['og:site_name', preview.site_name],
  ];
  const names = [
    ['twitter:card', preview.image_url ? 'summary_large_image' : 'summary'],
    ['twitter:title', preview.title],
    ['twitter:description', preview.description],
    ['twitter:image', preview.image_url],
  ];

  let html = OPEN_MARKER;
  for (const [key, value] of properties) {
    if (value) html += `<meta property="${key}" content="${escapeHtml(value)}">`;
  }
  for (const [key, value] of names) {
    if (value) html += `<meta name="${key}" content="${escapeHtml(value)}">`;
  }
  return `${html}${CLOSE_MARKER}`;
}

/**
 * The browser snippet tag — install heartbeat plus click analytics.
 *
 * @param {string} snippetUrl
 * @param {string} site optional, only added when it earns its place
 */
function renderSnippetTag(snippetUrl, site) {
  const attrs = site ? ` data-site="${escapeHtml(site)}"` : '';
  return `<script src="${escapeHtml(snippetUrl)}"${attrs} defer></script>`;
}

/**
 * A Next.js `Metadata` object for the same preview, for apps that render their
 * head through the framework instead of through a response filter.
 */
function toNextMetadata(preview, url) {
  if (!preview || !preview.title) return {};

  const images = preview.image_url ? [preview.image_url] : undefined;
  const metadata = {
    title: preview.title,
    openGraph: {
      url: preview.url || url,
      title: preview.title,
      type: OG_TYPES[preview.type] || 'website',
    },
    twitter: {
      card: preview.image_url ? 'summary_large_image' : 'summary',
      title: preview.title,
    },
  };

  if (preview.description) {
    metadata.description = preview.description;
    metadata.openGraph.description = preview.description;
    metadata.twitter.description = preview.description;
  }
  if (images) {
    metadata.openGraph.images = images;
    metadata.twitter.images = images;
  }
  if (preview.site_name) metadata.openGraph.siteName = preview.site_name;

  return metadata;
}

module.exports = {
  CLOSE_MARKER,
  OG_TYPES,
  OPEN_MARKER,
  escapeHtml,
  renderMetaTags,
  renderSnippetTag,
  toNextMetadata,
};
