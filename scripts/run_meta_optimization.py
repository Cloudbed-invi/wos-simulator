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
    def evaluate_scenario(scenario_name, attacker_cfg, defender_cfg, optimize_side="attacker", is_attack=True):
        print(f"\n==================================================")
        print(f"Starting Scenario: {scenario_name}")
        print(f"==================================================")

        # Restrict to Gen 3 and below
        available_joiners = ["Jessie", "Jasser", "Seo-yoon", "Patrick", "Sergey", "Flint", "Zinman", "Alonso", "Philly", "Jeronimo"]
        defensive_joiners = ["Patrick", "Sergey"]

        leads = attacker_cfg["heroes"] if optimize_side == "attacker" else defender_cfg["heroes"]
        lead_names = [h["name"] for h in leads.values()]

        valid_joiners = [j for j in available_joiners if j not in lead_names]
        joiner_combos = list(itertools.combinations(valid_joiners, 4))
        
        # Filter for defensive joiners if defending
        if not is_attack:
            joiner_combos = [combo for combo in joiner_combos if sum(1 for j in combo if j in defensive_joiners) >= 2]

        print(f"Testing {len(joiner_combos)} different joiner combinations with 1.5M troops per side...")

        best_overall = None
        best_combo = None

        for combo in joiner_combos:
            if optimize_side == "attacker":
                attacker_cfg["joiners"] = [{"name": j} for j in combo]
            else:
                defender_cfg["joiners"] = [{"name": j} for j in combo]

            payload = {
                "attacker": {
                    "troops": {"infantry": 500000, "lancer": 500000, "marksman": 500000},
                    "troop_types": attacker_cfg["troop_types"],
                    "stats": attacker_cfg["stats"],
                    "heroes": attacker_cfg["heroes"],
                    "joiners": attacker_cfg.get("joiners", [])
                },
                "defender": {
                    "troops": {"infantry": 500000, "lancer": 500000, "marksman": 500000},
                    "troop_types": defender_cfg["troop_types"],
                    "stats": defender_cfg["stats"],
                    "heroes": defender_cfg["heroes"],
                    "joiners": defender_cfg.get("joiners", [])
                },
                "rally_mode": True,
                "optimize_side": optimize_side,
                "search_mode": "adaptive",
                "search_replicates": 1,
                "jobs": 4
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
                print(f"Subprocess failed with code {process.returncode}:\nSTDERR: {stderr}")
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
                print(f"Parse error: {e}")

        if best_combo is None:
            print(f"\n>>> ERROR: All combinations failed for {scenario_name}. Please check the STDERR above. <<<")
            return

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
    
    opponent_cfg = copy.deepcopy(whale1_cfg)
    for unit in opponent_cfg["stats"]:
        opponent_cfg["stats"][unit] = [val * 1.05 for val in opponent_cfg["stats"][unit]]
    
    # Opponent Defending (Whale 1 Attacking)
    opp_defend_cfg = copy.deepcopy(opponent_cfg)
    opp_defend_cfg["garrison_leads"] = ["Logan", "Greg", "Philly"]
    opp_defend_cfg["defense_joiners"] = ["Patrick", "Patrick", "Patrick", "Patrick"]
    w2_defend = build_fighter_cfg(opp_defend_cfg, is_rally_lead=False)

    # Opponent Attacking (Whale 1 Defending)
    opp_attack_cfg = copy.deepcopy(opponent_cfg)
    opp_attack_cfg["rally_leads"] = ["Jeronimo", "Greg", "Mia"]
    opp_attack_cfg["rally_joiners"] = ["Jessie", "Jessie", "Jessie", "Jessie"]
    w2_attack = build_fighter_cfg(opp_attack_cfg, is_rally_lead=True)

    # We will optimize Whale 1's attack and defense against this slightly stronger opponent
    print("Opponent configured with +5% stats.")
    print("Opponent Defending Joiners: 4x Patrick")
    print("Opponent Attacking Joiners: 4x Jessie\n")
    
    # Whale 1 Attacking Opponent
    evaluate_scenario("State Whale 1 Attacking", w1_attack, w2_defend, "attacker", True)
    
    # Whale 1 Defending against Opponent
    evaluate_scenario("State Whale 1 Defending", w2_attack, w1_defend, "defender", False)

if __name__ == "__main__":
    main()
