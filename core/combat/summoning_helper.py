import random
import re

class SummoningHelper:
    
    @staticmethod
    def _evaluate_math_string(math_str, context):
        """Safely evaluates a math string substituting the provided context variables."""
        if isinstance(math_str, (int, float)):
            return int(math_str)
            
        try:
            # Replace variables like {level} or {s_level} using the context
            formatted_str = str(math_str).format(**context)
            
            # If it looks like a dice string (e.g., '2d6'), don't evaluate it as math, just return it formatted
            if 'd' in formatted_str and not any(op in formatted_str for op in ['+', '-', '*', '/']):
                return formatted_str
                
            # Sanitize the string to allow only math operations
            safe_str = re.sub(r'[^0-9+\-*/(). ]', '', formatted_str)
            
            if safe_str.strip() == "":
                return formatted_str # Fallback to string if no math is present
                
            # Safely evaluate the math string
            return int(eval(safe_str, {"__builtins__": None}))
        except Exception as e:
            # If evaluation fails, just format and return the string (for strings like "2d6")
            try:
                return str(math_str).format(**context)
            except:
                return math_str

    @staticmethod
    def create_summons(ability_data, caster, summons_data):
        """
        Reads the ability data and caster stats to generate a list of new summon entities.
        """
        # 1. Build context for math evaluation from caster stats
        caster_level = caster.get('level', 1)
        caster_prof = caster.get('proficiency_bonus', 2)
        caster_name = caster.get('name', 'Caster')
        
        # Ensure caster has a unique ID for ownership tracking
        if 'id' not in caster:
            caster['id'] = f"actor_{id(caster)}_{random.randint(1000, 9999)}"
        caster_id = caster['id']

        context = {
            'level': caster_level,
            'prof': caster_prof,
            's_level': caster_level,
            's_prof': caster_prof,
            's_name': caster_name
        }

        # 2. Determine how many of EACH type to summon
        summon_count_expr = ability_data.get('summon_count', 1)
        count = SummoningHelper._evaluate_math_string(summon_count_expr, context)
        # Ensure at least 1 is summoned if the ability is triggered
        if isinstance(count, int):
            count = max(1, count)
        else:
            count = 1 

        # 3. Identify the summon type(s)
        summon_types = ability_data.get('summon_type', [])
        if not summon_types:
            print(f"[COMBAT] No summon_type defined in ability '{ability_data.get('name')}'!")
            return []

        # Access the summon templates, respecting the 'summon_list' wrapper
        summon_pool = summons_data.get("summon_list", summons_data)

        # 4. Calculate starting resources based on ability cost
        raw_cost = ability_data.get('cost', 0)
        evaluated_cost = SummoningHelper._evaluate_math_string(raw_cost, context)
        if not isinstance(evaluated_cost, int):
            evaluated_cost = 0
        starting_resources = max(0, evaluated_cost // 2)

        new_summons = []
        # UPDATED: Summon 'count' of EACH type
        for chosen_type in summon_types:
            template = summon_pool.get(chosen_type)
            if not template:
                print(f"[COMBAT] Summon template '{chosen_type}' not found in summons_data!")
                continue

            for _ in range(count):
                # 5. Build the summon entity
                is_enemy_team = caster.get('is_enemy', False)
                name_template = template.get('name_template', "{s_name}'s Minion")
                summon_name = name_template.format(**context)
                
                sprites = template.get('sprites', ["placeholder.png"])
                sprite = random.choice(sprites)
                
                stats_template = template.get('stats', {})
                evaluated_stats = {}
                
                # Evaluate each stat from the JSON template
                for stat, value in stats_template.items():
                    if isinstance(value, str) and ('{' in value or any(op in value for op in ['+', '-', '*', '/'])):
                        evaluated_stats[stat] = SummoningHelper._evaluate_math_string(value, context)
                    else:
                        evaluated_stats[stat] = value
                
                # Extract standard combat parameters (map template stats to actual actor state)
                max_hp = evaluated_stats.get('hp', 10)
                max_sp = evaluated_stats.get('max_sp', 0)
                max_mp = evaluated_stats.get('max_mp', 0)
                
                # Extract sprite metadata from template
                sprite_folder = template.get('sprite_folder', "")
                category = template.get('category', "beast") # Default to beast if not specified
                
                summon_entity = {
                    'id': f"summon_{chosen_type}_{random.randint(10000, 99999)}",
                    'owner_id': caster_id,
                    'name': summon_name,
                    'is_summon': True,
                    'is_enemy': is_enemy_team,
                    'enemy_type': chosen_type, # Used as 'base_name' by SpriteManager
                    'category': category,
                    'sprite_folder': sprite_folder,
                    'sprite': sprite, # Filename
                    'level': caster_level,
                    'max_hp': max_hp,
                    'current_hp': max_hp,
                    'max_sp': max_sp,
                    'current_sp': min(starting_resources, max_sp),
                    'sp': len(evaluated_stats.get('skills', [])) > 0,
                    'max_mp': max_mp,
                    'current_mp': min(starting_resources, max_mp),
                    'mp': len(evaluated_stats.get('spells', [])) > 0,
                    'ac': evaluated_stats.get('ac', 10),
                    'proficiency_bonus': evaluated_stats.get('proficiency_bonus', 2),
                    'weapon_bonus': evaluated_stats.get('weapon_bonus', 0),
                    'damage_die': evaluated_stats.get('damage_die', "1d4"),
                    'bonus_dmg': evaluated_stats.get('bonus_dmg', 0),
                    'attack_count': evaluated_stats.get('attack_count', 1),
                    'spells': evaluated_stats.get('spells', []),
                    'skills': evaluated_stats.get('skills', []),
                    'is_dead': False
                }
                new_summons.append(summon_entity)
            
        return new_summons

    @staticmethod
    def place_summons(new_summons, target_list, target_col, max_slots, owner_id):
        """
        Places a list of new summons.
        Radius logic:
        - If total summons <= 3: Spread within 1 tile radius of target_col.
        - If total summons > 3: Spread within 2 tile radius of target_col.
        Max 3 creatures per slot.
        """
        MAX_PER_TILE = 3
        total_summons = len(new_summons)
        # 1-tile radius if <= 3, 2-tile radius if > 3
        radius = 1 if total_summons <= 3 else 2
        
        # Determine valid columns for the team
        # Standard: Faction 0 (Party) uses 0-1, Faction 1 (Enemies) uses 3-4. (Index 2 is usually No-Man's-Land)
        is_enemy = any(s.get('is_enemy', False) for s in new_summons)
        if is_enemy:
            valid_cols = [3, 4]
        else:
            valid_cols = [0, 1]

        # Restrict valid_cols to those within radius of target_col
        nearby_cols = [c for c in valid_cols if abs(c - target_col) <= radius]
        if not nearby_cols:
            nearby_cols = [target_col] # Safety fallback

        # 1. Map current occupancy and ownership in ALL nearby tiles
        occupancy = {} # (col, slot) -> count
        slot_owners = {} # (col, slot) -> set(ids)

        for col in nearby_cols:
            for slot in range(max_slots):
                occupancy[(col, slot)] = 0
                slot_owners[(col, slot)] = set()

        for e in target_list:
            gx = e.get('grid_x', e.get('col'))
            gy = e.get('grid_y', e.get('slot'))
            if (gx, gy) in occupancy:
                occupancy[(gx, gy)] += 1
                ent_owner = e.get('owner_id')
                if ent_owner:
                    slot_owners[(gx, gy)].add(ent_owner)
                else:
                    slot_owners[(gx, gy)].add(f"solo_{id(e)}")

        # 2. Distribute new summons
        placed_summons = []
        
        # Prepare a randomized list of tiles within the allowed area
        available_tiles = []
        for col in nearby_cols:
            for slot in range(max_slots):
                available_tiles.append((col, slot))
        
        # Sort tiles by distance to target_col primarily, then randomize
        random.shuffle(available_tiles)
        available_tiles.sort(key=lambda t: abs(t[0] - target_col))

        for summon in new_summons:
            summon_placed = False

            for col, slot in available_tiles:
                is_full = occupancy[(col, slot)] >= MAX_PER_TILE
                current_owners = slot_owners[(col, slot)]
                is_exclusive = len(current_owners) == 0 or (len(current_owners) == 1 and owner_id in current_owners)

                if not is_full and is_exclusive:
                    summon['grid_x'] = col
                    summon['grid_y'] = slot
                    summon['sub_index'] = occupancy[(col, slot)]

                    occupancy[(col, slot)] += 1
                    slot_owners[(col, slot)].add(owner_id)
                    placed_summons.append(summon)
                    summon_placed = True
                    break

            if not summon_placed:
                print(f"[SUMMON] No room for {summon.get('name')} within radius {radius}!")

        return placed_summons
