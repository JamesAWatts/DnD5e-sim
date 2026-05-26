import pygame
import math
from core.game_rules.constants import scale_x, scale_y, COLOR_GOLD, COLOR_WHITE

def draw_cog_icon(screen, rect, color=COLOR_WHITE):
    """
    Draws a stylized settings cog using Pygame primitives.
    """
    center = rect.center
    outer_radius = rect.width // 2
    inner_radius = outer_radius // 2
    hole_radius = outer_radius // 4
    
    # 1. Outer circle (base of teeth)
    pygame.draw.circle(screen, color, center, outer_radius - scale_x(2))
    
    # 2. Draw Teeth (8 spokes)
    num_teeth = 8
    tooth_width = scale_x(4)
    tooth_depth = scale_x(3)
    
    for i in range(num_teeth):
        angle = math.radians(i * (360 / num_teeth))
        
        # Outer edge of tooth
        tx = center[0] + math.cos(angle) * outer_radius
        ty = center[1] + math.sin(angle) * outer_radius
        
        # Tooth is a small rectangle/line at the angle
        # For simplicity and style, we draw a thick line from the outer rim
        start_x = center[0] + math.cos(angle) * (outer_radius - tooth_depth)
        start_y = center[1] + math.sin(angle) * (outer_radius - tooth_depth)
        
        pygame.draw.line(screen, color, (start_x, start_y), (tx, ty), tooth_width)

    # 3. Inner circle (body)
    pygame.draw.circle(screen, color, center, inner_radius + scale_x(2))
    
    # 4. Hole (background color or transparent-ish)
    bg_color = (30, 30, 50) # Matching Panel default
    pygame.draw.circle(screen, bg_color, center, hole_radius)
