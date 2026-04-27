import json
import os

def generate_500_sovereign_abilities():
    blueprint = {
        "Layer_1_Sensory": {},
        "Layer_2_Cognitive": {},
        "Layer_3_Risk": {},
        "Layer_4_MetaCognitive": {},
        "Layer_5_Tactical": {},
        "Layer_6_Future_AGI": {},
        "Layer_7_Master_Key": {}
    }

    # Ability Names (Foundational)
    bases = {
        "Layer_1_Sensory": ["Tick", "Volume", "Sentiment", "Macro", "Flow", "Depth", "Spread", "Latency", "News", "Scent"],
        "Layer_2_Cognitive": ["Logic", "Reason", "Sim", "Predict", "Audit", "Context", "Memory", "Bias", "Path", "Concept"],
        "Layer_3_Risk": ["Guard", "Hedge", "Size", "Stop", "Drawdown", "Cap", "Margin", "Limit", "Wall", "Safety"],
        "Layer_4_MetaCognitive": ["Self", "Reflect", "Correct", "Drift", "Decay", "Aware", "Spirit", "Goal", "Prowess", "Integrity"],
        "Layer_5_Tactical": ["Move", "Shadow", "Route", "Scale", "Timing", "Execute", "Cancel", "Clean", "Batch", "Fill"],
        "Layer_6_Future_AGI": ["Quantum", "Neural", "Evolve", "Sync", "Parallel", "Graph", "Logic", "Entropy", "Ghost", "Zero"],
        "Layer_7_Master_Key": ["Sovereign", "Final", "Oracle", "Consensus", "Arch", "Purity", "Phoenix", "Resonance", "Focus", "Victory"]
    }

    count = 1
    # Distribute 500 nodes across layers
    items_per_layer = [70, 80, 100, 100, 50, 50, 50] # Total 500
    layers = list(blueprint.keys())

    for idx, layer in enumerate(layers):
        limit = items_per_layer[idx]
        b = bases[layer]
        for i in range(limit):
            name = f"{b[i % len(b)]}_Node_{count:03d}"
            # Carry over the specific manual ones we already defined
            manual_overrides = {
                "15": "HFT Footprint Detection",
                "17": "Absence of News (Abhava)",
                "31": "Antifragility",
                "151": "Fee-Aware Kelly Criterion",
                "164": "Net Liquidation Audit",
                "231": "Cognitive Audit",
                "381": "Cross-Model Interrogation",
                "460": "Final Consensus"
            }
            final_name = manual_overrides.get(str(count), name)
            blueprint[layer][str(count)] = final_name
            count += 1

    blueprint["Status"] = "V9.5_FULL_500_SINGULARITY_ACTIVE"
    
    with open("data/capabilities.json", "w", encoding="utf-8") as f:
        json.dump(blueprint, f, indent=4)
    print(f"✅ SUCCESSFULLY GENERATED {count-1} SOVEREIGN ABILITIES.")

if __name__ == "__main__":
    generate_500_sovereign_abilities()
