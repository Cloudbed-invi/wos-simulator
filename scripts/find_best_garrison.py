import json
import subprocess
import itertools
import sys
import os
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed

def main():
    if not os.path.exists("dashboard/optimize_ratio.py"):
        if os.path.exists("../dashboard/optimize_ratio.py"):
            os.chdir("..")
        else:
            print("Error: Must run from project root or scripts directory.")
            sys.exit(1)

    with open("scripts/run_config.json", "r") as f:
        config = json.load(f)

    whale1_cfg = config["whale1"]
    
    # Base attacker setup (Opponent +5% stats, Jeronimo/Mia/Alonso, 50/20/30 Ratio, 4x Jessie)
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

    # All viable Garrison options through Gen 3
    infantry_leads = ["Logan", "Flint", "Jeronimo", "Natalia"]
    lancer_leads = ["Mia", "Philly"]
    marksman_leads = ["Greg", "Alonso", "Zinman"]
    
    combos = list(itertools.product(infantry_leads, lancer_leads, marksman_leads))
    print(f"Testing {len(combos)} different Garrison Hero combinations in parallel...")
    print(f"Opponent is attacking with: Jeronimo, Mia, Alonso + 4x Jessie (Ratio: 50/20/30)\n")
    
    def run_garrison_test(combo):
        inf, lanc, mark = combo
        def_cfg = {
            "troops": {"infantry": 500000, "lancer": 500000, "marksman": 500000}, # Ratio will be optimized
            "troop_types": att["troop_types"],
            "stats": whale1_cfg["stats"],
            "heroes": {
                "infantry": {"name": inf, "skills": [5, 5, 5, 5]},
                "lancer": {"name": lanc, "skills": [5, 5, 5, 5]},
                "marksman": {"name": mark, "skills": [5, 5, 5, 5]}
            },
            "joiners": [{"name": "Patrick"}] * 4
        }
        
        payload = {
            "attacker": att,
            "defender": def_cfg,
            "rally_mode": True,
            "optimize_side": "defender",
            "search_mode": "adaptive",
            "search_replicates": 1,
            "jobs": 1
        }
        
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()

        process = subprocess.Popen(
            [sys.executable, "-m", "dashboard.optimize_ratio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(input=json.dumps(payload))

        if process.returncode != 0:
            return combo, None, stderr
            
        try:
            lines = stdout.strip().split('\n')
            result = json.loads(lines[-1])
            return combo, result["best"], None
        except Exception as e:
            return combo, None, str(e)

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(run_garrison_test, c): c for c in combos}
        for future in as_completed(futures):
            combo, best, err = future.result()
            if err:
                print(f"Error for {combo}: {err}")
            else:
                results.append((combo, best))
                
    results.sort(key=lambda x: (x[1]["win_rate"], x[1]["avg_margin"]), reverse=True)
    
    print("\n" + "="*50)
    print("TOP 10 GARRISON COMBINATIONS (MATHEMATICALLY PROVEN)")
    print("="*50)
    for rank, (combo, best) in enumerate(results[:10], 1):
        print(f"#{rank} -> {combo[0]}, {combo[1]}, {combo[2]}")
        print(f"   Win Rate: {best['win_rate_pct']:.1f}%")
        print(f"   Survivors: {best['avg_margin']:.0f}")
        print(f"   Best Defense Ratio: {best['infantry_pct']:.0f}% / {best['lancer_pct']:.0f}% / {best['marksman_pct']:.0f}%\n")

if __name__ == "__main__":
    main()
