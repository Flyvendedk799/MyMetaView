'use strict';

/**
 * Crawler detection.
 *
 * Kept deliberately in step with the server-side list
 * (`backend/utils/crawler_detection.py`) and the Cloudflare Worker: these are
 * the agents that read Open Graph tags and never run JavaScript, which is
 * exactly the population the browser snippet cannot reach.
 */
const CRAWLER_PATTERN = new RegExp(
  [
    'facebookexternalhit',
    'facebookcatalog',
    'Facebot',
    'Twitterbot',
    'LinkedInBot',
    'Slackbot',
    'Discordbot',
    'WhatsApp',
    'TelegramBot',
    'Pinterest',
    'redditbot',
    'Applebot',
    'Googlebot',
    'bingbot',
    'SkypeUriPreview',
    'vkShare',
    'Iframely',
    'Embedly',
    'nuzzel',
    'Yahoo Link Preview',
    'W3C_Validator',
    'Mastodon',
    'Bluesky',
    'developers\\.google\\.com/\\+/web/snippet',
  ].join('|'),
  'i'
);

/**
 * @param {string|undefined} userAgent
 * @returns {boolean} true when the agent renders share cards but not JavaScript
 */
function isCrawler(userAgent) {
  return typeof userAgent === 'string' && userAgent !== '' && CRAWLER_PATTERN.test(userAgent);
}

module.exports = { CRAWLER_PATTERN, isCrawler };
