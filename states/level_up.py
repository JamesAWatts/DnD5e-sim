import pygame
import os
from states.base_state import BaseState
from ui.menu import Menu
from graphics.backgrounds import BackgroundManager
from ui.inventory_panel import InventoryPanel
from core.players.leveler import load_player_classes, add_class_level
from core.players.player import load_weapons, load_armor, load_shields, load_trinkets
from core.game_rules.constants import COLOR_BG, COLOR_LIGHT_GRAY, SCREEN_WIDTH, scale_x, scale_y

class LevelUpState(BaseState):
    def __init__(self, game, font, player=None, is_dev_mode=False):
        super().__init__(game, font)
        self.is_dev_mode = is_dev_mode
        self.mode = "CLASS_SELECT"
        
        # Current player being leveled
        self.player = player if player else self.game.player

        # Use manager to pick random background
        self.background = BackgroundManager.get_levelup_bg()

        # Load data for inventory panel
        weapons_db = load_weapons()
        armor_db = load_armor()
        shields_db = load_shields()
        trinkets_db = load_trinkets()
        self.inventory_panel = InventoryPanel(self.fonts, weapons_db, armor_db, shields_db, trinkets_db)

        # Wasm Optimization: Caching
        self.cached_title = None
        self._last_selected_class = None
        self._cached_desc_surf = None

        self.refresh_class_menu()

    def _render_title_cache(self):
        from ui.panel import draw_text_outlined
        title_text = f"Level Up: {self.player.get('name', 'Adventurer')}!"
        tw, th = self.fonts['xlarge'].size(title_text)
        self.cached_title = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
        draw_text_outlined(self.cached_title, title_text, self.fonts['xlarge'], (255, 255, 0), 5, 5)

    def _render_desc_cache(self, text):
        from ui.panel import draw_text_outlined
        # Panel Dimensions (Matches Menu.draw_description defaults)
        raw_w = 200
        from core.game_rules.constants import SCALE_X, SCALE_Y, scale_x, scale_y
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
        from core.game_rules.constants import COLOR_GOLD
        panel = Panel(0, 0, raw_w, total_h / SCALE_Y, bg_color=(20, 20, 40), border_color=COLOR_GOLD, border_width=2, centered=False, border_radius=10, alpha=230)
        panel.draw(surf)
        
        for i, line in enumerate(lines):
            lw, _ = self.fonts['medium'].size(line)
            draw_text_outlined(surf, line, self.fonts['medium'], (220, 220, 220), scaled_w // 2 - lw // 2, scale_y(15) + i * (line_h + spacing))
            
        self._cached_desc_surf = surf

    def refresh_class_menu(self):
        self.class_names = [name.title() for name in load_player_classes().keys()]
        
        from core.players.leveler import get_level_up_benefits
        descriptions = {}
        for name in self.class_names:
            descriptions[name] = get_level_up_benefits(self.player, name)

        # Determine default selection - use the player's highest level class
        initial_selection = 0
        player_class_levels = self.player.get('class_levels', {})
        if player_class_levels:
            # Find the class with the highest level
            max_level = 0
            primary_class = None
            for class_name, level in player_class_levels.items():
                if level > max_level:
                    max_level = level
                    primary_class = class_name
            
            if primary_class:
                # Find the index of this class in our menu options
                primary_class_title = primary_class.title()
                if primary_class_title in self.class_names:
                    initial_selection = self.class_names.index(primary_class_title)

        # 25% transparent means 75% opacity, alpha = 255 * 0.75 = 191
        self.menu = Menu(self.class_names, self.fonts, bg_color=COLOR_BG, border_color=COLOR_LIGHT_GRAY, alpha=191, width=200, descriptions=descriptions, initial_selection=initial_selection, pos=(150, 150))
        self.menu.font = self.fonts['medium']
        self.active_menu = self.menu

    def on_select(self, option):
        if self.mode == "CLASS_SELECT":
            add_class_level(self.player, option.lower())
            
            # If dev mode and not max level, ask to level up again
            if self.is_dev_mode and self.player.get('level', 1) < 20:
                self.mode = "AGAIN_PROMPT"
                self.active_menu = Menu(["Yes", "No"], self.fonts['medium'], header="Level up again?")
            else:
                self.finish_level_up()
                
        elif self.mode == "AGAIN_PROMPT":
            if option == "Yes":
                self.mode = "CLASS_SELECT"
                self.refresh_class_menu()
            else:
                self.finish_level_up()

    def finish_level_up(self):
        # Check if anyone else needs to level up
        from core.players.leveler import needs_level_up
        next_player = None
        for p in self.game.party:
            if needs_level_up(p):
                next_player = p
                break
        
        if next_player:
            # Re-init this state with the next player
            self.game.change_state(LevelUpState(self.game, self.fonts, player=next_player, is_dev_mode=self.is_dev_mode))
        else:
            from states.hub import HubState
            self.game.change_state(HubState(self.game, self.fonts))

    def update(self, events, dt):
        super().update(events, dt)

    def draw(self, screen):
        # Draw background manually to avoid super().draw() centering the menu
        self.draw_background(screen)

        # 1. Title (Cached)
        if not self.cached_title:
            self._render_title_cache()
        screen.blit(self.cached_title, (SCREEN_WIDTH // 2 - self.cached_title.get_width() // 2, 50 - 5))

        # 2. Menu and Description
        if self.active_menu:
            # Tell menu not to draw built-in description so we can use our cached one
            orig_desc = self.active_menu.descriptions
            self.active_menu.descriptions = None
            rect = self.active_menu.draw(screen, 150, 150)
            self.active_menu.descriptions = orig_desc
            
            # Tracker-based description caching
            if orig_desc:
                selected_opt = self.active_menu.options[self.active_menu.selected]
                if selected_opt != self._last_selected_class:
                    desc_text = orig_desc.get(selected_opt, "")
                    self._render_desc_cache(desc_text)
                    self._last_selected_class = selected_opt
                
                if self._cached_desc_surf:
                    screen.blit(self._cached_desc_surf, (rect.centerx - self._cached_desc_surf.get_width() // 2, rect.bottom + scale_y(10)))

        # 3. Draw Player Info Panel (on the right)
        self.inventory_panel.draw(screen, self.player)
        self.inventory_panel.draw_tooltip(screen)

