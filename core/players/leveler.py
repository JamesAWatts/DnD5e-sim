import json
import os

def load_player_classes(path=None):
    """Load player class definitions."""
    base_dir = os.path.dirname(__file__)
    if path is None:
        path = os.path.join(base_dir, '..', '..', 'data', 'players', 'player_classes.json')
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def load_xp_table():
    """Load unified XP table."""
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, '..', '..', 'data', 'players', 'xp_table.json')
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def get_total_level_for_xp(total_xp):
    """Determine total character level from XP."""
    xp_table = load_xp_table()
    current_level = 1
    for lvl in range(1, 21):
        lvl_str = str(lvl)
        if lvl_str in xp_table:
            if total_xp >= xp_table[lvl_str]:
                current_level = lvl
            else:
                break
    return current_level

def get_class_stats_at_level(class_name, level, player_classes=None):
    """
    Get class stats at a specific level, merging base stats with level-specific overrides.
    """
    if player_classes is None:
        player_classes = load_player_classes()
    
    class_name = class_name.lower()
    if class_name not in player_classes:
        return {}
    
    class_def = player_classes[class_name]
    stats = {k: v for k, v in class_def.items() if k != 'levels'}
    
    for k, v in stats.items():
        if isinstance(v, list):
            stats[k] = list(v)

    levels_def = class_def.get('levels', {})
    for lvl in range(1, level + 1):
        lvl_str = str(lvl)
        if lvl_str in levels_def:
            level_data = levels_def[lvl_str]
            for key, value in level_data.items():
                if isinstance(value, list):
                    if key not in stats:
                        stats[key] = []
                    stats[key].extend([item for item in value if item not in stats[key]])
                else:
                    stats[key] = value
    return stats

def xp_to_next_level(total_xp):
    """Calculate XP needed for next character level."""
    xp_table = load_xp_table()
    current_level = get_total_level_for_xp(total_xp)
    next_level = current_level + 1
    if str(next_level) in xp_table:
        return xp_table[str(next_level)] - total_xp
    return None

def recalculate_stats(player_data):
    """
    Recalculate all stats based on class levels.
    player_data['class_levels'] = {"fighter": 2, "rogue": 1}
    """
    class_defs = load_player_classes()
    class_levels = player_data.get('class_levels', {})
    total_level = sum(class_levels.values())
    
    # Base stats from first class or default
    # If no class_levels, we can't do much.
    if not class_levels:
        return player_data

    # PROFICIENCY BONUS (based on TOTAL level)
    prof_bonus = 2 + (total_level - 1) // 4 
    player_data['proficiency_bonus'] = prof_bonus

    # MANA POOL (MP)
    # +1 MP per level in caster classes
    caster_classes = ["wizard", "druid", "alchemist", "sorcerer"]
    max_mp = 0
    for c_name, c_level in class_levels.items():
        if c_name.lower() in caster_classes:
            max_mp += c_level
    
    player_data['max_mp'] = max_mp
    # If MP was never set OR is zero at creation, initialize to full
    if 'current_mp' not in player_data or player_data['current_mp'] == 0:
        player_data['current_mp'] = player_data['max_mp']
    else:
        # Clamp only if already in use
        player_data['current_mp'] = min(player_data['current_mp'], max_mp)

    # RESET ACCUMULATORS
    player_data['spells'] = []
    player_data['skills'] = []
    player_data['attack_count'] = 1
    player_data['sneak_attack_rolls'] = 0
    player_data['cantrip_dice_rolled'] = 1
    
    # We should probably keep the original base HP from the starting class
    # and add gains from others.
    
    for class_name, level in class_levels.items():
        c_def = class_defs.get(class_name.lower())
        if not c_def: continue
        
        # Accumulate stats from each level of this class
        for lvl in range(1, level + 1):
            lvl_str = str(lvl)
            lvl_data = c_def.get('levels', {}).get(lvl_str, {})
            
            # Merging Logic:
            
            # Attack Count: Use the highest value found
            if 'attack_count' in lvl_data:
                player_data['attack_count'] = max(player_data['attack_count'], lvl_data['attack_count'])
                
            # Sneak Attack: Rogue specific accumulation
            if 'sneak_attack_rolls' in lvl_data:
                # Usually doesn't stack from multiple classes, but rogue level defines it.
                # In multi-classing, we just take the max rogue sneak attack.
                player_data['sneak_attack_rolls'] = max(player_data['sneak_attack_rolls'], lvl_data['sneak_attack_rolls'])

            # Cantrip Dice: Based on TOTAL level usually, but we'll follow class defs if they vary
            if 'cantrip_dice_rolled' in lvl_data:
                player_data['cantrip_dice_rolled'] = max(player_data['cantrip_dice_rolled'], lvl_data['cantrip_dice_rolled'])

            # Spells and Skills: Accumulate unique
            if 'spells' in lvl_data:
                for s in lvl_data['spells']:
                    if s not in player_data['spells']:
                        player_data['spells'].append(s)
            if 'skills' in lvl_data:
                for s in lvl_data['skills']:
                    if s not in player_data['skills']:
                        player_data['skills'].append(s)

            # Damage Die: Monk specific usually. Take highest.
            if 'damage_die' in lvl_data:
                player_data['damage_die'] = max(player_data.get('damage_die', 0), lvl_data['damage_die'])

    return player_data

def add_class_level(player_data, class_name):
    """Add a level in a specific class and update stats."""
    player_data.setdefault('class_levels', {})
    player_data['class_levels'][class_name] = player_data['class_levels'].get(class_name, 0) + 1
    
    # HP Increase: Use class hit die
    class_defs = load_player_classes()
    c_def = class_defs.get(class_name.lower())
    if c_def:
        hit_die = c_def.get('hp', 8)
        # 5e rule: gain half hit die + 1 on level up (or roll, we use fixed)
        hp_gain = (hit_die // 2) + 1
        player_data['hp'] += hp_gain
        player_data['max_hp'] = player_data.get('max_hp', player_data['hp']) + hp_gain
        player_data['current_hp'] = player_data.get('current_hp', player_data['hp']) + hp_gain

    player_data['level'] = sum(player_data['class_levels'].values())
    recalculate_stats(player_data)
    return player_data

def update_xp_and_level(player_data, xp_gain):
    """
    Update player XP and check if a level-up is available.
    Returns True if a level-up is pending.
    """
    player_data.setdefault('xp', 0)
    player_data.setdefault('level', 1)
    player_data['xp'] += xp_gain
    
    new_total_level = get_total_level_for_xp(player_data['xp'])
    if new_total_level > player_data['level']:
        # We don't apply it here because the user must CHOOSE the class.
        return True
    return False
