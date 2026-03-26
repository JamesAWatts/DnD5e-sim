import pygame
import json
import os
from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.ui.dialogue_box import DialogueBox
from core.players.player import apply_weapon_to_player, apply_armor_to_player, load_weapons, load_armor
from core.players.shop import load_consumables

class InventoryState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_hub_bg(game.player)
        self.dialogue = DialogueBox(self.font)
        self.message_queue = []
        
        # Mapping to remember original keys for display names
        self.item_map = {}

        # In this game, player.get("inventory_ref") seems to be the way to get inventory
        self.inventory = game.player.get("inventory_ref", {})
        if not self.inventory:
            # Fallback if inventory_ref is missing
            self.inventory = game.player.get("inventory", {})

        self.menus = []
        root_menu = Menu(
            ["Weapons", "Armor", "Consumables", "Back"],
            self.font,
            pos=(150, 150)
            )   
        self.menus.append(root_menu)

    def queue_message(self, text):
        self.message_queue.append(text)

    def start_next_message(self):
        if self.message_queue:
            self.dialogue.set_messages([self.message_queue.pop(0)])

    def handle_selection(self, option):
        # ROOT
        if len(self.menus) == 1:
            if option == "Back":
                from interfaces.pygame.states.hub import HubState
                self.game.change_state(HubState(self.game, self.font))
                return

            self.open_item_menu(option.lower())

        # ITEM LIST
        elif len(self.menus) == 2:
            if option == "Back":
                self.menus.pop()
                return

            # Retrieve original key from map
            item_key = self.item_map.get(option, option.split(" (")[0])
            self.open_confirm_menu(item_key)

        # CONFIRM MENU
        elif len(self.menus) == 3:
            if option == "No":
                self.menus.pop()
                return
            if option == "Yes":
                # The confirm menu title has the item name
                # But it's easier to just look at what was selected in menus[1]
                item_display = self.menus[1].options[self.menus[1].selected]
                item_key = self.item_map.get(item_display, item_display.split(" (")[0])

                result_text = self.handle_item_action(item_key)

                # Queue feedback
                if result_text:
                    self.queue_message(result_text)
                    self.start_next_message()

                # Keep root menu but clear others
                root = self.menus[0]
                self.menus = [root]
    
    def open_item_menu(self, category):
        if category == "weapons":
            data = load_weapons().get("weapon_list", {})
        elif category == "armor":
            data = load_armor()
        elif category == "consumables":
            data = load_consumables()
        else:
            return

        # inventory keys are likely singular: weapon, armor, consumable
        inv_key = category[:-1] if category.endswith('s') else category
        items = self.inventory.get(inv_key, [])

        options = []
        for item_key in items:
            # Format name: replace underscores and title case
            display_name = item_key.replace('_', ' ').title()
            
            if item_key in data:
                cost = data[item_key].get("cost", 0)
                full_display = f"{display_name} ({cost}g)"
            else:
                full_display = display_name
                
            options.append(full_display)
            self.item_map[full_display] = item_key

        options.append("Back")

        # Position to the right of previous menu
        x = self.menus[-1].pos[0] + 250
        y = self.menus[-1].pos[1]

        new_menu = Menu(options, self.font, pos=(x, y), header=category.title())
        self.menus.append(new_menu)

    def open_confirm_menu(self, item_key):
        display_name = item_key.replace('_', ' ').title()

        # Determine category from root menu
        category = self.menus[0].options[self.menus[0].selected].lower()

        if category == "consumables":
            action = "Use"
        else:
            action = "Equip"

        x = self.menus[-1].pos[0] + 250
        y = self.menus[-1].pos[1]

        confirm_menu = Menu(
            ["Yes", "No"],
            self.font,
            pos=(x, y),
            header=f"{action} {display_name}?"
        )

        self.menus.append(confirm_menu)
    
    def handle_item_action(self, item_key):
        category = self.menus[0].options[self.menus[0].selected].lower()

        if category == "weapons":
            return self.equip_weapon(item_key)
        elif category == "armor":
            return self.equip_armor(item_key)
        elif category == "consumables":
            return self.use_consumable(item_key)
        return None

    def equip_weapon(self, item_key):
        # We use player.py's function to ensure all derived stats update
        self.game.player["weapon"] = item_key
        apply_weapon_to_player(self.game.player)
        
        # Update inventory equipped state
        if "equipped" in self.inventory:
            self.inventory["equipped"]["weapon"] = item_key
            
        return f"Equipped {item_key.replace('_', ' ').title()}."

    def equip_armor(self, item_key):
        # We use player.py's function to ensure all derived stats update
        self.game.player["armor"] = item_key
        apply_armor_to_player(self.game.player)

        # Update inventory equipped state
        if "equipped" in self.inventory:
            self.inventory["equipped"]["armor"] = item_key

        return f"Equipped {item_key.replace('_', ' ').title()}."

    def use_consumable(self, item_key):
        consumables = load_consumables()

        if item_key not in consumables:
            return f"{item_key.replace('_', ' ').title()} not found."

        item = consumables[item_key]
        effect = item["effect_type"]
        value = item["value"]
        p = self.game.player

        if effect == "heal":
            p["current_hp"] = min(p.get("max_hp", 10), p.get("current_hp", 0) + value)
        elif effect == "buff_bonus":
            p["bonus"] = p.get("bonus", 0) + value
        elif effect == "buff_attacks":
            p["attack_count"] = p.get("attack_count", 1) + value
        elif effect == "extra_damage":
            p["extra_damage"] = p.get("extra_damage", 0) + value
        elif effect == "restore_mana":
            p["current_mp"] = min(p.get("max_mp", 0), p.get("current_mp", 0) + value)

        # Remove item after use
        if item_key in self.inventory.get("consumable", []):
            self.inventory["consumable"].remove(item_key)

        return f"Used {item.get('name', item_key.replace('_', ' ').title())}."

    def update(self, events):
        # Dialogue takes priority
        if self.dialogue.current_message:
            self.dialogue.update()

            for event in events:
                if event.type == pygame.KEYDOWN:
                    was_typing = self.dialogue.is_typing
                    self.dialogue.handle_event(event)

                    if not was_typing and not self.dialogue.current_message:
                        if self.message_queue:
                            self.start_next_message()
            return

        # Normal menu logic
        active_menu = self.menus[-1]
        for event in events:
            result = active_menu.handle_event(event)
            if result:
                if result == "BACK" and len(self.menus) > 1:
                    self.menus.pop()
                elif result == "BACK" and len(self.menus) == 1:
                    from interfaces.pygame.states.hub import HubState
                    self.game.change_state(HubState(self.game, self.font))
                else:
                    self.handle_selection(result)

    def draw(self, screen):
        # Draw background
        if self.background:
            screen.blit(self.background, (0, 0))
        else:
            screen.fill((30, 30, 30))

        from interfaces.pygame.ui.panel import draw_text_outlined
        from core.game_rules.constants import SCREEN_WIDTH
        
        title_text = "Inventory"
        tw, th = self.font.size(title_text)
        draw_text_outlined(screen, title_text, self.font, (255, 255, 255), (SCREEN_WIDTH // 2) - (tw // 2), 50)
        
        # Draw menus in reverse so the active one is on top (if they overlap)
        # But here they are side by side
        for menu in self.menus:
            menu.draw(screen)
        
        if self.dialogue.current_message:
            self.dialogue.draw(screen)
