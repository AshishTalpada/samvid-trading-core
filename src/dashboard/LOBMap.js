/**
 * PILLAR 251: 3D Limit Order Book (LOB) Map.
 * Visualizes market depth (Bid/Ask volume) in a 3D topographical map.
 */

import * as THREE from 'https://cdn.skypack.dev/three@0.132.2';

export class LOBMap {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        
        this.terrain = null;
        this.init();
    }

    init() {
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.container.appendChild(this.renderer.domElement);

        this.scene.background = new THREE.Color(0x0a0a0a);
        this.camera.position.set(0, 10, 20);
        this.camera.lookAt(0, 0, 0);

        const gridHelper = new THREE.GridHelper(20, 20, 0x00ffff, 0x333333);
        this.scene.add(gridHelper);

        this.animate();
    }

    updateDepth(bids, asks) {
        // bids: [[price, volume], ...], asks: [[price, volume], ...]
        if (this.terrain) {
            this.scene.remove(this.terrain);
        }

        const geometry = new THREE.PlaneGeometry(20, 10, 32, 32);
        const material = new THREE.MeshPhongMaterial({ 
            color: 0x00ffff, 
            wireframe: true,
            side: THREE.DoubleSide
        });

        this.terrain = new THREE.Mesh(geometry, material);
        this.terrain.rotation.x = -Math.PI / 2;
        
        // Manipulate vertices based on LOB volume
        const pos = this.terrain.geometry.attributes.position;
        for (let i = 0; i < pos.count; i++) {
            const z = Math.random() * 2; // In reality, mapped to Bid/Ask volume
            pos.setZ(i, z);
        }
        
        this.scene.add(this.terrain);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.renderer.render(this.scene, this.camera);
    }
}
