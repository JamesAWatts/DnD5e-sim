import pygame
from core.game_rules.constants import scale_y, scale_x, COLOR_ROYAL_BLUE, COLOR_GOLD
from interfaces.pygame.ui.panel import Panel

class Menu:
    def __init__(self, options, font, pos=(0, 0), header=None, disabled_indices=None, bg_color=(30, 30, 50), border_color=COLOR_GOLD, alpha=220, width = 100, descriptions=None, initial_selection=0, columns=None):
        """
        pos = (x, y) in BASE (800x600) coordinates.
        width = BASE (800x600) width.
        columns = Optional list of lists of options to display side-by-side.
        """
        self.font = font
        self.raw_pos = pos 
        self.header = header
        self.disabled_indices = disabled_indices if disabled_indices is not None else []
        self.bg_color = bg_color
        self.border_color = border_color
        self.alpha = alpha
        self.raw_width = width
        self.descriptions = descriptions # Dictionary mapping option text to description string
        self.columns = columns
        self.set_options(options, initial_selection)
        self.option_rects = []

    @staticmethod
    def calculate_raw_width(font, options, header=None, min_width=100):
        """Returns the RAW (unscaled) width needed for the menu options, including padding."""
        max_text_width = 0
        if header:
            hw, _ = font.size(header)
            max_text_width = hw

        for option in options:
            text = "> " + str(option)
            w, _ = font.size(text)
            max_text_width = max(max_text_width, w)
            
        from core.game_rules.constants import SCALE_X
        # Convert screen-space text width back to RAW space
        raw_text_w = max_text_width / SCALE_X
        # Add generous padding for borders and markers (40px)
        return max(raw_text_w + 40, min_width)

    def get_raw_width(self):
        """Returns the RAW (unscaled) width needed for the menu, including padding."""
        if self.columns:
            from core.game_rules.constants import SCALE_X
            total_raw_w = 0
            for col in self.columns:
                max_text_width = 0
                for option in col:
                    text = "> " + str(option)
                    w, _ = self.font.size(text)
                    max_text_width = max(max_text_width, w)
                total_raw_w += (max_text_width / SCALE_X) + 20 # Padding per column
            
            if self.header:
                hw, _ = self.font.size(self.header)
                total_raw_w = max(total_raw_w, hw / SCALE_X + 40)
            
            return max(total_raw_w + 20, self.raw_width) # Extra padding for borders

        return Menu.calculate_raw_width(self.font, self.options, self.header, self.raw_width)

    def get_raw_rect(self):
        """Returns a pygame.Rect in RAW 800x600 space representing the menu area, with clamping."""
        from core.game_rules.constants import SCALE_Y
        raw_w = self.get_raw_width()
        
        raw_line_h = self.font.get_height() / SCALE_Y
        raw_spacing = raw_line_h + 5
        raw_header_h = (raw_line_h + 15) if self.header else 0
        
        if self.columns:
            max_col_len = max(len(col) for col in self.columns)
            raw_h = raw_header_h + (max_col_len * raw_spacing) + 40
        else:
            raw_h = raw_header_h + (len(self.options) * raw_spacing) + 40 # 40 total vertical padding
        
        # Menu.draw uses raw_pos[0] as center_x
        raw_x = self.raw_pos[0] - raw_w // 2
        raw_y = self.raw_pos[1] - 15 # 15 is the top pad used in draw()

        # CLAMPING (must match draw())
        if raw_x < 5: raw_x = 5
        if raw_x + raw_w > 795: raw_x = 795 - raw_w
        if raw_y < 5: raw_y = 5
        if raw_y + raw_h > 595: raw_y = 595 - raw_h
        
        return pygame.Rect(raw_x, raw_y, raw_w, raw_h)

    def set_options(self, options, initial_selection=0):
        self.options = options
        self.selected = initial_selection

    def is_disabled(self, index):
        return index in self.disabled_indices

    def _get_grid_pos(self):
        if not self.columns: return 0, self.selected
        current = 0
        for c, col in enumerate(self.columns):
            for r, opt in enumerate(col):
                if current == self.selected:
                    return c, r
                current += 1
        return 0, 0

    def _set_from_grid_pos(self, col_idx, row_idx):
        if not self.columns:
            self.selected = row_idx
            return
        current = 0
        for c, col in enumerate(self.columns):
            for r, opt in enumerate(col):
                if c == col_idx and r == row_idx:
                    self.selected = current
                    return
                current += 1

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                if self.columns:
                    c, r = self._get_grid_pos()
                    r = (r + 1) % len(self.columns[c])
                    self._set_from_grid_pos(c, r)
                else:
                    self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_UP:
                if self.columns:
                    c, r = self._get_grid_pos()
                    r = (r - 1) % len(self.columns[c])
                    self._set_from_grid_pos(c, r)
                else:
                    self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_LEFT and self.columns:
                c, r = self._get_grid_pos()
                c = (c - 1) % len(self.columns)
                r = min(r, len(self.columns[c]) - 1)
                self._set_from_grid_pos(c, r)
            elif event.key == pygame.K_RIGHT and self.columns:
                c, r = self._get_grid_pos()
                c = (c + 1) % len(self.columns)
                r = min(r, len(self.columns[c]) - 1)
                self._set_from_grid_pos(c, r)
            elif event.key == pygame.K_RETURN:
                if self.is_disabled(self.selected):
                    return None
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
                    if self.is_disabled(i):
                        return None
                    return i 
        return None

    def draw(self, screen, raw_center_x=None, raw_start_y=None, force_bottom_desc=False):
        """
        raw_center_x, raw_start_y = BASE (800x600) coordinates.
        """
        from core.game_rules.constants import SCALE_X, SCALE_Y, scale_y, scale_x, SCREEN_WIDTH, SCREEN_HEIGHT
        
        if raw_center_x is None: raw_center_x = self.raw_pos[0]
        if raw_start_y is None: raw_start_y = self.raw_pos[1]
        
        # --- CALCULATE DIMENSIONS (RAW) ---
        raw_line_h = self.font.get_height() / SCALE_Y
        raw_spacing = raw_line_h + 5
        
        raw_header_h = (raw_line_h + 15) if self.header else 0
        raw_top_pad = 15
        raw_bottom_pad = 25
        
        raw_w = self.get_raw_width()
        
        if self.columns:
            max_col_len = max(len(col) for col in self.columns)
            raw_h = raw_header_h + (max_col_len * raw_spacing) + raw_top_pad + raw_bottom_pad
        else:
            raw_h = raw_header_h + (len(self.options) * raw_spacing) + raw_top_pad + raw_bottom_pad

        # Anchor Logic (RAW Space)
        raw_x = raw_center_x - raw_w // 2
        raw_y = raw_start_y - raw_top_pad

        # --- CLAMPING (RAW Space 800x600) ---
        if raw_x < 5: raw_x = 5
        if raw_x + raw_w > 795: raw_x = 795 - raw_w
        if raw_y < 5: raw_y = 5
        if raw_y + raw_h > 595: raw_y = 595 - raw_h

        panel = Panel(
            raw_x, raw_y, raw_w, raw_h,
            bg_color=self.bg_color, border_color=self.border_color,
            border_width=3, centered=False, border_radius=15, alpha=self.alpha
        )
        rect = panel.draw(screen) 
        
        self.option_rects = []
        from interfaces.pygame.ui.panel import draw_text_outlined
        
        # Draw Content (Screen Space from rect)
        draw_center_x = rect.centerx
        # We must use scaled versions of raw_top_pad and raw_spacing for screen-space Y
        current_y = rect.y + scale_y(raw_top_pad)
        line_h = self.font.get_height()
        spacing = scale_y(raw_spacing)
        
        if self.header:
            tw, th = self.font.size(self.header)
            draw_text_outlined(screen, self.header, self.font, COLOR_GOLD, draw_center_x - tw // 2, current_y)
            current_y += (line_h + scale_y(10))
            
            line_y = current_y - scale_y(5)
            pygame.draw.line(screen, self.border_color, (rect.x + scale_x(10), line_y), (rect.right - scale_x(10), line_y), 2)

        if self.columns:
            # Calculate column widths (Screen Space)
            scaled_col_widths = []
            for col in self.columns:
                max_w = 0
                for opt in col:
                    tw, th = self.font.size("> " + str(opt))
                    max_w = max(max_w, tw)
                scaled_col_widths.append(max_w + scale_x(20))
            
            option_idx = 0
            current_col_x = rect.x + scale_x(15)
            for c, col in enumerate(self.columns):
                col_y = current_y
                for r, option in enumerate(col):
                    color = (255, 255, 0) if option_idx == self.selected else (255, 255, 255)
                    if self.is_disabled(option_idx): color = (150, 150, 150)

                    text_str = ("> " if option_idx == self.selected else "  ") + str(option)
                    text_y = col_y + r * spacing
                    self.option_rects.append(draw_text_outlined(screen, text_str, self.font, color, current_col_x, text_y))
                    option_idx += 1
                current_col_x += scaled_col_widths[c]
        else:
            for i, option in enumerate(self.options):
                color = (255, 255, 0) if i == self.selected else (255, 255, 255)
                if self.is_disabled(i): color = (150, 150, 150)

                text_str = ("> " if i == self.selected else "  ") + str(option)
                tw, th = self.font.size(text_str)
                text_x = draw_center_x - tw // 2
                text_y = current_y + i * spacing
                self.option_rects.append(draw_text_outlined(screen, text_str, self.font, color, text_x, text_y))

        # --- Tooltip ---
        if self.descriptions:
            selected_option = str(self.options[self.selected])
            desc_text = self.descriptions.get(selected_option)
            if desc_text:
                if force_bottom_desc:
                    self.draw_description(screen, draw_center_x, rect.bottom + scale_y(10), raw_w, desc_text, centered=True)
                elif draw_center_x < SCREEN_WIDTH // 2:
                    self.draw_description(screen, rect.right + scale_x(5), rect.y, 160, desc_text, centered=False)
                else:
                    self.draw_description(screen, draw_center_x, rect.bottom + scale_y(10), raw_w, desc_text, centered=True)

    def draw_description(self, screen, x, y, raw_w, text, centered=True):
        from core.game_rules.constants import SCALE_X, SCALE_Y, scale_y, scale_x
        from interfaces.pygame.ui.panel import draw_text_outlined
        
        scaled_w = raw_w * SCALE_X
        words = str(text).split(' ')
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            tw, th = self.font.size(test_line)
            if tw > scaled_w - scale_x(20):
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        lines.append(' '.join(current_line))
        
        raw_line_h = self.font.get_height() / SCALE_Y
        raw_spacing = raw_line_h + 2
        raw_h = (len(lines) * raw_spacing) + 30
        
        raw_x = x / SCALE_X if not centered else (x / SCALE_X) - raw_w // 2
        raw_y = y / SCALE_Y
        
        # Clamp Tooltip (Raw 800x600)
        if raw_x < 5: raw_x = 5
        if raw_x + raw_w > 795: raw_x = 795 - raw_w
        if raw_y + raw_h > 595: raw_y = 595 - raw_h
        
        panel = Panel(
            raw_x, raw_y, raw_w, raw_h,
            bg_color=(20, 20, 40), border_color=COLOR_GOLD, border_width=2,
            centered=False, border_radius=10, alpha=230
        )
        rect = panel.draw(screen)
        
        spacing = scale_y(raw_spacing)
        for i, line in enumerate(lines):
            lw, lh = self.font.size(line)
            draw_text_outlined(screen, line, self.font, (220, 220, 220), rect.centerx - lw // 2, rect.y + scale_y(15) + i * spacing)
