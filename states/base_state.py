import pygame
from ui.panel import Panel
from ui.icons import draw_cog_icon

class BaseState:
    def __init__(self, game, font):
        self.game = game
        
        # Support both single font (backward compatibility) and multi-font dict
        if isinstance(font, dict):
            self.fonts = font
            self.font = font.get('medium')
        else:
            self.font = font
            self.fonts = {'small': font, 'medium': font, 'large': font, 'xlarge': font}
            
        self.active_menu = None
        self.background = None
        
        # Settings Button Panel (Top Right)
        # Anchor at 760, 10 (base 800x600). Size 30x30.
        self.settings_panel = Panel(760, 10, 28, 34, padding=0, border_radius=5)
        
        # Options to exclude when this state opens Settings
        self.settings_excluded_options = []

    def update(self, events, dt):
        # 1. Global Settings Check (Cog click or F1)
        if self.handle_settings_input(events):
            return True

        if not self.active_menu:
            return False

        # Handle all input (keyboard and mouse) via the menu's own event handling
        mouse_motion_event = None
        for event in events:
            if not self.active_menu:
                break
            
            # 1. Keyboard Navigation & Selection
            result = self.active_menu.handle_event(event)
            if result:
                self.on_select(result)
                return True

            # 2. Mouse Selection (Clicks)
            if event.type == pygame.MOUSEBUTTONDOWN:
                selection_idx = self.active_menu.handle_mouse(event.pos, True)
                if selection_idx is not None:
                    option = self.active_menu.options[selection_idx]
                    self.on_select(option)
                    return True
            
            # 3. Mouse Navigation (Motion) - Store only the latest
            if event.type == pygame.MOUSEMOTION:
                mouse_motion_event = event

        # Process the latest mouse motion once per frame
        if mouse_motion_event:
            self.active_menu.handle_mouse(mouse_motion_event.pos, False)

        return False

    def handle_settings_input(self, events):
        """Checks for settings button click or hotkey. Returns True if handled."""
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.settings_panel.get_rect().collidepoint(event.pos):
                    self.open_settings()
                    return True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                self.open_settings()
                return True
        return False

    def open_settings(self):
        """Transitions to the SettingsState."""
        from .settings_state import SettingsState
        self.game.change_state(SettingsState(self.game, self.fonts, previous_state=self, excluded_options=self.settings_excluded_options))

    def on_select(self, option):
        raise NotImplementedError

    def draw_background(self, screen):
        """Renders the background image if it exists."""
        if self.background:
            screen.blit(self.background, (0, 0))

    def draw_settings_button(self, screen):
        """Draws the settings cog button in the top right."""
        from core.game_rules.constants import scale_x, scale_y
        s_rect = self.settings_panel.draw(screen)
        
        # Center a 20x20 (base) cog in the 30x30 (base) panel
        cog_w, cog_h = scale_x(20), scale_y(20)
        cog_rect = pygame.Rect(0, 0, cog_w, cog_h)
        cog_rect.center = s_rect.center
        draw_cog_icon(screen, cog_rect)

    def draw(self, screen):
        """
        Default draw: renders background, settings button, then centers active menu.
        """
        self.draw_background(screen)
        self.draw_settings_button(screen)

        if self.active_menu:
            width, height = screen.get_size()
            self.active_menu.draw(screen, width // 2, height // 3)