'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { mergeVary } = require('../src/headers');

test('Vary gains User-Agent without losing or duplicating anything', () => {
  assert.equal(mergeVary(undefined), 'User-Agent');
  assert.equal(mergeVary(''), 'User-Agent');
  assert.equal(mergeVary('Accept-Encoding'), 'Accept-Encoding, User-Agent');
  assert.equal(mergeVary('Accept-Encoding, user-agent'), 'Accept-Encoding, user-agent');
  assert.equal(mergeVary(['Accept-Encoding', 'Cookie']), 'Accept-Encoding, Cookie, User-Agent');
  assert.equal(mergeVary('*'), '*');
});
