import pprint
import json
import os

# Locate JSON path in the same folder as this script
base_dir = os.path.dirname(__file__)
json_path = os.path.join(base_dir, 'player_classes.json')

with open(json_path, 'r', encoding='utf-8-sig') as f:
    classes = json.load(f)


def load_weapons():
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, 'Weapons.json')

    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

weapons_data = load_weapons()


def get_weapon_stats(weapon_name):
    weapon_key = (weapon_name or 'unarmed').lower()

    # Access weapons_list correctly (it's a flat dict of weapon names in Weapons.json)
    # Note: original code had .values() loop which might be for nested structure
    # but based on prompt, it seems it's one level deep
    
    wl = weapons_data.get('weapon_list', {})
    if weapon_key in wl:
        return wl[weapon_key]

    return wl.get('unarmed', {'die': 4, 'attack_range': 1, 'bonus': 0})

def load_armor():
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, 'armor.json')

    with open(path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)

    return data.get('armor_list', {})
    
armor_data = load_armor()

def apply_weapon_to_player(player_data, weapon_name=None):
    if not weapon_name:
        weapon_name = player_data.get('weapon', 'unarmed')

    weapon_stats = get_weapon_stats(weapon_name)

    player_data['weapon'] = weapon_name
    player_data['damage_die'] = weapon_stats.get('die')
    player_data['on_hit_effect'] = weapon_stats.get('on_hit_effect') or weapon_stats.get('condition')
    player_data['weapon_bonus'] = weapon_stats.get('bonus', 0)
    player_data['weapon_range'] = weapon_stats.get('attack_range', 1)

    return player_data


def get_armor_stats(armor_name):
    armor_name = (armor_name or 'unarmored').lower()

    if armor_name in armor_data:
        armor_entry = armor_data[armor_name]
        return {
            'name': armor_name,
            'type': armor_entry.get('type', 'none'),
            'ac': armor_entry.get('ac', 10)
        }

    # fallback to unarmored
    return {'name': 'unarmored', 'type': 'none', 'ac': 10}


def apply_armor_to_player(player_data):
    armor_item = player_data.get('armor', 'unarmored')

    if isinstance(armor_item, int):
        return player_data

    armor_stats = get_armor_stats(armor_item)

    armor_type = armor_stats['type']
    base_ac = armor_stats['ac']

    proficiency = int(player_data.get('proficiency_bonus', player_data.get('proficiency', 0)))

    # Simple AC calc: Base AC + Proficiency scaling for light/medium, or just AC for heavy/shield
    # This logic follows what was there but cleaned up.
    if armor_type == 'light':
        bonus = max(0, proficiency - 1)
    elif armor_type == 'medium':
        bonus = max(0, proficiency - 2)
    elif armor_type == 'shield':
        # Shields add to the player's current AC. 
        # In this simple model, we just treat it as part of the total.
        bonus = 0
    else:
        bonus = 0

    ac_value = base_ac + bonus

    player_data['armor_name'] = armor_stats['name']
    player_data['armor_type'] = armor_type
    player_data['armor_base'] = base_ac
    player_data['armor_bonus'] = bonus
    player_data['ac'] = ac_value

    # keep compatibility with simulator
    player_data['armor'] = ac_value

    return player_data

def choose_player_class(class_data):
    class_names = list(class_data.keys())

    while True:
        print('Available classes:')
        for i, class_name in enumerate(class_names, start=1):
            print(f"  {i}. {class_name.title()}")

        selection = input('Choose your class (name or number): ').strip().lower()

        chosen_name = None
        if selection.isdigit():
            idx = int(selection) - 1
            if 0 <= idx < len(class_names):
                chosen_name = class_names[idx]
        elif selection in class_data:
            chosen_name = selection

        if not chosen_name:
            print('Invalid class selection, please try again.')
            continue

        chosen_data = class_data[chosen_name].copy() # Copy to avoid mutating original source

        # Apply armor to show AC in stats display
        apply_armor_to_player(chosen_data)

        print('\nSelected class: ' + chosen_name.title())
        print('Class stats:')
        # Get level 1 attack count from player_classes.json
        from players.leveler import load_player_classes
        player_classes = load_player_classes()
        level1_stats = player_classes[chosen_name].get('levels', {}).get('1', {})
        level1_attack_count = level1_stats.get('attack_count', 1)
        
        print(f"  HP: {chosen_data.get('hp')}")
        print(f"  Weapon: {chosen_data.get('weapon')}")
        print(f"  Armor AC: {chosen_data.get('ac')} ({chosen_data.get('armor_name')})")
        print(f"  Level 1 Attack Count: {level1_attack_count}")

        confirm = input('Confirm this class? (y/n): ').strip().lower()
        if confirm in ('y', 'yes'):
            return chosen_name, chosen_data

        print('Returning to class selection...\n')



try:
    from players.leveler import update_xp_and_level, xp_to_next_level
except ModuleNotFoundError:
    from leveler import update_xp_and_level, xp_to_next_level


if __name__ == '__main__':
    selected_class_name, selected_class_data = choose_player_class(classes)
    selected_class_data.setdefault('xp', 0)
    selected_class_data.setdefault('level', 1)
    selected_class_data['base_hp'] = selected_class_data.get('hp', 0)
    selected_class_data['class'] = selected_class_name

    apply_weapon_to_player(selected_class_data)
    apply_armor_to_player(selected_class_data)

    print(f"You chose {selected_class_name.title()}.")
    print('Starting class details:')
    pprint.pprint(selected_class_data)

    while True:
        entry = input('\nXP gained from defeating enemy, weapon <name>, or type quit: ').strip().lower()
        if entry in ('quit', 'exit'):
            break

        if entry.startswith('weapon '):
            new_weapon = entry.split(' ', 1)[1].strip()
            apply_weapon_to_player(selected_class_data, new_weapon)
            print(f"Weapon changed to '{selected_class_data['weapon']}'.")
            print(f"Damage die: d{selected_class_data['damage_die']}, on_hit_effect: {selected_class_data['on_hit_effect']}")
            continue

        if not entry.isdigit():
            print('Please enter a valid number for XP gain.')
            continue

        xp_gain = int(entry)
        update_xp_and_level(selected_class_data, xp_gain, class_name=selected_class_name, base_hp=selected_class_data['base_hp'])

        next_xp = xp_to_next_level(selected_class_data['xp'], class_name=selected_class_name)
        print(f"Total XP: {selected_class_data['xp']}")
        print(f"Level: {selected_class_data['level']} (HP: {selected_class_data['hp']}, prof +{selected_class_data['proficiency_bonus']})")
        if next_xp is None:
            print('Max level reached.')
        else:
            print(f"XP to next level: {next_xp}")

    total_score = selected_class_data.get('xp', 0)
    print(f'\nFinal Total Score: {total_score} XP')
