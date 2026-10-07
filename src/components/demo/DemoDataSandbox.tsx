import React, { useState } from 'react';

export default function DemoDataSandbox() {
  const [active, setActive] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const handlePointerDown = (e: React.PointerEvent) => {
    setIsDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging) return;
    setPos(p => ({ x: p.x + e.movementX, y: p.y + e.movementY }));
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    setIsDragging(false);
    // Snap back
    setPos({ x: 0, y: 0 });
    e.currentTarget.releasePointerCapture(e.pointerId);
  };

  return (
    <div className="relative p-12 bg-[#05050A] rounded-3xl border border-white/5 overflow-hidden">
      <div className="flex flex-col items-center justify-center gap-12">

        {/* Glowing chart line (SVG) */}
        <div className="w-full h-32 relative">
          <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 100">
            <path
              d="M0,100 C20,80 40,100 60,40 C80,0 100,20 100,20"
              fill="none"
              stroke="#00F0FF"
              strokeWidth="2"
              className="drop-shadow-[0_0_15px_rgba(0,240,255,0.8)]"
              style={{ filter: 'drop-shadow(0px 0px 8px rgba(0, 240, 255, 0.5))' }}
            />
          </svg>
        </div>

        {/* Skeuomorphic Toggle */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setActive(!active)}
            className={`w-20 h-10 rounded-full p-1 shadow-inner transition-colors duration-300 ${active ? 'bg-[#00F0FF]/20 border border-[#00F0FF]/50' : 'bg-black border border-white/10'}`}
            style={{ boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.5)' }}
          >
            <div
              className={`w-8 h-8 rounded-full shadow-lg transition-transform duration-300 ${active ? 'translate-x-10 bg-[#00F0FF]' : 'translate-x-0 bg-neutral-700'}`}
              style={{
                boxShadow: active ? '0 0 10px #00F0FF, inset 0 2px 2px rgba(255,255,255,0.5)' : 'inset 0 2px 2px rgba(255,255,255,0.1)'
              }}
            />
          </button>
          <span className="text-white/60 text-sm font-medium">Live Data Sync</span>
        </div>

        {/* Drag-and-drop snap element */}
        <div
          className="w-32 h-32 bg-[#7000FF]/20 border border-[#7000FF]/50 rounded-2xl flex items-center justify-center cursor-grab active:cursor-grabbing backdrop-blur-md z-10 transition-transform"
          style={{
            transform: `translate(${pos.x}px, ${pos.y}px)`,
            transitionTimingFunction: isDragging ? 'linear' : 'cubic-bezier(0.2, 0.8, 0.2, 1)',
            transitionDuration: isDragging ? '0s' : '0.5s'
          }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        >
          <span className="text-white font-bold select-none text-sm">Drag & Snap</span>
        </div>
      </div>
    </div>
  );
}
