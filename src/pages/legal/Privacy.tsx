import LegalPage from './LegalPage'

export default function Privacy() {
  return (
    <LegalPage
      title="Privacy Policy"
      path="/privacy"
      description="What MyMetaView collects, why, and how to remove it."
      updated="August 2026"
    >
      <section>
        <h2>1. What we collect</h2>
        <ul>
          <li><strong>Account data</strong> — your email address and a hashed password.</li>
          <li><strong>Product data</strong> — the domains you connect, brand settings you enter (colors, logo, voice), and the previews generated for your pages.</li>
          <li><strong>Page content</strong> — when generating a preview we fetch and screenshot the public page you point us at, and extract its public metadata. We do not access anything behind a login.</li>
          <li><strong>Analytics events</strong> — when a social platform fetches one of your previews (an impression) or a visitor arrives at your site from a social link (a click), we record the event with the platform name and a truncated user agent. These power your analytics dashboard.</li>
          <li><strong>Operational logs</strong> — request logs and error reports with IP addresses, kept for debugging and abuse prevention.</li>
        </ul>
      </section>

      <section>
        <h2>2. What we don't do</h2>
        <ul>
          <li>We don't sell your data or share it with advertisers.</li>
          <li>We don't track visitors on your website beyond the preview events described above.</li>
          <li>We don't store payment card details — payments are processed by Stripe.</li>
        </ul>
      </section>

      <section>
        <h2>3. Third parties we rely on</h2>
        <ul>
          <li><strong>Stripe</strong> — subscription billing.</li>
          <li><strong>Cloud hosting and storage</strong> — the application and generated preview images are hosted with cloud infrastructure providers (currently Railway and Cloudflare).</li>
          <li><strong>AI providers</strong> — page screenshots and extracted text may be sent to an AI model to compose preview copy and layout. They are used for generation, not for training on your data by us.</li>
          <li><strong>Email delivery</strong> — transactional emails (welcome, password reset, notifications) are sent through our email provider.</li>
        </ul>
      </section>

      <section>
        <h2>4. Cookies and storage</h2>
        <p>
          The dashboard uses browser localStorage for your session token and UI
          preferences. The public site sets no tracking cookies. The embed
          snippet on your website uses sessionStorage only to avoid repeated
          requests, and stores nothing about your visitors.
        </p>
      </section>

      <section>
        <h2>5. Retention and deletion</h2>
        <ul>
          <li>Your data is kept while your account is active.</li>
          <li><strong>Export</strong> — Account settings offers a full JSON export of your data at any time.</li>
          <li><strong>Deletion</strong> — deleting your account removes your profile, domains, brand settings, previews, and analytics events. Operational logs age out on a rolling basis.</li>
        </ul>
      </section>

      <section>
        <h2>6. Contact</h2>
        <p>
          Privacy questions or requests: <a href="mailto:hello@mymetaview.com">hello@mymetaview.com</a>.
        </p>
      </section>
    </LegalPage>
  )
}
