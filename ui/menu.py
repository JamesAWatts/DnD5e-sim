import pygame
from constants import scale_y, scale_x, COLOR_ROYAL_BLUE, COLOR_GOLD
from game.ui.panel import Panel

class Menu:
    def __init__(self, options, font, disabled_indices=None, bg_color=COLOR_ROYAL_BLUE, border_color=COLOR_GOLD, alpha=255, width = 100):
        self.font = font
        self.disabled_indices = disabled_indices if disabled_indices is not None else []
        self.bg_color = bg_color
        self.border_color = border_color
        self.alpha = alpha
        self.width = width
        self.set_options(options)
        self.option_rects = []

    def get_width(self):
        from constants import scale_x
        max_text_width = 0
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

    # --- Calculate panel size ---
    def draw(self, screen, center_x, start_y):
        spacing = scale_y(30)

        # --- Auto-size based on longest option ---
        max_text_width = 0
        for option in self.options:
            text = "> " + str(option)
            w, _ = self.font.size(text)
            if w > max_text_width:
                max_text_width = w

        base_width = max(max_text_width + scale_x(60), self.width)

        base_height = (len(self.options) * 30) + 20

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

        # --- Draw options ---
        from game.ui.panel import draw_text_outlined
        for i, option in enumerate(self.options):
            if self.is_disabled(i):
                color = (150, 150, 150) # Light grey
            elif i == self.selected:
                color = (255, 255, 0) # Gold/Yellow
            else:
                color = (255, 255, 255) # White

            prefix = "> " if i == self.selected else "  "
            text_str = prefix + str(option)

            # Measure to center
            tw, th = self.font.size(text_str)
            text_x = center_x - tw // 2
            text_y = start_y + i * spacing

            rect_opt = draw_text_outlined(screen, text_str, self.font, color, text_x, text_y)

            self.option_rects.append(rect_opt)