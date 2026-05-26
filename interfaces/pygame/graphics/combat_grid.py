import pygame
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y

class CombatGridManager:
    """
    Manages the tactical grid, entity positioning, and coordinate mapping.
    """
    def __init__(self, state):
        self.state = state
        # Dimensions are stored on state for targeting system compatibility
        self.state.grid_width = 6
        self.state.grid_height = 4
        
    def _initialize_positions(self):
        """Strict 6-column tactical grid positioning engine."""
        import random
        
        play_x_start = 20
        play_x_end = SCREEN_WIDTH - 20
        play_y_start = 200
        play_y_end = SCREEN_HEIGHT - 200
        
        play_width = play_x_end - play_x_start
        play_height = play_y_end - play_y_start
        
        tile_width = play_width // 6
        
        # Internal coordinate arrays (stored on state)
        self.state.GRID_X = [play_x_start + (x * tile_width) + (tile_width // 2) for x in range(6)]
        
        # 1. Player and Player Summon Allocation (Columns 0 & 1)
        tile_height_3 = play_height // 3
        self.state.PLAYER_Y = [play_y_start + (y * tile_height_3) for y in range(3)]
        
        for i, p in enumerate(self.state.party):
            # Assign to Column 0
            gx, gy = 0, i % 3
            p['grid_x'] = gx
            p['grid_y'] = gy
            
            # screen_pos (TOP-LEFT)
            sx = play_x_start + (gx * tile_width)
            sy = play_y_start + (gy * tile_height_3)
            
            p['screen_pos'] = (sx, sy)
            p['_combat_pos'] = p['screen_pos']
            p['tile_size'] = (tile_width, tile_height_3)

        # 2. Enemy Deployment Slots (Columns 4 & 5)
        tile_height_4 = play_height // 4
        self.state.ENEMY_Y = [play_y_start + (y * tile_height_4) for y in range(4)]
        
        col_4_slots = [(4, y) for y in range(4)]
        col_5_slots = [(5, y) for y in range(4)]
        
        random.shuffle(col_4_slots)
        random.shuffle(col_5_slots)
        
        available_slots = col_4_slots + col_5_slots

        # 3. Range Sorting and Assignment
        enemies_sorted = sorted(self.state.enemies, key=lambda e: (e.get('attack_range', 1), random.random()))
        
        for e in enemies_sorted:
            if not available_slots:
                break
                
            gx, gy = available_slots.pop(0)
            e['grid_x'] = gx
            e['grid_y'] = gy
            
            # screen_pos (TOP-LEFT)
            sx = play_x_start + (gx * tile_width)
            sy = play_y_start + (gy * tile_height_4)
            
            e['screen_pos'] = (sx, sy)
            e['_combat_pos'] = e['screen_pos']
            e['tile_size'] = (tile_width, tile_height_4)
            
        self.sync_combat_grid()

    def assign_summon_visual_position(self, summon):
        """Calculates and stores the visual position for a new summon."""
        play_x_start = 20
        play_width = SCREEN_WIDTH - 40
        play_y_start = 200
        play_height = SCREEN_HEIGHT - 400
        tile_width = play_width // 6
        
        is_party = (summon in self.state.party)
        target_col = 1 if is_party else 3
        max_slots = 3 if is_party else 4
        
        gx, gy = summon['grid_x'], summon['grid_y']
        tile_height = play_height // max_slots
        
        sx = play_x_start + (gx * tile_width)
        sy = play_y_start + (gy * tile_height)
        
        summon['screen_pos'] = (sx, sy)
        summon['_combat_pos'] = summon['screen_pos']
        summon['tile_size'] = (tile_width, tile_height)
        
        self.sync_combat_grid()

    def sync_combat_grid(self):
        """Wipes and repopulates the 2D grid from current living entities."""
        self.state.combat_grid = [[[] for _ in range(self.state.grid_height)] for _ in range(self.state.grid_width)]
        for actor in self.state.party + self.state.enemies:
            if actor.get('current_hp', 0) > 0:
                gx, gy = actor.get('grid_x', 0), actor.get('grid_y', 0)
                if 0 <= gx < self.state.grid_width and 0 <= gy < self.state.grid_height:
                    self.state.combat_grid[gx][gy].append(actor)

    def generate_valid_target_map(self, action_data=None, actor_faction='party'):
        """
        Populates valid_target_tiles with (grid_x, grid_y) of all living actors
        that are valid targets for the current action (Faction filtering).
        """
        self.state.valid_target_tiles = []
        
        # Determine intended faction
        if action_data:
            a_type = action_data.get('type', 'attack')
            if a_type == 'heal' or action_data.get('friendly', False):
                intended_faction = actor_faction
            else:
                intended_faction = 'enemy' if actor_faction == 'party' else 'party'
        else:
            intended_faction = None # Allow all if no action specified

        for entity in self.state.party + self.state.enemies:
            if entity.get('current_hp', 0) > 0:
                if intended_faction is None or entity.get('faction') == intended_faction:
                    self.state.valid_target_tiles.append((entity.get('grid_x'), entity.get('grid_y')))

    def snap_to_nearest_valid(self, menu_controller):
        """Snaps the menu_controller cursor to the closest tile in valid_target_tiles."""
        if not self.state.valid_target_tiles: return
        cx, cy = menu_controller.cursor_grid_x, menu_controller.cursor_grid_y
        if (cx, cy) in self.state.valid_target_tiles: return
        
        # Manhattan distance to find nearest valid tile
        best_tile = min(self.state.valid_target_tiles, key=lambda t: abs(t[0] - cx) + abs(t[1] - cy))
        menu_controller.cursor_grid_x, menu_controller.cursor_grid_y = best_tile

    def jump_to_next_valid(self, menu_controller, direction):
        """
        Intelligently moves the cursor to the next valid target in a direction.
        Skips empty tiles and columns entirely. 
        When changing columns, picks the target closest to the current row.
        """
        valid = self.state.valid_target_tiles
        if not valid: return
        
        cx, cy = menu_controller.cursor_grid_x, menu_controller.cursor_grid_y
        
        if direction == 'up':
            # Same column, above
            targets = [t for t in valid if t[0] == cx and t[1] < cy]
            if targets:
                best = max(targets, key=lambda t: t[1])
                menu_controller.cursor_grid_x, menu_controller.cursor_grid_y = best
                
        elif direction == 'down':
            # Same column, below
            targets = [t for t in valid if t[0] == cx and t[1] > cy]
            if targets:
                best = min(targets, key=lambda t: t[1])
                menu_controller.cursor_grid_x, menu_controller.cursor_grid_y = best
                
        elif direction == 'left':
            # 1. Same row, left
            targets = [t for t in valid if t[0] < cx and t[1] == cy]
            if targets:
                best = max(targets, key=lambda t: t[0])
                menu_controller.cursor_grid_x, menu_controller.cursor_grid_y = best
            else:
                # 2. Skip to nearest non-empty column to the left
                left_cols = sorted(list(set([t[0] for t in valid if t[0] < cx])), reverse=True)
                if left_cols:
                    next_col = left_cols[0]
                    col_targets = [t for t in valid if t[0] == next_col]
                    # Find one closest to current row (cy)
                    best = min(col_targets, key=lambda t: abs(t[1] - cy))
                    menu_controller.cursor_grid_x, menu_controller.cursor_grid_y = best
                    
        elif direction == 'right':
            # 1. Same row, right
            targets = [t for t in valid if t[0] > cx and t[1] == cy]
            if targets:
                best = min(targets, key=lambda t: t[0])
                menu_controller.cursor_grid_x, menu_controller.cursor_grid_y = best
            else:
                # 2. Skip to nearest non-empty column to the right
                right_cols = sorted(list(set([t[0] for t in valid if t[0] > cx])))
                if right_cols:
                    next_col = right_cols[0]
                    col_targets = [t for t in valid if t[0] == next_col]
                    # Find one closest to current row (cy)
                    best = min(col_targets, key=lambda t: abs(t[1] - cy))
                    menu_controller.cursor_grid_x, menu_controller.cursor_grid_y = best

    def _get_grid_from_mouse(self, mouse_pos):
        """Maps screen coordinates to the nearest combat grid tile."""
        mx, my = mouse_pos
        if not hasattr(self.state, 'GRID_X'): return None, None
        
        # For columns, find the closest X index
        best_x, min_dx = None, 50
        for i, gx in enumerate(self.state.GRID_X):
            dx = abs(mx - gx)
            if dx < min_dx:
                min_dx = dx
                best_x = i
        
        if best_x is None: return None, None

        # For rows, check side (Cols 0-1 are 3-row, 2-5 are 4-row)
        best_y, min_dy = None, 50
        rows = self.state.PLAYER_Y if best_x < 2 else self.state.ENEMY_Y
        
        # We check distance to the center of each row
        tile_h = rows[1] - rows[0] if len(rows) > 1 else (SCREEN_HEIGHT // 6)
        for i, gy in enumerate(rows):
            row_center = gy + (tile_h // 2)
            dy = abs(my - row_center)
            if dy < min_dy:
                min_dy = dy
                best_y = i
        
        return best_x, best_y
