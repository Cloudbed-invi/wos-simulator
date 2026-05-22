import json
import subprocess
import itertools
import sys
import os
import copy

def main():
    # Ensure we are in the scripts directory or the project root
    if not os.path.exists("dashboard/optimize_ratio.py"):
        if os.path.exists("../dashboard/optimize_ratio.py"):
            os.chdir("..")
        else:
            print("Error: Must run from project root or scripts directory.")
            sys.exit(1)

    with open("scripts/run_config.json", "r") as f:
        config = json.load(f)

    user_cfg = config["user"]
    whale1_cfg = config["whale1"]
    whale2_cfg = config["whale2"]

    # Candidate joiners for the user
    available_joiners = ["Jessie", "Jasser", "Seo-yoon", "Patrick", "Ahmose", "Hector", "Gwen"]

    def build_fighter_cfg(cfg_data, is_rally_lead=False):
        # Base config for a fighter
        fighter = {
            "troops": {"infantry": 100000, "lancer": 100000, "marksman": 100000},
            "troop_types": {
                "infantry": f"infantry_{cfg_data['troop_tier']}",
                "lancer": f"lancer_{cfg_data['troop_tier']}",
                "marksman": f"marksman_{cfg_data['troop_tier']}"
            },
            "stats": cfg_data["stats"],
            "heroes": {
                "infantry": {"name": None, "skills": [5, 5, 5, 5]},
                "lancer": {"name": None, "skills": [5, 5, 5, 5]},
                "marksman": {"name": None, "skills": [5, 5, 5, 5]}
            },
            "joiners": []
        }
        
        leads = cfg_data["rally_leads"] if is_rally_lead else cfg_data["garrison_leads"]
        if len(leads) > 0: fighter["heroes"]["infantry"]["name"] = leads[0]
        if len(leads) > 1: fighter["heroes"]["lancer"]["name"] = leads[1]
        if len(leads) > 2: fighter["heroes"]["marksman"]["name"] = leads[2]
        
        # Add default defense joiners for whales
        if not is_rally_lead and "defense_joiners" in cfg_data:
            fighter["joiners"] = [{"name": j} for j in cfg_data["defense_joiners"]]
            
        return fighter

    def evaluate_scenario(scenario_name, attacker_base, defender_base, optimize_side, user_is_attacker):
        print(f"\n{'='*50}\nStarting Scenario: {scenario_name}\n{'='*50}")
        best_overall = None
        best_combo = None

        user_leads = [
            attacker_base["heroes"]["infantry"]["name"],
            attacker_base["heroes"]["lancer"]["name"],
            attacker_base["heroes"]["marksman"]["name"]
        ] if user_is_attacker else [
            defender_base["heroes"]["infantry"]["name"],
            defender_base["heroes"]["lancer"]["name"],
            defender_base["heroes"]["marksman"]["name"]
        ]

        # Filter out joiners that are already in the lead
        valid_joiners = [j for j in available_joiners if j not in user_leads]
        
        # Generate combinations of 4 joiners
        joiner_combos = list(itertools.combinations(valid_joiners, 4))
        print(f"Testing {len(joiner_combos)} different joiner combinations...")

        for combo in joiner_combos:
            att_cfg = copy.deepcopy(attacker_base)
            def_cfg = copy.deepcopy(defender_base)

            joiners_formatted = [{"name": j} for j in combo]
            if user_is_attacker:
                att_cfg["joiners"] = joiners_formatted
            else:
                def_cfg["joiners"] = joiners_formatted

            payload = {
                "attacker": att_cfg,
                "defender": def_cfg,
                "rally_mode": True,
                "optimize_side": optimize_side,
                "search_mode": "adaptive",
                "search_replicates": 20,
                "jobs": 4
            }

            process = subprocess.Popen(
                [sys.executable, "dashboard/optimize_ratio.py"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=json.dumps(payload))

            if process.returncode != 0:
                continue

            try:
                lines = stdout.strip().split('\n')
                result = json.loads(lines[-1])
                best = result["best"]
                
                # We want the highest win rate, then best margin
                if best_overall is None or best["win_rate"] > best_overall["win_rate"] or (best["win_rate"] == best_overall["win_rate"] and best["avg_margin"] > best_overall["avg_margin"]):
                    best_overall = best
                    best_combo = combo
                    print(f"New Best for {scenario_name}: {combo} -> {best['infantry_pct']:.0f}/{best['lancer_pct']:.0f}/{best['marksman_pct']:.0f} (Win Rate: {best['win_rate_pct']:.1f}%, Margin: {best['avg_margin']:.0f})")
            except Exception as e:
                pass

        print(f"\n>>> FINAL BEST FOR {scenario_name} <<<")
        print(f"Joiners: {', '.join(best_combo)}")
        print(f"Ratio: {best_overall['infantry_pct']:.0f}% Inf / {best_overall['lancer_pct']:.0f}% Lanc / {best_overall['marksman_pct']:.0f}% Mark")
        print(f"Win Rate: {best_overall['win_rate_pct']:.1f}%")
        print(f"Average Margin: {best_overall['avg_margin']:.0f} survivors")

    # Build the configurations
    user_attack = build_fighter_cfg(user_cfg, is_rally_lead=True)
    user_defend = build_fighter_cfg(user_cfg, is_rally_lead=False)
    
    w1_attack = build_fighter_cfg(whale1_cfg, is_rally_lead=True)
    w1_defend = build_fighter_cfg(whale1_cfg, is_rally_lead=False)

    w2_attack = build_fighter_cfg(whale2_cfg, is_rally_lead=True)
    w2_defend = build_fighter_cfg(whale2_cfg, is_rally_lead=False)

    # 1. You Attacking Whale 1
    evaluate_scenario("You Attacking Whale 1's Garrison", user_attack, w1_defend, "attacker", True)

    # 2. Whale 1 Attacking You
    evaluate_scenario("Whale 1 Rallying Your Garrison", w1_attack, user_defend, "defender", False)

    # 3. You Attacking Whale 2
    evaluate_scenario("You Attacking Whale 2's Garrison", user_attack, w2_defend, "attacker", True)

    # 4. Whale 2 Attacking You
    evaluate_scenario("Whale 2 Rallying Your Garrison", w2_attack, user_defend, "defender", False)

if __name__ == "__main__":
    main()
