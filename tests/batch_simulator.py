import sys
import os
import random
import json
import math
from collections import Counter

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.game_rules.game_manager import GameManager
from core.combat.combat_engine import CombatEngine
from core.creatures.enemies import get_scaled_enemies
from core.players.leveler import (
    recalculate_stats, get_class_stats_at_level, load_player_classes, load_xp_table
)
from core.players.player import (
    apply_weapon_to_player, apply_armor_to_player
)
from core.combat.enemy_ai import EnemyAI

class BatchSimulator:
    def __init__(self, category, start_level, iterations=10):
        self.category = category
        self.start_level = start_level
        self.iterations = iterations
        self.results = []

    def init_party(self, game):
        player_classes_data = load_player_classes()
        xp_table = load_xp_table()
        target_xp = xp_table.get(str(self.start_level), 0)
        
        classes = ["fighter", "wizard", "cleric", "rogue", "ranger", "monk", "druid", "sorcerer"]
        chosen_classes = random.sample(classes, 3)
        
        game.party = []
        for i, c_key in enumerate(chosen_classes):
            name = "Hero" if i == 0 else f"Merc_{i}"
            profile = get_class_stats_at_level(c_key, self.start_level, player_classes_data)
            profile.update({
                'class': c_key,
                'name': name,
                'xp': target_xp,
                'level': self.start_level,
                'class_levels': {c_key: self.start_level},
                'inventory_ref': game.inventory,
                'current_hp': profile['hp'],
                'max_hp': profile['hp']
            })
            recalculate_stats(profile)
            if self.start_level >= 31: profile['weapon_bonus'] = 2
            elif self.start_level >= 16: profile['weapon_bonus'] = 1
            apply_weapon_to_player(profile)
            apply_armor_to_player(profile)
            profile['current_hp'] = profile['max_hp']
            game.party.append(profile)
        game.player = game.party[0]

    def run_single_playthrough(self):
        game = GameManager()
        self.init_party(game)
        game.battle_counter = 0
        victories = 0
        lethal_creature = "None"
        lethal_ability = "None"
        
        for _ in range(10):
            # Determine encounter level (Budget)
            party_size = len(game.party)
            total_level = sum(p.get('level', 1) for p in game.party)
            
            if party_size > 1:
                encounter_level = math.ceil((total_level / 2) + (party_size - 1))
            else:
                encounter_level = total_level
            
            enemies, _ = get_scaled_enemies(encounter_level, 
                                          category=self.category, 
                                          battle_count=game.battle_counter,
                                          party_size=len(game.party))
            game.battle_counter += 1
            
            # Combat loop (Simplified for batch)
            combatants = []
            for p in game.party: combatants.append({'actor': p, 'is_p': True})
            for e in enemies: combatants.append({'actor': e, 'is_p': False})
            
            for c in combatants: c['init'] = random.randint(1, 20) + int(c['actor'].get('proficiency_bonus', 0))
            combatants.sort(key=lambda x: x['init'], reverse=True)
            
            win = False
            for round_num in range(1, 31): # 30 round cap
                for c in combatants:
                    actor = c['actor']
                    if actor.get('current_hp', actor.get('hp', 0)) <= 0: continue
                    
                    if c['is_p']:
                        target = next((e for e in enemies if e['hp'] > 0), None)
                        if not target: break
                        res = CombatEngine.resolve_attack(actor, target)
                        target['hp'] -= res['damage']
                    else:
                        target = next((p for p in game.party if p['current_hp'] > 0), None)
                        if not target: break
                        action = EnemyAI.decide_action(actor)
                        if action['type'] == 'ability':
                            res = CombatEngine.resolve_ability(action['data'], actor, [target])
                            target['current_hp'] -= res['damage']
                            if target['current_hp'] <= 0:
                                lethal_creature = actor['name']
                                lethal_ability = action['data']['name']
                        else:
                            res = CombatEngine.resolve_attack(actor, target)
                            target['current_hp'] -= res['damage']
                            if target['current_hp'] <= 0:
                                lethal_creature = actor['name']
                                lethal_ability = "Basic Attack"
                
                if all(e['hp'] <= 0 for e in enemies):
                    win = True; break
                if game.party[0]['current_hp'] <= 0:
                    win = False; break
            
            if win:
                victories += 1
                # Minor heal between fights
                for p in game.party:
                    if p['current_hp'] > 0:
                        p['current_hp'] = min(p['max_hp'], p['current_hp'] + p['max_hp'] // 3)
                        p['current_mp'] = min(p.get('max_mp', 0), p.get('current_mp', 0) + 3)
                # Remove dead mercs
                game.party = [p for p in game.party if p['current_hp'] > 0]
                if not game.party: break
            else:
                break
                
        return {'victories': victories, 'lethal_creature': lethal_creature, 'lethal_ability': lethal_ability}

    def execute(self):
        for _ in range(self.iterations):
            self.results.append(self.run_single_playthrough())
        
        avg_wins = sum(r['victories'] for r in self.results) / self.iterations
        lethals = Counter(r['lethal_creature'] for r in self.results if r['lethal_creature'] != "None")
        abilities = Counter(r['lethal_ability'] for r in self.results if r['lethal_ability'] != "None")
        
        return {
            'avg_wins': avg_wins,
            'top_killer': lethals.most_common(1)[0][0] if lethals else "None",
            'top_ability': abilities.most_common(1)[0][0] if abilities else "None"
        }

if __name__ == "__main__":
    categories = ['beast', 'dragon', 'fae', 'goblinoid', 'humanoid', 'undead']
    tiers = [5, 10, 15, 20]
    
    summary = {}
    print("Starting Batch Simulation (240 runs)...")
    for cat in categories:
        summary[cat] = {}
        for tier in tiers:
            sim = BatchSimulator(cat, tier, iterations=10)
            res = sim.execute()
            summary[cat][tier] = res
            print(f"[{cat.upper()}] Tier {tier}: Avg Wins {res['avg_wins']}, Top Killer: {res['top_killer']}")

    with open("balance_report.json", "w") as f:
        json.dump(summary, f, indent=4)
    print("\nBatch Simulation Complete. Data saved to balance_report.json")
