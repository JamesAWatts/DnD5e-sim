import pygame
from collections import deque
from core.game_rules.constants import scale_x, scale_y

class DebugOverlay:
    def __init__(self, font_size=18, max_lines=12):
        pygame.font.init()
        # Try to use a fixed-width font for better alignment, fallback to default
        try:
            self.font = pygame.font.SysFont("consolas", font_size)
        except:
            self.font = pygame.font.SysFont(None, font_size)
        
        self.visible = False
        self.padding = scale_x(10)
        self.line_height = font_size + scale_y(2)
        
        # Store recent logs
        self.logs = deque(maxlen=max_lines)
        
        # Live values
        self.data = {}

    def toggle(self):
        self.visible = not self.visible

    def log(self, message):
        self.logs.appendleft(message)

    def set(self, key, value):
        self.data[key] = value

    def clear_frame_data(self):
        """Call this each frame if you want transient values"""
        self.data = {}

    def draw(self, surface, game=None):
        if not self.visible:
            return
        
        x, y = self.padding, self.padding
        
        # Background box
        width = scale_x(420)
        height = scale_y(400)
        bg_rect = pygame.Rect(x - 5, y - 5, width, height)
        
        # Draw semi-transparent background (if surface supports it, otherwise solid)
        # For simplicity in this engine, we'll stick to a dark solid or high-alpha black
        pygame.draw.rect(surface, (10, 10, 10), bg_rect)
        pygame.draw.rect(surface, (0, 255, 0), bg_rect, 1) # Green border
        
        # --- System Info ---
        if game and game.state:
            self.set("State", type(game.state).__name__)

        # --- Live Data ---
        for key, value in self.data.items():
            text = f"{key}: {value}"
            surf = self.font.render(text, True, (0, 255, 0))
            surface.blit(surf, (x, y))
            y += self.line_height
        
        y += scale_y(10)
        pygame.draw.line(surface, (0, 100, 0), (x, y), (x + width - scale_x(20), y))
        y += scale_y(10)
        
        # --- Logs ---
        for log in self.logs:
            color = (255, 255, 255)
            if "FAIL" in log or "Missed" in log:
                color = (255, 100, 100)
            elif "Hit" in log or "resisted" in log:
                color = (100, 255, 100)
            
            surf = self.font.render(log, True, color)
            surface.blit(surf, (x, y))
            y += self.line_height
