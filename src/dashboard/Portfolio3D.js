/**
 * PILLAR 250: WebGL 3D Portfolio Dashboard.
 * Renders the real-time Sovereign portfolio in a 3D spatial grid.
 * Uses Three.js for hardware-accelerated visuals.
 */

import * as THREE from 'https://cdn.skypack.dev/three@0.132.2';

export class Portfolio3D {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        
        this.bars = {}; // symbol -> mesh
        this.init();
    }

    init() {
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.container.appendChild(this.renderer.domElement);

        this.scene.background = new THREE.Color(0x050505);
        this.camera.position.z = 15;
        this.camera.position.y = 5;
        this.camera.lookAt(0, 0, 0);

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);

        const pointLight = new THREE.PointLight(0x00ffff, 1);
        pointLight.position.set(5, 5, 5);
        this.scene.add(pointLight);

        this.animate();
    }

    updateData(positions) {
        // positions: [{symbol: 'BTC', value: 1000, pnl: 0.05}, ...]
        positions.forEach((pos, index) => {
            if (!this.bars[pos.symbol]) {
                const geometry = new THREE.BoxGeometry(1, 1, 1);
                const material = new THREE.MeshPhongMaterial({ color: 0x00ff00 });
                const bar = new THREE.Mesh(geometry, material);
                bar.position.x = (index - positions.length / 2) * 1.5;
                this.scene.add(bar);
                this.bars[pos.symbol] = bar;
            }

            const bar = this.bars[pos.symbol];
            const height = Math.max(0.1, pos.value / 1000);
            bar.scale.y = height;
            bar.position.y = height / 2;
            
            // Color based on PnL
            if (pos.pnl > 0) {
                bar.material.color.setHex(0x00ff00);
            } else {
                bar.material.color.setHex(0xff0000);
            }
        });
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.scene.rotation.y += 0.005;
        this.renderer.render(this.scene, this.camera);
    }
}
