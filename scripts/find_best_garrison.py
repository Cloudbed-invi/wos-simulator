import json
import itertools
import sys
import os
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed

def main():
    if not os.path.exists("dashboard/simulate_common.py"):
        if os.path.exists("../dashboard/simulate_common.py"):
            os.chdir("..")
        else:
            print("Error: Must run from project root.")
            sys.exit(1)

    sys.path.insert(0, os.getcwd())
    from dashboard.simulate_common import prepare_simulation_environment, fight_once
    
    print("Loading simulation assets... (Fast mode)")
    prepare_simulation_environment()

    with open("scripts/run_config.json", "r") as f:
        config = json.load(f)

    whale1_cfg = config["whale1"]
    
    opponent_cfg = copy.deepcopy(whale1_cfg)
    for unit in opponent_cfg["stats"]:
        opponent_cfg["stats"][unit] = [val * 1.05 for val in opponent_cfg["stats"][unit]]
        
    att = {
        "troops": {"infantry": 750000, "lancer": 300000, "marksman": 450000},
        "troop_types": {
            "infantry": f"infantry_{whale1_cfg['troop_tier']}",
            "lancer": f"lancer_{whale1_cfg['troop_tier']}",
            "marksman": f"marksman_{whale1_cfg['troop_tier']}"
        },
        "stats": opponent_cfg["stats"],
        "heroes": {
            "infantry": {"name": "Jeronimo", "skills": [5, 5, 5, 5]},
            "lancer": {"name": "Mia", "skills": [5, 5, 5, 5]},
            "marksman": {"name": "Alonso", "skills": [5, 5, 5, 5]}
        },
        "joiners": [{"name": "Jessie"}] * 4
    }

    infantry_leads = ["Logan", "Flint", "Jeronimo", "Natalia"]
    lancer_leads = ["Mia", "Philly"]
    marksman_leads = ["Greg", "Alonso", "Zinman"]
    
    combos = list(itertools.product(infantry_leads, lancer_leads, marksman_leads))
    print(f"Testing {len(combos)} different Garrison Hero combinations INSTANTLY...\n")
    
    def run_garrison_test(combo):
        inf, lanc, mark = combo
        def_cfg = {
            # Fixed Defense Ratio: 50/20/30
            "troops": {"infantry": 750000, "lancer": 300000, "marksman": 450000},
            "troop_types": att["troop_types"],
            "stats": whale1_cfg["stats"],
            "heroes": {
                "infantry": {"name": inf, "skills": [5, 5, 5, 5]},
                "lancer": {"name": lanc, "skills": [5, 5, 5, 5]},
                "marksman": {"name": mark, "skills": [5, 5, 5, 5]}
            },
            "joiners": [{"name": "Patrick"}] * 4
        }
        
        # Run 20 replicates for each combo to average out RNG
        total_margin = 0
        wins = 0
        replicates = 20
        
        for _ in range(replicates):
            result = fight_once(att, def_cfg, True)
            total_margin += result["outcome"]
            if result["outcome"] < 0: # Negative outcome means defender survived
                wins += 1
                
        avg_margin = total_margin / replicates
        win_rate = (wins / replicates) * 100
        
        return combo, {"win_rate_pct": win_rate, "avg_margin": -avg_margin}

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(run_garrison_test, c): c for c in combos}
        for future in as_completed(futures):
            combo, best = future.result()
            results.append((combo, best))
                
    results.sort(key=lambda x: (x[1]["win_rate_pct"], x[1]["avg_margin"]), reverse=True)
    
    print("="*50)
    print("TOP 10 GARRISON COMBINATIONS (FAST SIMULATION)")
    print("="*50)
    for rank, (combo, best) in enumerate(results[:10], 1):
        print(f"#{rank} -> {combo[0]}, {combo[1]}, {combo[2]}")
        print(f"   Win Rate: {best['win_rate_pct']:.1f}%")
        print(f"   Average Survivors: {best['avg_margin']:.0f}\n")

if __name__ == "__main__":
    main()
