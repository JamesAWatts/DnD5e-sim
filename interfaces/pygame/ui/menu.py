import pygame
from core.game_rules.constants import scale_y, scale_x, COLOR_ROYAL_BLUE, COLOR_GOLD
from interfaces.pygame.ui.panel import Panel

class Menu:
    def __init__(self, options, font, pos=(0, 0), header=None, disabled_indices=None, bg_color=COLOR_ROYAL_BLUE, border_color=COLOR_GOLD, alpha=255, width = 100):
        self.font = font
        self.pos = pos
        self.header = header
        self.disabled_indices = disabled_indices if disabled_indices is not None else []
        self.bg_color = bg_color
        self.border_color = border_color
        self.alpha = alpha
        self.width = width
        self.set_options(options)
        self.option_rects = []

    def get_width(self):
        from core.game_rules.constants import scale_x
        max_text_width = 0
        
        # Check header width
        if self.header:
            hw, _ = self.font.size(self.header)
            max_text_width = hw

        # Check options width
        for option in self.options:
            text = "> " + str(option)
            w, _ = self.font.size(text)
            max_text_width = max(max_text_width, w)
            
        return max(max_text_width + scale_x(60), self.width)

    def set_options(self, options):
        self.options = options
        self.selected = 0

    def is_disabled(self, index):
        return index in self.disabled_indices

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_RETURN:
                return self.options[self.selected]
            elif event.key == pygame.K_BACKSPACE:
                return "BACK"
        return None

    def handle_mouse(self, mouse_pos, mouse_click):
        if not self.option_rects:
            return None

        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(mouse_pos):
                self.selected = i  
                if mouse_click:
                    return i 
        return None

    def draw(self, screen, center_x=None, start_y=None):
        if center_x is None:
            center_x = self.pos[0]
        if start_y is None:
            start_y = self.pos[1]

        spacing = scale_y(30)
        
        # --- Auto-size based on longest element ---
        max_text_width = 0
        if self.header:
            hw, _ = self.font.size(self.header)
            max_text_width = hw
            
        for option in self.options:
            text = "> " + str(option)
            w, _ = self.font.size(text)
            if w > max_text_width:
                max_text_width = w

        base_width = max(max_text_width + scale_x(60), self.width)
        
        # Extra height for header
        header_height = scale_y(40) if self.header else 0
        base_height = (len(self.options) * 30) + 20 + (40 if self.header else 0)

        panel = Panel(
            center_x,
            start_y - scale_y(10),
            base_width,
            base_height,
            bg_color=self.bg_color,
            border_color=self.border_color,
            border_width=3,
            centered=True,
            border_radius=15,
            alpha=self.alpha
        )

        rect = panel.draw(screen)
        self.option_rects = []
        from interfaces.pygame.ui.panel import draw_text_outlined
        
        current_y = start_y
        
        # --- Draw Header ---
        if self.header:
            tw, th = self.font.size(self.header)
            draw_text_outlined(screen, self.header, self.font, COLOR_GOLD, center_x - tw // 2, current_y)
            current_y += header_height
            
            # Draw a small separator line under header
            line_y = current_y - scale_y(5)
            line_width = base_width - scale_x(20)
            pygame.draw.line(screen, self.border_color, 
                             (center_x - line_width//2, line_y), 
                             (center_x + line_width//2, line_y), 2)

        # --- Draw options ---
        for i, option in enumerate(self.options):
            if self.is_disabled(i):
                color = (150, 150, 150) # Light grey
            elif i == self.selected:
                color = (255, 255, 0) # Gold/Yellow
            else:
                color = (255, 255, 255) # White

            prefix = "> " if i == self.selected else "  "
            text_str = prefix + str(option)

            tw, th = self.font.size(text_str)
            text_x = center_x - tw // 2
            text_y = current_y + i * spacing

            rect_opt = draw_text_outlined(screen, text_str, self.font, color, text_x, text_y)
            self.option_rects.append(rect_opt)