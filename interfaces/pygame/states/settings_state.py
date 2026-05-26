import pygame
from .base_state import BaseState
from ui.menu import Menu
from ui.panel import Panel, draw_text_outlined
from core.game_rules.constants import (
    scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, 
    COLOR_WHITE, COLOR_GOLD, COLOR_RED, COLOR_MIDNIGHT_BLUE
)

class SettingsState(BaseState):
    def __init__(self, game, font, previous_state=None, excluded_options=None):
        super().__init__(game, font)
        self.previous_state = previous_state
        self.excluded_options = excluded_options or []
        
        # UI Elements
        self.menu = Menu(["Music: On", "Exit Game", "Back"], font, width=200)
        self.active_menu = self.menu
        self.refresh_menu_text()
        
        # Volume Slider Settings
        self.slider_rect = pygame.Rect(SCREEN_WIDTH // 2 - scale_x(150), SCREEN_HEIGHT // 2, scale_x(300), scale_y(10))
        self.thumb_radius = scale_y(10)
        self.is_dragging = False

    def refresh_menu_text(self):
        """Updates the menu text to show current settings."""
        music_status = "Off" if self.game.music_manager.is_muted else "On"
        all_options = [f"Music: {music_status}", "Save Game", "Exit Game", "Back"]
        
        # Filter based on keywords in excluded_options
        new_options = []
        for opt in all_options:
            is_excluded = False
            for excl in self.excluded_options:
                if excl.lower() in opt.lower():
                    is_excluded = True
                    break
            if not is_excluded:
                new_options.append(opt)
                
        self.menu.set_options(new_options)

    def update(self, events, dt):
        mouse_pos = pygame.mouse.get_pos()
        
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Check for slider click
                thumb_x = self.slider_rect.x + (self.game.music_manager.volume * self.slider_rect.width)
                thumb_rect = pygame.Rect(thumb_x - self.thumb_radius, self.slider_rect.centery - self.thumb_radius, 
                                        self.thumb_radius * 2, self.thumb_radius * 2)
                
                if thumb_rect.collidepoint(mouse_pos) or self.slider_rect.inflate(0, 20).collidepoint(mouse_pos):
                    self.is_dragging = True
                    self.update_volume_from_mouse(mouse_pos[0])
            
            elif event.type == pygame.MOUSEBUTTONUP:
                self.is_dragging = False
            
            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                self.update_volume_from_mouse(mouse_pos[0])

        super().update(events, dt)

    def update_volume_from_mouse(self, mx):
        """Calculates volume based on mouse X position relative to slider."""
        rel_x = mx - self.slider_rect.x
        new_vol = rel_x / self.slider_rect.width
        self.game.music_manager.set_volume(new_vol)

    def handle_settings_input(self, events):
        """Override to prevent opening settings while already in settings."""
        return False

    def on_select(self, option):
        if "Music:" in option:
            self.game.music_manager.toggle_mute()
            self.refresh_menu_text()
        elif option == "Save Game":
            from .save_state import SaveState
            self.game.change_state(SaveState(self.game, self.font, mode="SAVE"))
        elif option == "Back":
            if self.previous_state:
                self.game.change_state(self.previous_state)
            else:
                from .title import TitleState
                self.game.change_state(TitleState(self.game, self.font))
        elif option == "Exit Game":
            self.game.quit()

    def draw(self, screen):
        # Background
        screen.fill((20, 20, 40))
        
        # Header
        draw_text_outlined(screen, "Settings", self.font, COLOR_GOLD, SCREEN_WIDTH // 2 - 50, scale_y(50))
        
        # Slider Label
        vol_percent = int(self.game.music_manager.volume * 100)
        draw_text_outlined(screen, f"Music Volume: {vol_percent}%", self.font, COLOR_WHITE, 
                          SCREEN_WIDTH // 2 - 100, self.slider_rect.y - scale_y(40))
        
        # Draw Slider Track
        pygame.draw.rect(screen, (100, 100, 100), self.slider_rect)
        pygame.draw.rect(screen, COLOR_GOLD, (self.slider_rect.x, self.slider_rect.y, 
                                             self.game.music_manager.volume * self.slider_rect.width, 
                                             self.slider_rect.height))
        
        # Draw Slider Thumb
        thumb_x = int(self.slider_rect.x + (self.game.music_manager.volume * self.slider_rect.width))
        pygame.draw.circle(screen, COLOR_WHITE, (thumb_x, self.slider_rect.centery), self.thumb_radius)
        
        # Menu (Below Slider - Base 400, 450)
        if self.active_menu:
            self.active_menu.draw(screen, 400, 450)
