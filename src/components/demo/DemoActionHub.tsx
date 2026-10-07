import React, { useState } from 'react';
import { PlayIcon, ShareIcon, CodeBracketIcon } from '@heroicons/react/24/outline';

export default function DemoActionHub() {
  const [hovered, setHovered] = useState(false);

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50">
      <div
        className="flex items-center gap-2 px-2 py-2 bg-black/40 border border-white/10 rounded-full overflow-hidden transition-all duration-500"
        style={{
          backdropFilter: 'blur(12px)',
          transitionTimingFunction: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
          width: hovered ? '280px' : '64px'
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <button className="w-12 h-12 flex-shrink-0 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors">
          <PlayIcon className="w-6 h-6" />
        </button>
        <div className="flex gap-2 min-w-max opacity-0 transition-opacity duration-300 delay-100" style={{ opacity: hovered ? 1 : 0 }}>
          <button className="px-4 py-2 text-sm font-medium text-white hover:bg-white/10 rounded-full transition-colors">
            Deploy
          </button>
          <button className="p-2 text-white hover:bg-white/10 rounded-full transition-colors">
            <ShareIcon className="w-5 h-5" />
          </button>
          <button className="p-2 text-white hover:bg-white/10 rounded-full transition-colors">
            <CodeBracketIcon className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
