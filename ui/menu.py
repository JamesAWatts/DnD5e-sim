import pygame
from core.game_rules.constants import scale_y, scale_x, COLOR_ROYAL_BLUE, COLOR_GOLD
from ui.panel import Panel

class Menu:
    def __init__(self, options, font, pos=(0, 0), header=None, disabled_indices=None, bg_color=(30, 30, 50), border_color=COLOR_GOLD, alpha=220, width = 100, descriptions=None, initial_selection=0, columns=None, enable_horizontal=True, tooltip_offset_x=5, tooltip_vert_centered=False, line_spacing=5, top_padding=15, bottom_padding=25):
        # Support both single font and multi-font dict
        if isinstance(font, dict):
            self.fonts = font
            self.font = font.get('medium')
        else:
            self.font = font
            self.fonts = {'small': font, 'medium': font, 'large': font, 'xlarge': font}

        self.raw_pos = pos 
        self.header = header
        self.disabled_indices = disabled_indices if disabled_indices is not None else []
        self.bg_color = bg_color
        self.border_color = border_color
        self.alpha = alpha
        self.raw_width = width
        self.descriptions = descriptions
        self.columns = columns
        self.enable_horizontal = enable_horizontal
        self.tooltip_offset_x = tooltip_offset_x
        self.tooltip_vert_centered = tooltip_vert_centered
        self.line_spacing = line_spacing
        self.top_padding = top_padding
        self.bottom_padding = bottom_padding
        
        self.options = options
        self.selected = initial_selection
        self.option_rects = []
        
        self.refresh_layout()

    def set_options(self, options, initial_selection=None):
        self.options = options
        if initial_selection is not None:
            self.selected = initial_selection
        self.refresh_layout()

    def get_raw_width(self):
        return self.raw_width

    def get_raw_rect(self):
        """Returns the menu's rect in 800x600 space."""
        return pygame.Rect(self.panel.raw_x, self.panel.raw_y, self.panel.raw_w, self.panel.raw_h)

    def is_disabled(self, index):
        return index in self.disabled_indices

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP or event.key == pygame.K_w:
                self.selected = (self.selected - 1) % len(self.options)
                while self.is_disabled(self.selected):
                    self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                self.selected = (self.selected + 1) % len(self.options)
                while self.is_disabled(self.selected):
                    self.selected = (self.selected + 1) % len(self.options)
            elif (event.key == pygame.K_LEFT or event.key == pygame.K_a) and self.enable_horizontal:
                if self.columns:
                    col_idx, row_idx = self._get_col_row(self.selected)
                    new_col = (col_idx - 1) % len(self.columns)
                    self.selected = self._get_index_from_col_row(new_col, row_idx)
                    # If the new selection is disabled, keep moving left or just cycle
                    while self.is_disabled(self.selected):
                        new_col = (new_col - 1) % len(self.columns)
                        self.selected = self._get_index_from_col_row(new_col, row_idx)
                else:
                    self.selected = (self.selected - 1) % len(self.options)
                    while self.is_disabled(self.selected):
                        self.selected = (self.selected - 1) % len(self.options)

            elif (event.key == pygame.K_RIGHT or event.key == pygame.K_d) and self.enable_horizontal:
                if self.columns:
                    col_idx, row_idx = self._get_col_row(self.selected)
                    new_col = (col_idx + 1) % len(self.columns)
                    self.selected = self._get_index_from_col_row(new_col, row_idx)
                    while self.is_disabled(self.selected):
                        new_col = (new_col + 1) % len(self.columns)
                        self.selected = self._get_index_from_col_row(new_col, row_idx)
                else:
                    self.selected = (self.selected + 1) % len(self.options)
                    while self.is_disabled(self.selected):
                        self.selected = (self.selected + 1) % len(self.options)

            elif event.key in [pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER]:
                if not self.is_disabled(self.selected):
                    return self.options[self.selected]
        return None

    def _get_col_row(self, index):
        if not self.columns:
            return 0, index
        
        count = 0
        for c_idx, col in enumerate(self.columns):
            if count <= index < count + len(col):
                return c_idx, index - count
            count += len(col)
        return 0, index

    def _get_index_from_col_row(self, col_idx, row_idx):
        if not self.columns:
            return row_idx % len(self.options)
        
        col_idx = col_idx % len(self.columns)
        target_col = self.columns[col_idx]
        
        # Clamp row to available rows in this column
        row_idx = min(row_idx, len(target_col) - 1)
        
        count = 0
        for i in range(col_idx):
            count += len(self.columns[i])
        return count + row_idx

    def handle_mouse(self, mouse_pos, mouse_click):
        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(mouse_pos):
                if not self.is_disabled(i):
                    self.selected = i
                    if mouse_click:
                        return i
        return None

    @staticmethod
    def calculate_raw_width(font, options, header=None):
        """Static helper to estimate menu width before instantiation."""
        from core.game_rules.constants import SCALE_X
        max_w = 0
        for opt in options:
            tw, _ = font.size("> " + str(opt))
            if tw > max_w: max_w = tw
        
        if header:
            tw, _ = font.size(header)
            if tw > max_w: max_w = tw
            
        return (max_w / SCALE_X) + 40

    def refresh_layout(self):
        """Pre-calculates all geometry and panel data."""
        from core.game_rules.constants import scale_y, scale_x
        
        raw_w = self.get_raw_width()
        raw_h = self._calculate_raw_height()
        
        # Anchor Logic (RAW Space)
        raw_x = self.raw_pos[0] - raw_w // 2
        raw_y = self.raw_pos[1] - self.top_padding

        # CLAMPING
        if raw_x < 5: raw_x = 5
        if raw_x + raw_w > 795: raw_x = 795 - raw_w
        if raw_y < 5: raw_y = 5
        if raw_y + raw_h > 595: raw_y = 595 - raw_h

        self.panel = Panel(
            raw_x, raw_y, raw_w, raw_h,
            bg_color=self.bg_color, border_color=self.border_color,
            border_width=3, centered=False, border_radius=15, alpha=self.alpha
        )
        self._rect = self.panel.get_rect()
        self._layout_dirty = False

    def _calculate_raw_height(self):
        from core.game_rules.constants import SCALE_Y
        raw_line_h = self.font.get_height() / SCALE_Y
        raw_spacing = raw_line_h + self.line_spacing
        header_font = self.fonts.get('xlarge')
        raw_header_h = (header_font.get_height() / SCALE_Y + 15) if self.header else 0
        
        if self.columns:
            max_col_len = max(len(col) for col in self.columns)
            return raw_header_h + (max_col_len * raw_spacing) + self.top_padding + self.bottom_padding
        return raw_header_h + (len(self.options) * raw_spacing) + self.top_padding + self.bottom_padding

    def draw(self, screen, raw_center_x=None, raw_start_y=None, force_bottom_desc=False):
        """Renders the pre-calculated menu and options."""
        from core.game_rules.constants import scale_y, scale_x, COLOR_GOLD, SCREEN_WIDTH
        from ui.panel import draw_text_outlined
        
        # If position changed, we might need a refresh, but usually states pass same pos
        rect = self.panel.draw(screen)
        
        self.option_rects = []
        draw_center_x = rect.centerx
        current_y = rect.y + scale_y(self.top_padding)
        
        from core.game_rules.constants import SCALE_Y
        spacing = scale_y(self.font.get_height() / SCALE_Y + self.line_spacing)

        if self.header:
            header_font = self.fonts.get('xlarge')
            tw, th = header_font.size(self.header)
            draw_text_outlined(screen, self.header, header_font, COLOR_GOLD, draw_center_x - tw // 2, current_y)
            current_y += (header_font.get_height() + scale_y(10))
            line_y = current_y - scale_y(5)
            pygame.draw.line(screen, self.border_color, (rect.x + scale_x(10), line_y), (rect.right - scale_x(10), line_y), 2)

        if self.columns:
            option_idx = 0
            current_col_x = rect.x + scale_x(15)
            for col in self.columns:
                max_w = 0
                for opt in col:
                    tw, _ = self.font.size("> " + str(opt))
                    max_w = max(max_w, tw)
                
                for r, option in enumerate(col):
                    color = (255, 255, 0) if option_idx == self.selected else (255, 255, 255)
                    if self.is_disabled(option_idx): color = (150, 150, 150)
                    text_str = ("> " if option_idx == self.selected else "  ") + str(option)
                    self.option_rects.append(draw_text_outlined(screen, text_str, self.font, color, current_col_x, current_y + r * spacing))
                    option_idx += 1
                current_col_x += max_w + scale_x(20)
        else:
            for i, option in enumerate(self.options):
                color = (255, 255, 0) if i == self.selected else (255, 255, 255)
                if self.is_disabled(i): color = (150, 150, 150)
                text_str = ("> " if i == self.selected else "  ") + str(option)
                tw, _ = self.font.size(text_str)
                text_x = draw_center_x - tw // 2
                self.option_rects.append(draw_text_outlined(screen, text_str, self.font, color, text_x, current_y + i * spacing))

        if self.descriptions:
            selected_option = str(self.options[self.selected])
            desc_text = self.descriptions.get(selected_option)
            if desc_text:
                if force_bottom_desc or draw_center_x >= SCREEN_WIDTH // 2:
                    self.draw_description(screen, draw_center_x, rect.bottom + scale_y(10), self.panel.raw_w, desc_text, centered=True)
                else:
                    tx = rect.right + scale_x(self.tooltip_offset_x)
                    ty = rect.centery if self.tooltip_vert_centered else rect.y
                    self.draw_description(screen, tx, ty, 160, desc_text, centered=False, vert_centered=self.tooltip_vert_centered)

        return rect

    def draw_description(self, screen, x, y, raw_w, text, centered=True, vert_centered=False):
        from core.game_rules.constants import SCALE_X, SCALE_Y, scale_y, scale_x
        from ui.panel import draw_text_outlined
        
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
        raw_y = y / SCALE_Y if not vert_centered else (y / SCALE_Y) - raw_h // 2
        
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
