import sys
import os
import random
import json
import math

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.game_rules.game_manager import GameManager
from core.combat.combat_engine import CombatEngine
from core.creatures.enemies import get_scaled_enemies
from core.players.leveler import (
    update_xp_and_level, add_class_level, recalculate_stats, 
    get_class_stats_at_level, load_player_classes, load_xp_table
)
from core.players.player import (
    apply_weapon_to_player, apply_armor_to_player
)
from core.combat.enemy_ai import EnemyAI

class CategorySimulator:
    def __init__(self, category='undead', start_level=5):
        self.game = GameManager()
        self.category = category
        self.start_level = start_level
        self.log_messages = []
        self.victory_count = 0
        self.init_party()

    def log(self, msg):
        self.log_messages.append(msg)
        print(msg)

    def init_party(self):
        self.log(f"Initializing {self.category.upper()} Gauntlet - Level {self.start_level} Trio")
        player_classes_data = load_player_classes()
        xp_table = load_xp_table()
        target_xp = xp_table.get(str(self.start_level), 0)
        
        classes = ["fighter", "wizard", "cleric", "rogue", "ranger", "monk", "druid", "sorcerer"]
        chosen_classes = random.sample(classes, 3)
        
        self.game.party = []
        for i, c_key in enumerate(chosen_classes):
            name = "Hero" if i == 0 else f"Merc_{i}"
            profile = get_class_stats_at_level(c_key, self.start_level, player_classes_data)
            profile.update({
                'class': c_key,
                'name': name,
                'xp': target_xp,
                'level': self.start_level,
                'class_levels': {c_key: self.start_level},
                'inventory_ref': self.game.inventory
            })
            
            recalculate_stats(profile)
            
            # Standard gearing for tier
            if self.start_level >= 31: profile['weapon_bonus'] = 2
            elif self.start_level >= 16: profile['weapon_bonus'] = 1
            
            apply_weapon_to_player(profile)
            apply_armor_to_player(profile)
            
            profile['current_hp'] = profile['max_hp']
            self.game.party.append(profile)
            
        self.game.player = self.game.party[0]
        self.game.inventory['gold'] = 500

    def simulate_combat(self):
        party_size = len(self.game.party)
        total_level = sum(p.get('level', 1) for p in self.game.party)
        
        if party_size > 1:
            encounter_level = math.ceil((total_level / 2) + (party_size - 1))
        else:
            encounter_level = total_level
        
        # FORCED CATEGORY HERE
        enemies, _ = get_scaled_enemies(encounter_level, 
                                      category=self.category, 
                                      battle_count=self.game.battle_counter,
                                      party_size=len(self.game.party))
        self.game.battle_counter += 1
        
        self.log(f"\n--- {self.category.upper()} COMBAT #{self.game.battle_counter} ---")
        self.log(f"Enemies: {', '.join([e['name'] for e in enemies])}")
        
        combatants = []
        for p in self.game.party: combatants.append({'actor': p, 'is_player': True})
        for e in enemies: combatants.append({'actor': e, 'is_player': False})
        
        for c in combatants:
            c['init'] = random.randint(1, 20) + int(c['actor'].get('proficiency_bonus', 0))
        combatants.sort(key=lambda x: x['init'], reverse=True)
        
        round_num = 1
        while any(p['current_hp'] > 0 for p in self.game.party) and any(e['hp'] > 0 for e in enemies):
            for c in combatants:
                actor = c['actor']
                if actor.get('current_hp', actor.get('hp', 0)) <= 0: continue
                
                if c['is_player']:
                    living_enemies = [e for e in enemies if e['hp'] > 0]
                    if not living_enemies: break
                    target = random.choice(living_enemies)
                    
                    used_ability = False
                    spells = actor.get('spells', [])
                    if spells and actor.get('current_mp', 0) > 0:
                        s_name = random.choice(spells)
                        s_data = EnemyAI.get_ability_data(s_name)
                        if s_data:
                            targets = living_enemies if s_data.get('aoe') else [target]
                            res = CombatEngine.resolve_ability(s_data, actor, targets)
                            actor['current_mp'] -= res.get('mana_cost', 0)
                            used_ability = True
                            for tid, dmg in res.get('damage_by_target', {}).items():
                                for e in living_enemies:
                                    if id(e) == tid: e['hp'] -= dmg
                    
                    if not used_ability:
                        res = CombatEngine.resolve_attack(actor, target)
                        target['hp'] -= res['damage']
                else:
                    living_players = [p for p in self.game.party if p['current_hp'] > 0]
                    if not living_players: break
                    action = EnemyAI.decide_action(actor)
                    if action['type'] == 'ability':
                        targets = living_players if action['data'].get('aoe') else [random.choice(living_players)]
                        res = CombatEngine.resolve_ability(action['data'], actor, targets)
                        for tid, dmg in res.get('damage_by_target', {}).items():
                            for p in living_players:
                                if id(p) == tid: p['current_hp'] -= dmg
                    else:
                        target = random.choice(living_players)
                        res = CombatEngine.resolve_attack(actor, target)
                        target['current_hp'] -= res['damage']
            
            round_num += 1
            if round_num > 100: break

        victory = all(e['hp'] <= 0 for e in enemies)
        if victory:
            self.victory_count += 1
            self.log(f"Victory in {round_num} rounds!")
            # Post-battle recovery
            for p in self.game.party:
                if p['current_hp'] > 0:
                    p['current_hp'] = min(p['max_hp'], p['current_hp'] + p['max_hp'] // 3)
                    p['current_mp'] = min(p.get('max_mp', 0), p.get('current_mp', 0) + 3)
        else:
            self.log(f"DEFEAT by {self.category}.")

        for p in list(self.game.party):
            if p['current_hp'] <= 0:
                if self.game.party.index(p) == 0:
                    self.log("Main Hero Died. Gauntlet Over.")
                    return False
                else:
                    self.log(f"{p['name']} died permanently.")
                    self.game.party.remove(p)
        
        return len(self.game.party) > 0

    def run(self, max_fights=10):
        for i in range(max_fights):
            if not self.simulate_combat():
                break
        
        self.log(f"\n=== FINAL {self.category.upper()} GAUNTLET STATE ===")
        self.log(f"Battles Won: {self.victory_count}")
        self.log(f"Survivors: {len(self.game.party)}")

if __name__ == "__main__":
    # Get all available categories from data/creatures
    categories = [f.replace('.json', '') for f in os.listdir('data/creatures') if f.endswith('.json')]
    
    # Run a Level 10 gauntlet for each category
    for cat in categories:
        sim = CategorySimulator(category=cat, start_level=10)
        sim.run(max_fights=5)
        print("\n" + "="*40 + "\n")
