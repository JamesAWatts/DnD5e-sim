import json
import os
import random
import sys

# Add project root to path to allow absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.players.player import choose_player_class, classes as player_classes, apply_weapon_to_player, apply_armor_to_player, load_consumables, load_spells, load_skills
from core.creatures.enemies import load_enemy_data, get_scaled_enemies
from core.players.player_inventory import create_inventory, add_gold, add_item, display_inventory, manage_inventory, award_loot
from core.players.leveler import update_xp_and_level, xp_to_next_level, get_class_stats_at_level, load_player_classes, add_class_level
from core.combat.attack_roller import attack_roll, damage_roll
from core.combat.combat_engine import CombatEngine
from core.combat.over_time import OverTimeProcessor
from core.players.shop import visit_shop

def choose_enemies(enemy_data, player_level=1):
    enemies, category = get_scaled_enemies(player_level, party_size=1)
    names = ", ".join([e['name'].title() for e in enemies])
    print(f"You encountered {names}!")
    input('Press Enter to Roll initiative!\n')
    return enemies


def simulate_combat(player_data, enemy_list, player_goes_first=True):
    player = player_data # Reference to update HP/MP
    enemies = [e.copy() for e in enemy_list] # Work with copies

    # HP Tracking
    player_hp = int(player.get('hp', 1))
    player_max_hp = player.get('max_hp', player_hp)
    
    # Stats (Local modifiable versions for combat)
    p_attack_count = int(player.get('attack_count', 1))
    
    player_advantage = 0 
    enemy_advantage = 0
    extra_damage_once = 0 # From poisons, etc.

    # Condition tracking
    player_conditions = {}
    player['active_effects'] = []
    player['current_hp'] = player_hp
    player['max_hp'] = player_max_hp
    player['name'] = player.get('name', 'Player')

    for e in enemies: 
        e['conditions'] = {}
        e['active_effects'] = []
        e['current_hp'] = e.get('hp', 0)
        e['max_hp'] = e.get('max_hp', e['current_hp'])

    consumables_db = load_consumables()
    spells_db = load_spells()
    skills_db = load_skills()

    turn = 1
    
    def get_alive_enemies():
        return [e for e in enemies if e.get('hp', 0) > 0]

    print(f"Combat start: player hp={player_hp}, enemies={len(enemies)}\n")

    while player_hp > 0 and len(get_alive_enemies()) > 0:
        print(f"--- Turn {turn} ---")

        def player_phase():
            nonlocal player_hp, player_advantage, enemy_advantage, p_attack_count, extra_damage_once
            
            # --- Turn Start: Process Over-Time Effects ---
            player['current_hp'] = player_hp
            ot_results = OverTimeProcessor.process_effects(player)
            for res in ot_results:
                print(f"  [EFFECT] {res['msg']}")
            player_hp = player['current_hp']
            player['hp'] = player_hp

            if player_hp <= 0:
                print("You have succumbed to lingering damage!")
                return "ok"

            if player_conditions.get('stunned', 0) > 0:
                print("You are stunned and skip your turn!")
                player_conditions['stunned'] -= 1
                return "ok"

            action_taken = False
            while not action_taken:
                alive_enemies = get_alive_enemies()
                if not alive_enemies: break

                status_str = f"\nPLAYER TURN (HP: {player_hp}/{player_max_hp}"
                if player.get('max_mp', 0) > 0:
                    status_str += f", MP: {player.get('current_mp', 0)}/{player.get('max_mp', 0)}"
                if player.get('max_sp', 0) > 0:
                    status_str += f", SP: {player.get('current_sp', 0)}/{player.get('max_sp', 0)}"
                status_str += ")"
                print(status_str)
                
                print("Enemies:")
                for i, e in enumerate(alive_enemies, 1):
                    cond_str = f" [{', '.join(e['conditions'].keys())}]" if e['conditions'] else ""
                    # Show active effects
                    eff_list = [eff['name'] for eff in e.get('active_effects', [])]
                    eff_str = f" (Effects: {', '.join(eff_list)})" if eff_list else ""
                    print(f"  {i}. {e['name'].title()} (HP: {e['hp']}){cond_str}{eff_str}")

                print("\n1. Attack")
                print("2. Use Item")
                print("3. Skills/Spells")
                print("4. Run")
                
                choice = input("Select an action: ").strip()
                
                if choice == '1':
                    # Select target
                    t_choice = input(f"Select target (1-{len(alive_enemies)}): ").strip()
                    if not (t_choice.isdigit() and 1 <= int(t_choice) <= len(alive_enemies)):
                        print("Invalid target.")
                        continue
                    
                    target = alive_enemies[int(t_choice) - 1]
                    total_damage = 0
                    for _ in range(p_attack_count):
                        res = CombatEngine.resolve_attack(player, target, advantage=player_advantage)
                        player_advantage = 0 
                        
                        dmg = max(0, res['damage'] - target.get('damage_resist', 0))
                        if res['hit']:
                            if extra_damage_once > 0:
                                dmg += extra_damage_once
                                print(f"  Effect applied! +{extra_damage_once} damage.")
                                extra_damage_once = 0
                                
                            total_damage += dmg
                            print(f"Player hits {target['name']} for {dmg} (roll {res['roll']})")
                            
                            # Handle effects (Refactored for dicts)
                            for effect_dict in res['effects']:
                                e_type = effect_dict.get('type')
                                val = effect_dict.get('value', 0)
                                if e_type == 'vex': player_advantage = 1; print("  Vex: Advantage on next attack!")
                                elif e_type == 'sap': enemy_advantage = -1; print("  Sap: Enemy disadvantage on next attack!")
                                elif e_type == 'heal_attacker':
                                    player_hp = min(player_max_hp, player_hp + val)
                                    print(f"  Lifesteal: Healed for {val} HP!")
                                elif e_type == 'poisoned':
                                    target['conditions']['poisoned'] = effect_dict.get('duration', 1)
                                    print(f"  Effect: {target['name']} is poisoned!")
                                elif e_type == 'dot' or e_type == 'hot':
                                    refreshed = OverTimeProcessor.apply_effect(target, effect_dict)
                                    verb = "refreshed on" if refreshed else "applied to"
                                    print(f"  Effect: {effect_dict['name']} {verb} {target['name']}!")
                                elif e_type == 'msg': print(f"  {val}")
                        else:
                            if dmg > 0:
                                total_damage += dmg
                                print(f"Player grazes {target['name']} for {dmg} damage (roll {res['roll']})")
                            else:
                                print(f"Player misses {target['name']} (roll {res['roll']})")
                    
                    target['hp'] = max(0, target['hp'] - total_damage)
                    target['current_hp'] = target['hp']
                    print(f"Total damage to {target['name']}: {total_damage}. Remaining HP: {target['hp']}")
                    action_taken = True
                    
                elif choice == '2':
                    inv = player_data.get('inventory_ref', {})
                    consumable_dict = inv.get('consumable', {})
                    if not consumable_dict:
                        print("You have no consumables!")
                        continue
                    
                    items = sorted(consumable_dict.keys())
                    print("\n--- Consumables ---")
                    for i, item_name in enumerate(items, 1):
                        count = consumable_dict[item_name]
                        print(f"{i}. {item_name.replace('_', ' ').title()} (x{count})")
                    print(f"{len(items) + 1}. Back")
                    
                    item_choice = input("Select an item to use: ").strip()
                    if item_choice.isdigit() and 1 <= int(item_choice) <= len(items):
                        item_name = items[int(item_choice) - 1]
                        item_key = item_name.lower().replace(' ', '_')
                        item_data = consumables_db.get(item_key)
                        
                        if item_data:
                            res = CombatEngine.resolve_item(item_data, player)
                            print(res['msg'])
                            
                            if res['hp_gain'] > 0:
                                player_hp = min(player_max_hp, player_hp + res['hp_gain'])
                                player['hp'] = player_hp
                                print(f"Healed for {res['hp_gain']} HP! (Current: {player_hp}/{player_max_hp})")
                            
                            # Resources
                            if res['mana_gain'] > 0:
                                player['current_mp'] = min(player.get('max_mp', 0), player.get('current_mp', 0) + res['mana_gain'])
                            
                            if res['bonus_gain'] > 0:
                                player['weapon_bonus'] = player.get('weapon_bonus', 0) + res['bonus_gain']
                                print(f"Attack/Damage bonus increased by {res['bonus_gain']}!")
                            if res['attack_gain'] > 0:
                                p_attack_count += res['attack_gain']
                                print(f"Attack count increased by {res['attack_gain']}!")
                            if res['extra_damage'] > 0:
                                extra_damage_once += res['extra_damage']
                                print(f"Next hit will deal +{res['extra_damage']} damage!")
                            
                            from core.players.player_inventory import remove_item
                            remove_item(inv, item_name, 'consumable')
                            action_taken = True
                    else:
                        continue

                elif choice == '3':
                    skills = player.get('skills', [])
                    spells = player.get('spells', [])
                    all_abilities = skills + spells
                    
                    if not all_abilities:
                        print("You have no skills or spells yet!")
                        continue
                    
                    print("\n--- Skills & Spells ---")
                    for i, ability in enumerate(all_abilities, 1):
                        print(f"{i}. {ability.title()}")
                    print(f"{len(all_abilities) + 1}. Back")
                    
                    s_choice = input("Select an ability: ").strip()
                    if s_choice.isdigit() and 1 <= int(s_choice) <= len(all_abilities):
                        ability_name = all_abilities[int(s_choice) - 1]
                        ability_key = ability_name.lower().replace(' ', '_')
                        ability_data = skills_db.get(ability_key) or spells_db.get(ability_key)
                        
                        if ability_data:
                            cost = ability_data.get('cost', ability_data.get('level', 0))
                            resource_type = ability_data.get('resource', 'mp')
                            resource_key = 'current_mp' if resource_type == 'mp' else 'current_sp'
                            current_resource = player.get(resource_key, 0)
                            
                            if current_resource < cost:
                                print(f"Not enough {resource_type.upper()}! (Need {cost}, have {current_resource})")
                                continue

                            # Target selection for non-AOE
                            targets = alive_enemies
                            if not ability_data.get('aoe'):
                                t_choice = input(f"Select target (1-{len(alive_enemies)}): ").strip()
                                if not (t_choice.isdigit() and 1 <= int(t_choice) <= len(alive_enemies)):
                                    print("Invalid target.")
                                    continue
                                targets = [alive_enemies[int(t_choice) - 1]]

                            # Use resolve_action to match Pygame logic and get effects
                            res_list = CombatEngine.resolve_action(player, ability_data, targets)
                            
                            for res in res_list:
                                target = res['target']
                                dmg = res['damage']
                                heal = res['healing']
                                
                                if dmg > 0:
                                    target['hp'] = max(0, target['hp'] - dmg)
                                    target['current_hp'] = target['hp']
                                    print(f"  {target['name']} took {dmg} damage! (HP: {target['hp']})")
                                
                                if heal > 0:
                                    # Healing in resolve_action targets the target, not necessarily player
                                    target['hp'] = min(target.get('max_hp', 100), target.get('hp', 0) + heal)
                                    target['current_hp'] = target['hp']
                                    if target == player: player_hp = target['hp']
                                    print(f"  {target['name']} healed for {heal} HP!")
                                
                                for effect_dict in res.get('effects', []):
                                    e_type = effect_dict.get('type')
                                    if e_type in ['dot', 'hot']:
                                        if 'active_effects' not in target: target['active_effects'] = []
                                        target['active_effects'].append(effect_dict)
                                        print(f"  Effect: {effect_dict['name']} applied to {target['name']}!")
                                    elif e_type == 'stunned':
                                        target['conditions']['stunned'] = effect_dict.get('duration', 1)
                                        print(f"  Effect: {target['name']} is stunned!")

                            action_taken = True
                        else:
                            print(f"You used {ability_name.title()}!")
                            action_taken = True
                    else:
                        continue

                elif choice == '4':
                    if random.random() < 0.4:
                        print("You successfully ran away!")
                        return "ran"
                    else:
                        print("You failed to run away!")
                        action_taken = True
                else:
                    print("Invalid selection.")
            
            return "ok"

        def enemy_phase():
            nonlocal player_hp, enemy_advantage
            total_damage = 0
            alive_enemies = get_alive_enemies()
            from core.combat.combat_ai import CombatAI
            
            for enemy in alive_enemies:
                # --- Turn Start: Process Over-Time Effects ---
                enemy['current_hp'] = enemy['hp']
                ot_results = OverTimeProcessor.process_effects(enemy)
                for res in ot_results:
                    print(f"  [{enemy['name'].upper()} EFFECT] {res['msg']}")
                enemy['hp'] = enemy['current_hp']

                if enemy['hp'] <= 0:
                    print(f"{enemy['name'].title()} has succumbed to lingering damage!")
                    continue

                if enemy['conditions'].get('stunned', 0) > 0:
                    print(f"{enemy['name'].title()} is stunned and skips their turn!")
                    enemy['conditions']['stunned'] -= 1
                    continue

                # Regen (CLI equivalent)
                max_sp = 10
                max_mp = 10
                enemy['current_sp'] = min(max_sp, enemy.get('current_sp', 0) + 1)
                enemy['current_mp'] = min(max_mp, enemy.get('current_mp', 0) + 1)

                max_attacks = int(enemy.get('attack_count', 1))
                attacks_made = 0
                
                while attacks_made < max_attacks:
                    action = CombatAI.decide_action(enemy)
                    
                    # Ensure Action Data is compatible with resolve_action
                    action_data = action.get('data', {})
                    if action['type'] == 'attack':
                        from core.combat.action_builder import ActionBuilder
                        action_data = ActionBuilder.build_basic_attack(enemy)

                    # Target selection
                    if action_data.get('type') == 'heal':
                        targets = [enemy]
                    else:
                        targets = [player]

                    res_list = CombatEngine.resolve_action(enemy, action_data, targets)
                    
                    for res in res_list:
                        target = res['target']
                        dmg = res['damage']
                        heal = res['healing']

                        if dmg > 0:
                            if target == player:
                                player_hp = max(0, player_hp - dmg)
                                player['current_hp'] = player_hp
                                print(f"{enemy['name']} hits you for {dmg} damage!")
                            else:
                                target['hp'] = max(0, target['hp'] - dmg)
                                print(f"{enemy['name']} hits {target['name']} for {dmg} damage!")
                        
                        if heal > 0:
                            target['hp'] = min(target.get('max_hp', 100), target.get('hp', 0) + heal)
                            print(f"{enemy['name']} healed {target['name']} for {heal} HP!")

                        # Apply effects
                        for effect_dict in res.get('effects', []):
                            e_type = effect_dict.get('type')
                            if e_type in ['dot', 'hot']:
                                if 'active_effects' not in target: target['active_effects'] = []
                                target['active_effects'].append(effect_dict)
                                print(f"  Effect: {effect_dict['name']} applied to {target['name']}!")
                            elif e_type == 'stunned':
                                if target == player:
                                    player_conditions['stunned'] = effect_dict.get('duration', 1)
                                    print("  Effect: You are stunned!")
                                else:
                                    target['conditions']['stunned'] = effect_dict.get('duration', 1)
                        
                    if action_data.get('use_attack_count') or action['type'] == 'attack':
                        attacks_made += 1
                    else:
                        break # Non-multi-hit ability ends turn

            player_hp = max(0, player_hp - total_damage)
            print(f"Total damage received this round: {total_damage}. Player HP: {player_hp}\n")

        if player_goes_first:
            res = player_phase()
            if res == "ran": return {'winner': 'none', 'player_hp': player_hp, 'turns': turn}
            if not get_alive_enemies(): break
            input('Next phase...')
            enemy_phase()
        else:
            enemy_phase()
            if player_hp <= 0: break
            input('Next phase...')
            res = player_phase()
            if res == "ran": return {'winner': 'none', 'player_hp': player_hp, 'turns': turn}

        if player_hp <= 0 or not get_alive_enemies(): break
        input('Next turn...')
        turn += 1

    winner = 'player' if player_hp > 0 else 'enemy'
    print(f"Combat ends: {winner.upper()} wins")
    player['hp'] = player_hp 

    # Cleanse party effects after combat
    from core.combat.combat_resolver import CombatResolver
    CombatResolver.cleanse_party([player])

    return {'winner': winner, 'player_hp': player_hp, 'turns': turn}


def hub_menu(player_profile, player_inventory):
    while True:
        print("\n--- ADVENTURE HUB ---")
        print(f"Level {player_profile['level']} {player_profile['class'].title()}")
        print(f"HP: {player_profile['hp']} / {player_profile.get('max_hp', player_profile['hp'])}")
        print(f"Gold: {player_inventory['gold']}")
        
        rest_cost = 5 + player_profile.get('rest_count', 0)
        
        print("1. Next Fight")
        print("2. Visit Shop")
        print(f"3. Rest (Restores full HP, costs {rest_cost} gold)")
        print("4. View Inventory/Stats")
        print("5. Exit Game")
        
        choice = input("What would you like to do? ").strip()
        
        if choice == '1':
            return True
        elif choice == '2':
            visit_shop(player_profile, player_inventory)
        elif choice == '3':
            rest(player_profile, player_inventory)
        elif choice == '4':
            manage_inventory(player_profile, player_inventory)
        elif choice == '5':
            return False
        else:
            print("Invalid selection.")

def rest(player_profile, player_inventory):
    cost = 5 + player_profile.get('rest_count', 0)
    if player_inventory['gold'] >= cost:
        player_inventory['gold'] -= cost
        player_profile['hp'] = player_profile.get('max_hp', player_profile['hp'])
        player_profile['rest_count'] = player_profile.get('rest_count', 0) + 1
        print(f"You rested for {cost} gold. HP fully restored to {player_profile['hp']}!")
        print(f"Your next rest will cost {5 + player_profile['rest_count']} gold.")
    else:
        print(f"You don't have enough gold! You need {cost} gold to rest.")


def main():
    enemy_data = load_enemy_data()
    player_name, player_profile = choose_player_class(player_classes)
    player_profile['class'] = player_name
    player_profile.setdefault('xp', 0)
    player_profile.setdefault('level', 1)
    player_profile.setdefault('base_hp', player_profile.get('hp', 0))
    player_profile['max_hp'] = player_profile['hp']
    
    player_profile['rest_count'] = 0

    player_classes_data = load_player_classes()
    level1_stats = get_class_stats_at_level(player_name, 1, player_classes_data)
    for k, v in level1_stats.items(): player_profile[k] = v

    apply_weapon_to_player(player_profile)
    apply_armor_to_player(player_profile)
    player_inventory = create_inventory(player_profile)
    
    player_profile['inventory_ref'] = player_inventory

    print(f"Player: {player_name.title()} ({player_profile['hp']} HP)")

    continue_playing = True
    enemies_defeated = 0

    while continue_playing and player_profile['hp'] > 0:
        if not hub_menu(player_profile, player_inventory):
            break

        enemies = choose_enemies(enemy_data, player_profile.get('level', 1))
        
        p_init = random.randint(1, 20) + player_profile.get('proficiency_bonus', 0) + player_profile.get('initiative_boost', 0)
        # Initiative against the "first" enemy's bonus as a representative
        e_init = random.randint(1, 20) + enemies[0].get('bonus', 0) + enemies[0].get('initiative_boost', 0)
        player_first = p_init >= e_init
        
        print(f"Initiative: Player {p_init} vs Enemies {e_init}")
        result = simulate_combat(player_profile, enemies, player_goes_first=player_first)

        if result['winner'] == 'player':
            enemies_defeated += len(enemies)
            # Sum XP from all enemies in the group
            total_xp = sum([e.get('xp', 0) for e in enemies])
            player_profile['hp'] = result['player_hp']
            
            level_up_available = update_xp_and_level(player_profile, total_xp)
            
            if level_up_available:
                from core.players.leveler import get_level_up_benefits
                benefits = get_level_up_benefits(player_profile, player_profile['class'])
                add_class_level(player_profile, player_profile['class'])
                print(f"\n*** LEVEL UP! ***")
                print(f"You are now level {player_profile['level']}.")
                print(f"{benefits}")
                print(f"Max HP: {player_profile['max_hp']}\n")

            # Loot from each enemy
            for e in enemies:
                loot_msg = award_loot(player_inventory, e.get('reward', {}))
                if loot_msg:
                    print(f"Loot from {e['name']}: {loot_msg}")
            
            print(f"Current HP: {player_profile['hp']}")
            next_xp_val = xp_to_next_level(player_profile['xp'])
            print(f"You gained {total_xp} xp, you are now {next_xp_val if next_xp_val is not None else 0} xp away from next level.")
        elif result['winner'] == 'none':
            print(f"You escaped.")
            player_profile['hp'] = result['player_hp']
        else:
            print("Game Over.")
            break

if __name__ == '__main__':
    main()
