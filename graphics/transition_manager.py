import pygame
import math
import random
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT

class TransitionManager:
    def __init__(self):
        self.phase = 'IDLE' # 'LEADER_FLASH', 'WHITE_FLASH', 'CLOSING', 'OPENING', 'IDLE'
        self.anim_type = 'FADE'
        self.progress = 0.0 # 0.0 to 1.0
        self.duration = 600 # ms
        self.callback = None
        
        # Leader Flash state
        self.flash_count = 0
        self.flash_timer = 0
        self.flash_duration = 100 # ms per flicker
        self.grayscale_surface = None
        self.original_surface = None
        
        self.overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.is_finished = False

    def start_transition(self, is_closing=True, duration=300, callback=None, transition_type='fade'):
        self.phase = 'CLOSING' if is_closing else 'OPENING'
        self.duration = duration
        self.progress = 0.0
        self.callback = callback
        self.is_finished = False
        
        if is_closing:
            if transition_type == 'random':
                self.anim_type = random.choice(['FADE', 'SWEEP', 'SWIRL', 'CURTAIN', 'GROWTH'])
            else:
                self.anim_type = transition_type.upper()
        # If opening, we use the same anim_type that was just used for closing

    def trigger_leader_flash(self, screen_surface, callback=None):
        self.phase = 'LEADER_FLASH'
        self.flash_count = 0
        self.flash_timer = 0
        self.flash_duration = 80 # Fast flicker
        self.callback = callback
        self.is_finished = False
        
        # Capture current screen
        self.original_surface = screen_surface.copy()
        self.grayscale_surface = self._make_grayscale(self.original_surface)

    def _make_grayscale(self, surface):
        """Creates a high-quality grayscale version of the surface."""
        try:
            # Fast native conversion in Pygame 2.1.3+
            return pygame.transform.grayscale(surface.copy())
        except (AttributeError, pygame.error):
            # Fallback using RGBA_MULT (Fastest, though less accurate than weighted RGB)
            gs = surface.copy()
            gs.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            return gs

    def update(self, dt_ms):
        if self.phase == 'IDLE':
            return

        if self.phase == 'LEADER_FLASH':
            self.flash_timer += dt_ms
            if self.flash_timer >= self.flash_duration:
                self.flash_timer = 0
                self.flash_count += 1
                if self.flash_count >= 8: # 4 full flickers (on/off)
                    self.phase = 'WHITE_FLASH'
                    self.flash_timer = 0
                    self.flash_duration = 150 # Duration for white bridge
            return

        if self.phase == 'WHITE_FLASH':
            self.flash_timer += dt_ms
            if self.flash_timer >= self.flash_duration:
                self.phase = 'IDLE'
                if self.callback:
                    self.callback()
            return

        # Handle CLOSING or OPENING
        self.progress += dt_ms / self.duration
        if self.progress >= 1.0:
            self.progress = 1.0
            self.is_finished = True
            p = self.phase
            self.phase = 'IDLE'
            if self.callback:
                self.callback()

    def draw(self, surface):
        if self.phase == 'IDLE':
            return

        if self.phase == 'LEADER_FLASH':
            # Alternate between original and grayscale
            if (self.flash_count // 1) % 2 == 1:
                surface.blit(self.grayscale_surface, (0, 0))
            else:
                surface.blit(self.original_surface, (0, 0))
            return

        if self.phase == 'WHITE_FLASH':
            surface.blit(self.original_surface, (0, 0))
            white = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            white.fill((255, 255, 255, 150)) # Alpha 150
            surface.blit(white, (0, 0))
            return

        # Draw transitions
        p = self.progress
        if self.phase == 'OPENING':
            p = 1.0 - p # Reverse for reveal

        if self.anim_type == 'FADE':
            self._draw_fade(surface, p)
        elif self.anim_type == 'SWEEP':
            self._draw_sweep(surface, p)
        elif self.anim_type == 'SWIRL':
            self._draw_swirl(surface, p)
        elif self.anim_type == 'CURTAIN':
            self._draw_curtain(surface, p)
        elif self.anim_type == 'GROWTH':
            self._draw_growth(surface, p)

    def _draw_fade(self, surface, p):
        alpha = int(255 * p)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(alpha)
        surface.blit(overlay, (0, 0))

    def _draw_sweep(self, surface, p):
        if p <= 0: return
        center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        angle = 360 * p
        radius = math.sqrt(SCREEN_WIDTH**2 + SCREEN_HEIGHT**2)
        
        points = [center]
        points.append((SCREEN_WIDTH // 2, -radius))
        steps = int(angle / 10) + 1
        for i in range(steps + 1):
            curr_angle = min(i * 10, angle)
            rad = math.radians(curr_angle - 90)
            x = center[0] + radius * math.cos(rad)
            y = center[1] + radius * math.sin(rad)
            points.append((x, y))
        pygame.draw.polygon(surface, (0, 0, 0), points)

    def _draw_swirl(self, surface, p):
        if p <= 0: return
        center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        max_radius = math.sqrt(SCREEN_WIDTH**2 + SCREEN_HEIGHT**2)
        radius = max_radius * p
        points = [center]
        steps = 60
        for i in range(steps + 1):
            t = i / steps
            if t > p: break
            curr_rad = max_radius * t
            curr_angle = t * 720
            rad = math.radians(curr_angle - 90)
            x = center[0] + curr_rad * math.cos(rad)
            y = center[1] + curr_rad * math.sin(rad)
            points.append((x, y))
        if len(points) > 2:
            pygame.draw.polygon(surface, (0, 0, 0), points)
            if p > 0.8:
                pygame.draw.circle(surface, (0, 0, 0), center, int(max_radius * (p - 0.5) * 2))

    def _draw_curtain(self, surface, p):
        h = int(SCREEN_HEIGHT * p)
        pygame.draw.rect(surface, (0, 0, 0), (0, 0, SCREEN_WIDTH, h))

    def _draw_growth(self, surface, p):
        center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        max_radius = math.sqrt(SCREEN_WIDTH**2 + SCREEN_HEIGHT**2)
        radius = int(max_radius * p)
        if radius > 0:
            pygame.draw.circle(surface, (0, 0, 0), center, radius)
