import { useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { useGLTF, Environment, Float, PresentationControls } from '@react-three/drei'
import * as THREE from 'three'

function DataSphereModel() {
  // We use useGLTF to load the model
  const { scene } = useGLTF('https://assets.mymetaview.com/3d/data-sphere-optimized.glb')
  const modelRef = useRef<THREE.Group>(null)

  useFrame((state) => {
    if (modelRef.current) {
      modelRef.current.rotation.y = state.clock.elapsedTime * 0.1
      modelRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.2) * 0.1
    }
  })

  return (
    <Float speed={2} rotationIntensity={0.5} floatIntensity={1}>
      <primitive object={scene} ref={modelRef} scale={1.5} />
    </Float>
  )
}

export function DataSphere() {
  return (
    <div className="w-full h-full min-h-[400px] sm:min-h-[500px]">
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }} dpr={[1, 2]}>
        <ambientLight intensity={0.5} />
        <spotLight position={[10, 10, 10]} angle={0.15} penumbra={1} intensity={1} />
        <PresentationControls
          global
          rotation={[0, 0, 0]}
          polar={[-Math.PI / 4, Math.PI / 4]}
          azimuth={[-Math.PI / 4, Math.PI / 4]}
          config={{ mass: 1, tension: 170, friction: 26 }}
        >
          <DataSphereModel />
        </PresentationControls>
        <Environment preset="city" />
      </Canvas>
    </div>
  )
}
