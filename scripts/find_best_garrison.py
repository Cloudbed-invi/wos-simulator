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
    
    # We will use the exact same stats for both Attacker and Defender
    # to purely test the strength of the Heroes.
    att = {
        "troops": {"infantry": 750000, "lancer": 300000, "marksman": 450000},
        "troop_types": {
            "infantry": f"infantry_{whale1_cfg['troop_tier']}",
            "lancer": f"lancer_{whale1_cfg['troop_tier']}",
            "marksman": f"marksman_{whale1_cfg['troop_tier']}"
        },
        "stats": whale1_cfg["stats"], # NO +5% handicap! Pure hero vs hero test
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
    print(f"Testing {len(combos)} different Garrison Hero combinations INSTANTLY...")
    print(f"Both sides have EQUAL STATS. Attacker is Jeronimo, Mia, Alonso + 4x Jessie.\n")
    
    def run_garrison_test(combo):
        inf, lanc, mark = combo
        def_cfg = {
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
        
        total_def_survivors = 0
        total_att_survivors = 0
        wins = 0
        replicates = 100  # High replicates for accurate results
        
        for _ in range(replicates):
            result = fight_once(att, def_cfg, True)
            if result["outcome"] < 0: # Defender won
                wins += 1
                total_def_survivors += abs(result["outcome"])
            else: # Attacker won
                total_att_survivors += result["outcome"]
                
        win_rate = (wins / replicates) * 100
        
        avg_def_survivors = total_def_survivors / replicates if wins > 0 else 0
        avg_att_survivors = total_att_survivors / replicates if wins < replicates else 0
        
        # Sort metric: First by win rate, then by margin (defender survivors minus attacker survivors)
        sort_metric = avg_def_survivors - avg_att_survivors
        
        return combo, win_rate, avg_def_survivors, avg_att_survivors, sort_metric

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(run_garrison_test, c): c for c in combos}
        for future in as_completed(futures):
            results.append(future.result())
                
    results.sort(key=lambda x: (x[1], x[4]), reverse=True)
    
    print("="*60)
    print("TOP 10 GARRISON COMBINATIONS (PURE HERO COMPARISON)")
    print("="*60)
    for rank, (combo, win_rate, avg_def, avg_att, _) in enumerate(results[:10], 1):
        print(f"#{rank} -> {combo[0]}, {combo[1]}, {combo[2]}")
        print(f"   Win Rate: {win_rate:.1f}%")
        if win_rate > 50:
            print(f"   Result: Garrison Holds! (Avg {avg_def:.0f} Defenders Survive)\n")
        else:
            print(f"   Result: Wall Breaks. (Avg {avg_att:.0f} Attackers Survive)\n")

if __name__ == "__main__":
    main()
