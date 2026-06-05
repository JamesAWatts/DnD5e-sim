import pygame
import math
from core.game_rules.constants import scale_x, scale_y, COLOR_GOLD, COLOR_WHITE, COLOR_GREEN, COLOR_BLUE, COLOR_YELLOW, COLOR_RED, SCALE_X, SCALE_Y
from ui.bars import draw_bar
from ui.panel import Panel, draw_text_outlined

class CombatRenderer:
    def __init__(self, state):
        self.state = state
        self.hovered_effects_actor = None
        self.hovered_effects_rect = None
        
        # Wasm Optimization: Text Cache
        self._text_cache = {}

        # Pre-render targeting cursors
        self.cursor_w = scale_x(120)
        self.cursor_h = scale_y(40)
        self.cursor_surf_base = pygame.Surface((self.cursor_w, self.cursor_h), pygame.SRCALPHA)
        # We'll create red and green versions
        self.cursor_red = self.cursor_surf_base.copy()
        self.cursor_green = self.cursor_surf_base.copy()
        
        pygame.draw.ellipse(self.cursor_red, (255, 50, 50), self.cursor_red.get_rect())
        pygame.draw.ellipse(self.cursor_red, (255, 255, 255), self.cursor_red.get_rect(), 2)
        
        pygame.draw.ellipse(self.cursor_green, (50, 255, 50), self.cursor_green.get_rect())
        pygame.draw.ellipse(self.cursor_green, (255, 255, 255), self.cursor_green.get_rect(), 2)

    def _get_cached_text(self, text, font, color):
        """Retrieves or renders a text surface from cache."""
        # Using id(font) as part of key to handle different font sizes
        cache_key = f"{text}_{id(font)}_{color}"
        if cache_key not in self._text_cache:
            tw, th = font.size(text)
            surf = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
            draw_text_outlined(surf, text, font, color, 5, 5)
            self._text_cache[cache_key] = surf
        return self._text_cache[cache_key]

    def draw_turn_order(self, screen):
        """Displays the turn order using optimized Panel and text cache."""
        if not self.state.current_actor: return
        
        # 1. Prepare Data
        current_name = self.state.current_actor.get('name', 'Unknown')
        next_actor = self.state.turn_queue[1] if len(self.state.turn_queue) > 1 else None
        next_name = next_actor.get('name', 'None') if next_actor else 'None'
        
        # 2. Layout
        padding = scale_x(10)
        line_spacing = scale_y(25)
        base_x, base_y = scale_x(10), scale_y(10)
        
        cur_text = f"Current: {current_name}"
        nxt_text = f"Next: {next_name}"
        
        font = self.state.font
        
        # Use Cached Surfaces
        cur_surf = self._get_cached_text(cur_text, font, COLOR_GOLD)
        nxt_surf = self._get_cached_text(nxt_text, font, COLOR_WHITE)
        
        panel_w_raw = max(cur_surf.get_width(), nxt_surf.get_width()) / SCALE_X + 20
        panel_h_raw = 70

        # Use a temporary Panel for dynamic sizing, but it's much faster than raw drawing
        # Ideally, we'd cache this panel if the names don't change
        panel = Panel(10, 10, panel_w_raw, panel_h_raw, bg_color=(30, 30, 50), border_color=COLOR_GOLD, alpha=200, border_radius=10)
        rect = panel.draw(screen)

        screen.blit(cur_surf, (rect.x + padding - 5, rect.y + padding - scale_y(10)))
        screen.blit(nxt_surf, (rect.x + padding - 5, rect.y + padding + line_spacing - scale_y(10)))
        
        # 5. Handle Hover Tooltip
        mouse_pos = pygame.mouse.get_pos()
        if rect.collidepoint(mouse_pos):
            self._draw_turn_tooltip(screen, mouse_pos)
            
        # 6. Handle Effect Tooltip
        if self.hovered_effects_actor:
            self._draw_effect_tooltip(screen, self.hovered_effects_actor, mouse_pos)

    def _draw_effect_tooltip(self, screen, actor, mouse_pos):
        """Displays status effects for the hovered actor."""
        padding = scale_x(12)
        line_h = scale_y(22)
        font = self.state.font
        
        effects = actor.get('active_effects', [])
        if not effects: return
        
        cached_lines = []
        max_w = 0
        for eff in effects:
            name = eff.get('name', 'Effect').replace('_', ' ').title()
            ability = eff.get('source_ability', 'Innate')
            duration = eff.get('duration', 0)
            text = f"{name} - {ability} - {duration} turns"
            
            surf = self._get_cached_text(text, font, COLOR_WHITE)
            cached_lines.append(surf)
            if surf.get_width() > max_w: max_w = surf.get_width()
            
        tip_w_raw = (max_w + padding * 2) / SCALE_X
        tip_h_raw = (len(cached_lines) * line_h + padding * 2) / SCALE_Y
        
        tx_raw = (mouse_pos[0] + 15) / SCALE_X
        ty_raw = (mouse_pos[1] + 15) / SCALE_Y
        
        tip_panel = Panel(tx_raw, ty_raw, tip_w_raw, tip_h_raw, bg_color=(20, 20, 30), border_color=COLOR_GOLD, alpha=240, border_radius=5)
        rect = tip_panel.draw(screen)
        
        for i, surf in enumerate(cached_lines):
            screen.blit(surf, (rect.x + padding - 5, rect.y + padding + (i * line_h) - 5))

    def _draw_turn_tooltip(self, screen, mouse_pos):
        """Displays the full turn order list with optimized rendering."""
        padding = scale_x(12)
        line_h = scale_y(22)
        font = self.state.font
        
        cached_lines = []
        max_w = 0
        for i, actor in enumerate(self.state.turn_queue, 1):
            name = actor.get('name', 'Unknown')
            text = f"{i}-{name}"
            color = COLOR_YELLOW if actor == self.state.current_actor else COLOR_WHITE
            
            surf = self._get_cached_text(text, font, color)
            cached_lines.append(surf)
            if surf.get_width() > max_w: max_w = surf.get_width()
            
        tip_w_raw = (max_w + padding * 2) / SCALE_X
        tip_h_raw = (len(cached_lines) * line_h + padding * 2) / SCALE_Y
        
        tx_raw = (mouse_pos[0] + 15) / SCALE_X
        ty_raw = (mouse_pos[1] + 15) / SCALE_Y
        
        tip_panel = Panel(tx_raw, ty_raw, tip_w_raw, tip_h_raw, bg_color=(20, 20, 30), border_color=COLOR_GOLD, alpha=240, border_radius=5)
        rect = tip_panel.draw(screen)
        
        for i, surf in enumerate(cached_lines):
            screen.blit(surf, (rect.x + padding - 5, rect.y + padding + (i * line_h) - 5))

    def draw_targeting_cursor(self, screen):
        """Renders pulsing cursors using pre-rendered surfaces and set_alpha."""
        gx, gy = self.state.menu_controller.cursor_grid_x, self.state.menu_controller.cursor_grid_y
        if not hasattr(self.state, 'GRID_X'): return
        
        time_ms = pygame.time.get_ticks()
        alpha = int(115 + math.sin(time_ms * 0.008) * 76)
        
        action_type = self.state.pending_action_data.get('type', 'attack')
        cursor_img = self.cursor_green if action_type == 'heal' else self.cursor_red
        cursor_img.set_alpha(alpha)

        # 2. Draw Highlight Under Cursor Tile
        row_list = self.state.PLAYER_Y if gx < 2 else self.state.ENEMY_Y
        tile_h = (row_list[1] - row_list[0]) if len(row_list) > 1 else scale_y(100)
        target_x = self.state.GRID_X[gx]
        safe_y = gy if gy < len(row_list) else len(row_list) - 1
        target_y = row_list[safe_y] + (tile_h // 2)
        
        screen.blit(cursor_img, (target_x - self.cursor_w // 2, target_y + scale_y(30)))

        # 3. Draw Highlights Under Affected Targets
        targets = self.state._get_current_target_list()
        for t in targets:
            tgx, tgy = t.get('grid_x'), t.get('grid_y')
            if tgx == gx and tgy == gy: continue
            
            if tgx is not None and tgy is not None:
                t_row_list = self.state.PLAYER_Y if tgx < 2 else self.state.ENEMY_Y
                t_tile_h = (t_row_list[1] - t_row_list[0]) if len(t_row_list) > 1 else scale_y(100)
                t_target_x = self.state.GRID_X[tgx]
                t_safe_y = tgy if tgy < len(t_row_list) else len(t_row_list) - 1
                t_target_y = t_row_list[t_safe_y] + (t_tile_h // 2)
                screen.blit(cursor_img, (t_target_x - self.cursor_w // 2, t_target_y + scale_y(30)))

    def draw_debug_placement(self, screen):
        """Overlays grid coordinates on all living combatants for layout verification."""
        all_actors = self.state.party + list(getattr(self.state, 'summons', {}).values()) + self.state.enemies
        for actor in all_actors:
            if actor.get('current_hp', 0) <= 0: continue
            
            v_rect = actor.get('_visual_rect')
            if v_rect:
                gx, gy = actor.get('grid_x', 0), actor.get('grid_y', 0)
                debug_text = f"({gx},{gy})"
                
                surf = self._get_cached_text(debug_text, self.state.font, (0, 255, 255))
                screen.blit(surf, (v_rect.centerx - scale_x(20), v_rect.top - scale_y(25)))

    def draw_entity_bars(self, screen):
        """Renders resource bars (HP/MP/SP) and effect indicators for all living combatants."""
        dimmed_alpha = 128
        target_x, target_y = self.state.menu_controller.cursor_grid_x, self.state.menu_controller.cursor_grid_y
        is_in_targeting = self.state.menu_controller.state.name == "SELECTING_TARGET"
        
        # Reset hovered effect info
        self.hovered_effects_actor = None
        self.hovered_effects_rect = None
        mouse_pos = pygame.mouse.get_pos()
        ox, oy = self.state.shake_mgr.get_offsets()
        adjusted_mouse = (mouse_pos[0] - ox, mouse_pos[1] - oy)

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
                base_y = v_rect.top - scale_y(5)
            else:
                pos_x, pos_y = entity.get('screen_pos', (0, 0))
                draw_x, base_y = pos_x - (bar_w // 2), pos_y - scale_y(10)
            
            current_y = base_y
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

            # 4. Effect Indicator Icon
            if entity.get('active_effects'):
                indicator_y = current_y + bar_h + spacing
                icon_size = scale_y(14)
                icon_rect = pygame.Rect(draw_x, indicator_y, icon_size, icon_size)
                
                # Draw a small gold circle with a star-like center
                pygame.draw.circle(screen, (40, 40, 60), icon_rect.center, icon_size // 2) # Shadow/BG
                pygame.draw.circle(screen, COLOR_GOLD, icon_rect.center, icon_size // 2 - 1)
                pygame.draw.circle(screen, COLOR_WHITE, icon_rect.center, icon_size // 2 - 1, 1)
                
                if icon_rect.collidepoint(adjusted_mouse):
                    self.hovered_effects_actor = entity
                    # Store screen-space rect for tooltip placement
                    self.hovered_effects_rect = pygame.Rect(icon_rect.x + ox, icon_rect.y + oy, icon_size, icon_size)
