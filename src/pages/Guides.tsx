import { Link } from 'react-router-dom'
import Seo from '../components/Seo'
import SiteNav from '../components/SiteNav'

const paths = [
  {
    title: 'Node',
    body: 'Install the package and add one line of middleware. Social crawlers get server-rendered tags; everyone else passes through.',
    code: `npm install mymetaview\n\nconst mymetaview = require('mymetaview')\napp.use(mymetaview())`,
  },
  {
    title: 'Cloudflare',
    body: 'From Install, download the Worker already bound to your domain. Paste it into Workers & Pages and attach a route for that hostname.',
    code: 'Install → Download Cloudflare Worker → Deploy → add a route for your domain/*',
  },
  {
    title: 'WordPress',
    body: 'Download the plugin zip from Install and upload it in Plugins → Add New. It prints the tags in wp_head before the page is sent.',
    code: 'Install → Download WordPress plugin → Plugins → Upload → Activate',
  },
  {
    title: 'Snippet',
    body: 'For Shopify, Webflow, Squarespace, Wix, Framer, or plain HTML, paste the script tag from Install into the site head. It covers crawlers that run JavaScript and reports install plus clicks.',
    code: '<script src="https://your-api/snippet.js" data-site="example.com" defer></script>',
  },
]

export default function Guides() {
  return (
    <div className="min-h-screen bg-paper">
      <Seo
        title="Install guides"
        description="How to put MyMetaView tags on a Node app, Cloudflare, WordPress, or any site that can paste a snippet."
        path="/guides"
      />
      <SiteNav />
      <main className="max-w-3xl mx-auto px-4 py-16">
        <p className="font-mono text-xs uppercase tracking-wide text-primary-600 mb-2">Documentation</p>
        <h1 className="font-display text-4xl font-semibold text-secondary-900 mb-4">Install MyMetaView</h1>
        <p className="text-secondary-600 mb-10">
          Four ways to put the same tags in the page head. The{' '}
          <a href="/docs" className="text-primary-600 hover:underline">API reference</a>{' '}
          is separate. After a domain is verified, the Install page in the{' '}
          <Link to="/app/install" className="text-primary-600 hover:underline">dashboard</Link>{' '}
          generates the file or tag already bound to that domain.
        </p>
        <div className="space-y-8">
          {paths.map((path) => (
            <section key={path.title}>
              <h2 className="text-xl font-semibold text-secondary-900 mb-2">{path.title}</h2>
              <p className="text-secondary-600 mb-3">{path.body}</p>
              <pre className="text-sm bg-secondary-900 text-paper rounded-xl p-4 overflow-x-auto whitespace-pre-wrap">{path.code}</pre>
            </section>
          ))}
        </div>
      </main>
    </div>
  )
}
