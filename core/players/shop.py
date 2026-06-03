import json
import os
from .player import load_weapons, load_armor, load_trinkets, load_shields, apply_weapon_to_player, apply_armor_to_player, apply_trinket_to_player, apply_shield_to_player, load_consumables
from .player_inventory import spend_gold, add_item

def is_item_unlocked(category, item, party_level):
    """Core logic for determining if an item should be visible in the shop based on party level."""
    cost = item.get('cost', 0)
    
    # Robust bonus detection: check 'bonus' flag and name (e.g., "Sword +1")
    bonus = item.get('bonus', 0)
    try:
        bonus = int(bonus)
    except (ValueError, TypeError):
        bonus = 0
        
    name = item.get('name', '')
    if '+' in name:
        try:
            # Extract number after '+'
            name_bonus = int(name.split('+')[-1].strip())
            bonus = max(bonus, name_bonus)
        except (ValueError, IndexError):
            pass

    cat = category.lower()
    lvl = max(0, int(party_level))
    
    if cat == "weapons":
        # Exclusive Tiered Progression based on TPL
        if lvl >= 45:
            return bonus == 3
        elif lvl >= 30:
            return bonus == 2
        elif lvl >= 15:
            return bonus == 1
        else:
            return bonus == 0 # Early game: Base gear only
        
    elif cat == "armor":
        if lvl >= 36: return True # All armor
        if lvl >= 21: return cost < 1000
        if lvl >= 1: return cost < 500
        return False 
        
    elif cat == "shields":
        if lvl >= 36: return True # All shields
        if lvl >= 21: return cost < 800
        if lvl >= 1: return cost < 400
        return False
        
    elif cat == "trinkets":
        if lvl >= 51: return True # All trinkets
        if lvl >= 41: return cost < 2000
        if lvl >= 26: return cost < 1500
        if lvl >= 6: return cost < 500
        return False
        
    return True # Consumables (always unlocked)

def get_available_shop_inventory(party_level, category, sub_category=None):
    """
    Returns a dictionary of items available for purchase in the given category/subcategory
    filtered by progression logic.
    """
    cat = category.lower()
    if cat == "weapons":
        data = load_weapons()
        if sub_category:
            data = {k: v for k, v in data.items() if v.get('weapon_class', 'simple').lower() == sub_category.lower()}
    elif cat == "armor":
        data = load_armor()
        if sub_category:
            target_type = sub_category.lower()
            if target_type == "robes": target_type = "robe"
            data = {k: v for k, v in data.items() if v.get('type', 'none').lower() == target_type}
    elif cat == "shields":
        data = load_shields()
    elif cat == "consumables":
        data = load_consumables()
    elif cat == "trinkets":
        data = load_trinkets()
    else:
        return {}

    # Filter by level and in_shop
    available = {k: v for k, v in data.items() if v.get('cost', 0) > 0 and v.get('in_shop', True) and is_item_unlocked(cat, v, party_level)}
    return available

def get_sell_price(category, item_data):
    """Calculates the gold return for selling an item."""
    if category == "junk":
        return item_data.get('cost', 1)
    
    price = item_data.get('cost', 2) // 2
    return max(1, price) # Ensures price never drops below 1

def visit_shop(player_data, inventory):
    # NOTE: This method is now legacy for the CLI/API and should ideally be 
    # refactored further or removed to ensure zero I/O in core.
    # For now, it remains as a reference for CLI implementation.
    pass
