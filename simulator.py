import json
import os
import random

from players.player import choose_player_class, classes as player_classes, apply_weapon_to_player, apply_armor_to_player
from players.player_inventory import create_inventory, award_loot, display_inventory, manage_inventory
from players.leveler import update_xp_and_level, xp_to_next_level, get_class_stats_at_level, load_player_classes
from combat.attack_roller import attack_roll, damage_roll
from players.shop import visit_shop


def load_enemy_data():
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, 'creatures', 'enemies.json')
    with open(json_path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def load_consumables():
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, 'players', 'consumables.json')
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f).get('consumable_list', {})
    except FileNotFoundError:
        return {}

def load_spells():
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, 'players', 'spells.json')
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f).get('spell_list', {})
    except FileNotFoundError:
        return {}

def get_scaled_enemy(enemy_data, player_level=1):
    enemy_names = list(enemy_data.keys())
    # Dynamic scaling: player level determines how deep into the list we can pull from.
    # Level 1: index 0-3
    # Level 5: index 0-10
    # Level 10+: Full list
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
    player = player_data.copy()
    enemy = enemy_data.copy()

    # HP Tracking
    player_hp = int(player.get('hp', 1))
    player_max_hp = player.get('max_hp', player_hp)
    enemy_hp = int(enemy.get('hp', 1))

    # Stats (Local modifiable versions for combat)
    p_attack_count = int(player.get('attack_count', 1))
    p_bonus = int(player.get('proficiency_bonus', 0)) + int(player.get('weapon_bonus', 0))
    p_die = int(player.get('damage_die', player.get('die', 8)))
    
    # Robust Armor Handling
    p_armor_val = player.get('ac', player.get('armor', 10))
    try:
        player_armor = int(p_armor_val)
    except (ValueError, TypeError):
        player_armor = 10

    e_attack_count = int(enemy.get('attack_count', 1))
    e_die = int(enemy.get('die', 6))
    e_bonus = int(enemy.get('bonus', 0))
    e_armor_val = enemy.get('armor', 10)
    try:
        enemy_armor = int(e_armor_val)
    except (ValueError, TypeError):
        enemy_armor = 10

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
            nonlocal enemy_hp, player_hp, player_advantage, enemy_advantage, p_bonus, p_attack_count, extra_damage_once
            
            action_taken = False
            while not action_taken:
                print(f"\nPLAYER TURN (HP: {player_hp}/{player_max_hp})")
                print("1. Attack")
                print("2. Use Item")
                print("3. Skills/Spells")
                print("4. Run")
                
                choice = input("Select an action: ").strip()
                
                if choice == '1':
                    total_damage = 0
                    on_hit = player.get('on_hit_effect', '').lower()
                    for _ in range(p_attack_count):
                        attack = attack_roll(p_bonus, enemy_armor, advantage=player_advantage)
                        player_advantage = 0 # Reset
                        
                        if attack['hit']:
                            dmg = damage_roll(p_die, p_bonus, attack['critical'], player_data=player)
                            # Apply temporary extra damage
                            if extra_damage_once > 0:
                                dmg += extra_damage_once
                                print(f"  Poison applied! +{extra_damage_once} damage.")
                                extra_damage_once = 0
                                
                            total_damage += dmg
                            print(f"Player hits for {dmg} (roll {attack['roll']})")
                            
                            if on_hit == 'vex':
                                player_advantage = 1
                                print("  Vex: Advantage on next attack!")
                            elif on_hit == 'sap':
                                enemy_advantage = -1
                                print("  Sap: Enemy disadvantage on next attack!")
                            elif on_hit == 'lifesteal':
                                heal = max(1, dmg // 2)
                                player_hp = min(player_max_hp, player_hp + heal)
                                print(f"  Lifesteal: Healed for {heal} HP!")
                            elif on_hit == 'slow':
                                print("  Slow: Enemy's speed reduced!")
                            elif on_hit == 'push':
                                print("  Push: Enemy shoved back!")
                        else:
                            print(f"Player misses (roll {attack['roll']})")
                            if on_hit == 'graze':
                                total_damage += p_bonus
                                print(f"  Graze: Dealt {p_bonus} damage on miss!")
                    
                    enemy_hp = max(0, enemy_hp - total_damage)
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
                            etype = item_data['effect_type']
                            val = item_data['value']
                            print(f"Using {item_data['name']}...")
                            
                            if etype == 'heal':
                                player_hp = min(player_max_hp, player_hp + val)
                                print(f"Healed for {val} HP! (Current: {player_hp}/{player_max_hp})")
                            elif etype == 'buff_bonus':
                                p_bonus += val
                                print(f"Attack/Damage bonus increased by {val}!")
                            elif etype == 'buff_attacks':
                                p_attack_count += val
                                print(f"Attack count increased by {val}!")
                            elif etype == 'extra_damage':
                                extra_damage_once += val
                                print(f"Next hit will deal +{val} damage!")
                            
                            items.pop(int(item_choice) - 1)
                            action_taken = True
                        else:
                            print("That item doesn't seem to work here.")
                    else:
                        continue

                elif choice == '3':
                    # Load skills and spells from profile
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
                        
                        # Check spells DB
                        spell_data = spells_db.get(ability_key)
                        if spell_data:
                            mana_cost = spell_data.get('level', 0)
                            current_mp = player.get('current_mp', 0)
                            
                            if current_mp < mana_cost:
                                print(f"Not enough mana! (Need {mana_cost}, have {current_mp})")
                                continue

                            print(f"\nCasting {spell_data['name']}!")
                            player['current_mp'] = current_mp - mana_cost
                            print(f"Description: {spell_data['description']} ({mana_cost} MP used)")
                            
                            # Basic mechanical implementation for some spell types
                            if 'damage' in spell_data:
                                # Simple damage calculation (e.g. "8d6")
                                dmg_str = spell_data['damage']
                                if 'd' in dmg_str:
                                    num, die = dmg_str.split('d')
                                    bonus_dmg = 0
                                    if '+' in die:
                                        die, bonus_dmg = die.split('+')
                                        bonus_dmg = int(bonus_dmg)
                                    dmg = sum(random.randint(1, int(die)) for _ in range(int(num))) + bonus_dmg
                                else:
                                    dmg = int(dmg_str)
                                
                                enemy_hp = max(0, enemy_hp - dmg)
                                print(f"Spell dealt {dmg} damage to enemy!")
                            
                            if 'healing' in spell_data:
                                heal_str = spell_data['healing']
                                if 'd' in heal_str:
                                    num, die = heal_str.split('d')
                                    bonus_heal = 0
                                    if '+' in die:
                                        die, bonus_heal = die.split('+')
                                        bonus_heal = int(bonus_heal)
                                    heal = sum(random.randint(1, int(die)) for _ in range(int(num))) + bonus_heal
                                else:
                                    heal = int(heal_str)
                                
                                player_hp = min(player_max_hp, player_hp + heal)
                                print(f"Spell healed you for {heal} HP!")
                                
                            if spell_data.get('effect') == 'stunned':
                                enemy_advantage = -1 # Simplified
                                print("Enemy is stunned/disadvantaged!")
                                
                            action_taken = True
                        else:
                            print(f"You used {ability_name.title()}! (Mechanical effect not fully defined in spells.json)")
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
            on_hit = enemy.get('on_hit_effect', '').lower()

            for _ in range(e_attack_count):
                attack = attack_roll(e_bonus, player_armor, advantage=enemy_advantage)
                enemy_advantage = 0 # Reset
                
                if attack['hit']:
                    dmg = damage_roll(e_die, e_bonus, attack['critical'], player_data=enemy)
                    total_damage += dmg
                    print(f"Enemy hits for {dmg} (roll {attack['roll']})")
                    
                    if on_hit == 'vex':
                        enemy_advantage = 1
                        print("  Vex: Enemy gains advantage!")
                    elif on_hit == 'sap':
                        player_advantage = -1
                        print("  Sap: Player disadvantage!")
                else:
                    print(f"Enemy misses (roll {attack['roll']})")
                    if on_hit == 'graze':
                        total_damage += e_bonus
                        print(f"  Graze: Enemy deals {e_bonus} on miss!")

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
    return {'winner': winner, 'player_hp': player_hp, 'turns': turn}


def hub_menu(player_profile, player_inventory):
    while True:
        print("\n--- ADVENTURE HUB ---")
        print(f"Level {player_profile['level']} {player_profile['class'].title()}")
        print(f"HP: {player_profile['hp']} / {player_profile.get('max_hp', player_profile['hp'])}")
        print(f"Gold: {player_inventory['gold']}")
        
        # Scaling rest cost
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
    
    # Initialize rest count
    player_profile['rest_count'] = 0

    player_classes_data = load_player_classes()
    level1_stats = get_class_stats_at_level(player_name, 1, player_classes_data)
    for k, v in level1_stats.items(): player_profile[k] = v

    apply_weapon_to_player(player_profile)
    apply_armor_to_player(player_profile)
    player_inventory = create_inventory(player_profile)
    
    # Give simulator access to inventory for combat items
    player_profile['inventory_ref'] = player_inventory

    print(f"Player: {player_name.title()} ({player_profile['hp']} HP)")

    continue_playing = True
    enemies_defeated = 0

    while continue_playing and player_profile['hp'] > 0:
        # Before combat, enter the Hub
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
            
            # Update HP in profile to match combat result
            player_profile['hp'] = result['player_hp']
            
            old_level = player_profile['level']
            # New update_xp_and_level returns bool and doesn't apply level up automatically
            level_up_available = update_xp_and_level(player_profile, xp)
            
            if level_up_available:
                # For CLI simulator, we just automatically level up the same class for now
                # to keep it simple, or we could ask. Let's just do same class.
                from players.leveler import add_class_level
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
