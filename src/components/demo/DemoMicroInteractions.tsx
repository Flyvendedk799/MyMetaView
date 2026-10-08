import React, { useEffect, useRef } from 'react';

export default function DemoMicroInteractions() {
  const cursorRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let ticking = false;
    let latestEvent: MouseEvent | null = null;

    const updatePosition = () => {
      if (!latestEvent) return;
      const e = latestEvent;

      let isHovering = false;
      let btnOffsetX = 0;
      let btnOffsetY = 0;

      if (buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const distanceX = e.clientX - centerX;
        const distanceY = e.clientY - centerY;
        const distance = Math.sqrt(distanceX * distanceX + distanceY * distanceY);

        if (distance < 100) {
          isHovering = true;
          // Magnetic pull
          btnOffsetX = distanceX * 0.2;
          btnOffsetY = distanceY * 0.2;
        }

        // Apply transforms directly to DOM node to avoid React state re-renders on every mouse move
        buttonRef.current.style.transform = `translate(${btnOffsetX}px, ${btnOffsetY}px)`;
      }

      if (cursorRef.current) {
        const scale = isHovering ? 1.5 : 1;
        cursorRef.current.style.transform = `translate(${e.clientX - 16}px, ${e.clientY - 16}px) scale(${scale})`;
      }

      ticking = false;
    };

    const onMouseMove = (e: MouseEvent) => {
      latestEvent = e;
      if (!ticking) {
        window.requestAnimationFrame(updatePosition);
        ticking = true;
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      latestEvent = null;
    };
  }, []);

  return (
    <>
      {/* Custom Cursor Ring */}
      <div
        ref={cursorRef}
        className="fixed top-0 left-0 w-8 h-8 border-2 border-white rounded-full pointer-events-none z-[9999] transition-transform duration-75 ease-out"
        style={{
          transform: `translate(-100px, -100px) scale(1)`,
          mixBlendMode: 'difference'
        }}
      />

      {/* Magnetic Button */}
      <div className="py-24 flex items-center justify-center bg-[#05050A]">
        <button
          ref={buttonRef}
          className="px-8 py-4 bg-white text-black font-bold rounded-full transition-transform duration-300"
          style={{
            transform: `translate(0px, 0px)`,
            transitionTimingFunction: 'cubic-bezier(0.25, 1, 0.5, 1)'
          }}
        >
          Hover Me
        </button>
      </div>
    </>
  );
}
