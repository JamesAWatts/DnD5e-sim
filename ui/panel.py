import pygame
from core.game_rules.constants import scale_x, scale_y, COLOR_GOLD

def draw_text_outlined(screen, text, font, color, x, y, outline_color=(0,0,0), outline_width=2):
    """Draws text with a simple outline for readability."""
    # Pre-render the surfaces to avoid multiple renders in loops
    outline_surf = font.render(text, True, outline_color)
    main_surf = font.render(text, True, color)
    
    # Draw outline in 4 diagonal directions (sufficient for 2px outline)
    offsets = [(-outline_width, -outline_width), (outline_width, -outline_width), 
               (-outline_width, outline_width), (outline_width, outline_width)]
    
    for dx, dy in offsets:
        screen.blit(outline_surf, (x + dx, y + dy))

    # Draw main text
    screen.blit(main_surf, (x, y))
    return main_surf.get_rect(topleft=(x, y))

class Panel:
    def __init__(
        self,
        x,
        y,
        width,
        height,
        bg_color=(30, 30, 50),
        border_color=COLOR_GOLD,
        border_width=2,
        padding=10,
        centered=False,
        border_radius=10,
        alpha=220
    ):
        """
        x, y = base resolution position (will be scaled)
        width, height = base resolution size (will be scaled)
        """
        self.raw_x = x
        self.raw_y = y
        self.raw_w = width
        self.raw_h = height

        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.border_radius = scale_y(border_radius)

        self.padding = scale_x(padding)
        self.centered = centered
        self.alpha = alpha

    @property
    def rect(self):
        return self.get_rect()

    def get_rect(self):
        # Scale EVERYTHING consistently
        sx, sy = scale_x(self.raw_x), scale_y(self.raw_y)
        sw, sh = scale_x(self.raw_w), scale_y(self.raw_h)

        if self.centered:
            return pygame.Rect(sx - sw // 2, sy, sw, sh)
        else:
            return pygame.Rect(sx, sy, sw, sh)

    def draw(self, screen):
        rect = self.get_rect()
        
        if self.alpha < 255:
            temp_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            temp_rect = pygame.Rect(0, 0, rect.width, rect.height)
            
            pygame.draw.rect(temp_surface, (*self.bg_color, self.alpha), temp_rect, border_radius=self.border_radius)
            pygame.draw.rect(temp_surface, (*self.border_color, self.alpha), temp_rect, self.border_width, border_radius=self.border_radius)
            
            screen.blit(temp_surface, rect.topleft)
        else:
            pygame.draw.rect(screen, self.bg_color, rect, border_radius=self.border_radius)
            pygame.draw.rect(screen, self.border_color, rect, self.border_width, border_radius=self.border_radius)

        return rect

    def draw_text(self, screen, text, font, color=(255,255,255), center=False, y_offset=0):
        rect = self.get_rect()
        text_size = font.size(text)

        if center:
            text_x = rect.centerx - text_size[0] // 2
        else:
            text_x = rect.x + self.padding

        text_y = rect.y + self.padding + scale_y(y_offset)
        return draw_text_outlined(screen, text, font, color, text_x, text_y)
