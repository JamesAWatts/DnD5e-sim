import pygame
from core.game_rules.constants import COLOR_GOLD

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

    # Numbers (Using optimized draw_text_outlined)
    if font and show_numbers:
        text_str = f"{int(current)} / {int(max_val)}"
        tw, th = font.size(text_str)
        tx = x + (w // 2) - (tw // 2)
        ty = y + (h // 2) - (th // 2)
        
        if alpha == 255:
            from ui.panel import draw_text_outlined
            draw_text_outlined(screen, text_str, font, (255, 255, 255), tx, ty)
        else:
            # For alpha text, we still need to render, but it's rare compared to main bars
            txt = font.render(text_str, True, (255, 255, 255))
            txt.set_alpha(alpha)
            screen.blit(txt, (tx, ty))
