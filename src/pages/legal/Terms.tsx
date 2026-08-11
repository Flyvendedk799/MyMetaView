import LegalPage from './LegalPage'

export default function Terms() {
  return (
    <LegalPage
      title="Terms of Service"
      path="/terms"
      description="The terms that govern your use of MyMetaView."
      updated="August 2026"
    >
      <section>
        <h2>1. The service</h2>
        <p>
          MyMetaView ("the service", "we") generates and serves branded link-preview
          cards and metadata for websites you connect. These terms are an agreement
          between you and the operator of MyMetaView, and apply to every plan,
          including the free trial.
        </p>
      </section>

      <section>
        <h2>2. Your account</h2>
        <ul>
          <li>You must provide a working email address and keep your credentials secure.</li>
          <li>You are responsible for activity that happens under your account and organization.</li>
          <li>You may only connect domains you own or are authorized to act for. We verify ownership before serving previews.</li>
        </ul>
      </section>

      <section>
        <h2>3. Acceptable use</h2>
        <p>You agree not to use the service to:</p>
        <ul>
          <li>generate previews for content that is unlawful, deceptive, or infringes someone else's rights;</li>
          <li>misrepresent the source or nature of a page (for example, previews designed to disguise phishing);</li>
          <li>probe, overload, or disrupt the service, or access it with automated tools beyond the documented API and snippet.</li>
        </ul>
        <p>We may suspend accounts that violate these rules.</p>
      </section>

      <section>
        <h2>4. Plans, trials, and billing</h2>
        <ul>
          <li>New accounts start with a 14-day trial. No payment method is required for the trial.</li>
          <li>Paid plans are billed through Stripe on a monthly cycle and renew automatically until cancelled.</li>
          <li>You can change or cancel your plan at any time from Billing; changes are prorated by Stripe.</li>
          <li>Plan limits (domains, previews per month, AI generations) are enforced by the service; usage past a limit gracefully degrades rather than incurring surprise charges.</li>
        </ul>
      </section>

      <section>
        <h2>5. Your content</h2>
        <p>
          You keep all rights to your websites, brand assets, and the pages we
          preview. You grant us the limited license needed to fetch your pages,
          generate preview images and text from them, store those previews, and
          serve them publicly on your behalf — that is the product working as
          intended. Generated previews for your domains are yours to use.
        </p>
      </section>

      <section>
        <h2>6. Service quality</h2>
        <p>
          We work to keep the service fast and available, but it is provided "as
          is" without warranties. Preview generation depends on your pages being
          reachable, and on third-party platforms (social networks, AI providers,
          hosting) we do not control. Our total liability for any claim is capped
          at the amount you paid us in the three months before the claim arose.
        </p>
      </section>

      <section>
        <h2>7. Termination</h2>
        <p>
          You can delete your account at any time from Account settings; this
          removes your data as described in the Privacy Policy. We may terminate
          accounts that breach these terms, with notice where practical.
        </p>
      </section>

      <section>
        <h2>8. Changes</h2>
        <p>
          We may update these terms as the product evolves. Material changes will
          be announced by email or in the dashboard before they take effect.
          Continuing to use the service after a change means you accept it.
        </p>
      </section>

      <section>
        <h2>9. Contact</h2>
        <p>
          Questions about these terms: <a href="mailto:hello@mymetaview.com">hello@mymetaview.com</a>.
        </p>
      </section>
    </LegalPage>
  )
}
