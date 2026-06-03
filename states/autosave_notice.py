import pygame
import os
from .base_state import BaseState
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD, COLOR_WHITE
from ui.panel import draw_text_outlined
from core.game_rules.path_utils import get_resource_path

class AutoSaveNoticeState(BaseState):
    def __init__(self, game, font, next_state_name="HUB_STATE"):
        super().__init__(game, font)
        self.next_state_name = next_state_name
        self.timer = 4000 # 4 seconds total
        self.min_timer = 1000 # 1 second minimum
        self.transitioning = False
        
        self.stone_image = None
        path = get_resource_path(os.path.join("assets", "sprites", "loot", "trinket.png"))
        if os.path.exists(path):
            try:
                self.stone_image = pygame.image.load(path).convert_alpha()
                # Scaled up version (150x150)
                self.stone_image = pygame.transform.scale(self.stone_image, (scale_x(150), scale_y(150)))
            except: pass

    def update(self, events, dt):
        if self.transitioning:
            return True

        self.timer -= dt
        if self.min_timer > 0:
            self.min_timer -= dt

        if self.timer <= 0:
            self.transition()
            return True

        # Only allow input skip after 1 second
        if self.min_timer <= 0:
            for event in events:
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    self.transition()
                    return True
        return False

    def transition(self):
        if self.transitioning:
            return
        self.transitioning = True
        
        if self.next_state_name == "HUB_STATE":
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.fonts))
        # Add other state routing as needed

    def draw(self, screen):
        screen.fill((0, 0, 0)) # Solid black background
        
        # Draw trinket in center
        if self.stone_image:
            rect = self.stone_image.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - scale_y(50)))
            screen.blit(self.stone_image, rect)
        else:
            # Fallback circle
            pygame.draw.circle(screen, (100, 100, 255), (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - scale_y(50)), scale_x(75))

        # Render text below
        text1 = "This game uses an auto save feature."
        text2 = "Please don't exit while the sending stone is active."
        
        tw1, th1 = self.fonts['medium'].size(text1)
        tw2, th2 = self.fonts['medium'].size(text2)
        
        base_y = SCREEN_HEIGHT // 2 + scale_y(60)
        draw_text_outlined(screen, text1, self.fonts['medium'], COLOR_WHITE, SCREEN_WIDTH // 2 - tw1 // 2, base_y)
        draw_text_outlined(screen, text2, self.fonts['medium'], COLOR_WHITE, SCREEN_WIDTH // 2 - tw2 // 2, base_y + th1 + scale_y(10))
