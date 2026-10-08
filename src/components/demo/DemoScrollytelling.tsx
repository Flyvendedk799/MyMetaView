import React, { useEffect, useRef } from 'react';

export default function DemoScrollytelling() {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphicRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    let ticking = false;

    const updateScroll = () => {
      const scrollY = window.scrollY;

      // Update graphic
      if (graphicRef.current) {
        graphicRef.current.style.borderRadius = `${50 + Math.sin(scrollY * 0.01) * 20}% ${50 + Math.cos(scrollY * 0.01) * 20}%`;
        graphicRef.current.style.transform = `scale(${1 + Math.sin(scrollY * 0.005) * 0.2})`;
      }

      // Update cards
      cardRefs.current.forEach((card, idx) => {
        if (card) {
          // Add some offset based on index so they stagger slightly
          const offset = idx * 10;
          const y = Math.max(0, 100 - (scrollY - offset) * 0.1);
          const opacity = Math.max(0, Math.min(1, (scrollY - offset) * 0.005));
          card.style.transform = `translateY(${y}px)`;
          card.style.opacity = opacity.toString();
        }
      });

      ticking = false;
    };

    // Initial render
    updateScroll();

    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(updateScroll);
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const cards = [
    { title: 'Extraction', desc: 'Parsing dom for insights.' },
    { title: 'Analysis', desc: 'Understanding your brand.' },
    { title: 'Generation', desc: 'Creating tailored assets.' }
  ];

  return (
    <div ref={containerRef} className="relative py-20 bg-[#05050A]" style={{
      '--card-easing': 'cubic-bezier(0.16, 1, 0.3, 1)',
      '--morph-easing': 'cubic-bezier(0.65, 0, 0.35, 1)'
    } as React.CSSProperties}>
      <div className="max-w-5xl mx-auto px-6 flex flex-col md:flex-row gap-12">
        <div className="flex-1 space-y-24 py-32">
          {cards.map((card, idx) => (
            <div
              key={idx}
              ref={el => { cardRefs.current[idx] = el; }}
              className="p-8 rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 shadow-2xl transition-all duration-700"
              style={{
                transitionTimingFunction: 'var(--card-easing)',
                opacity: 0,
                transform: 'translateY(100px)'
              }}
            >
              <h3 className="text-2xl font-bold text-white mb-2">{card.title}</h3>
              <p className="text-white/60">{card.desc}</p>
            </div>
          ))}
        </div>
        <div className="flex-1 sticky top-32 h-[400px] flex items-center justify-center">
          <div
            ref={graphicRef}
            className="w-64 h-64 bg-gradient-to-tr from-[#00F0FF] to-[#7000FF] rounded-full blur-2xl opacity-50 transition-all duration-1000"
            style={{
              transitionTimingFunction: 'var(--morph-easing)',
            }}
          />
        </div>
      </div>
    </div>
  );
}
