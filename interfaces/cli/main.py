import json
import os
import random
import sys

# Add project root to path to allow absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.players.player import choose_player_class, classes as player_classes, apply_weapon_to_player, apply_armor_to_player
from core.players.player_inventory import create_inventory, add_gold, add_item, display_inventory, manage_inventory, award_loot
from core.players.leveler import update_xp_and_level, xp_to_next_level, get_class_stats_at_level, load_player_classes, add_class_level
from core.combat.attack_roller import attack_roll, damage_roll
from core.combat.combat_engine import CombatEngine
from core.players.shop import visit_shop

def load_enemy_data():
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, '..', '..', 'data', 'creatures', 'enemies.json')
    with open(json_path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def load_consumables():
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, '..', '..', 'data', 'players', 'consumables.json')
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f).get('consumable_list', {})
    except FileNotFoundError:
        return {}

def load_spells():
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, '..', '..', 'data', 'players', 'spells.json')
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f).get('spell_list', {})
    except FileNotFoundError:
        return {}

def get_scaled_enemy(enemy_data, player_level=1):
    enemy_names = list(enemy_data.keys())
    max_index = min(len(enemy_names) - 1, 2 + (player_level * 2))

    if max_index < 0:
        raise ValueError('Enemy data is empty')

    selected_names = enemy_names[0:max_index + 1]
    enemy_name = random.choice(selected_names)
    return enemy_name, enemy_data[enemy_name]


def choose_enemy(enemy_data, player_level=1):
    enemy_name, enemy_profile = get_scaled_enemy(enemy_data, player_level)
    print(f"You encountered {enemy_name.title()}!")
    input('Press Enter to Roll initiative!\n')
    return enemy_name, enemy_profile


def simulate_combat(player_data, enemy_data, player_goes_first=True):
    player = player_data # Reference to update HP/MP
    enemy = enemy_data.copy()

    # HP Tracking
    player_hp = int(player.get('hp', 1))
    player_max_hp = player.get('max_hp', player_hp)
    enemy_hp = int(enemy.get('hp', 1))

    # Stats (Local modifiable versions for combat)
    p_attack_count = int(player.get('attack_count', 1))
    
    player_advantage = 0 
    enemy_advantage = 0
    extra_damage_once = 0 # From poisons, etc.

    consumables_db = load_consumables()
    spells_db = load_spells()

    turn = 1
    print(f"Combat start: player hp={player_hp}, enemy hp={enemy_hp}\n")

    while player_hp > 0 and enemy_hp > 0:
        print(f"--- Turn {turn} ---")

        def player_phase():
            nonlocal enemy_hp, player_hp, player_advantage, enemy_advantage, p_attack_count, extra_damage_once
            
            action_taken = False
            while not action_taken:
                print(f"\nPLAYER TURN (HP: {player_hp}/{player_max_hp}, MP: {player.get('current_mp', 0)})")
                print("1. Attack")
                print("2. Use Item")
                print("3. Skills/Spells")
                print("4. Run")
                
                choice = input("Select an action: ").strip()
                
                if choice == '1':
                    total_damage = 0
                    for _ in range(p_attack_count):
                        res = CombatEngine.resolve_attack(player, enemy, advantage=player_advantage)
                        player_advantage = 0 # Reset
                        
                        if res['hit']:
                            dmg = res['damage']
                            if extra_damage_once > 0:
                                dmg += extra_damage_once
                                print(f"  Poison applied! +{extra_damage_once} damage.")
                                extra_damage_once = 0
                                
                            total_damage += dmg
                            print(f"Player hits for {dmg} (roll {res['roll']})")
                            
                            for effect, val in res['effects']:
                                if effect == 'player_advantage': player_advantage = val; print("  Vex: Advantage on next attack!")
                                elif effect == 'enemy_advantage': enemy_advantage = val; print("  Sap: Enemy disadvantage on next attack!")
                                elif effect == 'heal_attacker':
                                    player_hp = min(player_max_hp, player_hp + val)
                                    print(f"  Lifesteal: Healed for {val} HP!")
                                elif effect == 'msg': print(f"  {val}")
                        else:
                            print(f"Player misses (roll {res['roll']})")
                            for effect, val in res['effects']:
                                if effect == 'msg':
                                    print(f"  {val}")
                                    if "Graze" in val:
                                        total_damage += int(val.split(" ")[2]) 
                    
                    enemy_hp = max(0, enemy_hp - total_damage)
                    enemy['current_hp'] = enemy_hp 
                    print(f"Total player damage: {total_damage}. Enemy HP: {enemy_hp}")
                    action_taken = True
                    
                elif choice == '2':
                    items = player_data.get('inventory_ref', {}).get('consumable', [])
                    if not items:
                        print("You have no consumables!")
                        continue
                    
                    print("\n--- Consumables ---")
                    for i, item in enumerate(items, 1):
                        print(f"{i}. {item.replace('_', ' ').title()}")
                    print(f"{len(items) + 1}. Back")
                    
                    item_choice = input("Select an item to use: ").strip()
                    if item_choice.isdigit() and 1 <= int(item_choice) <= len(items):
                        item_key = items[int(item_choice) - 1].lower().replace(' ', '_')
                        item_data = consumables_db.get(item_key)
                        
                        if item_data:
                            res = CombatEngine.resolve_item(item_data, player)
                            print(res['msg'])
                            
                            if res['hp_gain'] > 0:
                                player_hp = min(player_max_hp, player_hp + res['hp_gain'])
                                print(f"Healed for {res['hp_gain']} HP! (Current: {player_hp}/{player_max_hp})")
                            if res['bonus_gain'] > 0:
                                player['weapon_bonus'] = player.get('weapon_bonus', 0) + res['bonus_gain']
                                print(f"Attack/Damage bonus increased by {res['bonus_gain']}!")
                            if res['attack_gain'] > 0:
                                p_attack_count += res['attack_gain']
                                print(f"Attack count increased by {res['attack_gain']}!")
                            if res['extra_damage'] > 0:
                                extra_damage_once += res['extra_damage']
                                print(f"Next hit will deal +{res['extra_damage']} damage!")
                            
                            items.pop(int(item_choice) - 1)
                            action_taken = True
                        else:
                            print("That item doesn't seem to work here.")
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
                        
                        spell_data = spells_db.get(ability_key)
                        if spell_data:
                            mana_cost = spell_data.get('level', 0)
                            current_mp = player.get('current_mp', 0)
                            
                            if current_mp < mana_cost:
                                print(f"Not enough mana! (Need {mana_cost}, have {current_mp})")
                                continue

                            res = CombatEngine.resolve_spell(spell_data, player, enemy)
                            print(res['msg'])
                            player['current_mp'] = current_mp - res['mana_cost']
                            
                            if res['damage'] > 0:
                                enemy_hp = max(0, enemy_hp - res['damage'])
                                enemy['current_hp'] = enemy_hp
                                print(f"Spell dealt {res['damage']} damage to enemy!")
                            
                            if res['healing'] > 0:
                                player_hp = min(player_max_hp, player_hp + res['healing'])
                                print(f"Spell healed you for {res['healing']} HP!")
                                
                            for effect, val in res['effects']:
                                if effect == 'enemy_advantage':
                                    enemy_advantage = val
                                    print("Enemy is stunned/disadvantaged!")
                                
                            action_taken = True
                        else:
                            print(f"You used {ability_name.title()}! (No mechanical effect defined)")
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
            nonlocal player_hp, enemy_hp, player_advantage, enemy_advantage
            total_damage = 0
            e_attack_count = int(enemy.get('attack_count', 1))

            for _ in range(e_attack_count):
                res = CombatEngine.resolve_attack(enemy, player, advantage=enemy_advantage)
                enemy_advantage = 0 
                
                if res['hit']:
                    dmg = res['damage']
                    total_damage += dmg
                    print(f"Enemy hits for {dmg} (roll {res['roll']})")
                    
                    for effect, val in res['effects']:
                        if effect == 'player_advantage': player_advantage = val; print("  Enemy Vex: Enemy gains advantage!")
                        elif effect == 'enemy_advantage': enemy_advantage = val; print("  Enemy Sap: Player disadvantage!")
                        elif effect == 'msg': print(f"  {val}")
                else:
                    print(f"Enemy misses (roll {res['roll']})")
                    for effect, val in res['effects']:
                        if effect == 'msg':
                            print(f"  {val}")
                            if "Graze" in val:
                                total_damage += int(val.split(" ")[2])

            player_hp = max(0, player_hp - total_damage)
            print(f"Total enemy damage: {total_damage}. Player HP: {player_hp}\n")

        if player_goes_first:
            res = player_phase()
            if res == "ran": return {'winner': 'none', 'player_hp': player_hp, 'turns': turn}
            if enemy_hp <= 0: break
            input('Next phase...')
            enemy_phase()
        else:
            enemy_phase()
            if player_hp <= 0: break
            input('Next phase...')
            res = player_phase()
            if res == "ran": return {'winner': 'none', 'player_hp': player_hp, 'turns': turn}

        if player_hp <= 0 or enemy_hp <= 0: break
        input('Next turn...')
        turn += 1

    winner = 'player' if player_hp > 0 else 'enemy'
    print(f"Combat ends: {winner.upper()} wins")
    player['hp'] = player_hp 
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

        enemy_name, enemy_profile = choose_enemy(enemy_data, player_profile.get('level', 1))
        
        p_init = random.randint(1, 20) + player_profile.get('proficiency_bonus', 0)
        e_init = random.randint(1, 20) + enemy_profile.get('bonus', 0)
        player_first = p_init >= e_init
        
        print(f"Initiative: Player {p_init} vs Enemy {e_init}")
        result = simulate_combat(player_profile, enemy_profile, player_goes_first=player_first)

        if result['winner'] == 'player':
            enemies_defeated += 1
            xp = enemy_profile.get('xp', 0)
            player_profile['hp'] = result['player_hp']
            
            level_up_available = update_xp_and_level(player_profile, xp)
            
            if level_up_available:
                add_class_level(player_profile, player_profile['class'])
                print(f"LEVEL UP! You are now level {player_profile['level']}. Max HP increased to {player_profile['max_hp']}.")

            loot_msg = award_loot(player_inventory, enemy_profile.get('reward', {}))
            if loot_msg:
                print(loot_msg)
            
            print(f"You defeated {enemy_name}! Current HP: {player_profile['hp']}")
            next_xp_val = xp_to_next_level(player_profile['xp'])
            print(f"You gained {xp} xp, you are now {next_xp_val if next_xp_val is not None else 0} xp away from next level.")
        elif result['winner'] == 'none':
            print(f"You escaped from {enemy_name}.")
            player_profile['hp'] = result['player_hp']
        else:
            print(f"Game Over. Final Score: {player_profile['xp'] + enemies_defeated}")
            break

    final_score = player_profile['xp'] + enemies_defeated
    print(f"Final Score: {final_score} (XP: {player_profile['xp']}, Defeated: {enemies_defeated})")

if __name__ == '__main__':
    main()
