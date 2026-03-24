import random


def create_inventory(selected_player):
    # Initialize player inventory using chosen class equipment.
    starting_weapon = selected_player.get('weapon', 'unarmed')
    starting_armor = selected_player.get('armor', 'unarmored')
    
    inventory = {
        'gold': 0,
        'weapon': [],
        'armor': [],
        'junk': [],
        'consumable': [],
        'key_items': [],
        'equipped': {
            'weapon': starting_weapon,
            'armor': starting_armor
        }
    }

    if starting_weapon:
        add_item(inventory, starting_weapon, 'weapon')

    if starting_armor:
        add_item(inventory, starting_armor, 'armor')

    return inventory


def add_gold(inventory, amount):
    inventory['gold'] = inventory.get('gold', 0) + int(amount)
    return inventory['gold']


def spend_gold(inventory, amount):
    # Subtract gold from inventory if sufficient funds exist.
    current_gold = inventory.get('gold', 0)
    if current_gold >= amount:
        inventory['gold'] = current_gold - amount
        return True
    return False


def add_item(inventory, item_name, item_type='junk'):
    if not item_name:
        return None
    
    # Ensure item_type is a valid key in inventory, fallback to junk
    if item_type not in inventory and item_type != 'gold':
        item_type = 'junk'
        
    category = inventory.setdefault(item_type, [])
    if item_name not in category:
        category.append(item_name)
    return item_name


def choose_loot(enemy_reward):
    # Choose loot based on specific probabilities:
    # - 60% chance for gold
    # - 25% chance for the 2nd item (index 1)
    # - 15% chance for the 1st item (index 0)
    if not enemy_reward:
        return None

    gold = enemy_reward.get('gold', 0)
    items = enemy_reward.get('items', [])
    if isinstance(items, str):
        items = [items]

    roll = random.randint(1, 100)

    if roll <= 60:
        # 60% chance for gold
        if gold > 0:
            return {'type': 'gold', 'amount': gold}
        # If no gold defined but we rolled gold, try items instead
        roll = random.randint(61, 100)

    if 61 <= roll <= 85:
        # 25% chance for 2nd item (index 1)
        if len(items) >= 2:
            dropped = items[1]
        elif len(items) >= 1:
            dropped = items[0]
        else:
            return None
    else:
        # 15% chance (86-100) for 1st item (index 0)
        if len(items) >= 1:
            dropped = items[0]
        else:
            return None

    if isinstance(dropped, dict):
        return {
            'type': 'item', 
            'name': dropped.get('name'), 
            'item_type': dropped.get('type', 'junk')
        }
    else:
        return {'type': 'item', 'name': dropped, 'item_type': 'junk'}


def award_loot(inventory, enemy_reward):
    # Process one loot drop and update inventory.
    drop = choose_loot(enemy_reward)
    if not drop:
        return None

    if drop['type'] == 'gold':
        add_gold(inventory, drop['amount'])
        return f"Loot: +{drop['amount']} gold. Total gold now {inventory['gold']}"

    if drop['type'] == 'item':
        add_item(inventory, drop['name'], drop['item_type'])
        return f"Loot: {drop['name']} ({drop['item_type']}) added to inventory."

    return None

def display_inventory(inventory):
    # Cleanly display inventory contents.
    print("\n--- INVENTORY ---")
    print(f"Gold: {inventory.get('gold', 0)}")
    
    for category in ['weapon', 'armor', 'consumable', 'junk', 'key_items']:
        items = inventory.get(category, [])
        if items:
            print(f"{category.title()}: {', '.join(items)}")
            
    equipped = inventory.get('equipped', {})
    if equipped:
        print(f"Equipped: {equipped.get('weapon', 'None')} / {equipped.get('armor', 'None')}")
    print("-----------------\n")

def manage_inventory(player_profile, inventory):
    # Interactive inventory manager for Hub.
    from players.player import apply_weapon_to_player, apply_armor_to_player

    while True:
        print("\n=== INVENTORY MANAGEMENT ===")
        equipped = inventory.get('equipped', {})
        print(f"Currently Equipped:\n  Weapon: {equipped.get('weapon', 'None')}\n  Armor: {equipped.get('armor', 'None')}")
        print(f"Gold: {inventory.get('gold', 0)}")
        
        categories = ['weapon', 'armor', 'consumable', 'junk']
        for i, category in enumerate(categories, 1):
            print(f"{i}. View {category.title()}")
        print(f"5. Back to Hub")
        
        choice = input("Select a category or go back: ").strip()
        
        if choice == '5' or choice.lower() == 'back':
            break
        
        if not choice.isdigit() or not (1 <= int(choice) <= 4):
            print("Invalid choice.")
            continue
            
        category_key = categories[int(choice) - 1]
        
        while True:
            items = inventory.get(category_key, [])
            if not items:
                print(f"\nYou have no {category_key} items.")
                break
                
            print(f"\n--- {category_key.title()} ---")
            for j, item in enumerate(items, 1):
                print(f"{j}. {item.replace('_', ' ').title()}")
            print(f"{len(items) + 1}. Back")
            
            item_choice = input(f"Select an item to use/equip or go back: ").strip()
            
            if item_choice == str(len(items) + 1) or item_choice.lower() == 'back':
                break
                
            if not item_choice.isdigit() or not (1 <= int(item_choice) <= len(items)):
                print("Invalid choice.")
                continue
                
            selected_item = items[int(item_choice) - 1]
            
            if category_key == 'weapon':
                player_profile['weapon'] = selected_item
                apply_weapon_to_player(player_profile)
                inventory['equipped']['weapon'] = selected_item
                print(f"Equipped {selected_item.replace('_', ' ').title()}.")
            elif category_key == 'armor':
                player_profile['armor'] = selected_item
                apply_armor_to_player(player_profile)
                inventory['equipped']['armor'] = selected_item
                print(f"Equipped {selected_item.replace('_', ' ').title()}.")
            elif category_key == 'consumable':
                if 'potion' in selected_item.lower():
                    heal_amount = max(10, player_profile.get('max_hp', 20) // 2)
                    player_profile['hp'] = min(player_profile.get('max_hp', 20), player_profile['hp'] + heal_amount)
                    items.remove(selected_item)
                    print(f"You consumed {selected_item.replace('_', ' ').title()} and healed for {heal_amount} HP!")
                    print(f"HP is now {player_profile['hp']} / {player_profile.get('max_hp', 20)}")
                    if not items: break
                else:
                    print("You're not sure how to use this consumable.")
            elif category_key == 'junk':
                print("It's best just to sell this.")
