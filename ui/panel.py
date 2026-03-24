import pygame
from constants import scale_x, scale_y

def draw_text_outlined(screen, text, font, color, x, y, outline_color=(0,0,0), outline_width=2):
    """Draws text with a simple outline for readability."""
    # Draw outline in 4-8 directions
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0: continue
            outline_surf = font.render(text, True, outline_color)
            screen.blit(outline_surf, (x + dx, y + dy))

    # Draw main text
    main_surf = font.render(text, True, color)
    screen.blit(main_surf, (x, y))
    return main_surf.get_rect(topleft=(x, y))

class Panel:
    def __init__(
        self,
        x,
        y,
        width,
        height,
        bg_color=(40, 40, 40),
        border_color=(255, 255, 255),
        border_width=2,
        padding=10,
        centered=False,
        border_radius=10,
        alpha=255
    ):
        """
        x, y = position (or center if centered=True)
        width, height = panel size (base resolution values, will be scaled)
        """
        self.x = x
        self.y = y
        self.width = scale_x(width)
        self.height = scale_y(height)

        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width
        self.border_radius = scale_y(border_radius)

        self.padding = scale_x(padding)
        self.centered = centered
        self.alpha = alpha

    def get_rect(self):
        if self.centered:
            return pygame.Rect(
                self.x - self.width // 2,
                self.y,
                self.width,
                self.height
            )
        else:
            return pygame.Rect(self.x, self.y, self.width, self.height)

    def draw(self, screen):
        rect = self.get_rect()
        
        if self.alpha < 255:
            # Create a surface for transparency
            temp_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            temp_rect = pygame.Rect(0, 0, self.width, self.height)
            
            # Background
            pygame.draw.rect(temp_surface, (*self.bg_color, self.alpha), temp_rect, border_radius=self.border_radius)
            
            # Border
            pygame.draw.rect(temp_surface, (*self.border_color, self.alpha), temp_rect, self.border_width, border_radius=self.border_radius)
            
            screen.blit(temp_surface, rect.topleft)
        else:
            # Background
            pygame.draw.rect(screen, self.bg_color, rect, border_radius=self.border_radius)

            # Border
            pygame.draw.rect(screen, self.border_color, rect, self.border_width, border_radius=self.border_radius)

        return rect  # useful for aligning text inside

    def draw_text(self, screen, text, font, color=(255,255,255), center=False, y_offset=0):
        rect = self.get_rect()

        # Measure first for centering
        text_size = font.size(text)

        if center:
            text_x = rect.centerx - text_size[0] // 2
        else:
            text_x = rect.x + self.padding

        text_y = rect.y + self.padding + scale_y(y_offset)

        return draw_text_outlined(screen, text, font, color, text_x, text_y)