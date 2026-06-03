import pygame
import asyncio
from .base_state import BaseState
from ui.menu import Menu
from graphics.backgrounds import BackgroundManager
from ui.panel import draw_text_outlined
from core.game_rules.save_manager import SaveManager
from core.game_rules.constants import scale_y, scale_x, COLOR_WHITE, COLOR_GOLD

class SaveState(BaseState):
    def __init__(self, game, font, mode="SAVE"):
        super().__init__(game, font)
        self.mode = mode # "SAVE" or "LOAD"
        self.background = BackgroundManager.get_rest_bg()
        
        self.slots = [1, 2, 3]
        self.slot_options = [SaveManager.get_slot_info(s) for s in self.slots]
        self.slot_options.append("Back")
        
        header = "Save Game" if mode == "SAVE" else "Load Game"
        self.menu = Menu(self.slot_options, self.fonts['medium'], header=header, width=300, pos=(400, 300))
        self.active_menu = self.menu
        
        self.confirm_menu = None
        self.selected_slot = None

    def on_select(self, option):
        if self.confirm_menu:
            if option == "Yes":
                if self.mode == "SAVE":
                    # Save currently selected party and global inventory
                    asyncio.create_task(SaveManager.save_game_async(self.selected_slot, self.game.party, self.game.inventory, self.game.battle_counter, self.game.bestiary_rp))
                    print(f"Game saved to slot {self.selected_slot}")
                else: # LOAD
                    data = SaveManager.load_game_data(self.selected_slot)
                    if data:
                        party_data = SaveManager.load_game(self.selected_slot)
                        self.game.party = party_data
                        self.game.battle_counter = data.get("battle_counter", 0)
                        self.game.bestiary_rp = data.get("bestiary_rp", {})
                        
                        # Set the global inventory to the reference shared by the party
                        if self.game.party:
                            self.game.inventory = self.game.party[0].get('inventory_ref', {})
                        
                        # Store current slot for autosave
                        self.game.current_save_slot = self.selected_slot
                        
                        from .autosave_notice import AutoSaveNoticeState
                        self.game.change_state(AutoSaveNoticeState(self.game, self.fonts))
                        return # Exit early after loading
                
                # Back to main slot menu after saving
                self.confirm_menu = None
                self.active_menu = self.menu
                self.refresh_slots()
            else: # No
                self.confirm_menu = None
                self.active_menu = self.menu
        else:
            if option == "Back":
                if self.mode == "SAVE":
                    from .hub import HubState
                    self.game.change_state(HubState(self.game, self.fonts))
                else: # From Title
                    from .title import TitleState
                    self.game.change_state(TitleState(self.game, self.fonts))
            else:
                # Find the index in our original options list to know which slot was chosen
                idx = -1
                for i, s_opt in enumerate(self.slot_options):
                    if s_opt == option:
                        idx = i
                        break

                if idx != -1 and idx < len(self.slots):
                    self.selected_slot = self.slots[idx]
                    
                    if self.mode == "LOAD" and SaveManager.load_game(self.selected_slot) is None:
                        # Cannot load an empty slot
                        return
                        
                    confirm_text = f"Overwrite Slot {self.selected_slot}?" if self.mode == "SAVE" else f"Load Slot {self.selected_slot}?"
                    self.confirm_menu = Menu(["Yes", "No"], self.fonts['medium'], header=confirm_text, width=200, pos=(400, 300))
                    self.active_menu = self.confirm_menu

    def refresh_slots(self):
        self.slot_options = [SaveManager.get_slot_info(s) for s in self.slots]
        self.slot_options.append("Back")
        self.menu.set_options(self.slot_options)

    def handle_settings_input(self, events):
        """Override to prevent opening settings while in the save menu."""
        return False

    def update(self, events, dt):
        super().update(events, dt)

    def draw(self, screen):
        self.draw_background(screen)
        
        # Center active menu (Base 400, 300)
        if self.active_menu:
            self.active_menu.draw(screen, 400, 300)

        title_str = "Save / Load"
        tw, th = self.fonts['xlarge'].size(title_str)
        # SCREEN_WIDTH // 2 is fine for simple horizontal centering of text
        from core.game_rules.constants import SCREEN_WIDTH
        draw_text_outlined(screen, title_str, self.fonts['xlarge'], COLOR_WHITE, SCREEN_WIDTH // 2 - tw // 2, scale_y(50))
