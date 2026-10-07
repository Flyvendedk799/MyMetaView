import React, { useEffect, useRef } from 'react';

export default function DemoDataSphere() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let time = 0;

    const render = () => {
      time += 0.01;
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const centerX = width / 2;
      const centerY = height / 2;
      const radius = Math.min(width, height) * 0.3;

      for (let i = 0; i < 50; i++) {
        const angle = (i / 50) * Math.PI * 2 + time;
        const x = centerX + Math.cos(angle) * radius * Math.sin(time + i);
        const y = centerY + Math.sin(angle) * radius * Math.cos(time + i);

        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = i % 2 === 0 ? '#00F0FF' : '#7000FF';
        ctx.fill();

        // Connect to center
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(x, y);
        ctx.strokeStyle = i % 2 === 0 ? 'rgba(0, 240, 255, 0.1)' : 'rgba(112, 0, 255, 0.1)';
        ctx.stroke();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  return (
    <div className="relative w-full h-[600px] overflow-hidden bg-[#05050A]" style={{ '--camera-easing': 'cubic-bezier(0.85, 0, 0.15, 1)' } as React.CSSProperties}>
      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        className="absolute inset-0 w-full h-full"
        style={{ transition: 'transform 1s var(--camera-easing)' }}
      />
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <h1 className="text-6xl font-black text-transparent bg-clip-text bg-white/50 backdrop-blur-md" style={{ WebkitTextStroke: '1px rgba(255,255,255,0.1)' }}>
          Data Sphere
        </h1>
      </div>
    </div>
  );
}
