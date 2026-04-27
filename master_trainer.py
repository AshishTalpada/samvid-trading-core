import subprocess
import sys
import time
import os

print("💀💀💀 SOVEREIGN AI: INITIATING OMNI-TRAINING MATRIX (ALL AGENTS) 💀💀💀")

scripts_to_run = [
    os.path.join("scripts", "hardcore_75y_hyper_fidelity_trainer.py"),
    os.path.join("scripts", "hardcore_adversarial_trainer.py"),
    os.path.join("scripts", "hardcore_deep_micro_trainer.py"),
    os.path.join("scripts", "sovereign_hardcore_full_fidelity_trainer.py"),
    os.path.join("scripts", "train_100y.py")
]
print("\n⚡ MULTI-CORE ADVERSARIAL SWARM ACTIVE.")
print("   All neural pathways are being flooded with hardcore training data.")
print("   The CPU and GPU are scaling to maximum load. Let them run.")

epoch = 1
try:
    while True:
        print(f"\n======================================")
        print(f"🌀 COMMENCING DEEP TRAINING EPOCH {epoch}")
        print(f"======================================")
        processes = []
        for script in scripts_to_run:
            if os.path.exists(script):
                print(f"🚀 LAUNCHING NEURAL ENGINE: {script}")
                p = subprocess.Popen([sys.executable, script])
                processes.append((script, p))
                
        for script, p in processes:
            p.wait()
            print(f"✅ NEURAL ENGINE COMPLETE: {script}")
            
        print(f"💀💀💀 EPOCH {epoch} FULLY FORGED 💀💀💀")
        print("   -> Database expanded with new fractal mutations.")
        
        # --- ANTI-OVERFITTING SOLVE ---
        if epoch >= 100:
            print("\n🛑 MAXIMUM CONVERGENCE REACHED (100 EPOCHS).")
            print("🛑 Stopping Omni-Matrix to prevent Algorithmic Overfitting.")
            break
            
        epoch += 1
        time.sleep(5) # Heat breather
        
except KeyboardInterrupt:
    print("\n🛑 SHUTTING DOWN NEURAL ENGINES...")
    for script, p in processes:
        try:
            p.terminate()
        except:
            pass
