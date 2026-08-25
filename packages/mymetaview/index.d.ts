/// <reference types="node" />

import type { IncomingMessage, ServerResponse } from 'node:http';

declare namespace mymetaview {
  /** The public preview payload returned by the MyMetaView API. */
  interface Preview {
    url: string;
    title: string;
    description?: string | null;
    image_url?: string | null;
    site_name?: string | null;
    type?: string | null;
    status?: string | null;
    version?: string | null;
  }

  interface Options {
    /** API origin. Default: https://mymetaview.com (env MYMETAVIEW_API_ORIGIN). */
    apiOrigin?: string;
    /** Registered domain, when it differs from the request host (env MYMETAVIEW_SITE). */
    site?: string;
    /** Turn the integration off without removing it (env MYMETAVIEW_ENABLED). */
    enabled?: boolean;
    /** Inject the browser snippet for human visitors. Default: true. */
    snippet?: boolean;
    /** Override the snippet URL (env MYMETAVIEW_SNIPPET_URL). */
    snippetUrl?: string;
    /** Preview lookup timeout in ms. Default: 1500. */
    timeout?: number;
    /** Cache TTL for a hit, in seconds. Default: 300. */
    cacheTtl?: number;
    /** Maximum cached URLs. Default: 500. */
    cacheMax?: number;
    /** Cache TTL for a miss, in seconds. Default: 60. */
    negativeCacheTtl?: number;
    /** How much of the document to buffer while looking for the end of head. Default: 256KB. */
    maxHeadBytes?: number;
    /** Only look up previews for social crawlers. Default: true. */
    crawlersOnly?: boolean;
    /** Called instead of throwing, for logging. */
    onError?: (error: unknown, context: { url?: string; stage?: string }) => void;
    /** Return true to leave a request untouched. */
    skip?: (url: string, req: unknown) => boolean;
    /** Override the fetch implementation (tests, proxies). */
    fetch?: typeof fetch;
  }

  interface ResolvedConfig extends Required<Omit<Options, 'onError' | 'skip' | 'fetch'>> {
    onError: Options['onError'] | null;
    skip: Options['skip'] | null;
    fetch: Options['fetch'] | null;
  }

  type Middleware = ((
    req: IncomingMessage,
    res: ServerResponse,
    next?: () => void
  ) => void) & {
    config: ResolvedConfig;
    client: PreviewClient;
  };

  class PreviewClient {
    constructor(config: ResolvedConfig);
    getPreview(url: string, options?: { variant?: string }): Promise<Preview | null>;
    endpoint(url: string, variant?: string): string;
  }

  function createMiddleware(options?: Options): Middleware;
  function middleware(options?: Options): Middleware;
  /** Aliases of `createMiddleware`, for readability at the call site. */
  function express(options?: Options): Middleware;
  function connect(options?: Options): Middleware;

  function getPreview(
    url: string,
    options?: Options & { variant?: string }
  ): Promise<Preview | null>;
  function metaTags(url: string, options?: Options & { variant?: string }): Promise<string>;
  function metadataFor(url: string, options?: Options): Promise<Record<string, unknown>>;
  function snippetTag(options?: Options): string;
  function renderMetaTags(preview: Preview | null, url: string): string;
  function renderSnippetTag(snippetUrl: string, site?: string): string;
  function toNextMetadata(preview: Preview | null, url: string): Record<string, unknown>;
  function isCrawler(userAgent?: string): boolean;
  function resolveConfig(options?: Options): ResolvedConfig;

  const DEFAULT_API_ORIGIN: string;
  const CRAWLER_PATTERN: RegExp;
}

/** Express/Connect middleware. `app.use(mymetaview())` is the whole install. */
declare function mymetaview(options?: mymetaview.Options): mymetaview.Middleware;

export = mymetaview;
