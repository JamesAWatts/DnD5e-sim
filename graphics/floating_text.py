import pygame
import random
from core.game_rules.constants import scale_x, scale_y, FONT_PATH
from core.game_rules.path_utils import get_resource_path

class FloatingText:
    def __init__(self, text, pos, color=(255, 255, 255), lifetime=120, rise_speed=1.0, font_size=24, delay=0):
        # Initialize font if not already done
        if not pygame.font.get_init():
            pygame.font.init()
            
        self.font = pygame.font.Font(get_resource_path(FONT_PATH), scale_y(font_size))
        self.font.set_bold(True)
            
        self.text = text
        self.x, self.y = pos
        
        # Add slight horizontal randomness (juice)
        self.x += random.randint(scale_x(-20), scale_x(20))
        
        self.color = color
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.delay = delay
        
        self.rise_speed = rise_speed * scale_y(1)
        self.alpha = 255

    def update(self):
        if self.delay > 0:
            self.delay -= 1
            return

        self.y -= self.rise_speed
        self.rise_speed += 0.02 # Slight acceleration
        self.lifetime -= 1
        
        # Fade out
        self.alpha = int(255 * (self.lifetime / self.max_lifetime))

    def draw(self, surface):
        if self.delay > 0 or self.alpha <= 0:
            return
            
        surf = self.font.render(self.text, True, self.color)
        
        # Create a copy with alpha support for fading
        temp_surf = surf.convert_alpha()
        temp_surf.fill((255, 255, 255, self.alpha), special_flags=pygame.BLEND_RGBA_MULT)
        
        surface.blit(temp_surf, (self.x, self.y))

    def is_alive(self):
        return self.lifetime > 0 or self.delay > 0


class FloatingTextManager:
    def __init__(self, font=None):
        self.texts = []
        self.font = font
        self.COLORS = {
            "hit": (255, 255, 255),
            "miss": (255, 255, 0),       # Yellow
            "fail": (150, 0, 255),       # Purple (debuff failed save)
            "save": (255, 255, 0),       # Yellow (resisted)
            "crit": (255, 50, 50),       # Red
            "damage": (255, 255, 255),   # White (for standard)
            "heal": (0, 255, 0),         # Green
            "debuff": (150, 0, 255),     # Purple
            "buff": (255, 165, 0),       # Orange
            "resource": (0, 255, 255),   # Cyan (MP/SP)
            "mana": (0, 255, 255),       # Cyan
            "stamina": (0, 255, 255)     # Cyan
        }

    def add(self, text, pos, color_key="hit", lifetime=120, rise_speed=1.2, delay=0):
        color = self.COLORS.get(color_key, (255, 255, 255))
        # Support passing direct color tuples too
        if isinstance(color_key, tuple):
            color = color_key
            
        self.texts.append(FloatingText(text, pos, color, lifetime, rise_speed, delay=delay))

    def update(self):
        for t in self.texts:
            t.update()
        self.texts = [t for t in self.texts if t.is_alive()]

    def draw(self, surface):
        for t in self.texts:
            t.draw(surface)

    def is_busy(self):
        """Returns True if there are active floating texts being displayed."""
        return len(self.texts) > 0
