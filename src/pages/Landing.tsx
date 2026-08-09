import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import {
  CheckIcon,
  BoltIcon,
  ChartBarIcon,
  PuzzlePieceIcon,
  StarIcon,
  PhotoIcon,
  SparklesIcon,
  ShieldCheckIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import Logo, { LogoMark } from '../components/ui/Logo'
import Seo from '../components/Seo'
import SiteNav from '../components/SiteNav'
import { getPlans } from '../api/client'
import { FALLBACK_PLANS, toDisplayPlan, type DisplayPlan } from '../lib/plans'

// Animated counter hook for stats
function useCountUp(target: number, duration: number = 2000, startOnView: boolean = true) {
  const [count, setCount] = useState(0)
  const [hasStarted, setHasStarted] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!startOnView) {
      setHasStarted(true)
    }
  }, [startOnView])

  useEffect(() => {
    if (startOnView && ref.current) {
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting && !hasStarted) {
            setHasStarted(true)
          }
        },
        { threshold: 0.5 }
      )
      observer.observe(ref.current)
      return () => observer.disconnect()
    }
  }, [startOnView, hasStarted])

  useEffect(() => {
    if (!hasStarted) return

    let startTime: number
    const animate = (currentTime: number) => {
      if (!startTime) startTime = currentTime
      const progress = Math.min((currentTime - startTime) / duration, 1)
      // Ease out cubic for smooth deceleration
      const easeOut = 1 - Math.pow(1 - progress, 3)
      setCount(Math.floor(easeOut * target))
      if (progress < 1) {
        requestAnimationFrame(animate)
      }
    }
    requestAnimationFrame(animate)
  }, [hasStarted, target, duration])

  return { count, ref }
}

const steps = [
  {
    step: '01',
    title: 'Connect a domain',
    description: 'One DNS record or one line of middleware. MetaView verifies it and starts crawling.',
  },
  {
    step: '02',
    title: 'It learns your brand',
    description: 'Colours, type, logo, and tone are extracted from your live pages, then locked as a brand profile you can edit.',
  },
  {
    step: '03',
    title: 'Every link is covered',
    description: 'New pages get metadata within minutes of publishing. Crawlers get the tags, humans get the image.',
  },
]

const features = [
  {
    title: 'AI Semantic Understanding',
    description: 'Deep AI analyzes content to extract meaningful titles, descriptions, and keywords.',
    icon: BoltIcon,
    badge: 'AI-Powered',
  },
  {
    title: 'Smart Screenshots',
    description: 'Automatic website screenshots with intelligent highlight cropping and focal points.',
    icon: PhotoIcon,
    badge: null,
  },
  {
    title: 'Multi-Variant A/B/C Testing',
    description: 'Generate three preview variants per URL. Test what resonates best automatically.',
    icon: StarIcon,
    badge: 'Popular',
  },
  {
    title: 'Real-Time Analytics',
    description: 'Track impressions, clicks, CTR, and performance metrics per domain and preview.',
    icon: ChartBarIcon,
    badge: null,
  },
  {
    title: 'Brand Voice Rewriting',
    description: 'Automatically rewrite preview text to match your brand voice and tone.',
    icon: SparklesIcon,
    badge: null,
  },
  {
    title: 'One-Click Integration',
    description: 'Single script tag works everywhere—WordPress, React, Vue, static sites.',
    icon: PuzzlePieceIcon,
    badge: 'Easy',
  },
]

// Rendered instantly from the plans.py mirror, then swapped for live /plans data.
const FALLBACK_DISPLAY_PLANS: DisplayPlan[] = FALLBACK_PLANS.map(toDisplayPlan)

const platforms = ['Slack', 'X', 'LinkedIn', 'iMessage']

export default function Landing() {
  const navigate = useNavigate()
  const [heroDomain, setHeroDomain] = useState('')
  const [plans, setPlans] = useState<DisplayPlan[]>(FALLBACK_DISPLAY_PLANS)
  const sectionRefs = useRef<(HTMLElement | null)[]>([])

  // Pull live tiers from the backend (single source of truth). The fallback is
  // already on screen, so this just corrects any drift without a loading flash.
  useEffect(() => {
    let active = true
    getPlans()
      .then((live) => {
        if (active && live.length) setPlans(live.map(toDisplayPlan))
      })
      .catch(() => {
        /* keep the fallback tiers */
      })
    return () => {
      active = false
    }
  }, [])

  // Animated counters for stats section
  const stat1 = useCountUp(2000, 2000)
  const stat2 = useCountUp(40, 1500)
  const stat3 = useCountUp(10, 1800)
  const stat4 = useCountUp(99, 2200)

  useEffect(() => {
    // Intersection Observer for staggered fade-in animations
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const children = entry.target.querySelectorAll('[data-animate]')
          children.forEach((child, index) => {
            setTimeout(() => {
              child.classList.add('animate-fade-in-up')
              child.classList.remove('opacity-0')
            }, index * 80)
          })
          observer.unobserve(entry.target)
        }
      })
    }, { threshold: 0.1, rootMargin: '0px 0px -80px 0px' })

    sectionRefs.current.forEach(ref => {
      if (ref) observer.observe(ref)
    })

    return () => observer.disconnect()
  }, [])

  const handleHeroSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const target = heroDomain.trim()
    navigate(target ? `/demo?url=${encodeURIComponent(target)}` : '/demo')
  }

  return (
    <div className="min-h-screen bg-ink overflow-x-hidden">
      <Seo path="/" />
      {/* Navigation */}
      <SiteNav />

      {/* Hero */}
      <header className="pt-32 sm:pt-40 pb-16 sm:pb-24 px-4 sm:px-6 lg:px-12">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          <div className="flex flex-col gap-7">
            <span className="inline-flex items-center gap-2 self-start font-mono text-[11px] uppercase tracking-[0.1em] text-accent-500 border border-accent-500/35 rounded-md px-2.5 py-1.5">
              Metadata, automated
            </span>
            <h1 className="font-display font-semibold text-4xl sm:text-5xl lg:text-[68px] leading-[1.02] tracking-display-lg text-paper text-balance">
              Your links deserve a better first impression.
            </h1>
            <p className="max-w-[46ch] text-lg leading-relaxed text-paper/70">
              MetaView writes the metadata your pages are missing — starting with the share image.
              Point it at a domain and every link you post arrives with a title, description, and a
              generated image that looks like you made it on purpose.
            </p>
            <form onSubmit={handleHeroSubmit} className="flex flex-col sm:flex-row gap-2.5 max-w-[520px]">
              <div className="flex-1 flex items-center gap-2.5 bg-paper/5 border border-paper/15 rounded-lg px-4 h-[52px] focus-within:border-accent-500 transition-colors">
                <span className="font-mono text-sm text-paper/40">https://</span>
                <input
                  type="text"
                  value={heroDomain}
                  onChange={(e) => setHeroDomain(e.target.value)}
                  placeholder="yourdomain.com"
                  aria-label="Your domain"
                  className="flex-1 min-w-0 bg-transparent font-mono text-[15px] text-paper placeholder-paper/30 outline-none border-none focus:ring-0 p-0"
                />
              </div>
              <button
                type="submit"
                className="font-semibold text-[15px] text-paper bg-accent-500 hover:bg-accent-600 rounded-lg px-6 h-[52px] transition-colors"
              >
                See my preview
              </button>
            </form>
            <span className="font-mono text-xs text-paper/40">
              No account needed · first preview in ~20s
            </span>
          </div>

          {/* Preview card mock */}
          <div className="flex flex-col gap-4">
            <div className="bg-paper rounded-xl overflow-hidden shadow-overlay">
              <div className="h-56 sm:h-[232px] bg-primary-500 p-8 flex flex-col justify-between relative overflow-hidden">
                <div className="absolute -right-16 -top-16 w-60 h-60 rounded-full bg-accent-500/15" />
                <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-paper/60 relative">
                  acme.dk / pricing
                </span>
                <span className="font-display font-semibold text-2xl sm:text-[34px] leading-[1.1] tracking-display text-paper max-w-[22ch] relative">
                  Plans that scale with your team
                </span>
              </div>
              <div className="px-5 sm:px-6 py-4 sm:py-5 flex flex-col gap-1">
                <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">acme.dk</span>
                <span className="text-[15px] font-semibold text-secondary-900">Plans that scale with your team — Acme</span>
                <span className="text-[13px] leading-normal text-secondary-600">
                  Transparent pricing, unlimited seats on annual, and no charge for viewers.
                </span>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {['og:image 1200×630', 'twitter:card', 'og:description'].map((tag) => (
                <span key={tag} className="font-mono text-[11px] text-paper/50 border border-paper/15 rounded-md px-2.5 py-1.5">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* Stats band */}
      <section className="bg-paper border-y border-line py-12 sm:py-16 px-4 sm:px-6 lg:px-12">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div ref={stat1.ref} className="flex flex-col items-center gap-1.5 text-center">
              <span className="font-display font-semibold text-3xl sm:text-4xl lg:text-5xl tracking-display text-secondary-900 tabular-nums">
                {stat1.count.toLocaleString()}+
              </span>
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">Active teams</span>
            </div>
            <div ref={stat2.ref} className="flex flex-col items-center gap-1.5 text-center">
              <span className="font-display font-semibold text-3xl sm:text-4xl lg:text-5xl tracking-display text-secondary-900 tabular-nums">
                {stat2.count}%
              </span>
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">Avg. CTR increase</span>
            </div>
            <div ref={stat3.ref} className="flex flex-col items-center gap-1.5 text-center">
              <span className="font-display font-semibold text-3xl sm:text-4xl lg:text-5xl tracking-display text-secondary-900 tabular-nums">
                {stat3.count}M+
              </span>
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">Previews generated</span>
            </div>
            <div ref={stat4.ref} className="flex flex-col items-center gap-1.5 text-center">
              <span className="font-display font-semibold text-3xl sm:text-4xl lg:text-5xl tracking-display text-secondary-900 tabular-nums">
                {stat4.count}.9%
              </span>
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">Uptime SLA</span>
            </div>
          </div>

          <div className="border-t border-line mt-10 pt-8">
            <p className="text-center font-mono text-[11px] uppercase tracking-[0.2em] text-secondary-400 mb-6">
              Trusted by forward-thinking teams
            </p>
            <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-12 lg:gap-16">
              {['NordicStore', 'CloudWave', 'TechFlow', 'DataVault', 'StreamLine'].map((company) => (
                <span
                  key={company}
                  className="text-xl sm:text-2xl font-display font-semibold tracking-display-sm text-secondary-300 hover:text-secondary-600 transition-colors cursor-default"
                >
                  {company}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section
        id="product"
        className="bg-paper py-16 sm:py-24 px-4 sm:px-6 lg:px-12"
        ref={el => sectionRefs.current[0] = el}
      >
        <div className="max-w-7xl mx-auto flex flex-col gap-12">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
            <h2 className="font-display font-semibold text-3xl sm:text-[40px] leading-[1.08] tracking-display text-secondary-900 max-w-[24ch]">
              Three steps, then you stop thinking about it
            </h2>
            <p className="max-w-[40ch] text-base leading-relaxed text-secondary-600">
              MetaView reads your site once, learns its brand, and keeps every new URL covered as you publish.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-line border border-line rounded-xl overflow-hidden">
            {steps.map((item, index) => (
              <div
                key={item.step}
                data-animate
                className="bg-surface p-8 sm:p-9 flex flex-col gap-3 opacity-0"
                style={{ animationDelay: `${index * 120}ms` }}
              >
                <span className="font-mono text-xs text-accent-700">{item.step}</span>
                <h3 className="text-[19px] font-semibold text-secondary-900">{item.title}</h3>
                <p className="text-[15px] leading-relaxed text-secondary-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section
        id="features"
        className="bg-secondary-50 py-16 sm:py-24 px-4 sm:px-6 lg:px-12 border-y border-line"
        ref={el => sectionRefs.current[1] = el}
      >
        <div className="max-w-7xl mx-auto flex flex-col gap-12">
          <div className="text-center flex flex-col items-center gap-4">
            <span className="label-mono">Features</span>
            <h2 className="font-display font-semibold text-3xl sm:text-[40px] leading-[1.08] tracking-display text-secondary-900">
              Everything you need to convert
            </h2>
            <p className="text-base sm:text-lg text-secondary-600 max-w-xl">
              Create stunning URL previews that drive engagement and clicks.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((feature, index) => (
              <div
                key={feature.title}
                data-animate
                className="relative bg-surface rounded-xl p-6 border border-line shadow-card hover:border-primary-500 hover:-translate-y-0.5 transition-all duration-200 opacity-0"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                {feature.badge && (
                  <span className={`absolute top-5 right-5 font-mono text-[10px] uppercase tracking-[0.04em] px-2 py-1 rounded-md ${
                    feature.badge === 'AI-Powered' ? 'bg-accent-100 text-accent-700' :
                    feature.badge === 'Popular' ? 'bg-warning-50 text-warning-700' :
                    'bg-brand-100 text-primary-500'
                  }`}>
                    {feature.badge}
                  </span>
                )}

                <div className="w-11 h-11 rounded-lg bg-brand-100 text-primary-500 flex items-center justify-center mb-4">
                  <feature.icon className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-semibold text-secondary-900 mb-2">{feature.title}</h3>
                <p className="text-secondary-600 text-sm leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Platform coverage */}
      <section
        className="bg-paper py-16 sm:py-24 px-4 sm:px-6 lg:px-12"
        ref={el => sectionRefs.current[2] = el}
      >
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div className="flex flex-col gap-5">
            <span className="label-mono">Every platform</span>
            <h2 className="font-display font-semibold text-3xl sm:text-[40px] leading-[1.08] tracking-display text-secondary-900 max-w-[20ch]">
              One preview, correct everywhere it lands
            </h2>
            <p className="text-base leading-relaxed text-secondary-600 max-w-[48ch]">
              Slack unfurls, X cards, LinkedIn shares, iMessage bubbles — each platform reads your
              tags differently. MetaView validates every preview against each one before it ships.
            </p>
            <div className="flex flex-wrap gap-2">
              {platforms.map((platform, i) => (
                <span
                  key={platform}
                  className={`font-mono text-[11px] uppercase tracking-[0.06em] rounded-md px-2.5 py-1.5 ${
                    i === 0
                      ? 'text-paper bg-ink'
                      : 'text-secondary-500 border border-secondary-300'
                  }`}
                >
                  {platform}
                </span>
              ))}
            </div>
            <Link
              to="/demo"
              className="self-start font-semibold text-sm text-primary-500 hover:text-accent-500 transition-colors"
            >
              Try it on your own URL →
            </Link>
          </div>

          <div className="bg-surface rounded-xl overflow-hidden border border-line shadow-card max-w-[640px] w-full lg:justify-self-end">
            <div className="h-64 sm:h-[300px] bg-primary-500 p-8 sm:p-10 flex flex-col justify-between relative overflow-hidden">
              <div className="absolute -left-10 -bottom-20 w-64 h-64 rounded-full bg-accent-500/[0.18]" />
              <div className="flex items-center gap-2.5 relative">
                <div className="w-[26px] h-[26px] rounded-[7px] bg-accent-500" />
                <span className="font-mono text-xs uppercase tracking-[0.12em] text-paper/70">Acme</span>
              </div>
              <span className="font-display font-semibold text-3xl sm:text-[42px] leading-[1.06] tracking-display text-paper max-w-[20ch] relative">
                What shipped in the Q3 roadmap
              </span>
            </div>
            <div className="px-6 py-5 flex flex-col gap-1">
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-secondary-500">acme.dk</span>
              <span className="text-base font-semibold text-secondary-900">What shipped in the Q3 roadmap — Acme</span>
              <span className="text-sm leading-normal text-secondary-600">
                Nine releases, one migration, and the three things we cut. A short read on what changed for customers this quarter.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section
        id="pricing"
        className="bg-secondary-50 py-16 sm:py-24 px-4 sm:px-6 lg:px-12 border-y border-line"
        ref={el => sectionRefs.current[3] = el}
      >
        <div className="max-w-7xl mx-auto flex flex-col gap-12">
          <div className="text-center flex flex-col items-center gap-4">
            <span className="label-mono">Pricing</span>
            <h2 className="font-display font-semibold text-3xl sm:text-[40px] leading-[1.08] tracking-display text-secondary-900">
              Choose your plan
            </h2>
            <p className="text-base sm:text-lg text-secondary-600 max-w-xl">
              Start free for 14 days. No credit card required.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-5xl mx-auto w-full">
            {plans.map((plan, index) => (
              <div
                key={plan.name}
                data-animate
                className={`relative rounded-xl p-7 sm:p-8 transition-all duration-200 opacity-0 ${
                  plan.highlighted
                    ? 'bg-ink text-paper shadow-overlay'
                    : 'bg-surface border border-line shadow-card hover:border-primary-500 hover:-translate-y-0.5'
                }`}
                style={{ animationDelay: `${index * 150}ms` }}
              >
                {plan.highlighted && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 font-mono text-[10px] uppercase tracking-[0.06em] bg-accent-500 text-paper px-2.5 py-1.5 rounded-md whitespace-nowrap">
                    Most popular
                  </span>
                )}

                <div className="mb-6">
                  <h3 className={`text-xl font-semibold mb-1 ${plan.highlighted ? 'text-paper' : 'text-secondary-900'}`}>
                    {plan.name}
                  </h3>
                  <p className={`text-sm mb-4 ${plan.highlighted ? 'text-paper/60' : 'text-secondary-600'}`}>
                    {plan.description}
                  </p>
                  <div className="flex items-baseline">
                    <span className={`font-display font-semibold text-4xl sm:text-5xl tracking-display tabular-nums ${plan.highlighted ? 'text-paper' : 'text-secondary-900'}`}>
                      {plan.price}
                    </span>
                    <span className={`ml-1 text-sm ${plan.highlighted ? 'text-paper/60' : 'text-secondary-500'}`}>
                      {plan.period}
                    </span>
                  </div>
                </div>

                <ul className="space-y-3 mb-7">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center text-sm">
                      <CheckIcon className={`w-4 h-4 mr-2.5 flex-shrink-0 ${plan.highlighted ? 'text-accent-400' : 'text-success-500'}`} />
                      <span className={plan.highlighted ? 'text-paper/85' : 'text-secondary-700'}>{feature}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  to="/signup"
                  className={`block w-full text-center py-3 rounded-lg font-semibold text-sm transition-colors ${
                    plan.highlighted
                      ? 'bg-accent-500 text-paper hover:bg-accent-600'
                      : 'bg-primary-500 text-paper hover:bg-primary-600'
                  }`}
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-secondary-600">
            <span className="flex items-center gap-2">
              <ShieldCheckIcon className="w-4 h-4 text-success-500" />
              Secure payment
            </span>
            <span className="flex items-center gap-2">
              <ClockIcon className="w-4 h-4 text-success-500" />
              Cancel anytime
            </span>
            <span className="flex items-center gap-2">
              <CheckIcon className="w-4 h-4 text-success-500" />
              14-day money back
            </span>
          </div>
        </div>
      </section>

      {/* Docs */}
      <section
        id="docs"
        className="bg-paper py-16 sm:py-24 px-4 sm:px-6 lg:px-12"
        ref={el => sectionRefs.current[4] = el}
      >
        <div className="max-w-7xl mx-auto flex flex-col gap-12">
          <div className="text-center flex flex-col items-center gap-4">
            <span className="label-mono">Documentation</span>
            <h2 className="font-display font-semibold text-3xl sm:text-[40px] leading-[1.08] tracking-display text-secondary-900">
              Built for developers, ready for everyone
            </h2>
            <p className="text-base sm:text-lg text-secondary-600 max-w-xl">
              From one-line installs to full API integrations — the docs cover it.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-5xl mx-auto w-full">
            <a
              href="/docs"
              className="bg-surface rounded-xl p-6 border border-line shadow-card hover:border-primary-500 hover:-translate-y-0.5 transition-all duration-200 flex flex-col gap-2"
            >
              <span className="font-mono text-xs text-accent-700">01</span>
              <h3 className="text-lg font-semibold text-secondary-900">Quick start</h3>
              <p className="text-sm leading-relaxed text-secondary-600">
                Connect a domain and ship your first preview in under five minutes.
              </p>
              <span className="mt-auto pt-2 font-mono text-[13px] text-primary-500">/docs → getting-started</span>
            </a>
            <a
              href="/docs"
              className="bg-surface rounded-xl p-6 border border-line shadow-card hover:border-primary-500 hover:-translate-y-0.5 transition-all duration-200 flex flex-col gap-2"
            >
              <span className="font-mono text-xs text-accent-700">02</span>
              <h3 className="text-lg font-semibold text-secondary-900">API reference</h3>
              <p className="text-sm leading-relaxed text-secondary-600">
                Generate, list, and update previews programmatically with the REST API.
              </p>
              <span className="mt-auto pt-2 font-mono text-[13px] text-primary-500">/docs → api</span>
            </a>
            <Link
              to="/blog"
              className="bg-surface rounded-xl p-6 border border-line shadow-card hover:border-primary-500 hover:-translate-y-0.5 transition-all duration-200 flex flex-col gap-2"
            >
              <span className="font-mono text-xs text-accent-700">03</span>
              <h3 className="text-lg font-semibold text-secondary-900">Guides & blog</h3>
              <p className="text-sm leading-relaxed text-secondary-600">
                Best practices for og:images, metadata SEO, and share-ready launches.
              </p>
              <span className="mt-auto pt-2 font-mono text-[13px] text-primary-500">/blog</span>
            </Link>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="bg-ink border-t border-paper/10 py-16 sm:py-20 px-4 sm:px-6 lg:px-12">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-8">
          <div className="flex flex-col gap-2.5">
            <h2 className="font-display font-semibold text-3xl sm:text-4xl tracking-display text-paper">
              Run it on your own site first.
            </h2>
            <p className="text-base text-paper/60">
              Free preview, no card, no crawler access required.
            </p>
          </div>
          <Link
            to="/demo"
            className="self-start sm:self-auto font-semibold text-[15px] text-paper bg-accent-500 hover:bg-accent-600 rounded-lg px-8 h-[52px] inline-flex items-center transition-colors flex-shrink-0"
          >
            Generate a preview
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-ink border-t border-paper/10 py-12 sm:py-16 px-4 sm:px-6 lg:px-12">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-10">
            <div className="flex flex-col gap-4">
              <Logo size={26} surface="dark" />
              <p className="text-sm leading-relaxed text-paper/50 max-w-[32ch]">
                AI-powered URL previews that make every link you share look like you made it on purpose.
              </p>
            </div>
            <div>
              <h4 className="font-mono text-[11px] uppercase tracking-label text-paper/40 mb-4">Product</h4>
              <ul className="space-y-2.5 text-sm text-paper/60">
                <li><a href="#features" className="hover:text-paper transition-colors">Features</a></li>
                <li><a href="#pricing" className="hover:text-paper transition-colors">Pricing</a></li>
                <li><Link to="/app" className="hover:text-paper transition-colors">Dashboard</Link></li>
                <li><a href="/docs" className="hover:text-paper transition-colors">Documentation</a></li>
                <li><Link to="/blog" className="hover:text-paper transition-colors">Blog</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-mono text-[11px] uppercase tracking-label text-paper/40 mb-4">Company</h4>
              <ul className="space-y-2.5 text-sm text-paper/60">
                <li><a href="#product" className="hover:text-paper transition-colors">About</a></li>
                <li><Link to="/blog" className="hover:text-paper transition-colors">Blog</Link></li>
                <li><a href="mailto:hello@mymetaview.com" className="hover:text-paper transition-colors">Contact</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-mono text-[11px] uppercase tracking-label text-paper/40 mb-4">Legal</h4>
              <ul className="space-y-2.5 text-sm text-paper/60">
                <li><a href="/privacy" className="hover:text-paper transition-colors">Privacy</a></li>
                <li><a href="/terms" className="hover:text-paper transition-colors">Terms</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-paper/10 mt-10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
            <span className="text-sm text-paper/40">
              © {new Date().getFullYear()} MetaView. All rights reserved.
            </span>
            <span className="font-mono text-[11px] text-paper/30">
              og:image · 1200×630 · always on brand
            </span>
          </div>
        </div>
      </footer>
    </div>
  )
}
