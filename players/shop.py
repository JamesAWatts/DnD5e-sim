import json
import os
from players.player import load_weapons, load_armor, apply_weapon_to_player, apply_armor_to_player
from players.player_inventory import spend_gold, add_item

def load_consumables():
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, 'consumables.json')
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f).get('consumable_list', {})
    except FileNotFoundError:
        return {}

def visit_shop(player_data, inventory):
    weapons_data = load_weapons().get('weapon_list', {})
    armor_data = load_armor()
    consumables_data = load_consumables()

    while True:
        print("\n=== THE DRAGON'S HOARD SHOP ===")
        print(f"Your Gold: {inventory.get('gold', 0)}")
        print("1. Buy Weapons")
        print("2. Buy Armor")
        print("3. Buy Consumables")
        print("4. Sell Junk (1 gold each)")
        print("5. Exit Shop")
        
        choice = input("What would you like to do? ").strip()

        if choice == '1':
            buy_items(player_data, inventory, weapons_data, 'weapon')
        elif choice == '2':
            buy_items(player_data, inventory, armor_data, 'armor')
        elif choice == '3':
            buy_items(player_data, inventory, consumables_data, 'consumable')
        elif choice == '4':
            sell_junk(inventory)
        elif choice == '5' or choice.lower() == 'exit':
            break
        else:
            print("Invalid choice.")

def buy_items(player_data, inventory, item_list, item_type):
    available = {k: v for k, v in item_list.items() if v.get('cost', 0) > 0}
    
    names = sorted(available.keys())
    print(f"\n--- Available {item_type.title()} ---")
    for i, name in enumerate(names, 1):
        item = available[name]
        cost = item['cost']
        if item_type == 'weapon':
            stats = f"(d{item['die']}, {item.get('on_hit_effect', 'no effect')})"
        elif item_type == 'armor':
            stats = f"(AC {item['ac']})"
        else:
            stats = f"({item.get('description', '')})"
            
        display_name = item.get('name', name.replace('_', ' ')).title()
        print(f"{i}. {display_name}: {cost} gold {stats}")
    print(f"{len(names) + 1}. Back")

    choice = input(f"Select a {item_type} to buy: ").strip()
    if not choice.isdigit():
        return
    
    idx = int(choice) - 1
    if idx == len(names):
        return
    
    if 0 <= idx < len(names):
        item_key = names[idx]
        item = available[item_key]
        cost = item['cost']
        item_name = item.get('name', item_key.replace('_', ' '))
        
        # You can own multiple consumables
        if item_type != 'consumable' and item_key in inventory.get(item_type, []):
            print(f"You already own a {item_name}!")
            return

        if spend_gold(inventory, cost):
            add_item(inventory, item_key, item_type)
            print(f"Successfully bought {item_name}!")
            
            if item_type in ['weapon', 'armor']:
                confirm = input(f"Equip {item_name} now? (y/n): ").strip().lower()
                if confirm in ('y', 'yes'):
                    if item_type == 'weapon':
                        player_data['weapon'] = item_key
                        apply_weapon_to_player(player_data)
                        inventory['equipped']['weapon'] = item_key
                    else:
                        player_data['armor'] = item_key
                        apply_armor_to_player(player_data)
                        inventory['equipped']['armor'] = item_key
                    print(f"Equipped {item_name}.")
        else:
            print("You don't have enough gold!")

def sell_junk(inventory):
    junk_items = inventory.get('junk', [])
    if not junk_items:
        print("You have no junk to sell.")
        return
    
    amount = len(junk_items)
    inventory['gold'] += amount
    inventory['junk'] = []
    print(f"Sold {amount} junk items for {amount} gold.")
