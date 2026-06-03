import pygame
import os
from core.game_rules.path_utils import get_resource_path
from core.game_rules.constants import scale_x, scale_y, COLOR_GOLD, SCREEN_WIDTH

class SaveIndicator:
    def __init__(self, font=None):
        self.raw_image = None
        path = get_resource_path(os.path.join("assets", "sprites", "loot", "trinket.png"))
        if os.path.exists(path):
            try:
                self.raw_image = pygame.image.load(path).convert_alpha()
                # Enlarge to 80x80
                self.raw_image = pygame.transform.scale(self.raw_image, (scale_x(80), scale_y(80)))
            except Exception as e:
                print(f"[UI] Failed to load trinket.png: {e}")
        
        self.alpha = 0
        self.timer = 0
        self.stay_duration = 2000  # 2 seconds
        self.fade_duration = 1000  # 1 second
        self.total_duration = self.stay_duration + self.fade_duration
        self.active = False

    def trigger(self):
        self.timer = self.total_duration
        self.alpha = 255
        self.active = True

    def update(self, dt):
        if not self.active:
            return

        self.timer -= dt
        if self.timer <= 0:
            self.timer = 0
            self.alpha = 0
            self.active = False
        elif self.timer > self.fade_duration:
            # During the stay phase
            self.alpha = 255
        else:
            # During the fade phase
            self.alpha = int((self.timer / self.fade_duration) * 255)

    def draw(self, screen):
        if not self.active or self.alpha <= 0:
            return

        # Anchor to Top-Left corner (20, 20)
        pos = (scale_x(20), scale_y(20))
        
        if self.raw_image:
            # Create a copy to adjust alpha
            temp_surface = self.raw_image.copy()
            temp_surface.set_alpha(self.alpha)
            screen.blit(temp_surface, pos)
        else:
            # Fallback: Drawn circle (Enlarged)
            surf = pygame.Surface((scale_x(80), scale_y(80)), pygame.SRCALPHA)
            pygame.draw.circle(surf, (200, 200, 255, self.alpha), (scale_x(40), scale_y(40)), scale_x(30))
            pygame.draw.circle(surf, (100, 100, 255, self.alpha), (scale_x(40), scale_y(40)), scale_x(20))
            screen.blit(surf, pos)
