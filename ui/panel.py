import pygame
from core.game_rules.constants import scale_x, scale_y, COLOR_GOLD

# Global cache for rendered text surfaces to prevent redundant font.render() calls
_TEXT_CACHE = {}

def draw_text_outlined(screen, text, font, color, x, y, outline_color=(0,0,0), outline_width=2):
    """Draws text with a simple outline, using a surface cache for performance."""
    cache_key = (text, id(font), color, outline_color, outline_width)
    
    if cache_key not in _TEXT_CACHE:
        # Render main text and outline once
        outline_surf = font.render(text, True, outline_color)
        main_surf = font.render(text, True, color)
        
        # Create a combined surface for the outlined text
        w, h = main_surf.get_size()
        # Add 2px margin for the outline
        combined_surf = pygame.Surface((w + outline_width * 2, h + outline_width * 2), pygame.SRCALPHA)
        
        # Draw outline in 4 diagonal directions
        offsets = [(-outline_width, -outline_width), (outline_width, -outline_width), 
                   (-outline_width, outline_width), (outline_width, outline_width)]
        for dx, dy in offsets:
            combined_surf.blit(outline_surf, (outline_width + dx, outline_width + dy))
        
        # Draw main text over outline
        combined_surf.blit(main_surf, (outline_width, outline_width))
        _TEXT_CACHE[cache_key] = combined_surf

    text_surf = _TEXT_CACHE[cache_key]
    # Adjust for the outline margin when blitting
    screen.blit(text_surf, (x - outline_width, y - outline_width))
    return pygame.Rect(x, y, text_surf.get_width() - outline_width * 2, text_surf.get_height() - outline_width * 2)

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
        
        # Pre-calculate the scaled rect and cached surface
        self._rect = self.get_rect()
        self._cached_surface = self._pre_render()

    def _pre_render(self):
        """Creates a static surface for the panel to avoid drawing every frame."""
        w, h = self._rect.width, self._rect.height
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        temp_rect = pygame.Rect(0, 0, w, h)
        
        pygame.draw.rect(surf, (*self.bg_color, self.alpha), temp_rect, border_radius=self.border_radius)
        pygame.draw.rect(surf, (*self.border_color, self.alpha), temp_rect, self.border_width, border_radius=self.border_radius)
        return surf

    def get_rect(self):
        sx, sy = scale_x(self.raw_x), scale_y(self.raw_y)
        sw, sh = scale_x(self.raw_w), scale_y(self.raw_h)
        if self.centered:
            return pygame.Rect(sx - sw // 2, sy, sw, sh)
        return pygame.Rect(sx, sy, sw, sh)

    def draw(self, screen):
        screen.blit(self._cached_surface, self._rect.topleft)
        return self._rect

    def draw_text(self, screen, text, font, color=(255,255,255), center=False, y_offset=0):
        text_size = font.size(text)
        if center:
            text_x = self._rect.centerx - text_size[0] // 2
        else:
            text_x = self._rect.x + self.padding
        text_y = self._rect.y + self.padding + scale_y(y_offset)
        return draw_text_outlined(screen, text, font, color, text_x, text_y)
