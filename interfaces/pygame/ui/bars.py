import pygame

def draw_bar(screen, x, y, w, h, current, max_val, color, font=None, border_radius=8, show_numbers=True, alpha=255):
    from core.game_rules.constants import COLOR_GRAY, COLOR_BLACK, COLOR_GOLD
    ratio = min(1.0, current / max_val) if max_val > 0 else 0

    # Create a temporary surface for the bar to support alpha
    # Use the bounding box size of the bar
    bar_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    
    # Background (Darker grey/black)
    pygame.draw.rect(bar_surf, (40, 40, 40), (0, 0, w, h), border_radius=border_radius)

    # Fill
    if ratio > 0:
        fill_w = int(w * ratio)
        pygame.draw.rect(bar_surf, color, (0, 0, fill_w, h), border_radius=border_radius)

    # Gold Border
    pygame.draw.rect(bar_surf, COLOR_GOLD, (0, 0, w, h), 2, border_radius=border_radius)

    # Blit the finished bar to the main screen
    if alpha < 255:
        bar_surf.set_alpha(alpha)
    screen.blit(bar_surf, (x, y))

    # Numbers (Drawn directly to screen to avoid clipping by bar_surf)
    if font and show_numbers:
        text_str = f"{int(current)} / {int(max_val)}"
        tw, th = font.size(text_str)
        # Center text relative to the bar's x, y, w, h
        tx = x + (w // 2) - (tw // 2)
        ty = y + (h // 2) - (th // 2)
        
        # Use draw_text_outlined if available for maximum contrast, 
        # or simple render if we need to respect the global alpha
        if alpha == 255:
            from interfaces.pygame.ui.panel import draw_text_outlined
            draw_text_outlined(screen, text_str, font, (255, 255, 255), tx, ty)
        else:
            txt = font.render(text_str, True, (255, 255, 255))
            txt.set_alpha(alpha)
            screen.blit(txt, (tx, ty))
