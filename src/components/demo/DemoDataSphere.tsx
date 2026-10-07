import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

const ParticleSphere = () => {
  const meshRef = useRef<THREE.InstancedMesh>(null);

  const particleCount = 200;

  const dummy = useMemo(() => new THREE.Object3D(), []);
  const colors = useMemo(() => {
    const array = new Float32Array(particleCount * 3);
    const color1 = new THREE.Color('#00F0FF');
    const color2 = new THREE.Color('#7000FF');

    for (let i = 0; i < particleCount; i++) {
      const color = i % 2 === 0 ? color1 : color2;
      color.toArray(array, i * 3);
    }
    return array;
  }, [particleCount]);

  useFrame((state) => {
    if (!meshRef.current) return;

    const time = state.clock.getElapsedTime();

    for (let i = 0; i < particleCount; i++) {
      // Golden ratio spiral distribution
      const phi = Math.acos(-1 + (2 * i) / particleCount);
      const theta = Math.sqrt(particleCount * Math.PI) * phi;

      const r = 3 + Math.sin(time + i * 0.1) * 0.5;

      const x = r * Math.cos(theta) * Math.sin(phi);
      const y = r * Math.sin(theta) * Math.sin(phi);
      const z = r * Math.cos(phi);

      dummy.position.set(x, y, z);
      dummy.scale.setScalar(1 + Math.sin(time * 2 + i) * 0.5);
      dummy.updateMatrix();

      meshRef.current.setMatrixAt(i, dummy.matrix);
    }

    meshRef.current.instanceMatrix.needsUpdate = true;
    meshRef.current.rotation.y = time * 0.1;
    meshRef.current.rotation.z = time * 0.05;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, particleCount]}>
      <sphereGeometry args={[0.05, 16, 16]}>
        <instancedBufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
        />
      </sphereGeometry>
      <meshBasicMaterial vertexColors toneMapped={false} />
    </instancedMesh>
  );
};

export default function DemoDataSphere() {
  return (
    <div className="relative w-full h-[600px] bg-[#05050A]" style={{ '--camera-easing': 'cubic-bezier(0.85, 0, 0.15, 1)' } as React.CSSProperties}>
      <div className="absolute inset-0 z-0">
        <Canvas camera={{ position: [0, 0, 8], fov: 45 }}>
          <color attach="background" args={['#05050A']} />
          <ambientLight intensity={0.5} />
          <ParticleSphere />
          <OrbitControls
            enableZoom={false}
            enablePan={false}
            autoRotate
            autoRotateSpeed={0.5}
          />
        </Canvas>
      </div>

      <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
        <h1
          className="text-6xl md:text-8xl font-black tracking-tighter"
          style={{
            color: 'rgba(255, 255, 255, 0.1)',
            WebkitTextStroke: '1px rgba(255, 255, 255, 0.2)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text'
          }}
        >
          Data Sphere
        </h1>
      </div>
    </div>
  );
}
