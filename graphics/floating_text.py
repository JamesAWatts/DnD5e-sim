import pygame
import random
from core.game_rules.constants import scale_x, scale_y, FONT_PATH
from core.game_rules.path_utils import get_resource_path

# Wasm Optimization: Module-level cache for floating text surfaces
_floating_text_cache = {}

class FloatingText:
    def __init__(self, text, pos, color=(255, 255, 255), lifetime=120, rise_speed=1.0, font=None, delay=0, is_crit=False):
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
        self.is_crit = is_crit

        # Pre-render or retrieve from cache
        if font:
            # For crits, we cache the WHITE version to allow dynamic tinting
            render_color = (255, 255, 255) if self.is_crit else self.color
            cache_key = (self.text, render_color, id(font))
            
            if cache_key not in _floating_text_cache:
                _floating_text_cache[cache_key] = font.render(self.text, True, render_color)
            self.base_surf = _floating_text_cache[cache_key]
        else:
            # Fallback if no font provided
            self.base_surf = pygame.Surface((1,1))

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
            
        if self.is_crit:
            # Dynamic Flashing: Red -> Bright Red -> White
            import math
            time_ms = pygame.time.get_ticks()
            # Pulse between 0 and 255
            pulse = int(127 + 127 * math.sin(time_ms * 0.015))
            # Resulting color: (255, pulse, pulse) 
            # 0   -> (255, 0, 0) Red
            # 128 -> (255, 128, 128) Bright Red
            # 255 -> (255, 255, 255) White
            
            # Create a tinted copy (fast for small text surfaces)
            tinted_surf = self.base_surf.copy()
            tinted_surf.fill((255, pulse, pulse, 255), special_flags=pygame.BLEND_RGBA_MULT)
            tinted_surf.set_alpha(self.alpha)
            surface.blit(tinted_surf, (self.x, self.y))
        else:
            # Standard optimization: Use set_alpha on pre-rendered surface
            self.base_surf.set_alpha(self.alpha)
            surface.blit(self.base_surf, (self.x, self.y))

    def is_alive(self):
        return self.lifetime > 0 or self.delay > 0


class FloatingTextManager:
    def __init__(self, font=None):
        self.texts = []
        self.font = font
        # If no font provided, load the default shared one
        if not self.font:
            if not pygame.font.get_init():
                pygame.font.init()
            self.font = pygame.font.Font(get_resource_path(FONT_PATH), scale_y(24))
            self.font.set_bold(True)

        self._text_cache = {}
        self.COLORS = {
            "hit": (255, 255, 255),
            "miss": (255, 255, 255),     # White
            "fail": (150, 0, 255),       # Purple (debuff failed save)
            "save": (255, 255, 255),     # White
            "crit": (255, 50, 50),       # Base Crit Color (Red)
            "damage": (255, 0, 0),       # Red
            "heal": (0, 255, 0),         # Green
            "effect": (255, 255, 0),     # Yellow
            "debuff": (150, 0, 255),     # Purple
            "buff": (255, 165, 0),       # Orange
            "resource": (0, 255, 255),   # Cyan (MP/SP)
            "mana": (0, 255, 255),       # Cyan
            "stamina": (0, 255, 255)     # Cyan
        }

    def add(self, text, pos, color_key="hit", lifetime=120, rise_speed=1.2, delay=0):
        color = self.COLORS.get(color_key, (255, 255, 255))
        is_crit = (color_key == "crit")
        
        # Support passing direct color tuples too
        if isinstance(color_key, tuple):
            color = color_key
            
        self.texts.append(FloatingText(text, pos, color, lifetime, rise_speed, font=self.font, delay=delay, is_crit=is_crit))

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
