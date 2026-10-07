import React, { useEffect, useState } from 'react';

export default function DemoScrollytelling() {
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      setScrollY(window.scrollY);
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
    <div className="relative py-20 bg-[#05050A]" style={{
      '--card-easing': 'cubic-bezier(0.16, 1, 0.3, 1)',
      '--morph-easing': 'cubic-bezier(0.65, 0, 0.35, 1)'
    } as React.CSSProperties}>
      <div className="max-w-5xl mx-auto px-6 flex flex-col md:flex-row gap-12">
        <div className="flex-1 space-y-24 py-32">
          {cards.map((card, idx) => (
            <div
              key={idx}
              className="p-8 rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 shadow-2xl transition-all duration-700"
              style={{
                transitionTimingFunction: 'var(--card-easing)',
                transform: `translateY(${Math.max(0, 100 - scrollY * 0.1)}px)`,
                opacity: Math.min(1, scrollY * 0.005)
              }}
            >
              <h3 className="text-2xl font-bold text-white mb-2">{card.title}</h3>
              <p className="text-white/60">{card.desc}</p>
            </div>
          ))}
        </div>
        <div className="flex-1 sticky top-32 h-[400px] flex items-center justify-center">
          <div
            className="w-64 h-64 bg-gradient-to-tr from-[#00F0FF] to-[#7000FF] rounded-full blur-2xl opacity-50 transition-all duration-1000"
            style={{
              transitionTimingFunction: 'var(--morph-easing)',
              borderRadius: `${50 + Math.sin(scrollY * 0.01) * 20}% ${50 + Math.cos(scrollY * 0.01) * 20}%`,
              transform: `scale(${1 + Math.sin(scrollY * 0.005) * 0.2})`
            }}
          />
        </div>
      </div>
    </div>
  );
}
