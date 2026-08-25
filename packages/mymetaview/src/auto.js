'use strict';

/**
 * Zero-code integration.
 *
 *   node --require mymetaview/auto server.js
 *
 * or, without touching the command at all:
 *
 *   NODE_OPTIONS="--require mymetaview/auto"
 *
 * It wraps whatever request handler the process hands to `http.createServer`,
 * which is how Express, Koa, Fastify, Nest, Next's own server and a plain
 * `http` handler all end up serving requests. Configuration comes from the
 * environment, because a process started this way has nowhere to put options.
 *
 * Prefer `app.use(mymetaview())` when you can edit the app: it is one line,
 * and it lets you choose where in the middleware chain the filter sits.
 */

const http = require('node:http');
const https = require('node:https');

const { createMiddleware } = require('./middleware');

const PATCHED = Symbol.for('mymetaview.patched');

const middleware = createMiddleware();

function wrapListener(listener) {
  if (typeof listener !== 'function' || listener[PATCHED]) return listener;

  const wrapped = function mymetaviewRequestListener(req, res) {
    middleware(req, res, () => listener.call(this, req, res));
  };
  wrapped[PATCHED] = true;
  return wrapped;
}

function patchCreateServer(target) {
  const original = target.createServer;
  if (typeof original !== 'function' || original[PATCHED]) return;

  const patched = function createServer(...args) {
    const last = args[args.length - 1];
    if (typeof last === 'function') args[args.length - 1] = wrapListener(last);
    return original.apply(this, args);
  };
  patched[PATCHED] = true;
  Object.defineProperty(patched, 'name', { value: original.name });
  target.createServer = patched;
}

/** Covers `http.createServer()` followed by `server.on('request', app)`. */
function patchRequestListeners(prototype) {
  for (const method of ['on', 'addListener', 'prependListener', 'once']) {
    const original = prototype[method];
    if (typeof original !== 'function' || original[PATCHED]) continue;

    const patched = function (event, listener) {
      if (event === 'request') {
        return original.call(this, event, wrapListener(listener));
      }
      return original.apply(this, arguments);
    };
    patched[PATCHED] = true;
    prototype[method] = patched;
  }
}

if (middleware.config.enabled) {
  patchCreateServer(http);
  patchCreateServer(https);
  patchRequestListeners(http.Server.prototype);

  if (!process.env.MYMETAVIEW_QUIET) {
    // One line, once, at startup: the only way to tell from the outside that a
    // `--require` actually took effect.
    console.log(
      `[mymetaview] serving preview tags to social crawlers (api: ${middleware.config.apiOrigin})`
    );
  }
}

module.exports = middleware;
