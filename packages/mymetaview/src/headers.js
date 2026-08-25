'use strict';

/**
 * Response-header bookkeeping for an injected page.
 *
 * The same URL now answers differently depending on who asked — a crawler gets
 * the card tags, a browser gets the snippet — so anything caching in front of
 * the app has to be told, or it will hand one audience the other's page.
 */

const VARY_ON = 'User-Agent';

/**
 * Merge a token into a Vary header value without duplicating it.
 *
 * @param {string|string[]|undefined} existing
 * @param {string} [token]
 * @returns {string}
 */
function mergeVary(existing, token = VARY_ON) {
  const current = Array.isArray(existing) ? existing.join(', ') : String(existing || '');
  if (current === '*') return '*';

  const parts = current
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.some((part) => part.toLowerCase() === token.toLowerCase())) {
    return parts.join(', ');
  }

  parts.push(token);
  return parts.join(', ');
}

module.exports = { VARY_ON, mergeVary };
