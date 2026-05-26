import json
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.combat.combat_ai import CombatAI

def run_enemy_tests():
    # 1. Load Enemy Data
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    enemies_path = os.path.join(base_dir, 'data', 'creatures', 'enemies.json')
    with open(enemies_path, 'r', encoding='utf-8-sig') as f:
        enemies_db = json.load(f)

    # 2. Mock Player
    player = {
        "name": "Test Hero",
        "hp": 1000,
        "current_hp": 1000,
        "ac": 15,
        "proficiency_bonus": 5,
        "weapon_bonus": 0
    }

    print(f"{'Enemy':<20} | {'Turns':<5} | {'Abilities Used'}")
    print("-" * 60)

    for name, data in enemies_db.items():
        # Setup enemy instance
        enemy = data.copy()
        enemy['name'] = name
        enemy['max_hp'] = enemy.get('hp', 10)
        enemy['current_hp'] = enemy['max_hp']
        enemy['max_sp'] = 10
        enemy['current_sp'] = 0
        enemy['max_mp'] = 10
        enemy['current_mp'] = 0
        enemy['has_healed'] = False
        
        abilities_triggered = []
        
        # Simulate 15 turns (to test high-cost ultimates)
        for turn in range(1, 16):
            # Resource Gen
            enemy['current_sp'] = min(10, enemy['current_sp'] + 1)
            enemy['current_mp'] = min(10, enemy['current_mp'] + 1)
            
            # Force health drop on turn 6 to test healing logic
            if turn == 6:
                enemy['current_hp'] = enemy['max_hp'] // 3
            
            # AI Decision
            action = CombatAI.decide_action(enemy)
            
            if action['type'] == 'ability':
                abilities_triggered.append(action['name'])
                # Deduct cost
                cost = action['data'].get('cost', action['data'].get('level', 0))
                res_type = action['data'].get('resource', 'mp')
                enemy[f'current_{res_type}'] -= cost
                
                # If it was a heal, reset HP for further testing
                if action['data'].get('type') == 'heal':
                    enemy['current_hp'] = enemy['max_hp']

        ability_str = ", ".join(set(abilities_triggered)) if abilities_triggered else "None"
        print(f"{name:<20} | {turn:<5} | {ability_str}")

if __name__ == "__main__":
    run_enemy_tests()
