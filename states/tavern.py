import pygame
import random
from .base_state import BaseState
from ui.menu import Menu
from graphics.backgrounds import BackgroundManager
from ui.panel import draw_text_outlined
from ui.dialogue_box import DialogueBox
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
        if party_lvl >= 10:
            self.options.append(f"Rumors ({self.rumor_cost} Gold)")
        if party_lvl >= 25:
            self.options.append(f"Order Feast ({self.feast_cost} Gold)")
        if party_lvl >= 35:
            self.options.append(f"Training Hall ({self.respec_cost} Gold)")
        
        self.options.append("Back")

        # Create descriptions for the menu options
        self.descriptions = {
            f"Rest ({self.rest_cost} Gold)": "Fully recover HP, MP, and SP. Resting also resets any daily buffs.",
            f"Hired Help ({self.hire_cost} Gold)": "A mercinary joins your party, price varies with skill.",
            f"Rumors ({self.rumor_cost} Gold)": "Learn what foes await you next.",
            f"Order Feast ({self.feast_cost} Gold)": "Enjoy a well-earned feast. Recover your HP, SP, MP, and gain a small buff.",
            f"Training Hall ({self.respec_cost} Gold)": "Send a party member in for a re-spec, reselecting their class levels."
        }

        # Create a modified font dict to reduce header size for this menu
        tavern_fonts = self.fonts.copy()
        tavern_fonts['xlarge'] = self.fonts['large']
        
        # Move menu left by 100px and align tooltips (matching shop)
        self.menu = Menu(self.options, tavern_fonts, header="The Gilded Flask Tavern", pos=(300, 300), width=280, 
                         descriptions=self.descriptions, tooltip_offset_x=105, tooltip_vert_centered=True)
        self.active_menu = self.menu
        self.menu_state = "MAIN"
        
        self.dialogue = DialogueBox(self.fonts['large'])
        self.hiring_name = ""
        self.is_typing_name = False

        # Wasm Optimization: Caching
        self._cached_prompt = None
        self._cached_instruct = None
        self._cached_party_str = None
        self._last_party_count = -1
        
        self._last_hiring_name = None
        self._cached_name_surf = None
        
        self._last_gold_tavern = -1
        self._cached_gold_surf_tavern = None
        
        self._render_static_cache_tavern()

    def _render_static_cache_tavern(self):
        """Pre-renders static strings for the tavern."""
        # Prompt
        prompt = "Name your ally:"
        pw, ph = self.fonts['medium'].size(prompt)
        self._cached_prompt = pygame.Surface((pw + 10, ph + 10), pygame.SRCALPHA)
        draw_text_outlined(self._cached_prompt, prompt, self.fonts['medium'], (255,255,255), 5, 5)
        
        # Instruct
        instruct = "Press ENTER to confirm, ESC to cancel"
        iw, ih = self.fonts['small'].size(instruct)
        self._cached_instruct = pygame.Surface((iw + 10, ih + 10), pygame.SRCALPHA)
        draw_text_outlined(self._cached_instruct, instruct, self.fonts['small'], (150, 150, 150), 5, 5)

    def _render_party_cache(self, count):
        """Pre-renders the party size indicator."""
        party_str = f"Party Size: {count}/3"
        pw, ph = self.fonts['xlarge'].size(party_str)
        self._cached_party_str = pygame.Surface((pw + 10, ph + 10), pygame.SRCALPHA)
        draw_text_outlined(self._cached_party_str, party_str, self.fonts['xlarge'], (255,255,255), 5, 5)

    def _render_gold_cache_tavern(self, gold):
        """Pre-renders the player gold amount."""
        gold_str = f"Gold: {gold}"
        gw, gh = self.fonts['xlarge'].size(gold_str)
        self._cached_gold_surf_tavern = pygame.Surface((gw + 10, gh + 10), pygame.SRCALPHA)
        draw_text_outlined(self._cached_gold_surf_tavern, gold_str, self.fonts['xlarge'], COLOR_GOLD, 5, 5)

    def _render_name_cache(self, name):
        """Pre-renders the character name being typed."""
        name_str = name + "_"
        nw, nh = self.fonts['medium'].size(name_str)
        self._cached_name_surf = pygame.Surface((nw + 10, nh + 10), pygame.SRCALPHA)
        draw_text_outlined(self._cached_name_surf, name_str, self.fonts['medium'], (255, 255, 0), 5, 5)

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
            self.game.change_state(HubState(self.game, self.fonts))
            
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
            self.active_menu = Menu([p['name'] for p in self.game.party] + ["Back"], self.fonts['medium'], header=f"ReSpec Training ({self.respec_cost} Gold)", pos=(400, 300), width=280)

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
            cs = ClassSelectState(self.game, self.fonts, hiring=True)
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
                            self.game.change_state(ClassSelectState(self.game, self.fonts, hiring=True))
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
            
            # Use cached prompt
            if self._cached_prompt:
                screen.blit(self._cached_prompt, (bx + (box_w - self._cached_prompt.get_width()) // 2, by + scale_y(20) - 5))
            
            # Tracker-based Cache for name input
            if self.hiring_name != self._last_hiring_name:
                self._render_name_cache(self.hiring_name)
                self._last_hiring_name = self.hiring_name
            
            if self._cached_name_surf:
                screen.blit(self._cached_name_surf, (bx + (box_w - self._cached_name_surf.get_width()) // 2, by + scale_y(70) - 5))
            
            # Use cached instructions
            if self._cached_instruct:
                screen.blit(self._cached_instruct, (bx + (box_w - self._cached_instruct.get_width()) // 2, by + scale_y(110) - 5))
        else:
            self.active_menu.draw(screen)
            
            # Show party size (Conditional Cache)
            party_count = len(self.game.party)
            if party_count != self._last_party_count:
                self._render_party_cache(party_count)
                self._last_party_count = party_count
                
            if self._cached_party_str:
                screen.blit(self._cached_party_str, (width // 2 - self._cached_party_str.get_width() // 2, height // 2 - scale_y(150) - 5))
            
            # Show gold (Tracker-based Cache)
            gold_val = self.game.player['inventory_ref']['gold']
            if gold_val != self._last_gold_tavern:
                self._render_gold_cache_tavern(gold_val)
                self._last_gold_tavern = gold_val
                
            if self._cached_gold_surf_tavern:
                screen.blit(self._cached_gold_surf_tavern, (width // 2 - self._cached_gold_surf_tavern.get_width() // 2, height // 2 - scale_y(110) - 5))

        if self.dialogue.current_message:
            self.dialogue.draw(screen)
