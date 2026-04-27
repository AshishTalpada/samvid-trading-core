
import sys

path = r'c:\Users\talpa\Desktop\System_Beta\TradingSystem\src\agent_d.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if 'def evolve_live(self, pattern_name: str, pnl: float, regime: str):' in line:
        new_lines.append(line)
        new_lines.append('        """\n')
        new_lines.append("        Updates the 75-year weights using a 'Recency Bias' override.\n")
        new_lines.append('        ENHANCEMENT (V12.0): Adaptive Learning Stability.\n')
        new_lines.append('        """\n')
        new_lines.append('        # outcome: 1=WIN, -1=LOSS, 0=BE\n')
        new_lines.append('        if pnl > 0.0001: outcome = 1.0\n')
        new_lines.append('        elif pnl < -0.0001: outcome = -1.0\n')
        new_lines.append('        else: outcome = 0.0\n')
        new_lines.append('\n')
        new_lines.append('        # --- ADAPTIVE REWIRE STABILITY ---\n')
        new_lines.append('        penalty_base = 0.08 # 8% Max\n')
        new_lines.append('        scaling_factor = 0.25 # Default for Preliminary data\n')
        new_lines.append('\n')
        new_lines.append('        if self.atlas and getattr(self.atlas, "atlas_data", {}):\n')
        new_lines.append('             patterns = self.atlas.atlas_data.get(pattern_name, [])\n')
        new_lines.append('             n_count = len(patterns)\n')
        new_lines.append('             if n_count > 100: scaling_factor = 1.0\n')
        new_lines.append('             elif n_count > 50: scaling_factor = 0.5\n')
        new_lines.append('\n')
        new_lines.append('             penalty_scalar = penalty_base * scaling_factor\n')
        new_lines.append('             penalty = (1.0 - penalty_scalar) if outcome < 0 else (1.0 + penalty_scalar)\n')
        new_lines.append('             if outcome == 0: penalty = 1.0\n')
        new_lines.append('\n')
        new_lines.append('             count = 0\n')
        new_lines.append('             for i in range(min(100, len(patterns))):\n')
        new_lines.append('                 idx = -(i+1)\n')
        new_lines.append('                 data = list(patterns[idx])\n')
        new_lines.append('                 # CAP: min 0.1, max 3.0 (Sovereign V22.1)\n')
        new_lines.append('                 data[1] = min(3.0, max(0.1, data[1] * penalty))\n')
        new_lines.append('                 patterns[idx] = tuple(data)\n')
        new_lines.append('                 count += 1\n')
        new_lines.append('\n')
        new_lines.append(f"             logging.info(f\"🏛️ Evolution: Adaptive Rewire complete for '{{pattern_name}}'. Impact: {{penalty:.4f}}x (Scaling: {{scaling_factor:.2f}}).\")\n")
        skip = True
        continue
    
    if skip:
        if 'class RegimeClassifier:' in line:
            new_lines.append('\n')
            new_lines.append(line)
            skip = False
        continue
    
    new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("File patched successfully.")
