# mymetaview

Serve your [MyMetaView](https://mymetaview.com) preview cards as **real,
server-rendered Open Graph tags** from any Node app.

```bash
npm install mymetaview
```

```js
const mymetaview = require('mymetaview')

app.use(mymetaview())
```

That is the install. No key, no build step, nothing to start, no config: the
middleware recognises social crawlers, fetches the card MyMetaView generated for
the URL they asked for, and puts the tags at the top of that page's `<head>`
before it goes out. Every other request is passed through untouched.

Why it matters: the browser snippet only reaches crawlers that execute
JavaScript, and most of them (Facebook, X, LinkedIn, Slack, Discord, WhatsApp)
do not. Tags injected here are in the HTML those crawlers actually read.

## Zero-code install

If you would rather not touch the app at all, load the package into the process
instead of into the code:

```bash
NODE_OPTIONS="--require mymetaview/auto" npm start
```

It wraps whatever handler the process gives to `http.createServer`, which is how
Express, Koa, Fastify, Nest, a custom Next server and a plain `http` handler all
end up serving requests. Configuration comes from the environment (below). This
is the right choice for a container you do not want to rebuild; `app.use(...)`
is the right choice everywhere else, because it lets you decide where in the
middleware chain the filter sits.

## Frameworks

**Express / Connect / Koa (with `koa-connect`) / Nest**

```js
app.use(mymetaview())
```

Register it **before** your routes and before any compression middleware — the
filter deliberately skips a response that is already compressed.

**Fastify**

```js
await fastify.register(require('mymetaview/fastify'))
```

**Next.js** — Next renders its own head, so it takes the metadata instead of a
response filter. Two one-line files:

```ts
// app/layout.tsx (or any page/route segment)
export { generateMetadata } from 'mymetaview/next'

// middleware.ts — tells generateMetadata which URL is being rendered
export { middleware, config } from 'mymetaview/next'
```

Already have a middleware? Add the header from yours instead:

```ts
import { withMyMetaViewUrl } from 'mymetaview/next'

export function middleware(request) {
  return NextResponse.next({ request: { headers: withMyMetaViewUrl(request) } })
}
```

**Anything else** — build the tags yourself and put them in your template:

```js
const { metaTags, snippetTag } = require('mymetaview')

const head = (await metaTags(url)) + snippetTag()
```

## Did it work?

```bash
npx mymetaview check https://your-site.com/some-page
```

`check` requests the page exactly the way Facebook's crawler does and prints
what came back — the tags, where they came from, and what to look at when they
are missing. Other commands: `preview <url>` (the raw JSON), `tags <url>`,
`snippet`.

## Configuration

Everything has a working default, and every option can also come from the
environment — which is how you configure a container you would rather not
rebuild.

| Option | Env | Default | What it does |
|---|---|---|---|
| `apiOrigin` | `MYMETAVIEW_API_ORIGIN` | `https://mymetaview.com` | API to fetch previews from |
| `site` | `MYMETAVIEW_SITE` | request host | Registered domain, when previews are owned by a different one (a subdomain served by the apex's account) |
| `enabled` | `MYMETAVIEW_ENABLED` | `true` | Turn it off without removing it |
| `snippet` | `MYMETAVIEW_SNIPPET` | `true` | Also inject the browser snippet, which powers install verification and click analytics |
| `crawlersOnly` | `MYMETAVIEW_CRAWLERS_ONLY` | `true` | Look up previews for crawlers only. Turning this off puts the API in the path of every page view |
| `timeout` | `MYMETAVIEW_TIMEOUT_MS` | `1500` | Preview lookup budget. On timeout the page ships with the tags it already had |
| `cacheTtl` | `MYMETAVIEW_CACHE_TTL` | `300` | Seconds to cache a preview in-process |
| `negativeCacheTtl` | `MYMETAVIEW_NEGATIVE_CACHE_TTL` | `60` | Seconds to cache a miss, so a down API costs one call per URL per minute |
| `cacheMax` | `MYMETAVIEW_CACHE_MAX` | `500` | Cached URLs before the coldest is evicted |
| `maxHeadBytes` | `MYMETAVIEW_MAX_HEAD_BYTES` | `262144` | How much document to buffer while looking for the end of `<head>` |
| `onError` | — | — | `(error, context)` for logging; nothing is ever thrown at a request |
| `skip` | — | — | `(url, req) => boolean`, to leave requests alone |

```js
app.use(
  mymetaview({
    site: 'example.com',
    onError: (error, { url }) => logger.warn({ err: error, url }, 'preview lookup failed'),
    skip: (url) => url.includes('/admin/'),
  })
)
```

## What it will not do

Deliberate limits, so nothing here can take a page down:

- **Never blocks on the API.** The lookup starts when the request arrives and is
  awaited only once the `<head>` has been written, so your app renders in
  parallel. It is aborted at `timeout`, and both hits and misses are cached.
- **Never rewrites what it does not understand.** Non-200, non-HTML, already
  compressed, non-GET, or a static file extension: passed straight through.
- **Never injects twice.** A page that already carries these tags — from this
  package, the Cloudflare Worker or the WordPress plugin — is left as it is.
- **Never invents a card.** When MyMetaView has no real preview for a URL, the
  page keeps its own tags.

Requires Node 18+ (it uses the built-in `fetch`). No dependencies.

## Related

The other server-side installs — the Cloudflare Worker and the WordPress plugin
— are generated pre-bound to your domain on the Install page of your MyMetaView
dashboard. Use whichever sits closest to your traffic; installing more than one
is harmless.
