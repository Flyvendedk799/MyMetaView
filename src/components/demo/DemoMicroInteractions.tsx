import React, { useEffect, useState, useRef } from 'react';

export default function DemoMicroInteractions() {
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
  const [isHovering, setIsHovering] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [btnOffset, setBtnOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      setCursorPos({ x: e.clientX, y: e.clientY });

      if (buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const distanceX = e.clientX - centerX;
        const distanceY = e.clientY - centerY;
        const distance = Math.sqrt(distanceX * distanceX + distanceY * distanceY);

        if (distance < 100) {
          setIsHovering(true);
          // Magnetic pull
          setBtnOffset({
            x: distanceX * 0.2,
            y: distanceY * 0.2
          });
        } else {
          setIsHovering(false);
          setBtnOffset({ x: 0, y: 0 });
        }
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    return () => window.removeEventListener('mousemove', onMouseMove);
  }, []);

  return (
    <>
      {/* Custom Cursor Ring */}
      <div
        className="fixed top-0 left-0 w-8 h-8 border-2 border-white rounded-full pointer-events-none z-[9999] transition-transform duration-75 ease-out"
        style={{
          transform: `translate(${cursorPos.x - 16}px, ${cursorPos.y - 16}px) scale(${isHovering ? 1.5 : 1})`,
          mixBlendMode: 'difference'
        }}
      />

      {/* Magnetic Button */}
      <div className="py-24 flex items-center justify-center bg-[#05050A]">
        <button
          ref={buttonRef}
          className="px-8 py-4 bg-white text-black font-bold rounded-full transition-transform duration-300"
          style={{
            transform: `translate(${btnOffset.x}px, ${btnOffset.y}px)`,
            transitionTimingFunction: 'cubic-bezier(0.25, 1, 0.5, 1)'
          }}
        >
          Hover Me
        </button>
      </div>
    </>
  );
}
