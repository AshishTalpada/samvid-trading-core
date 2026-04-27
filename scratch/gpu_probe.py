import subprocess
import os
import sys

def probe_sovereign_gpu():
    """
    Sovereign GPU Probe (SETO V18.2)
    Bypasses 'torch' to provide zero-latency VRAM diagnostics for GTX 1050.
    """
    print("\n" + "═"*60)
    print("🏛️  SOVEREIGN HARDWARE PROBE: GTX 1050 (4GB)")
    print("═"*60 + "\n")

    try:
        # 1. Check nvidia-smi (The Real Source of Truth)
        result = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu", "--format=csv,nounits,noheader"],
            encoding='utf-8'
        ).strip().split(',')
        
        name = result[0]
        used = result[1]
        total = result[2]
        util = result[3]
        
        pct = (int(used) / int(total)) * 100

        print(f"✅ GPU FOUND: {name}")
        print(f"📊 VRAM USE: {used} MiB / {total} MiB ({pct:.1f}%)")
        print(f"🔥 GPU LOAD: {util}%")
        
        if pct > 90:
            print("\n⚠  CRITICAL: VRAM is NEAR CAPACITY. Close Chrome or other apps.")
        elif pct > 75:
            print("\n🟡  WARNING: High VRAM usage. System may shift to Safe Mode.")
        else:
            print("\n🟢  HEALTHY: GPU has sufficient overhead for Full AI Vetting.")

    except FileNotFoundError:
        print("❌ ERROR: 'nvidia-smi' not found. Ensure NVIDIA Drivers are installed.")
    except Exception as e:
        print(f"❌ PROBE FAILED: {e}")

    print("\n" + "═"*60 + "\n")

if __name__ == "__main__":
    probe_sovereign_gpu()
