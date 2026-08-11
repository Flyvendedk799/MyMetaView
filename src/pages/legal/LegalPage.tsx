import { ReactNode } from 'react'
import SiteNav from '../../components/SiteNav'
import Footer from '../../components/layout/Footer'
import Seo from '../../components/Seo'

interface LegalPageProps {
  title: string
  path: string
  description: string
  updated: string
  children: ReactNode
}

/**
 * Shared shell for legal documents: public nav, readable measure, footer.
 */
export default function LegalPage({ title, path, description, updated, children }: LegalPageProps) {
  return (
    <div className="min-h-screen bg-ink text-white">
      <Seo title={title} description={description} path={path} />
      <SiteNav />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-32 pb-24">
        <h1 className="font-display text-4xl font-semibold tracking-display mb-3">{title}</h1>
        <p className="text-sm text-white/50 mb-12">Last updated: {updated}</p>
        <div className="legal-prose space-y-8 text-white/80 leading-relaxed [&_h2]:font-display [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-white [&_h2]:mt-10 [&_h2]:mb-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:space-y-1.5 [&_a]:text-accent-400 [&_a]:underline">
          {children}
        </div>
      </main>
      <Footer />
    </div>
  )
}
