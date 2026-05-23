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

    def build_fighter_cfg(cfg_data, is_rally_lead=False):
        fighter = {
            "troops": {"infantry": 500000, "lancer": 500000, "marksman": 500000},
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
        
        if "rally_joiners" in cfg_data and is_rally_lead:
            fighter["joiners"] = [{"name": j} for j in cfg_data["rally_joiners"]]
        if "defense_joiners" in cfg_data and not is_rally_lead:
            fighter["joiners"] = [{"name": j} for j in cfg_data["defense_joiners"]]
            
        return fighter

    def run_single_combo(combo, attacker_cfg, defender_cfg, optimize_side, phase2_fixed_ratio):
        att = copy.deepcopy(attacker_cfg)
        def_cfg = copy.deepcopy(defender_cfg)
        
        if optimize_side == "attacker":
            att["joiners"] = [{"name": j} for j in combo]
        else:
            def_cfg["joiners"] = [{"name": j} for j in combo]
            
        payload = {
            "attacker": att,
            "defender": def_cfg,
            "rally_mode": True,
            "optimize_side": optimize_side,
            "search_mode": "adaptive",
            "search_replicates": 1,
            "jobs": 1  # Reduce jobs per subprocess to allow higher ThreadPool concurrency
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
            return combo, None, f"Subprocess failed with code {process.returncode}:\nSTDERR: {stderr}"
            
        try:
            lines = stdout.strip().split('\n')
            result = json.loads(lines[-1])
            best = result["best"]
            return combo, best, None
        except Exception as e:
            return combo, None, f"Parse error: {e}"

    def run_optimization(scenario_name, attacker_cfg, defender_cfg, optimize_side="attacker", joiner_combos=None, is_phase2=False):
        print(f"\n{'='*60}")
        print(f"Starting: {scenario_name}")
        print(f"{'='*60}")
        
        if joiner_combos is None:
            joiner_combos = [[]]
            
        best_overall = None
        best_combo = None
        
        # Determine concurrency. If solo (1 combo), just 1 thread. If phase 2 (35 combos), use 8 threads.
        max_workers = 8 if len(joiner_combos) > 1 else 1
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_single_combo, combo, attacker_cfg, defender_cfg, optimize_side, is_phase2): combo 
                for combo in joiner_combos
            }
            
            for future in as_completed(futures):
                combo, best, error = future.result()
                if error:
                    print(error)
                    continue
                    
                if best_overall is None or best["win_rate"] > best_overall["win_rate"] or (best["win_rate"] == best_overall["win_rate"] and best["avg_margin"] > best_overall["avg_margin"]):
                    best_overall = best
                    best_combo = combo
                    if combo:
                        print(f"New Best: {combo} -> {best['infantry_pct']:.0f}/{best['lancer_pct']:.0f}/{best['marksman_pct']:.0f} (Win Rate: {best['win_rate_pct']:.1f}%, Margin: {best['avg_margin']:.0f})")
                
        if best_combo is None:
            print(f"\n>>> ERROR: All combinations failed for {scenario_name}. Check STDERR. <<<")
            return
            
        print(f"\n>>> FINAL BEST FOR {scenario_name} <<<")
        if best_combo:
            print(f"Joiners: {', '.join(best_combo)}")
        else:
            print(f"Joiners: NONE (Solo Phase)")
        print(f"Ratio: {best_overall['infantry_pct']:.0f}% Inf / {best_overall['lancer_pct']:.0f}% Lanc / {best_overall['marksman_pct']:.0f}% Mark")
        print(f"Win Rate: {best_overall['win_rate_pct']:.1f}%")
        print(f"Average Margin: {best_overall['avg_margin']:.0f} survivors\n")

    # Opponent setup
    opponent_cfg = copy.deepcopy(whale1_cfg)
    for unit in opponent_cfg["stats"]:
        opponent_cfg["stats"][unit] = [val * 1.05 for val in opponent_cfg["stats"][unit]]

    def set_troops(cfg, inf_pct, lanc_pct, mark_pct):
        cfg["troops"] = {
            "infantry": int(1500000 * (inf_pct / 100)),
            "lancer": int(1500000 * (lanc_pct / 100)),
            "marksman": int(1500000 * (mark_pct / 100))
        }
        return cfg

    opp_attack_ratios = [(50, 20, 30), (50, 0, 50), (50, 10, 40), (34, 33, 33)]
    opp_defend_ratios = [(50, 30, 20), (60, 20, 20), (50, 0, 50), (33, 33, 34)]
    
    available_joiners = ["Jessie", "Jasser", "Seo-yoon", "Patrick", "Sergey", "Flint", "Zinman", "Alonso", "Philly", "Jeronimo"]
    defensive_joiners = ["Patrick", "Sergey"]

    w1_attack_leads = [h for h in whale1_cfg.get("rally_leads", [])]
    w1_defend_leads = [h for h in whale1_cfg.get("garrison_leads", [])]

    att_valid_joiners = [j for j in available_joiners if j not in w1_attack_leads]
    def_valid_joiners = [j for j in available_joiners if j not in w1_defend_leads]

    att_joiner_combos = list(itertools.combinations(att_valid_joiners, 4))
    def_joiner_combos = list(itertools.combinations(def_valid_joiners, 4))
    def_joiner_combos = [c for c in def_joiner_combos if sum(1 for j in c if j in defensive_joiners) >= 2]

    # --- PHASE 1: SOLO ATTACKS ---
    print("\n" + "#"*70)
    print("PHASE 1: SOLO ATTACKS (NO JOINERS)")
    print("#"*70)
    
    for ratio in opp_defend_ratios:
        w1_att = build_fighter_cfg(whale1_cfg, is_rally_lead=True)
        w1_att["joiners"] = []
        opp_def = build_fighter_cfg(opponent_cfg, is_rally_lead=False)
        opp_def["joiners"] = []
        opp_def = set_troops(opp_def, *ratio)
        run_optimization(f"Whale 1 Attacking (Opponent Defends with {ratio}) [SOLO]", w1_att, opp_def, optimize_side="attacker", is_phase2=False)

    for ratio in opp_attack_ratios:
        w1_def = build_fighter_cfg(whale1_cfg, is_rally_lead=False)
        w1_def["joiners"] = []
        opp_att = build_fighter_cfg(opponent_cfg, is_rally_lead=True)
        opp_att["joiners"] = []
        opp_att = set_troops(opp_att, *ratio)
        run_optimization(f"Whale 1 Defending (Opponent Attacks with {ratio}) [SOLO]", opp_att, w1_def, optimize_side="defender", is_phase2=False)

    # --- PHASE 2: RALLY ATTACKS ---
    print("\n" + "#"*70)
    print("PHASE 2: RALLY ATTACKS (META JOINERS)")
    print("#"*70)
    
    for ratio in opp_defend_ratios:
        w1_att = build_fighter_cfg(whale1_cfg, is_rally_lead=True)
        opp_def_cfg = copy.deepcopy(opponent_cfg)
        opp_def_cfg["defense_joiners"] = ["Patrick", "Patrick", "Patrick", "Patrick"]
        opp_def = build_fighter_cfg(opp_def_cfg, is_rally_lead=False)
        opp_def = set_troops(opp_def, *ratio)
        run_optimization(f"Whale 1 Attacking (Opponent Defends with {ratio} + 4x Patrick)", w1_att, opp_def, optimize_side="attacker", joiner_combos=att_joiner_combos, is_phase2=True)

    for ratio in opp_attack_ratios:
        w1_def = build_fighter_cfg(whale1_cfg, is_rally_lead=False)
        opp_att_cfg = copy.deepcopy(opponent_cfg)
        opp_att_cfg["rally_joiners"] = ["Jessie", "Jessie", "Jessie", "Jessie"]
        opp_att = build_fighter_cfg(opp_att_cfg, is_rally_lead=True)
        opp_att = set_troops(opp_att, *ratio)
        run_optimization(f"Whale 1 Defending (Opponent Attacks with {ratio} + 4x Jessie)", opp_att, w1_def, optimize_side="defender", joiner_combos=def_joiner_combos, is_phase2=True)

if __name__ == "__main__":
    main()
