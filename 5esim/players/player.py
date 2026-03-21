import pprint
import json
import os

try:
    from players import Weapons
    from players import armor as armor_module
except ModuleNotFoundError:
    import Weapons
    import armor as armor_module

# Locate JSON path in the same folder as this script
base_dir = os.path.dirname(__file__)
json_path = os.path.join(base_dir, 'player_classes.json')

with open(json_path, 'r', encoding='utf-8') as f:
    classes = json.load(f)


def get_weapon_stats(weapon_name):
    weapon_key = (weapon_name or 'unarmed').lower()
    weapon_data = Weapons.weapons_list.get(weapon_key)

    if not weapon_data:
        # fallback for undefined weapons, keep the player operational
        weapon_data = Weapons.weapons_list.get('unarmed', {
            'die': 4,
            'on_hit_effect': 'swift',
            'bonus': 0,
            'attack_range': 1,
        })

    return weapon_data


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

    # find armor in armor categories
    for category, entries in armor_module.armor_dict.items():
        if armor_name in entries:
            armor_entry = entries[armor_name]
            base_ac = armor_entry.get('armor') if 'armor' in armor_entry else armor_entry.get('ac', 10)
            return category, armor_name, int(base_ac)

    # fallback to unarmored light
    unarmored = armor_module.armor_dict['light_armor']['unarmored']
    return 'light_armor', 'unarmored', int(unarmored['armor'])


def apply_armor_to_player(player_data):
    armor_item = player_data.get('armor', 'unarmored')
    
    # If armor is already an integer (already processed), just return
    if isinstance(armor_item, int):
        return player_data
    
    category, armor_name, base_ac = get_armor_stats(armor_item)

    proficiency = int(player_data.get('proficiency', 0))
    if category == 'light_armor':
        bonus = proficiency - 1
    elif category == 'medium_armor':
        bonus = proficiency - 2
    else:
        bonus = 0

    ac_value = max(0, base_ac + bonus)

    player_data['armor_category'] = category
    player_data['armor_name'] = armor_name
    player_data['armor_base'] = base_ac
    player_data['armor_bonus'] = bonus
    player_data['ac'] = ac_value
    # keep compatibility with existing simulator expectations
    player_data['armor'] = ac_value

    return player_data


def apply_monk_rules(player_data):
    """Apply monk-specific rules"""
    player_class = player_data.get('class', '').lower()
    if player_class != 'monk':
        return player_data

    weapon = player_data.get('weapon', '').lower()
    is_unarmed = weapon in ('unarmed', 'unarmored')

    # Rule 1: Increase attack_count by 1 when weapon is unarmed (fist or unarmed)
    if is_unarmed:
        # Store the base attack_count the first time (from class definition)
        if 'base_attack_count' not in player_data:
            player_data['base_attack_count'] = int(player_data.get('attack_count', 1))
        
        # Always apply the bonus based on the base value, making this idempotent
        player_data['attack_count'] = player_data['base_attack_count'] + 1

    # Rule 2: Damage die scaling at levels 4, 8, 12, 16 (ONLY for unarmed)
    if is_unarmed:
        level = int(player_data.get('level', 1))
        base_die = 4  # monk martial arts starts at d4

        # Calculate how many times to scale (every 4 levels starting at level 4)
        scale_count = 0
        if level >= 4:
            scale_count = (level - 1) // 4

        scaled_die = base_die + (2 * scale_count)
        player_data['damage_die'] = scaled_die

    # Rule 3: Unarmored monks get 2*proficiency added to AC
    armor_name = player_data.get('armor_name', 'unarmored').lower()
    if armor_name == 'unarmored':
        proficiency = int(player_data.get('proficiency', 0))
        monks_bonus = 2 * proficiency
        player_data['ac'] = 10 + monks_bonus
        player_data['unarmored_ac_bonus'] = monks_bonus

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

        chosen_data = class_data[chosen_name]

        # Apply armor to show AC in stats display
        apply_armor_to_player(chosen_data)

        print('\nSelected class: ' + chosen_name.title())
        print('Class stats:')
        # Get level 1 attack count from player_classes.json
        from players.leveler import load_player_classes
        player_classes = load_player_classes()
        level1_attack_count = player_classes[chosen_name].get('levels', {}).get('1', {}).get('attack_count', 1)
        print(f"  HP: {chosen_data.get('hp')}")
        print(f"  Weapon: {chosen_data.get('weapon')}")
        print(f"  Armor: {chosen_data.get('armor')}")
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