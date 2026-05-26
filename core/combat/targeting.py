class TargetingHelper:
    @staticmethod
    def get_affected_targets(action_data, target_x, target_y, combat_grid, grid_width, grid_height, actor_faction):
        """
        Determines the full list of targets affected by an ability on a 2D grid, 
        strictly filtering by intended faction (Heals for allies, Attacks for enemies).
        """
        if not action_data:
            return []

        # 1. Determine the intended faction for the action
        a_type = action_data.get('type', 'attack')
        
        # User Directive: heal -> same faction; attack/auto/save -> opposing faction
        if a_type == 'heal' or action_data.get('friendly', False):
            intended_faction = actor_faction 
        else:
            intended_faction = 'enemy' if actor_faction == 'party' else 'party'

        raw_entities = []

        # Helper function: Safely fetches entities from a tile, preventing IndexError
        def get_tile_entities(x, y):
            if 0 <= x < grid_width and 0 <= y < grid_height:
                return combat_grid[x][y]
            return []

        # 2. Gather ALL entities in the blast radius based on AoE type
        if action_data.get('saoe', False):  # Global Super AoE
            for x in range(grid_width):
                for y in range(grid_height):
                    raw_entities.extend(get_tile_entities(x, y))

        elif action_data.get('vaoe', False):  # Vertical (Column)
            for y in range(grid_height):
                raw_entities.extend(get_tile_entities(target_x, y))

        elif action_data.get('haoe', False):  # Horizontal (Row)
            for x in range(grid_width):
                raw_entities.extend(get_tile_entities(x, target_y))

        elif action_data.get('aoe', False):   # Cross/Plus Shape (Center + 4 adjacent)
            raw_entities.extend(get_tile_entities(target_x, target_y))       # Center
            raw_entities.extend(get_tile_entities(target_x + 1, target_y))   # Right
            raw_entities.extend(get_tile_entities(target_x - 1, target_y))   # Left
            raw_entities.extend(get_tile_entities(target_x, target_y + 1))   # Down
            raw_entities.extend(get_tile_entities(target_x, target_y - 1))   # Up

        else:  # Fallback: Single Target Tile
            raw_entities.extend(get_tile_entities(target_x, target_y))

        # 3. Filter out friendly fire
        final_targets = []
        for entity in raw_entities:
            # Check the entity's faction (adjust .get('faction') to match your entity data structure)
            entity_faction = entity.get('faction') 
            
            if entity_faction == intended_faction:
                final_targets.append(entity)

        return final_targets