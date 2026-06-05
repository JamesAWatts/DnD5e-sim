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
        self.dialogue = DialogueBox(self.fonts['large'])

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

        self.main_menu = Menu(["Buy", "Sell", "Back"], self.fonts['medium'], width=140, header="The Dragon's Hoard", pos=(300, 300), tooltip_offset_x=105, tooltip_vert_centered=True)
        self.active_menu = self.main_menu

        # Calculate TPL once upon entering the shop
        self.tpl = sum(p.get('level', 1) for p in self.game.party)

        # Wasm Optimization: Caching
        self._last_gold = -1
        self._cached_gold_surf = None
        self._last_hovered_item = None
        self._cached_desc_surf = None

    def _render_gold_cache(self, gold):
        gold_text = f"Gold: {gold}"
        tw, th = self.fonts['large'].size(gold_text)
        self._cached_gold_surf = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
        draw_text_outlined(self._cached_gold_surf, gold_text, self.fonts['large'], COLOR_GOLD, 5, 5)

    def _render_desc_cache(self, text, menu_rect):
        from core.game_rules.constants import SCALE_X, SCALE_Y, scale_x, scale_y
        raw_w = 200 # Tooltip width
        scaled_w = raw_w * SCALE_X
        
        words = str(text).split(' ')
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            tw, _ = self.fonts['medium'].size(test_line)
            if tw > scaled_w - scale_x(20):
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        lines.append(' '.join(current_line))
        
        line_h = self.fonts['medium'].get_height()
        spacing = scale_y(2)
        total_h = len(lines) * (line_h + spacing) + scale_y(30)
        
        surf = pygame.Surface((scaled_w, total_h), pygame.SRCALPHA)
        from ui.panel import Panel
        panel = Panel(0, 0, raw_w, total_h / SCALE_Y, bg_color=(20, 20, 40), border_color=COLOR_GOLD, border_width=2, centered=False, border_radius=10, alpha=230)
        panel.draw(surf)
        
        for i, line in enumerate(lines):
            lw, _ = self.fonts['medium'].size(line)
            draw_text_outlined(surf, line, self.fonts['medium'], (220, 220, 220), scaled_w // 2 - lw // 2, scale_y(15) + i * (line_h + spacing))
        self._cached_desc_surf = surf

    def refresh_buy_menu(self):
        options = ["Weapons", "Armor", "Shields", "Consumables", "Trinkets", "Back"]
        self.active_menu = Menu(options, self.fonts['medium'], width=200, header="What are you looking for?", pos=(300, 300), tooltip_offset_x=105, tooltip_vert_centered=True)

    def refresh_weapon_categories(self):
        options = ["Simple", "Martial", "Caster", "Back"]
        self.active_menu = Menu(options, self.fonts['medium'], width=200, header="Weapon Class?", pos=(300, 300), tooltip_offset_x=105, tooltip_vert_centered=True)

    def refresh_armor_categories(self):
        options = ["Robes", "Light", "Medium", "Heavy", "Back"]
        self.active_menu = Menu(options, self.fonts['medium'], width=200, header="Armor Type?", pos=(300, 300), tooltip_offset_x=105, tooltip_vert_centered=True)

    def open_buy_category(self, category, sub_category=None):
        available = get_available_shop_inventory(self.tpl, category, sub_category)
        
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
        self.active_menu = Menu(options, self.fonts['medium'], width=280, header=header, descriptions=descriptions, pos=(300, 300), tooltip_offset_x=105, tooltip_vert_centered=True)

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
            options, self.fonts['medium'], width=240, 
            header="What would you like to sell?", 
            disabled_indices=disabled_indices,
            pos=(300, 300)
        )

    def open_sell_category(self, category):
        inv_key = category[:-1] if category.endswith('s') else category
        items_dict = self.inventory.get(inv_key, {})
        
        if not items_dict:
            self.dialogue.set_messages([f"You have no {category} to sell."])
            self.mode = "SELL_CAT"
            self.refresh_sell_menu()
            return

        # Load price data using DatabaseManager
        from core.game_rules.database_manager import db
        data = db.get_data(category if category != "junk" else "junk")

        options = []
        descriptions = {}
        self.item_map = {}
        
        # Sort keys
        all_keys = sorted(items_dict.keys())
        
        for k in all_keys:
            count = items_dict[k]
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
        self.active_menu = Menu(options, self.fonts['medium'], width=280, header=f"Sell {category.title()}", descriptions=descriptions, pos=(300, 300), tooltip_offset_x=105, tooltip_vert_centered=True)

    def on_select(self, option):
        if option == "BACK":
            # Handle menu-based BACK key/button
            if self.mode == "MAIN":
                from states.hub import HubState
                self.game.change_state(HubState(self.game, self.fonts))
            elif self.mode == "BUY_CAT":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            return

        if self.mode == "MAIN":
            if option == "Buy":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            elif option == "Sell":
                self.mode = "SELL_CAT"
                self.refresh_sell_menu()
            elif option == "Back":
                from states.hub import HubState
                self.game.change_state(HubState(self.game, self.fonts))

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

    def handle_sell(self, display_name):
        mapped = self.item_map.get(display_name)
        if not mapped: return
        
        item_key, price, inv_key = mapped
        category = self.inventory.get(inv_key, {})
        if category.get(item_key, 0) <= 0:
            self.dialogue.set_messages(["You no longer have this item."])
            self.open_sell_category(self.sell_category)
            return

        equipped = self.inventory.get('equipped', {})
        if item_key == equipped.get(inv_key) and category.get(item_key, 0) <= 1:
            self.dialogue.set_messages(["Cannot sell equipped items!"])
            self.open_sell_category(self.sell_category)
            return

        from core.players.player_inventory import remove_item
        if remove_item(self.inventory, item_key, inv_key):
            self.inventory['gold'] = self.inventory.get('gold', 0) + price
            self.dialogue.set_messages([f"Sold {item_key.replace('_',' ').title()} for {price} gold."])
        
        self.open_sell_category(self.sell_category)

    def handle_buy(self, display_name):
        item_key = self.item_map.get(display_name)
        if not item_key: return

        if self.buy_category == "weapons":
            data = load_weapons()
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
        
        inv = self.game.player['inventory_ref']
        if self.game.god_mode or inv.get('gold', 0) >= cost:
            if not self.game.god_mode:
                inv['gold'] -= cost
            
            from core.players.player_inventory import add_item
            inv_key = self.buy_category[:-1] if self.buy_category.endswith('s') else self.buy_category
            add_item(inv, item_key, inv_key)
            
            self.purchased_item_key = item_key
            self.purchased_item_cat = inv_key
            self.purchased_item_data = item
            
            self.mode = "CONFIRM_ACTION"
            action_verb = "Use on" if inv_key == "consumable" else "Equip to"
            party_names = [p.get('name', 'Adventurer') for p in self.game.party]
            self.active_menu = Menu(party_names + ["Back"], self.fonts['medium'], header=f"{action_verb}?", pos=(300, 300), tooltip_offset_x=105, tooltip_vert_centered=True)
        else:
            self.dialogue.set_messages(["Not enough gold!"])

    def execute_action(self, character_name):
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
                old = target_char.get("weapon", "unarmed")
                if old and old != "unarmed": add_item(inv, old, "weapon")
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
                old = target_char.get("armor", "unarmored")
                if old and old != "unarmored": add_item(inv, old, "armor")
                remove_item(inv, key, "armor")
                target_char['armor'] = key
                apply_armor_to_player(target_char)
                self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
                self.mode = "BUY_ITEMS"
                self.open_buy_category(self.buy_category, self.buy_sub_category)
            else:
                self.dialogue.set_messages([f"{item.get('name', key.replace('_',' ')).title()} cannot be equipped by {character_name}."])

        elif cat == "shield":
            old = target_char.get("shield", "none")
            if old and old != "none": add_item(inv, old, "shield")
            remove_item(inv, key, "shield")
            target_char["shield"] = key
            apply_shield_to_player(target_char)
            self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
            self.mode = "BUY_ITEMS"
            self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif cat == "trinket":
            old = target_char.get("trinket", "none")
            if old and old != "none": add_item(inv, old, "trinket")
            remove_item(inv, key, "trinket")
            target_char["trinket"] = key
            apply_trinket_to_player(target_char)
            self.dialogue.set_messages([f"Equipped {item.get('name', key.replace('_',' ')).title()} to {character_name}!"])
            self.mode = "BUY_ITEMS"
            self.open_buy_category(self.buy_category, self.buy_sub_category)

        elif cat == "consumable":
            from core.players.player import apply_consumable_effect
            res = CombatEngine.resolve_item(item, target_char)
            apply_consumable_effect(target_char, res)
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
        self.draw_background(screen)
        self.draw_settings_button(screen)

        # Gold (Tracker-based Cache)
        gold_val = self.inventory.get('gold', 0)
        if gold_val != self._last_gold:
            self._render_gold_cache(gold_val)
            self._last_gold = gold_val
            
        if self._cached_gold_surf:
            screen.blit(self._cached_gold_surf, (SCREEN_WIDTH // 2 - self._cached_gold_surf.get_width() // 2, scale_y(40) - 5))

        if self.active_menu and not self.dialogue.current_message:
            # Tracker-based description caching
            if self.active_menu.descriptions:
                selected_opt = str(self.active_menu.options[self.active_menu.selected])
                cache_key = f"{id(self.active_menu)}_{selected_opt}"
                
                # Temporarily disable menu's own description drawing
                orig_desc = self.active_menu.descriptions
                self.active_menu.descriptions = None
                rect = self.active_menu.draw(screen)
                self.active_menu.descriptions = orig_desc
                
                desc_text = orig_desc.get(selected_opt)
                if desc_text:
                    if cache_key != self._last_hovered_item:
                        self._render_desc_cache(desc_text, rect)
                        self._last_hovered_item = cache_key
                    
                    if self._cached_desc_surf:
                        from core.game_rules.constants import scale_x
                        tx = rect.right + scale_x(self.active_menu.tooltip_offset_x)
                        ty = rect.centery if self.active_menu.tooltip_vert_centered else rect.y
                        if tx + self._cached_desc_surf.get_width() > SCREEN_WIDTH:
                            tx = rect.left - self._cached_desc_surf.get_width() - scale_x(self.active_menu.tooltip_offset_x)
                        screen.blit(self._cached_desc_surf, (tx, ty))
            else:
                self.active_menu.draw(screen)
            
        if self.dialogue.current_message:
            self.dialogue.draw(screen)
