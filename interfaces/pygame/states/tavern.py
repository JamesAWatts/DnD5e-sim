import pygame
import random
from .base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.graphics.backgrounds import BackgroundManager
from interfaces.pygame.ui.panel import draw_text_outlined
from interfaces.pygame.ui.dialogue_box import DialogueBox
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD
from core.players.player import validate_player_data
from core.players.tavern import (
    get_party_level, get_mercenary_starting_level, get_rest_cost, 
    get_hire_cost, get_feast_cost, get_rumor_cost, get_respec_cost,
    apply_rest, apply_feast, get_rumor_info
)

class TavernState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_rest_bg() 

        party = self.game.party
        party_lvl = get_party_level(party)
        
        # Determine start level for Hired Help
        self.hire_level = get_mercenary_starting_level(party_lvl)

        # Calculate costs using core functions
        self.feast_cost = get_feast_cost(party)
        self.rest_cost = get_rest_cost(party)
        self.hire_cost = get_hire_cost(party_lvl)
        self.rumor_cost = get_rumor_cost()
        self.respec_cost = get_respec_cost()

        self.options = []
        if party_lvl >= 1:
            self.options.append(f"Rest ({self.rest_cost} Gold)")
        if party_lvl >= 3:
            self.options.append(f"Hired Help ({self.hire_cost} Gold)")
        if party_lvl >= 11:
            self.options.append(f"Rumors ({self.rumor_cost} Gold)")
        if party_lvl >= 26:
            self.options.append(f"Order Feast ({self.feast_cost} Gold)")
        if party_lvl >= 36:
            self.options.append(f"Training Hall ({self.respec_cost} Gold)")
        
        self.options.append("Back")

        self.menu = Menu(self.options, font, header="The Gilded Flask Tavern")
        self.active_menu = self.menu
        self.menu_state = "MAIN"
        
        self.dialogue = DialogueBox(self.font)
        self.hiring_name = ""
        self.is_typing_name = False

    def on_select(self, option):
        if self.menu_state == "MAIN":
            self.handle_main_menu(option)
        elif self.menu_state == "RESPEC_SELECT":
            if option == "Back":
                self.menu_state = "MAIN"
                self.active_menu = self.menu
            else:
                self.handle_respec(option)

    def handle_main_menu(self, option):
        lead = self.game.player
        inv = lead['inventory_ref']
        party = self.game.party
        party_lvl = get_party_level(party)
        
        if 'tavern_stats' not in lead:
            lead['tavern_stats'] = {'feast_used': False}
        tavern_stats = lead['tavern_stats']

        if option == "Back":
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.font))
            
        elif "Order Feast" in option:
            if tavern_stats['feast_used']:
                self.dialogue.set_messages("You've already feasted! Rest to feast again.")
                return

            if inv['gold'] >= self.feast_cost:
                inv['gold'] -= self.feast_cost
                msg = apply_feast(party, party_lvl)
                tavern_stats['feast_used'] = True
                self.dialogue.set_messages(msg)

        elif "Rest" in option:
            if self.game.god_mode or inv.get("gold", 0) >= self.rest_cost:
                if not self.game.god_mode: inv["gold"] -= self.rest_cost
                msg = apply_rest(self.game)
                self.dialogue.set_messages(msg)

        elif "Hired Help" in option:
            if len(self.game.party) >= 3:
                self.dialogue.set_messages("The party is full!")
                return
            if inv['gold'] >= self.hire_cost:
                self.menu_state = "NAMING"
                self.is_typing_name = True
                self.hiring_name = ""
            else:
                self.dialogue.set_messages(f"Not enough gold! Costs {self.hire_cost} Gold.")

        elif "Rumors" in option:
            if inv['gold'] >= self.rumor_cost:
                inv['gold'] -= self.rumor_cost
                types, encounter = get_rumor_info(self.game)
                self.game.next_encounter = encounter
                
                type_str = ", ".join([t.title() for t in types])
                self.dialogue.set_messages([f"You hear whispers of {type_str} lurking ahead in the next area."])
            else:
                self.dialogue.set_messages(f"Not enough gold for rumors ({self.rumor_cost} Gold).")

        elif "Training Hall" in option:
            self.menu_state = "RESPEC_SELECT"
            self.active_menu = Menu([p['name'] for p in self.game.party] + ["Back"], self.font, header=f"ReSpec Training ({self.respec_cost} Gold)")

    def handle_respec(self, name):
        inv = self.game.inventory
        if inv.get('gold', 0) < self.respec_cost:
            self.dialogue.set_messages("Not enough gold!")
            return

        target = next((p for p in self.game.party if p['name'] == name), None)
        if target:
            inv['gold'] -= self.respec_cost
            # Store XP and name, then reset
            xp = target.get('xp', 0)
            target_name = target['name']
            
            # Remove from party temporarily to recreate
            idx = self.game.party.index(target)
            self.game.party.pop(idx)
            
            # Transition to ClassSelect
            self.game.party_member_name = target_name
            from .class_select import ClassSelectState
            cs = ClassSelectState(self.game, self.font, hiring=True)
            cs.stored_xp = xp # Hack to pass XP back
            self.game.change_state(cs)

    def update(self, events, dt):
        if self.dialogue.current_message:
            self.dialogue.update()
            for event in events:
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    self.dialogue.handle_event(event)
            return

        if self.menu_state == "NAMING":
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        if self.hiring_name.strip():
                            # Pay and move to class select
                            self.game.player['inventory_ref']['gold'] -= self.hire_cost
                            self.game.party_member_name = self.hiring_name.strip()
                            from .class_select import ClassSelectState
                            self.game.change_state(ClassSelectState(self.game, self.font, hiring=True))
                    elif event.key == pygame.K_BACKSPACE:
                        self.hiring_name = self.hiring_name[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        self.menu_state = "MAIN"
                        self.is_typing_name = False
                    else:
                        if len(self.hiring_name) < 15 and event.unicode.isprintable():
                            self.hiring_name += event.unicode
            return

        super().update(events, dt)

    def draw(self, screen):
        self.draw_background(screen)
        self.draw_settings_button(screen)
        width, height = screen.get_size()
        
        if self.menu_state == "NAMING":
            # Draw naming box
            box_w, box_h = scale_x(400), scale_y(150)
            bx, by = (width - box_w) // 2, (height - box_h) // 2
            pygame.draw.rect(screen, (30, 30, 30), (bx, by, box_w, box_h))
            pygame.draw.rect(screen, (200, 200, 200), (bx, by, box_w, box_h), 2)
            
            prompt = "Name your ally:"
            pw, ph = self.font.size(prompt)
            draw_text_outlined(screen, prompt, self.font, (255,255,255), bx + (box_w - pw)//2, by + scale_y(20))
            
            # Draw current typing name
            name_str = self.hiring_name + "_"
            nw, nh = self.font.size(name_str)
            draw_text_outlined(screen, name_str, self.font, (255, 255, 0), bx + (box_w - nw)//2, by + scale_y(70))
            
            instruct = "Press ENTER to confirm, ESC to cancel"
            iw, ih = self.font.size(instruct)
            draw_text_outlined(screen, instruct, self.font, (150, 150, 150), bx + (box_w - iw)//2, by + scale_y(110))
        else:
            self.active_menu.draw(screen, 400, 300)
            
            # Show party size
            party_str = f"Party Size: {len(self.game.party)}/3"
            pw, ph = self.font.size(party_str)
            draw_text_outlined(screen, party_str, self.font, (255,255,255), width // 2 - pw // 2, height // 2 - scale_y(150))
            
            # Show gold
            gold_str = f"Gold: {self.game.player['inventory_ref']['gold']}"
            gw, gh = self.font.size(gold_str)
            draw_text_outlined(screen, gold_str, self.font, COLOR_GOLD, width // 2 - gw // 2, height // 2 - scale_y(110))

        if self.dialogue.current_message:
            self.dialogue.draw(screen)
