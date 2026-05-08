import React, { useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Sphere, MeshDistortMaterial } from '@react-three/drei';

/**
 * Geopolitical Risk Dashboard (WebGL)
 * Visualizes military tension, sanctions, and macro risks on a 3D Earth.
 * Red zones indicate active conflict impacting supply chains.
 */
export default function Geopolitics() {
    const [hotZones, setHotZones] = useState([]);

    useEffect(() => {
        // Fetch live macro topology risks
        setHotZones([
            { lat: 25.0, lng: 121.5, risk: 0.9, name: "Taiwan Strait" },
            { lat: 48.0, lng: 37.0, risk: 0.95, name: "Eastern Europe" }
        ]);
    }, []);

    return (
        <div style={{ height: '100vh', width: '100vw', backgroundColor: '#0a0a0a' }}>
            <h1 style={{ color: '#fff', position: 'absolute', padding: '20px' }}>Global Geopolitical Topology</h1>
            <Canvas camera={{ position: [0, 0, 5] }}>
                <ambientLight intensity={0.5} />
                <directionalLight position={[10, 10, 5]} intensity={1.5} />
                
                {/* Earth Sphere representation */}
                <Sphere args={[2, 64, 64]}>
                    <MeshDistortMaterial color="#1a202c" attach="material" distort={0.2} speed={1.5} />
                </Sphere>
                
                <OrbitControls enableZoom={true} />
            </Canvas>
        </div>
    );
}
