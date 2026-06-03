import pygame
import os
from .base_state import BaseState
from ui.menu import Menu
from graphics.backgrounds import BackgroundManager
from ui.panel import draw_text_outlined
from core.game_rules.constants import scale_y, scale_x, COLOR_WHITE, COLOR_GOLD, SCREEN_WIDTH, SCREEN_HEIGHT, FONT_PATH
from core.game_rules.path_utils import get_resource_path

class TitleState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_title_bg()
        
        # Exclude saving from title menu settings
        self.settings_excluded_options = ["Save Game"]
        
        # Use get_resource_path for dynamic banner loading
        banner_path = get_resource_path(os.path.join("assets", "banner", "Banner_noBG.png"))
        try:
            self.banner_img = pygame.image.load(banner_path).convert_alpha()
        except Exception as e:
            print(f"DEBUG: Could not load banner: {e}")
            self.banner_img = None

        # Pre-scale banner to prevent thread-blocking in render loop
        self.banner_scaled = None
        if self.banner_img:
            title_font = self.fonts['title']
            title_text = "V A L O R"
            tw, th = title_font.size(title_text)
            bw = int((tw + scale_x(100)) * 1.53)
            bh = int((th + scale_y(60)) * 3.04)
            self.banner_scaled = pygame.transform.scale(self.banner_img, (bw, bh))

        self.title_alpha = 0
        self.fade_speed = 2
        self.title_pos = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4)
        
        self.menu = Menu(["New Game", "Load Game"], font, width=200, pos=(400, 400))
        self.active_menu = None 
        
        self.state = "FADING" # FADING, PRESS_START, MENU, NAMING
        self.player_name = ""
        self.pulse_time = 0

    def update(self, events, dt):
        if self.state == "FADING":
            self.title_alpha += self.fade_speed
            if self.title_alpha >= 255:
                self.title_alpha = 255
                self.state = "PRESS_START"
        
        elif self.state == "PRESS_START":
            self.pulse_time += 0.05
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        self.state = "MENU"
                        self.active_menu = self.menu
                        return # Consume events and wait for next frame to avoid double-selection
        
        
        
        elif self.state == "NAMING":
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        if self.player_name.strip():
                            # Transition to ClassSelectState with the name
                            from .class_select import ClassSelectState
                            self.game.player_name = self.player_name
                            self.game.change_state(ClassSelectState(self.game, self.fonts), transition_type='growth')
                    elif event.key == pygame.K_BACKSPACE:
                        self.player_name = self.player_name[:-1]
                    elif event.unicode.isalnum() or event.unicode in " _-":
                        if len(self.player_name) < 15:
                            self.player_name += event.unicode
            return # Don't update menu if naming

        super().update(events, dt)

    def on_select(self, option):
        if option == "New Game":
            self.state = "NAMING"
            self.active_menu = None
        elif option == "Load Game":
            from .save_state import SaveState
            self.game.change_state(SaveState(self.game, self.fonts, mode="LOAD"))

    def draw(self, screen):
        self.draw_background(screen)
        self.draw_settings_button(screen)
        
        # Draw "Valor" title with alpha
        title_font = self.fonts['title']
        title_text = "V A L O R"
        tw, th = title_font.size(title_text)
        
        # 🚩 Draw Banner behind title
        if self.banner_scaled:
            bw, bh = self.banner_scaled.get_size()
            
            # Set alpha
            banner_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            banner_surf.blit(self.banner_scaled, (0, 0))
            banner_surf.set_alpha(self.title_alpha)
            
            # Draw with a larger Y offset (scale_y(45)) to sit lower behind text
            screen.blit(banner_surf, (SCREEN_WIDTH // 2 - bw // 2, (SCREEN_HEIGHT // 4 - bh // 2) + scale_y(45)))

        # Pygame surface with alpha for the title
        title_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        # Using white for text, but we need to handle the outline too
        # Simple approach: draw text with alpha
        
        # draw_text_outlined doesn't support alpha easily. 
        # I'll draw it to a surface and then blit the surface with alpha.
        from ui.panel import draw_text_outlined
        # Actually draw_text_outlined draws directly to screen.
        
        # Let's just draw simple text for the fade
        # If I want it outlined, I should create a surface, draw outlined text there, then blit with alpha.
        
        title_surf = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
        draw_text_outlined(title_surf, title_text, title_font, COLOR_WHITE, 5, 5)
        title_surf.set_alpha(self.title_alpha)
        
        screen.blit(title_surf, (SCREEN_WIDTH // 2 - tw // 2, (SCREEN_HEIGHT // 4 - th // 2) + scale_y(20)))

        if self.state == "PRESS_START":
            # Pulsing logic
            import math
            alpha = int(128 + 127 * math.sin(self.pulse_time * 5))
            prompt = "Press ENTER to Start"
            pw, ph = self.fonts['title'].size(prompt)
            
            # Draw pulsing text
            prompt_surf = pygame.Surface((pw + 10, ph + 10), pygame.SRCALPHA)
            draw_text_outlined(prompt_surf, prompt, self.fonts['title'], COLOR_GOLD, 5, 5)
            prompt_surf.set_alpha(alpha)
            screen.blit(prompt_surf, (SCREEN_WIDTH // 2 - pw // 2, SCREEN_HEIGHT * 2 // 3))

        elif self.state == "MENU" and self.active_menu:
            self.active_menu.draw(screen, 400, 400)
            
        elif self.state == "NAMING":
            # Draw name input box
            from ui.panel import Panel
            # Panel expects RAW coordinates (800x600 base)
            from core.game_rules.constants import BASE_WIDTH, BASE_HEIGHT
            panel_w = 400
            panel_h = 100
            panel = Panel(
                BASE_WIDTH // 2 - panel_w // 2, BASE_HEIGHT * 2 // 3 - panel_h // 2,
                panel_w, panel_h,
                bg_color=(30, 30, 50), border_color=COLOR_GOLD, alpha=220
            )
            rect = panel.draw(screen)
            
            # Draw header manually since Panel doesn't support it
            header_text = "Enter Character Name"
            hw, hh = self.font.size(header_text)
            draw_text_outlined(screen, header_text, self.font, COLOR_GOLD, rect.centerx - hw // 2, rect.y + scale_y(10))
            
            # Draw current name
            name_str = self.player_name + "_"
            nw, nh = self.font.size(name_str)
            draw_text_outlined(screen, name_str, self.font, COLOR_WHITE, rect.centerx - nw // 2, rect.y + scale_y(45))
            
            # Prompt
            prompt = "Press ENTER to Confirm"
            pw, ph = self.font.size(prompt)
            draw_text_outlined(screen, prompt, self.font, COLOR_GOLD, rect.centerx - pw // 2, rect.bottom + scale_y(10))
