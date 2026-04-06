import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Torus, Sphere, MeshDistortMaterial } from '@react-three/drei'
import * as THREE from 'three'

interface ArcReactorProps {
  active: boolean
  speaking: boolean
}

export function ArcReactor({ active, speaking }: ArcReactorProps) {
  const outerRef = useRef<THREE.Mesh>(null)
  const innerRef = useRef<THREE.Mesh>(null)
  const ringRef = useRef<THREE.Mesh>(null)

  useFrame((_, delta) => {
    if (outerRef.current) outerRef.current.rotation.z += delta * (active ? 1.5 : 0.3)
    if (innerRef.current) innerRef.current.rotation.z -= delta * (active ? 2.5 : 0.5)
    if (ringRef.current) ringRef.current.rotation.x += delta * 0.5
  })

  const color = active ? '#00d4ff' : '#1a4a6e'
  const emissive = speaking ? '#00ffff' : active ? '#0088aa' : '#001122'

  return (
    <group>
      <Sphere ref={outerRef} args={[1.2, 32, 32]}>
        <MeshDistortMaterial
          color={color}
          emissive={emissive}
          emissiveIntensity={speaking ? 2 : 0.8}
          distort={speaking ? 0.4 : 0.1}
          speed={speaking ? 3 : 1}
          transparent
          opacity={0.15}
          wireframe
        />
      </Sphere>

      <Torus ref={ringRef} args={[1.5, 0.05, 16, 100]}>
        <meshStandardMaterial color={color} emissive={emissive} emissiveIntensity={1} />
      </Torus>

      <Torus ref={innerRef} args={[0.8, 0.03, 16, 60]}>
        <meshStandardMaterial color="#00ffff" emissive="#00ffff" emissiveIntensity={1.5} />
      </Torus>

      <Sphere args={[0.3, 16, 16]}>
        <meshStandardMaterial color="#ffffff" emissive="#00d4ff" emissiveIntensity={speaking ? 4 : 1.5} />
      </Sphere>
    </group>
  )
}
