import pygame
import math
from core.game_rules.constants import scale_x, scale_y, COLOR_GOLD, COLOR_WHITE, COLOR_GREEN, COLOR_BLUE, COLOR_YELLOW, COLOR_RED
from interfaces.pygame.ui.bars import draw_bar
from interfaces.pygame.ui.panel import draw_text_outlined

class CombatRenderer:
    """
    Handles specialized combat UI rendering tasks.
    """
    def __init__(self, state):
        self.state = state

    def draw_turn_order(self, screen):
        """Displays the name of the current and next actors in a panel with a hover tooltip."""
        if not self.state.current_actor: return
        
        # 1. Prepare Data
        current_name = self.state.current_actor.get('name', 'Unknown')
        next_actor = self.state.turn_queue[1] if len(self.state.turn_queue) > 1 else None
        next_name = next_actor.get('name', 'None') if next_actor else 'None'
        
        # 2. Layout Calculations
        padding = scale_x(10)
        line_spacing = scale_y(25)
        base_x, base_y = scale_x(20), scale_y(20)
        
        cur_text = f"Current: {current_name}"
        nxt_text = f"Next: {next_name}"
        
        # Measure text for panel sizing
        font = self.state.font
        cur_size = font.size(cur_text)
        nxt_size = font.size(nxt_text)
        panel_w = max(cur_size[0], nxt_size[0]) + (padding * 2)
        panel_h = (line_spacing * 2) + (padding * 2) - scale_y(5) # Tight fit
        
        panel_rect = pygame.Rect(base_x, base_y, panel_w, panel_h)
        
        # 3. Draw Panel Background
        bg_surface = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(bg_surface, (30, 30, 50, 200), (0, 0, panel_rect.width, panel_rect.height), border_radius=10)
        pygame.draw.rect(bg_surface, (*COLOR_GOLD, 200), (0, 0, panel_rect.width, panel_rect.height), 2, border_radius=10)
        screen.blit(bg_surface, panel_rect.topleft)
        
        # 4. Draw Text
        draw_text_outlined(screen, cur_text, font, COLOR_GOLD, base_x + padding, base_y + padding)
        draw_text_outlined(screen, nxt_text, font, COLOR_WHITE, base_x + padding, base_y + padding + line_spacing)
        
        # 5. Handle Hover Tooltip
        mouse_pos = pygame.mouse.get_pos()
        if panel_rect.collidepoint(mouse_pos):
            self._draw_turn_tooltip(screen, mouse_pos)

    def _draw_turn_tooltip(self, screen, mouse_pos):
        """Displays the full turn order list when hovering over the turn panel."""
        padding = scale_x(12)
        line_h = scale_y(22)
        font = self.state.font # Or a slightly smaller one if needed
        
        lines = []
        max_w = 0
        for i, actor in enumerate(self.state.turn_queue, 1):
            name = actor.get('name', 'Unknown')
            text = f"{i}-{name}"
            color = COLOR_YELLOW if actor == self.state.current_actor else COLOR_WHITE
            lines.append((text, color))
            
            w = font.size(text)[0]
            if w > max_w: max_w = w
            
        tip_w = max_w + (padding * 2)
        tip_h = (len(lines) * line_h) + (padding * 2)
        
        # Offset from mouse
        tip_x = mouse_pos[0] + scale_x(15)
        tip_y = mouse_pos[1] + scale_y(15)
        
        # Keep on screen
        if tip_x + tip_w > screen.get_width(): tip_x = mouse_pos[0] - tip_w - scale_x(5)
        if tip_y + tip_h > screen.get_height(): tip_y = mouse_pos[1] - tip_h - scale_y(5)
        
        tip_rect = pygame.Rect(tip_x, tip_y, tip_w, tip_h)
        
        # Draw Tooltip Panel
        tip_surf = pygame.Surface((tip_rect.width, tip_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(tip_surf, (20, 20, 30, 240), (0, 0, tip_rect.width, tip_rect.height), border_radius=5)
        pygame.draw.rect(tip_surf, COLOR_GOLD, (0, 0, tip_rect.width, tip_rect.height), 1, border_radius=5)
        screen.blit(tip_surf, tip_rect.topleft)
        
        # Draw Tooltip Lines
        for i, (text, color) in enumerate(lines):
            draw_text_outlined(screen, text, font, color, tip_x + padding, tip_y + padding + (i * line_h))

    def draw_targeting_cursor(self, screen):
        """Renders the grid-based selection cursor and target highlights."""
        gx, gy = self.state.menu_controller.cursor_grid_x, self.state.menu_controller.cursor_grid_y
        if not hasattr(self.state, 'GRID_X'): return
        
        # 1. Pulse Alpha and Color Determination
        time_ms = pygame.time.get_ticks()
        # Max opacity 75% = 191. Range approx 40 to 191.
        alpha = int(115 + math.sin(time_ms * 0.008) * 76)
        
        action_type = self.state.pending_action_data.get('type', 'attack')
        if action_type == 'heal':
            main_color = (50, 255, 50, alpha)
        else:
            main_color = (255, 50, 50, alpha)

        # 2. Draw Highlight Under Cursor Tile
        row_list = self.state.PLAYER_Y if gx < 2 else self.state.ENEMY_Y
        tile_h = (row_list[1] - row_list[0]) if len(row_list) > 1 else scale_y(100)
        
        target_x = self.state.GRID_X[gx]
        safe_y = gy if gy < len(row_list) else len(row_list) - 1
        target_y = row_list[safe_y] + (tile_h // 2)
        
        # Draw a glowing ellipse under the current tile
        cursor_w = scale_x(120)
        cursor_h = scale_y(40)
        cursor_surf = pygame.Surface((cursor_w, cursor_h), pygame.SRCALPHA)
        pygame.draw.ellipse(cursor_surf, main_color, cursor_surf.get_rect())
        pygame.draw.ellipse(cursor_surf, (255, 255, 255, alpha), cursor_surf.get_rect(), 2)
        screen.blit(cursor_surf, (target_x - cursor_w // 2, target_y + scale_y(30)))

        # 3. Draw Highlights Under Affected Targets
        targets = self.state._get_current_target_list()
        for t in targets:
            tgx, tgy = t.get('grid_x'), t.get('grid_y')
            # Skip if it's the current cursor tile (already drawn in Section 2)
            if tgx == gx and tgy == gy: continue
            
            if tgx is not None and tgy is not None:
                # Calculate identical center-point to Section 2
                t_row_list = self.state.PLAYER_Y if tgx < 2 else self.state.ENEMY_Y
                t_tile_h = (t_row_list[1] - t_row_list[0]) if len(t_row_list) > 1 else scale_y(100)
                
                t_target_x = self.state.GRID_X[tgx]
                t_safe_y = tgy if tgy < len(t_row_list) else len(t_row_list) - 1
                t_target_y = t_row_list[t_safe_y] + (t_tile_h // 2)

                t_surf = pygame.Surface((cursor_w, cursor_h), pygame.SRCALPHA)
                pygame.draw.ellipse(t_surf, main_color, t_surf.get_rect())
                pygame.draw.ellipse(t_surf, (255, 255, 255, alpha), t_surf.get_rect(), 2)
                screen.blit(t_surf, (t_target_x - cursor_w // 2, t_target_y + scale_y(30)))

    def draw_debug_placement(self, screen):
        """Overlays grid coordinates on all living combatants for layout verification."""
        all_actors = self.state.party + list(getattr(self.state, 'summons', {}).values()) + self.state.enemies
        for actor in all_actors:
            if actor.get('current_hp', 0) <= 0: continue
            
            v_rect = actor.get('_visual_rect')
            if v_rect:
                gx, gy = actor.get('grid_x', 0), actor.get('grid_y', 0)
                debug_text = f"({gx},{gy})"
                draw_text_outlined(screen, debug_text, self.state.font, (0, 255, 255), v_rect.centerx - scale_x(15), v_rect.top - scale_y(20))

    def draw_entity_bars(self, screen):
        """Renders resource bars (HP/MP/SP) for all living combatants."""
        dimmed_alpha = 128
        target_x, target_y = self.state.menu_controller.cursor_grid_x, self.state.menu_controller.cursor_grid_y
        is_in_targeting = self.state.menu_controller.state.name == "SELECTING_TARGET"

        all_actors = self.state.party + list(getattr(self.state, 'summons', {}).values()) + self.state.enemies
        for entity in all_actors:
            if entity.get('current_hp', 0) <= 0: continue
            
            alpha = 255
            if entity.get('is_enemy', True):
                if is_in_targeting and entity.get('grid_x') == target_x and entity.get('grid_y') == target_y:
                    alpha = 255
                else:
                    alpha = dimmed_alpha

            v_rect = entity.get('_visual_rect')
            bar_w, bar_h, spacing = scale_x(80), scale_y(10), scale_y(2)
            
            if v_rect:
                draw_x = v_rect.centerx - (bar_w // 2)
                current_y = v_rect.top - scale_y(5)
            else:
                pos_x, pos_y = entity.get('screen_pos', (0, 0))
                draw_x, current_y = pos_x - (bar_w // 2), pos_y - scale_y(10)
            
            # Use state.mini_font if available, otherwise fallback to state.font
            bar_font = getattr(self.state, 'mini_font', self.state.font)

            # Calculate total height of the bar stack
            stack_h = bar_h + spacing
            if entity.get('mp') and entity.get('max_mp', 0) > 0: stack_h += bar_h + spacing
            if entity.get('sp') and entity.get('max_sp', 0) > 0: stack_h += bar_h + spacing

            current_y -= stack_h
            
            # 1. HP Bar
            hp_color = COLOR_GREEN if (entity.get('current_hp', 0) / max(1, entity.get('max_hp', 1))) >= 0.25 else COLOR_RED
            draw_bar(screen, draw_x, current_y, bar_w, bar_h, entity.get('current_hp', 0), entity.get('max_hp', 1), hp_color, font=bar_font, show_numbers=True, alpha=alpha)

            # 2. MP Bar
            if entity.get('mp') and entity.get('max_mp', 0) > 0:
                current_y += (bar_h + spacing)
                draw_bar(screen, draw_x, current_y, bar_w, bar_h, entity.get('current_mp', 0), entity.get('max_mp', 1), COLOR_BLUE, font=bar_font, show_numbers=True, alpha=alpha)

            # 3. SP Bar
            if entity.get('sp') and entity.get('max_sp', 0) > 0:
                current_y += (bar_h + spacing)
                draw_bar(screen, draw_x, current_y, bar_w, bar_h, entity.get('current_sp', 0), entity.get('max_sp', 1), COLOR_YELLOW, font=bar_font, show_numbers=True, alpha=alpha)
