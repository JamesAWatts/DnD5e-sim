import pprint
import json
import os
from core.game_rules.path_utils import get_resource_path

from core.game_rules.database_manager import db

# Use cached data from DatabaseManager
classes = db.get_classes()
weapons_data = db.get_weapons()
armor_data = db.get_armor()
shields_data = db.get_shields()
trinkets_data = db.get_trinkets()

def load_weapons():
    return db.get_weapons()

def get_weapon_stats(weapon_name):
    weapon_key = (weapon_name or 'unarmed').lower()
    wl = db.get_weapons() # Direct access to cache
    if weapon_key in wl:
        return wl[weapon_key]
    return wl.get('unarmed', {'die': 4, 'attack_range': 1, 'bonus': 0})

def load_armor():
    return db.get_armor()
    
def load_shields():
    return db.get_shields()

def load_trinkets():
    return db.get_trinkets()

def load_consumables():
    return db.get_consumables()

def load_spells():
    return db.get_spells()

def load_skills():
    return db.get_skills()

def load_summons():
    return db.get_summons()

def apply_weapon_to_player(player_data, weapon_name=None):
    if not weapon_name:
        weapon_name = player_data.get('weapon', 'unarmed')

    weapon_stats = get_weapon_stats(weapon_name)
    
    # Class die is set in recalculate_stats (from leveler.py)
    class_die = player_data.get('damage_die', 0)
    weapon_die = weapon_stats.get('die', 4)

    player_data['weapon'] = weapon_name
    
    # Helper to get numeric comparison value for a die
    def get_die_comp(d):
        if isinstance(d, int): return d
        if isinstance(d, str):
            import re
            match = re.search(r'd(\d+)', d)
            if match: return int(match.group(1))
            try: return int(d)
            except: return 0
        return 0

    # Monk Override: Unarmed or Simple weapons use class die if better
    if player_data.get('class') == 'monk':
        w_class = weapon_stats.get('weapon_class', 'simple')
        if weapon_name == 'unarmed' or w_class == 'simple':
            if get_die_comp(class_die) > get_die_comp(weapon_die):
                player_data['damage_die'] = class_die
            else:
                player_data['damage_die'] = weapon_die
        else:
            player_data['damage_die'] = weapon_die
    else:
        player_data['damage_die'] = weapon_die
    
    # Base on-hit effect from weapon stats
    player_data['on_hit_effect'] = weapon_stats.get('on_hit_effect') or weapon_stats.get('condition')
    player_data['dot'] = weapon_stats.get('dot', False)
    player_data['dot_dice'] = weapon_stats.get('dot_dice', 0)
    player_data['duration'] = weapon_stats.get('duration', 0)
    
    player_data['weapon_bonus'] = int(weapon_stats.get('bonus', 0))
    player_data['weapon_range'] = int(weapon_stats.get('attack_range', 1))
    player_data['weapon_type'] = weapon_stats.get('type', 'melee')
    
    # Critical hit logic
    crit_range_base = int(weapon_stats.get('critical', 20))
    player_data['critical'] = crit_range_base
    
    # Numerical bonus system (crit+ tag)
    # Start with weapon's bonus, but let armor/trinkets add to it in apply_armor_to_player
    player_data['crit_bonus'] = int(weapon_stats.get('crit+', 0))
    
    # Backward compatibility for existing 'critical' flag in JSON
    if crit_range_base <= 18: player_data['crit_bonus'] = max(player_data['crit_bonus'], 2)
    elif crit_range_base <= 19: player_data['crit_bonus'] = max(player_data['crit_bonus'], 1)

    # Legcy Flags
    player_data['crit_on_19'] = (player_data['crit_bonus'] >= 1)
    player_data['crit_on_18'] = (player_data['crit_bonus'] >= 2)

    # Spell DC bonus
    player_data['spell_save'] = int(weapon_stats.get('spell_save', 0))

    return player_data


def validate_player_data(player_data):
    """
    Ensures all player stats are correctly calculated based on class, level, and equipment.
    Call this whenever player data might be inconsistent or when entering the Hub.
    """
    from .leveler import recalculate_stats
    
    # 1. Recalculate base stats from class levels (MP, SP, Skills, Spells, etc.)
    recalculate_stats(player_data)
    
    # 2. Apply current weapon (Bonuses, Ranges, Enchantments)
    apply_weapon_to_player(player_data)
    
    # 3. Apply armor, shields, and trinkets (AC, HP/MP/SP bonuses, Spell DC)
    apply_armor_to_player(player_data)
    
    return player_data

def get_armor_stats(armor_name):
    armor_name = (armor_name or 'unarmored').lower().replace(' ', '_')
    if armor_name in armor_data:
        return armor_data[armor_name]
    alt_name = armor_name.replace('_', ' ')
    if alt_name in armor_data:
        return armor_data[alt_name]
    return {'name': 'unarmored', 'type': 'none', 'ac': 10}

def get_shield_stats(shield_name):
    shield_key = (shield_name or 'none').lower().replace(' ', '_')
    if shield_key in shields_data:
        return shields_data[shield_key]
    return shields_data.get('none', {'ac': 0})

def get_trinket_stats(trinket_name):
    trinket_key = (trinket_name or 'none').lower().replace(' ', '_')
    if trinket_key in trinkets_data:
        return trinkets_data[trinket_key]
    return trinkets_data.get('none', {'bonus_ac': 0, 'bonus_hp': 0})

def can_equip_weapon(player_data, weapon_name):
    """
    Checks if the player's class is proficient with the given weapon.
    """
    weapon_stats = get_weapon_stats(weapon_name)
    weapon_class = weapon_stats.get('weapon_class', 'simple')
    
    class_name = player_data.get('class', 'fighter')
    
    from .leveler import load_player_classes
    classes_data = load_player_classes()
    class_info = classes_data.get(class_name, {})
    
    # All classes get simple proficiency if not explicitly defined otherwise,
    # but we added it to all in player_classes.json
    proficiencies = class_info.get('weapon_proficiencies', ['simple'])

    # Fallback for cleric if missing
    if class_name == 'cleric' and 'caster' not in proficiencies:
        proficiencies.append('caster')

    return weapon_class in proficiencies
def can_equip_armor(player_data, armor_name):
    """
    Checks if the player's class is proficient with the given armor.
    """
    armor_stats = get_armor_stats(armor_name)
    armor_type = armor_stats.get('type', 'none')
    
    # All classes can use shields, and Shields are now separate, but checking just in case
    if armor_type == 'shield':
        return True
        
    class_name = player_data.get('class', 'fighter')
    
    from .leveler import load_player_classes
    classes_data = load_player_classes()
    class_info = classes_data.get(class_name, {})
    
    proficiencies = class_info.get('armor_proficiencies', ['none'])
    return armor_type in proficiencies

def get_weapon_display_name(player, weapon_name):
    """
    Returns the formatted name of a weapon.
    """
    if not weapon_name or weapon_name == 'none':
        return "None"
        
    weapon_stats = get_weapon_stats(weapon_name)
    return weapon_stats.get('name', weapon_name.replace('_', ' ').title())

def get_armor_display_name(player, armor_name):
    """
    Returns the formatted name of armor.
    """
    if not armor_name or armor_name == 'none':
        return "None"
    return armor_name.replace('_', ' ').title()

def apply_armor_to_player(player_data):
    # Recalculate AC and Buffs based on ALL equipment
    armor_name = player_data.get('armor', 'unarmored')
    shield_name = player_data.get('shield', 'none')
    trinket_name = player_data.get('trinket', 'none')

    armor_stats = get_armor_stats(armor_name)
    shield_stats = get_shield_stats(shield_name)
    trinket_stats = get_trinket_stats(trinket_name)

    armor_type = armor_stats.get('type', 'none')
    base_ac = armor_stats.get('ac', 10)
    shield_ac = shield_stats.get('ac', 0)
    trinket_ac = trinket_stats.get('bonus_ac', 0)

    proficiency = int(player_data.get('proficiency_bonus', 0))

    bonus = 0
    if armor_type == 'light':
        bonus = max(0, proficiency - 1)
    elif armor_type == 'medium':
        bonus = max(0, proficiency - 2)
    
    player_data['ac'] = base_ac + bonus + shield_ac + trinket_ac
    player_data['armor_base'] = base_ac
    player_data['armor_bonus'] = bonus
    player_data['shield_bonus'] = shield_ac
    player_data['trinket_ac_bonus'] = trinket_ac
    
    # 1. Capture OLD max stats to calculate differences
    old_max_hp = player_data.get('max_hp', 10)
    old_max_mp = player_data.get('max_mp', 0)
    old_max_sp = player_data.get('max_sp', 0)

    # 2. Get true BASE stats from class levels (set by recalculate_stats)
    base_hp = player_data.get('max_hp_base', 10)
    base_mp = player_data.get('max_mp_base', 0)
    base_sp = player_data.get('max_sp_base', 0)
    
    # 3. Calculate NEW max stats with equipment bonuses
    eq_hp = armor_stats.get('bonus_hp', 0) + shield_stats.get('bonus_hp', 0) + trinket_stats.get('bonus_hp', 0)
    eq_mp = armor_stats.get('bonus_mp', 0) + shield_stats.get('bonus_mp', 0) + trinket_stats.get('bonus_mp', 0)
    eq_sp = armor_stats.get('bonus_sp', 0) + shield_stats.get('bonus_sp', 0) + trinket_stats.get('bonus_sp', 0)
    
    new_max_hp = base_hp + eq_hp
    new_max_mp = base_mp + eq_mp
    new_max_sp = base_sp + eq_sp

    # 4. Apply NEW max stats
    player_data['max_hp'] = new_max_hp
    player_data['max_mp'] = new_max_mp
    player_data['max_sp'] = new_max_sp

    # 5. Adjust CURRENT values by the change in max (prevents "healing" but keeps relative health)
    if 'current_hp' not in player_data:
        player_data['current_hp'] = new_max_hp
        player_data['hp'] = new_max_hp
    else:
        hp_diff = new_max_hp - old_max_hp
        if hp_diff > 0:
            player_data['current_hp'] += hp_diff
        player_data['hp'] = player_data['current_hp']
        
    if 'current_mp' not in player_data or (old_max_mp == 0 and new_max_mp > 0):
        player_data['current_mp'] = new_max_mp
    else:
        mp_diff = new_max_mp - old_max_mp
        if mp_diff > 0:
            player_data['current_mp'] += mp_diff

    if 'current_sp' not in player_data or (old_max_sp == 0 and new_max_sp > 0):
        player_data['current_sp'] = new_max_sp
    else:
        sp_diff = new_max_sp - old_max_sp
        if sp_diff > 0:
            player_data['current_sp'] += sp_diff

    # Clamping
    player_data['hp'] = min(player_data.get('hp', player_data['max_hp']), player_data['max_hp'])
    player_data['current_hp'] = player_data['hp']
    player_data['current_mp'] = min(player_data.get('current_mp', 0), player_data['max_mp'])
    player_data['current_sp'] = min(player_data.get('current_sp', 0), player_data['max_sp'])

    # Bonuses
    eq_atk = armor_stats.get('bonus_atk', 0) + shield_stats.get('bonus_atk', 0) + trinket_stats.get('bonus_atk', 0)
    eq_dmg = armor_stats.get('bonus_dmg', 0) + shield_stats.get('bonus_dmg', 0) + trinket_stats.get('bonus_dmg', 0)
    
    # Crit Bonus aggregation
    eq_crit = int(armor_stats.get('crit+', 0)) + int(shield_stats.get('crit+', 0)) + int(trinket_stats.get('crit+', 0))
    player_data['crit_bonus'] = player_data.get('crit_bonus', 0) + eq_crit
    
    # Update legacy flags based on FINAL aggregated bonus
    player_data['crit_on_19'] = (player_data['crit_bonus'] >= 1)
    player_data['crit_on_18'] = (player_data['crit_bonus'] >= 2)

    # Include base weapon spell_save bonus
    weapon_name = player_data.get('weapon', 'unarmed')
    weapon_stats = get_weapon_stats(weapon_name)
    weapon_spell_save = weapon_stats.get('spell_save', 0)
    
    eq_spell_save = armor_stats.get('spell_save', 0) + shield_stats.get('spell_save', 0) + trinket_stats.get('spell_save', 0) + weapon_spell_save
    eq_spell_resist = armor_stats.get('spell_resist', 0) + shield_stats.get('spell_resist', 0) + trinket_stats.get('spell_resist', 0)
    
    player_data['equipment_atk_bonus'] = eq_atk
    player_data['equipment_dmg_bonus'] = eq_dmg
    player_data['damage_resist'] = armor_stats.get('damage_resist', 0) + shield_stats.get('damage_resist', 0) + trinket_stats.get('damage_resist', 0)
    player_data['initiative_boost'] = armor_stats.get('initiative_boost', 0) + shield_stats.get('initiative_boost', 0) + trinket_stats.get('initiative_boost', 0)
        
    player_data['spell_save'] = eq_spell_save
    player_data['spell_resist'] = eq_spell_resist
    
    # Crit Immunity (e.g. from Adamantite Armor)
    player_data['crit_immune'] = armor_stats.get('crit_immune', False) or shield_stats.get('crit_immune', False) or trinket_stats.get('crit_immune', False)

    return player_data

def apply_shield_to_player(player_data, shield_name=None):
    if shield_name:
        player_data['shield'] = shield_name
    return apply_armor_to_player(player_data)

def apply_trinket_to_player(player_data, trinket_name=None):
    if trinket_name:
        player_data['trinket'] = trinket_name
    return apply_armor_to_player(player_data)

def apply_consumable_effect(player, item_res):
    """
    Applies the results of a consumable item (from CombatEngine.resolve_item) to a player.
    """
    if item_res.get('hp_gain', 0) > 0:
        max_hp = player.get('max_hp_combat', player.get('max_hp', 10))
        player['current_hp'] = min(max_hp, player.get('current_hp', 0) + item_res['hp_gain'])
        player['hp'] = player['current_hp']
        
    if item_res.get('mana_gain', 0) > 0:
        max_mp = player.get('max_mp', 0)
        player['current_mp'] = min(max_mp, player.get('current_mp', 0) + item_res['mana_gain'])
        
    if item_res.get('stamina_gain', 0) > 0:
        max_sp = player.get('max_sp', 0)
        player['current_sp'] = min(max_sp, player.get('current_sp', 0) + item_res['stamina_gain'])
        
    if item_res.get('bonus_gain', 0) > 0:
        # Buffs like Grind Stone
        player['weapon_bonus'] = player.get('weapon_bonus', 0) + item_res['bonus_gain']
        
    if item_res.get('attack_gain', 0) > 0:
        # Extra attacks (temporary)
        player['attack_count'] = player.get('attack_count', 1) + item_res['attack_gain']

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

        chosen_data = class_data[chosen_name].copy() 
        chosen_data['class'] = chosen_name
        chosen_data.setdefault('shield', 'none')
        chosen_data.setdefault('trinket', 'none')

        apply_armor_to_player(chosen_data)

        print('\nSelected class: ' + chosen_name.title())
        print('Class stats:')
        from .leveler import load_player_classes
        player_classes = load_player_classes()
        level1_stats = player_classes[chosen_name].get('levels', {}).get('1', {})
        level1_attack_count = level1_stats.get('attack_count', 1)
        
        print(f"  HP: {chosen_data.get('hp')}")
        print(f"  Weapon: {chosen_data.get('weapon')}")
        print(f"  Armor AC: {chosen_data.get('ac')}")
        print(f"  Level 1 Attack Count: {level1_attack_count}")

        confirm = input('Confirm this class? (y/n): ').strip().lower()
        if confirm in ('y', 'yes'):
            return chosen_name, chosen_data

        print('Returning to class selection...\n')


try:
    from .leveler import update_xp_and_level, xp_to_next_level
except (ImportError, ValueError):
    from leveler import update_xp_and_level, xp_to_next_level


if __name__ == '__main__':
    selected_class_name, selected_class_data = choose_player_class(classes)
    selected_class_data.setdefault('xp', 0)
    selected_class_data.setdefault('level', 1)
    selected_class_data['base_hp'] = selected_class_data.get('hp', 0)
    selected_class_data['class'] = selected_class_name
    selected_class_data.setdefault('shield', 'none')
    selected_class_data.setdefault('trinket', 'none')

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
            continue

        if not entry.isdigit():
            print('Please enter a valid number for XP gain.')
            continue

        xp_gain = int(entry)
        update_xp_and_level(selected_class_data, xp_gain)

        next_xp = xp_to_next_level(selected_class_data['xp'])
        print(f"Total XP: {selected_class_data['xp']}")
        print(f"Level: {selected_class_data['level']} (HP: {selected_class_data['hp']}, AC: {selected_class_data['ac']})")
        if next_xp is None:
            print('Max level reached.')
        else:
            print(f"XP to next level: {next_xp}")
