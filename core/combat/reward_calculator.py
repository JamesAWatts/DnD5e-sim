import random

def calculate_combat_rewards(defeated_enemies):
    """
    Calculates the total XP, Gold, and item drops from a list of defeated enemies.
    
    Logic:
    1. Sums up base 'xp' and 'gold' for all enemies (guaranteed).
    2. For each enemy, rolls a weighted randomizer for an EXTRA reward:
       - 2 Items: 60% extra Gold, 25% Item 1, 15% Item 2
       - 1 Item: 60% extra Gold, 40% Item 1
       - 0 Items: 100% extra Gold
    
    Args:
        defeated_enemies (list): A list of enemy dictionaries.
        
    Returns:
        dict: {"total_xp": int, "total_gold": int, "items": [list of item names]}
    """
    total_xp = 0
    total_gold = 0
    dropped_items = []

    for enemy in defeated_enemies:
        # 1. Sum up base XP and Gold from enemy data
        total_xp += enemy.get('xp', 0)
        
        reward_data = enemy.get('reward', {})
        base_gold = reward_data.get('gold', 0)
        total_gold += base_gold
        
        # 2. Weighted Randomizer for EXTRA rewards (Item drops)
        reward_items = reward_data.get('items', [])
        roll = random.random() * 100
        
        def get_item_name(item):
            if isinstance(item, dict):
                return item.get('name')
            return item

        if len(reward_items) >= 2:
            # 60% chance for Gold, 25% for Item 1, 15% for Item 2
            if roll < 60:
                total_gold += base_gold
            elif roll < 85:
                dropped_items.append(get_item_name(reward_items[0]))
            else:
                dropped_items.append(get_item_name(reward_items[1]))
                
        elif len(reward_items) == 1:
            # 60% chance for Gold, 40% for Item 1
            if roll < 60:
                total_gold += base_gold
            else:
                dropped_items.append(get_item_name(reward_items[0]))
                
        else:
            # 0 items: Guaranteed extra Gold drop
            total_gold += base_gold

    return {
        "total_xp": total_xp,
        "total_gold": total_gold,
        "items": dropped_items
    }
