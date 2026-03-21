import json
import os


def load_player_classes(path=None):
    """Load player class definitions with level progressions."""
    base_dir = os.path.dirname(__file__)
    if path is None:
        path = os.path.join(base_dir, 'player_classes.json')
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data


def get_class_stats_at_level(class_name, level, player_classes=None):
    """
    Get class stats at a specific level, merging base stats with level-specific overrides.
    Returns a dictionary with all stats that should be applied for this class at this level.
    """
    if player_classes is None:
        player_classes = load_player_classes()
    
    class_name = class_name.lower()
    if class_name not in player_classes:
        return {}
    
    class_def = player_classes[class_name]
    
    # Start with base stats (excluding 'levels' key)
    stats = {k: v for k, v in class_def.items() if k != 'levels'}
    
    # Apply level-specific overrides for all levels up to and including current level
    levels_def = class_def.get('levels', {})
    for lvl in range(1, level + 1):
        lvl_str = str(lvl)
        if lvl_str in levels_def:
            stats.update(levels_def[lvl_str])
    
    return stats


def get_level_for_xp(total_xp, class_name=None, player_classes=None):
    """
    Determine player level from total XP using class-specific progression from player_classes.json.
    """
    if class_name and player_classes is None:
        player_classes = load_player_classes()
    
    # Get progression from player_classes.json
    if class_name and player_classes:
        class_name = class_name.lower()
        if class_name in player_classes:
            class_def = player_classes[class_name]
            levels_def = class_def.get('levels', {})
            
            current_level = 1
            for lvl in range(1, 21):  # Levels 1-20
                lvl_str = str(lvl)
                if lvl_str in levels_def and 'xp_threshold' in levels_def[lvl_str]:
                    if total_xp >= levels_def[lvl_str]['xp_threshold']:
                        current_level = lvl
                    else:
                        break
            return current_level
    
    # Default to level 1 if no class found
    return 1


def xp_to_next_level(total_xp, class_name=None, player_classes=None):
    """
    Calculate XP needed to reach next level using class-specific progression from player_classes.json.
    """
    if class_name and player_classes is None:
        player_classes = load_player_classes()
    
    current_level = get_level_for_xp(total_xp, class_name, player_classes)
    next_level = current_level + 1

    # Get progression from player_classes.json
    if class_name and player_classes:
        class_name = class_name.lower()
        if class_name in player_classes:
            class_def = player_classes[class_name]
            levels_def = class_def.get('levels', {})
            
            next_level_str = str(next_level)
            if next_level_str in levels_def and 'xp_threshold' in levels_def[next_level_str]:
                return levels_def[next_level_str]['xp_threshold'] - total_xp
            return None

    # No next level available
    return None


def apply_level_up(player_data, old_level, new_level, base_hp=None):
    if new_level <= old_level:
        return player_data

    if base_hp is None:
        base_hp = player_data.get('base_hp', player_data.get('hp', 0))

    hp_increase = int(base_hp / 2)
    for _ in range(new_level - old_level):
        player_data['hp'] += hp_increase

    player_data['level'] = new_level
    return player_data


def update_xp_and_level(player_data, xp_gain, class_name=None, base_hp=None):
    """
    Update player XP and level, applying class-specific stats from player_classes.json.
    """
    player_data.setdefault('xp', 0)
    player_data.setdefault('level', 1)
    player_data['xp'] += xp_gain

    # Use class name from player_data if not provided
    if class_name is None:
        class_name = player_data.get('class', '')
    
    # Load player classes
    player_classes = load_player_classes()
    
    old_level = player_data['level']
    new_level = get_level_for_xp(player_data['xp'], class_name, player_classes)

    if new_level > old_level:
        apply_level_up(player_data, old_level, new_level, base_hp=base_hp)

    # Get level-specific stats from player_classes.json
    class_stats = get_class_stats_at_level(class_name, player_data['level'], player_classes)
    
    # Apply all class-specific level progression stats
    level_progression_keys = [
        'proficiency_bonus', 'attack_count', 'damage_die', 
        'sneak_attack_rolls', 'cantrip_dice_rolled'
    ]
    for key in level_progression_keys:
        if key in class_stats:
            player_data[key] = class_stats[key]

    return player_data
