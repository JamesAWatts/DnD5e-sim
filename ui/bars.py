import pygame
from core.game_rules.constants import COLOR_GOLD

# Wasm Optimization: Module-level cache for bar text
_bar_text_cache = {}

def draw_bar(screen, x, y, w, h, current, max_val, color, font=None, border_radius=8, show_numbers=True, alpha=255):
    """Renders a progress bar with optional alpha and numeric text."""
    ratio = min(1.0, current / max_val) if max_val > 0 else 0

    # Draw Background (direct to screen if no alpha, else use a temporary surface)
    # Note: Frequent Surface allocations for small bars are still costly on web, 
    # but much better than full-screen allocations.
    if alpha < 255:
        bar_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Background
        pygame.draw.rect(bar_surf, (40, 40, 40, alpha), (0, 0, w, h), border_radius=border_radius)
        # Fill
        if ratio > 0:
            fill_w = int(w * ratio)
            pygame.draw.rect(bar_surf, (*color, alpha), (0, 0, fill_w, h), border_radius=border_radius)
        # Border
        pygame.draw.rect(bar_surf, (*COLOR_GOLD, alpha), (0, 0, w, h), 2, border_radius=border_radius)
        screen.blit(bar_surf, (x, y))
    else:
        # Background
        pygame.draw.rect(screen, (40, 40, 40), (x, y, w, h), border_radius=border_radius)
        # Fill
        if ratio > 0:
            fill_w = int(w * ratio)
            pygame.draw.rect(screen, color, (x, y, fill_w, h), border_radius=border_radius)
        # Border
        pygame.draw.rect(screen, COLOR_GOLD, (x, y, w, h), 2, border_radius=border_radius)

    # Numbers (Using optimized dictionary cache)
    if font and show_numbers:
        text_str = f"{int(current)} / {int(max_val)}"
        cache_key = (text_str, id(font))
        
        if cache_key not in _bar_text_cache:
            from ui.panel import draw_text_outlined
            tw, th = font.size(text_str)
            # Create a transparent surface with some padding for the outline
            surf = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
            draw_text_outlined(surf, text_str, font, (255, 255, 255), 5, 5)
            _bar_text_cache[cache_key] = surf

        cached_surf = _bar_text_cache[cache_key]
        tw, th = cached_surf.get_size()
        tx = x + (w // 2) - (tw // 2)
        ty = y + (h // 2) - (th // 2)
        
        if alpha == 255:
            screen.blit(cached_surf, (tx, ty))
        else:
            # For alpha text, we still use the cached surface but adjust alpha
            cached_surf.set_alpha(alpha)
            screen.blit(cached_surf, (tx, ty))

