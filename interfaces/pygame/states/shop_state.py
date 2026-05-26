import pygame
from states.base_state import BaseState
from ui.menu import Menu
from graphics.backgrounds import BackgroundManager
from ui.dialogue_box import DialogueBox
from ui.panel import draw_text_outlined
from core.game_rules.constants import scale_y, SCREEN_WIDTH, COLOR_GOLD
from core.players.player import (
    load_weapons, load_armor, load_trinkets, load_shields, 
    apply_weapon_to_player, apply_armor_to_player, apply_shield_to_player, apply_trinket_to_player
)
from core.players.shop import get_sell_price, load_consumables, get_available_shop_inventory
from core.combat.combat_engine import CombatEngine

class ShopState(BaseState):
    def __init__(self, game, font, player=None):
        super().__init__(game, font)
        self.background = BackgroundManager.get_shop_bg()
        self.dialogue = DialogueBox(font)

        self.player = player if player else game.player
        self.inventory = self.player.get("inventory_ref", {})
        if not self.inventory:
             self.inventory = self.player.get("inventory", {})

        self.mode = "MAIN"
        self.item_map = {}
        self.buy_category = None
        self.current_page = 0
        self.items_per_page = 10
        
        self.purchased_item_key = None
        self.purchased_item_cat = None
        self.purchased_item_data = None

        self.main_menu = Menu(["Buy", "Sell", "Back"], font, width=100, header="The Dragon's Hoard")
        self.active_menu = self.main_menu

    def refresh_buy_menu(self):
        options = ["Weapons", "Armor", "Shields", "Consumables", "Trinkets", "Back"]
        self.active_menu = Menu(options, self.font, width=100, header="What are you looking for?")

    def refresh_weapon_categories(self):
        options = ["Simple", "Martial", "Caster", "Back"]
        self.active_menu = Menu(options, self.font, width=100, header="Weapon Class?")

    def refresh_armor_categories(self):
        options = ["Robes", "Light", "Medium", "Heavy", "Back"]
        self.active_menu = Menu(options, self.font, width=100, header="Armor Type?")

    def open_buy_category(self, category, sub_category=None):
        party_lvl = sum(p.get('level', 1) for p in self.game.party)
        available = get_available_shop_inventory(party_lvl, category, sub_category)
        
        if category == "armor":
            # none > light > medium > heavy > robe
            type_order = {'none': 0, 'light': 1, 'medium': 2, 'heavy': 3, 'robe': 4}
            all_keys = sorted(available.keys(), key=lambda k: (type_order.get(available[k].get('type', 'none'), 99), available[k].get('cost', 0)))
        elif category == "weapons":
            # melee > ranged
            type_order = {'melee': 0, 'ranged': 1}
            all_keys = sorted(available.keys(), key=lambda k: (type_order.get(available[k].get('type', 'melee'), 99), available[k].get('cost', 0)))
        else:
            all_keys = sorted(available.keys(), key=lambda k: available[k].get('cost', 0))

        
        total_pages = (len(all_keys) + self.items_per_page - 1) // self.items_per_page
        if self.current_page >= total_pages: self.current_page = 0
        if self.current_page < 0: self.current_page = total_pages - 1

        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_keys = all_keys[start_idx:end_idx]

        options = []
        descriptions = {}
        self.item_map = {}
        for k in page_keys:
            item = available[k]
            display_name = item.get('name', k.replace('_', ' ')).title()
            full_display = f"{display_name} ({item['cost']}g)"
            options.append(full_display)
            self.item_map[full_display] = k
            
            # Format description
            if category == "weapons":
                desc = f"{item.get('description', '')} (D{item.get('die', 4)}, {item.get('on_hit_effect', 'none').title()})"
            elif category == "armor":
                desc = f"{item.get('description', '')} (AC: {item.get('ac', 10)}, {item.get('type', 'light').title()})"
            elif category == "shields":
                desc = f"{item.get('description', '')} (AC: +{item.get('ac', 0)})"
            elif category == "trinkets":
                desc = item.get('description', '')
            else:
                desc = item.get('description', '')
            descriptions[full_display] = desc

        # Add Pagination/Footer options
        if total_pages > 1:
            options.append("Next Page")
            options.append("Previous Page")
        
        options.append("Return")
        
        sub_header = f" - {sub_category.title()}" if sub_category else ""
        header = f"{category.title()}{sub_header} (Page {self.current_page + 1}/{total_pages})"
        self.active_menu = Menu(options, self.font, width=200, header=header, descriptions=descriptions)

    def refresh_sell_menu(self):
        options = ["Weapons", "Armor", "Shields", "Consumables", "Trinkets", "Junk", "Back"]
        disabled_indices = []
        
        # Determine which categories are empty
        for i, option in enumerate(options):
            if option == "Back":
                continue
            
            # Map category name to inventory key (e.g., "Weapons" -> "weapon")
            cat_name = option.lower()
            inv_key = cat_name[:-1] if cat_name.endswith('s') else cat_name
            items_dict = self.inventory.get(inv_key, {})
            
            # If no items in this category, mark it as disabled (greyed out)
            if not items_dict or len(items_dict) == 0:
                disabled_indices.append(i)

        self.active_menu = Menu(
            options, self.font, width=100, 
            header="What would you like to sell?", 
            disabled_indices=disabled_indices
        )

    def open_sell_category(self, category):
        inv_key = category[:-1] if category.endswith('s') else category
        items_dict = self.inventory.get(inv_key, {})
        
        if not items_dict:
            self.dialogue.set_messages([f"You have no {category} to sell."])
            self.mode = "SELL_CAT"
            self.refresh_sell_menu()
            return

        # Load price data
        if category == "weapons":
            data = load_weapons().get("weapon_list", {})
        elif category == "armor":
            data = load_armor()
        elif category == "shields":
            data = load_shields()
        elif category == "consumables":
            data = load_consumables()
        elif category == "trinkets":
            data = load_trinkets()
        elif category == "junk":
            from core.game_rules.path_utils import get_resource_path
            import json
            import os
            try:
                with open(get_resource_path(os.path.join('data', 'items', 'junk.json')), 'r') as f:
                    data = json.load(f)
            except:
                data = {}
        else: # Misc
            data = {}

        options = []
        descriptions = {}
        self.item_map = {}
        
        # Sort keys
        all_keys = sorted(items_dict.keys())
        
        for k in all_keys:
            count = items_dict[k]
            if category == "junk":
                item_data = data.get('junk_list', {}).get(k, {})
            else:
                item_data = data.get(k, {})
            
            # Calculate sell prices
            price = get_sell_price(category, item_data)
            
            display_name = item_data.get('name', k.replace('_', ' ')).title()
            full_display = f"{display_name} x{count} ({price}g)"
            options.append(full_display)
            self.item_map[full_display] = (k, price, inv_key)
            descriptions[full_display] = item_data.get('description', 'A miscellaneous item.')

        if not options:
            self.dialogue.set_messages([f"You have no {category} to sell."])
            return

        options.append("Back")
        self.active_menu = Menu(options, self.font, width=200, header=f"Sell {category.title()}", descriptions=descriptions)

    def on_select(self, option):
        if self.mode == "MAIN":
            if option == "Buy":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            elif option == "Sell":
                self.mode = "SELL_CAT"
                self.refresh_sell_menu()
            elif option == "Back":
                from states.hub import HubState
                self.game.change_state(HubState(self.game, self.font))

        elif self.mode == "BUY_CAT":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            elif option == "Weapons":
                self.mode = "BUY_WEAPON_CAT"
                self.refresh_weapon_categories()
            elif option == "Armor":
                self.mode = "BUY_ARMOR_CAT"
                self.refresh_armor_categories()
            else:
                self.mode = "BUY_ITEMS"
                self.buy_category = option.lower()
                self.buy_sub_category = None
                self.current_page = 0
                self.open_buy_category(self.buy_category)

        elif self.mode == "BUY_WEAPON_CAT":
            if option == "Back":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            else:
                self.mode = "BUY_ITEMS"
                self.buy_category = "weapons"
                self.buy_sub_category = option.lower()
                self.current_page = 0
                self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif self.mode == "BUY_ARMOR_CAT":
            if option == "Back":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            else:
                self.mode = "BUY_ITEMS"
                self.buy_category = "armor"
                self.buy_sub_category = option.lower()
                self.current_page = 0
                self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif self.mode == "SELL_CAT":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            else:
                self.mode = "SELL_ITEMS"
                self.sell_category = option.lower()
                self.open_sell_category(self.sell_category)

        elif self.mode == "BUY_ITEMS":
            if option == "Return":
                if self.buy_category == "weapons":
                    self.mode = "BUY_WEAPON_CAT"
                    self.refresh_weapon_categories()
                elif self.buy_category == "armor":
                    self.mode = "BUY_ARMOR_CAT"
                    self.refresh_armor_categories()
                else:
                    self.mode = "BUY_CAT"
                    self.refresh_buy_menu()
            elif option == "Next Page":
                self.current_page += 1
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            elif option == "Previous Page":
                self.current_page -= 1
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            else:
                self.handle_buy(option)

        elif self.mode == "SELL_ITEMS":
            if option == "Back":
                self.mode = "SELL_CAT"
                self.refresh_sell_menu()
            else:
                self.handle_sell(option)

        elif self.mode == "CONFIRM_ACTION":
            if option == "Back":
                self.mode = "BUY_ITEMS"
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            else:
                self.execute_action(option)

        elif self.mode == "SELL": # Cleanup old mode if hit
            self.mode = "SELL_CAT"
            self.refresh_sell_menu()

    def handle_sell(self, display_name):
        mapped = self.item_map.get(display_name)
        if not mapped: 
            print(f"DEBUG SHOP: handle_sell called with '{display_name}' but not in item_map (mode={self.mode})")
            return
        
        item_key, price, inv_key = mapped
        
        print(f"DEBUG PYGAME SELL: Selling {item_key} for {price} gold (category: {inv_key})")
        
        # Verify we still have it
        category = self.inventory.get(inv_key, {})
        if category.get(item_key, 0) <= 0:
            self.dialogue.set_messages(["You no longer have this item."])
            self.open_sell_category(self.sell_category)
            return

        # Double check equipped
        equipped = self.inventory.get('equipped', {})
        if item_key == equipped.get(inv_key) and category.get(item_key, 0) <= 1:
            self.dialogue.set_messages(["Cannot sell equipped items!"])
            self.open_sell_category(self.sell_category)
            return

        # Remove item and add gold
        from core.players.player_inventory import remove_item
        if remove_item(self.inventory, item_key, inv_key):
            self.inventory['gold'] = self.inventory.get('gold', 0) + price
            self.dialogue.set_messages([f"Sold {item_key.replace('_',' ').title()} for {price} gold."])
            print(f"DEBUG PYGAME SELL: Successfully sold {item_key} for {price} gold")
        
        # Refresh the current sell category view
        self.open_sell_category(self.sell_category)

    def handle_buy(self, display_name):
        item_key = self.item_map.get(display_name)
        if not item_key: return

        if self.buy_category == "weapons":
            data = load_weapons().get("weapon_list", {})
        elif self.buy_category == "armor":
            data = load_armor()
        elif self.buy_category == "shields":
            data = load_shields()
        elif self.buy_category == "trinkets":
            data = load_trinkets()
        else:
            data = load_consumables()

        item = data[item_key]
        cost = item['cost']
        
        # Check gold (use party inventory gold)
        inv = self.game.player['inventory_ref']
        if self.game.god_mode or inv.get('gold', 0) >= cost:
            if not self.game.god_mode:
                inv['gold'] -= cost
            
            from core.players.player_inventory import add_item
            # Mapping Buy Categories to inventory keys
            inv_key = self.buy_category[:-1] if self.buy_category.endswith('s') else self.buy_category
            add_item(inv, item_key, inv_key)
            
            # Store for confirmation
            self.purchased_item_key = item_key
            self.purchased_item_cat = inv_key
            self.purchased_item_data = item
            
            # --- New "Equip to" Menu ---
            self.mode = "CONFIRM_ACTION"
            action_verb = "Use on" if inv_key == "consumable" else "Equip to"
            party_names = [p.get('name', 'Adventurer') for p in self.game.party]
            self.active_menu = Menu(party_names + ["Back"], self.font, header=f"{action_verb}?")
        else:
            self.dialogue.set_messages(["Not enough gold!"])

    def execute_action(self, character_name):
        # Find the character
        target_char = next((p for p in self.game.party if p.get('name') == character_name), None)
        if not target_char: return

        key = self.purchased_item_key
        cat = self.purchased_item_cat
        item = self.purchased_item_data
        inv = self.game.inventory
        
        from core.players.player_inventory import add_item, remove_item

        if cat == "weapon":
            from core.players.player import can_equip_weapon
            if can_equip_weapon(target_char, key):
                # Return old
                old = target_char.get("weapon", "unarmed")
                if old and old != "unarmed": add_item(inv, old, "weapon")
                # Remove new (it was added in handle_buy)
                remove_item(inv, key, "weapon")
                
                target_char["weapon"] = key
                apply_weapon_to_player(target_char)
                
                self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
                self.mode = "BUY_ITEMS"
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            else:
                self.dialogue.set_messages([f"{item.get('name', key.replace('_',' ')).title()} cannot be equipped by {character_name}."])
        
        elif cat == "armor":
            from core.players.player import can_equip_armor
            if can_equip_armor(target_char, key):
                # Return old
                old = target_char.get("armor", "unarmored")
                if old and old != "unarmored": add_item(inv, old, "armor")
                # Remove new
                remove_item(inv, key, "armor")

                target_char['armor'] = key
                apply_armor_to_player(target_char)
                self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
                self.mode = "BUY_ITEMS"
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            else:
                self.dialogue.set_messages([f"{item.get('name', key.replace('_',' ')).title()} cannot be equipped by {character_name}."])

        elif cat == "shield":
            # Return old
            old = target_char.get("shield", "none")
            if old and old != "none": add_item(inv, old, "shield")
            # Remove new
            remove_item(inv, key, "shield")

            target_char["shield"] = key
            apply_shield_to_player(target_char)
            self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
            self.mode = "BUY_ITEMS"
            self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif cat == "trinket":
            # Return old
            old = target_char.get("trinket", "none")
            if old and old != "none": add_item(inv, old, "trinket")
            # Remove new
            remove_item(inv, key, "trinket")

            target_char["trinket"] = key
            apply_trinket_to_player(target_char)
            self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
            self.mode = "BUY_ITEMS"
            self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif cat == "consumable":
            # Use logic
            from core.players.player import apply_consumable_effect
            res = CombatEngine.resolve_item(item, target_char)
            apply_consumable_effect(target_char, res)
            
            # Remove from shared inventory (it was added in handle_buy)
            remove_item(inv, key, "consumable")
            
            self.dialogue.set_messages([f"Used on {character_name}. {res.get('msg', '')}"])
            self.mode = "BUY_ITEMS"
            self.open_buy_category(self.buy_category, self.buy_sub_category)

    def update(self, events, dt):
        if self.dialogue.current_message:
            self.dialogue.update()
            for event in events:
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    self.dialogue.handle_event(event)
            return
            
        super().update(events, dt)

    def draw(self, screen):
        # --- Draw background FIRST ---
        self.draw_background(screen)
        self.draw_settings_button(screen)

        # Show Gold at the top
        gold_text = f"Gold: {self.inventory.get('gold', 0)}"
        gw, gh = self.font.size(gold_text)
        draw_text_outlined(screen, gold_text, self.font, COLOR_GOLD, (SCREEN_WIDTH // 2) - (gw // 2), scale_y(40))

        # --- MENU (Left Aligned, Vertically Centered in Base 800x600) ---
        if self.active_menu and not self.dialogue.current_message:
            # Position at x=150, y=300 in Base space
            self.active_menu.draw(screen, 150, 300)
            
        if self.dialogue.current_message:
            self.dialogue.draw(screen)
