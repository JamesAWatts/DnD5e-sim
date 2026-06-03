import pygame
import os
import random
import math
from core.game_rules.path_utils import get_resource_path
from core.game_rules.constants import scale_x, scale_y, COLOR_RED, COLOR_BLUE, COLOR_YELLOW, FONT_PATH
from ui.bars import draw_bar

class SpriteManager:
    """
    Manages static combat sprites for both players and enemies.
    """
    _cache = {}
    _path_cache = {}

    def __init__(self):
        self.targeted_entities = []
        self.anim_entity = None
        self.anim_timer = 0
        self.anim_max = 20

    def set_targeted_entities(self, entities):
        """
        Updates the list of entities that should be visually highlighted.
        Called by combat_state.py during the TARGETING menu phase.
        """
        self.targeted_entities = entities

    def trigger_lunge(self, entity):
        """Triggers a quick lunge forward animation."""
        self.anim_entity = entity
        self.anim_timer = self.anim_max

    def is_busy(self):
        """Returns True if an animation is currently playing."""
        return self.anim_timer > 0

    def update(self, dt):
        """Decrements animation timers."""
        if self.anim_timer > 0:
            self.anim_timer -= 1
            if self.anim_timer <= 0:
                self.anim_entity = None

    def trigger_wiggle(self, entity):
        """Stub for entity wiggle animation."""
        pass

    def spawn_summon_sprites(self, placed_summons):
        """Stub for spawning visual sprites for new summons."""
        pass

    def draw_sprites(self, screen, state):
        """Renders only the character sprites for all active combatants."""
        
        def get_stagger_data(entity):
            """Returns (offset_x, offset_y, sort_weight) based on sub_index."""
            idx = entity.get('sub_index', 0)
            if idx == 1: # Foreground (Left/Down)
                return -scale_x(20), scale_y(15), 1
            if idx == 2: # Background (Right/Up)
                return scale_x(20), -scale_y(15), -1
            return 0, 0, 0

        # 1. Draw Party
        party_sorted = sorted(state.party, key=lambda p: (p.get('screen_pos', (0, 0))[1], get_stagger_data(p)[2]))
        for p in party_sorted:
            if p.get('current_hp', 0) <= 0 or p.get('is_dying'): continue
            bx, by = p.get('screen_pos', (0, 0))
            tw, th = p.get('tile_size', (scale_x(150), scale_y(100)))
            
            st_x, st_y, _ = get_stagger_data(p)

            # Visual Offsets
            ox = (state.attacker_offset if getattr(state, 'active_attacker', None) is p else (state.target_offset_x if getattr(state, 'active_target', None) is p else 0))
            oy = (state.attacker_offset_y if getattr(state, 'active_attacker', None) is p else 0)
            
            # --- INTERNAL LUNGE ANIMATION ---
            if self.anim_entity is p:
                # Quick forward and back sine lunge
                progress = (self.anim_max - self.anim_timer) / self.anim_max
                lunge_dist = math.sin(progress * math.pi) * scale_x(60)
                # Player lunges right (positive X), Enemy lunges left (negative X)
                if p.get('is_enemy'):
                    ox -= lunge_dist
                else:
                    ox += lunge_dist

            p_size = (scale_x(128), scale_y(128))
            s = SpriteManager.get_player_sprite(p.get('class', 'fighter'), size=p_size, entity=p)
            sprite_rect = s.get_rect()
            sprite_rect.midbottom = (bx + (tw // 2) + ox + st_x, by + th - scale_y(5) + oy + st_y)
            p['_visual_rect'] = sprite_rect

            if p.get('current_hp', 0) <= 0:
                s = s.copy(); s.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif p.get('flash_frames', 0) > 0:
                s = state.apply_flash_effect(s, p['flash_frames'], p.get('flash_type', 'damage'))
            elif p in self.targeted_entities:
                # Breathing Grayscale effect
                time_ms = pygame.time.get_ticks()
                pulse = (math.sin(time_ms * 0.008) + 1) / 2
                alpha = int(pulse * 255)
                try:
                    gray_s = pygame.transform.grayscale(s.copy())
                    gray_s.set_alpha(alpha)
                    screen.blit(s, sprite_rect) # Draw normal
                    s = gray_s # This will be blitted by the final screen.blit(s, sprite_rect)
                except (AttributeError, pygame.error):
                    if (time_ms // 250) % 2 == 0:
                        s = s.copy(); s.fill((255, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(s, sprite_rect)

        # 2. Draw Summons
        all_summons = list(getattr(state, 'summons', {}).values())
        summons_sorted = sorted(all_summons, key=lambda s: (s.get('screen_pos', (0, 0))[1], get_stagger_data(s)[2]))
        
        for summon in summons_sorted:
            if summon.get('current_hp', 0) <= 0 or summon.get('is_dying'): continue
            bx, by = summon.get('screen_pos', (0, 0))
            tw, th = summon.get('tile_size', (scale_x(150), scale_y(100)))
            
            st_x, st_y, _ = get_stagger_data(summon)
            
            ox = (state.attacker_offset if getattr(state, 'active_attacker', None) is summon else (state.target_offset_x if getattr(state, 'active_target', None) is summon else 0))
            oy = (state.attacker_offset_y if getattr(state, 'active_attacker', None) is summon else 0)

            sz = (scale_x(100), scale_y(100))
            cat = summon.get('sprite_category', "humanoid")
            s = SpriteManager.get_player_sprite(summon.get('sprite_filename', "").replace(".png", ""), size=sz) if cat == "player" else SpriteManager.get_enemy_sprite(summon, size=sz)
            sprite_rect = s.get_rect()
            sprite_rect.midbottom = (bx + (tw // 2) + ox + st_x, by + th - scale_y(5) + oy + st_y)
            summon['_visual_rect'] = sprite_rect

            if summon.get('flash_frames', 0) > 0:
                s = state.apply_flash_effect(s, summon['flash_frames'], summon.get('flash_type', 'damage'))
            elif summon in self.targeted_entities:
                # Breathing Grayscale effect
                time_ms = pygame.time.get_ticks()
                pulse = (math.sin(time_ms * 0.008) + 1) / 2
                alpha = int(pulse * 255)
                try:
                    gray_s = pygame.transform.grayscale(s.copy())
                    gray_s.set_alpha(alpha)
                    screen.blit(s, sprite_rect)
                    s = gray_s
                except:
                    if (time_ms // 250) % 2 == 0:
                        s = s.copy(); s.fill((255, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(s, sprite_rect)

        # 3. Draw Enemies
        enemies_sorted = sorted(state.enemies, key=lambda e: (e.get('screen_pos', e.get('_combat_pos', (0, 0)))[1], get_stagger_data(e)[2]))
        for e in enemies_sorted:
            if e.get("current_hp", 0) <= 0 or e.get('is_dying'): continue
            bx, by = e.get('screen_pos', e.get('_combat_pos', (0, 0)))
            tw, th = e.get('tile_size', (scale_x(150), scale_y(100)))
            
            st_x, st_y, _ = get_stagger_data(e)
            
            ox = (state.attacker_offset if getattr(state, 'active_attacker', None) is e else (state.target_offset_x if getattr(state, 'active_target', None) is e else 0))
            oy = (state.attacker_offset_y if getattr(state, 'active_attacker', None) is e else 0)

            sz_val = int(125 * 1.3 if e.get('is_leader') else 125)
            s = SpriteManager.get_enemy_sprite(e, size=(scale_x(sz_val), scale_y(sz_val)))
            sprite_rect = s.get_rect()
            sprite_rect.midbottom = (bx + (tw // 2) + ox + st_x, by + th - scale_y(5) + oy + st_y)
            e['_visual_rect'] = sprite_rect

            if e.get("current_hp", 0) <= 0:
                s = s.copy(); s.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif e.get('flash_frames', 0) > 0:
                s = state.apply_flash_effect(s, e['flash_frames'], e.get('flash_type', 'damage'))
            elif e in self.targeted_entities:
                # Breathing Grayscale effect
                time_ms = pygame.time.get_ticks()
                pulse = (math.sin(time_ms * 0.008) + 1) / 2
                alpha = int(pulse * 255)
                try:
                    gray_s = pygame.transform.grayscale(s.copy())
                    gray_s.set_alpha(alpha)
                    screen.blit(s, sprite_rect)
                    s = gray_s
                except:
                    if (time_ms // 250) % 2 == 0:
                        s = s.copy(); s.fill((255, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(s, sprite_rect)

    def draw_bars(self, screen, state):
        """Renders all resource bars (HP, MP, SP) on top of character sprites."""
        res_font = getattr(state, 'mini_font', None)
        if not res_font and hasattr(state, 'fonts'):
            res_font = state.fonts.get('small')
        if not res_font:
            res_font = pygame.font.Font(get_resource_path(FONT_PATH), scale_y(18))
            
        bw, bh = scale_x(80), scale_y(10)

        # Draw bars for Party, Summons, and Enemies
        all_actors = state.party + list(getattr(state, 'summons', {}).values()) + state.enemies
        for entity in all_actors:
            if entity.get('current_hp', 0) <= 0: continue
            
            v_rect = entity.get('_visual_rect')
            if not v_rect: continue
            
            bar_x = v_rect.centerx - (bw // 2)
            base_bar_y = v_rect.top - scale_y(5)
            
            # Dynamic Alpha logic
            is_turn = (state.current_actor is entity)
            bar_alpha = 255 if is_turn else 128
            
            target_x, target_y = state.menu_controller.cursor_grid_x, state.menu_controller.cursor_grid_y
            is_in_targeting = state.menu_controller.state.name == "SELECTING_TARGET"
            if is_in_targeting and entity.get('grid_x') == target_x and entity.get('grid_y') == target_y:
                bar_alpha = 255

            # Calculate total height of the bar stack
            stack_h = bh + scale_y(2)
            if entity.get('mp') and entity.get('max_mp', 0) > 0: stack_h += bh + scale_y(2)
            if entity.get('sp') and entity.get('max_sp', 0) > 0: stack_h += bh + scale_y(2)

            current_y = base_bar_y - stack_h
            
            # 1. HP Bar (Green)
            draw_bar(screen, bar_x, current_y, bw, bh, entity.get('current_hp', 0), entity.get('max_hp', 1), (50, 200, 50), font=res_font, show_numbers=True, alpha=bar_alpha)

            # 2. MP Bar (Blue)
            if entity.get('mp') and entity.get('max_mp', 0) > 0:
                current_y += (bh + scale_y(2))
                draw_bar(screen, bar_x, current_y, bw, bh, entity.get('current_mp', 0), entity.get('max_mp', 1), (50, 100, 255), font=res_font, show_numbers=True, alpha=bar_alpha)

            # 3. SP Bar (Yellow)
            if entity.get('sp') and entity.get('max_sp', 0) > 0:
                current_y += (bh + scale_y(2))
                draw_bar(screen, bar_x, current_y, bw, bh, entity.get('current_sp', 0), entity.get('max_sp', 1), (255, 200, 0), font=res_font, show_numbers=True, alpha=bar_alpha)

    def draw(self, screen, state):
        """Legacy entry point; calls sprites then bars."""
        self.draw_sprites(screen, state)
        self.draw_bars(screen, state)

    def _draw_entity_bars(self, screen, entity, pos, size, font, is_party=False):
        """Helper to draw HP and secondary resource bars beneath an entity."""
        from ui.bars import draw_bar
        from core.game_rules.constants import COLOR_RED, COLOR_BLUE, COLOR_YELLOW, scale_x, scale_y

        # Don't draw bars for dead entities
        if entity.get('current_hp', 0) <= 0:
            return

        # Center horizontally relative to sprite
        bw = scale_x(80) # Bar width
        bh = scale_y(10) # Bar height
        bx = pos[0] + (size[0] - bw) // 2
        by = pos[1] + size[1] + scale_y(5)

        # 1. HP Bar (Red)
        draw_bar(screen, bx, by, bw, bh, entity.get('current_hp', 0), entity.get('max_hp', 1), COLOR_RED, font=font, show_numbers=True)

        # 2. MP Bar (Blue)
        if entity.get('mp') and entity.get('max_mp', 0) > 0:
            by += bh + scale_y(4)
            draw_bar(screen, bx, by, bw, scale_y(8), entity.get('current_mp', 0), entity['max_mp'], COLOR_BLUE, font=font, show_numbers=True)
            bh = scale_y(8) # Update height for next bar spacing

        # 3. SP Bar (Yellow)
        if entity.get('sp') and entity.get('max_sp', 0) > 0:
            by += bh + scale_y(4)
            draw_bar(screen, bx, by, bw, scale_y(8), entity.get('current_sp', 0), entity['max_sp'], COLOR_YELLOW, font=font, show_numbers=True)

    # Mapping of enemy keys to list of potential image filenames
    _enemy_mapping = {
        "beast": {
            "deep_roathe": ["deep_roathe1.png", "deep_roathe2.png"],
            "harpy": ["harpy1.png", "harpy2.png"],
            "minotaur": ["minotaur1.png", "minotaur2.png"],
            "medusa": ["medusa1.png", "medusa2.png"],
            "chimera": ["chimera1.png", "chimera2.png"],
            "brown_bear": ["brown_bear1.png", "brown_bear2.png"],
            "bulette": ["bulette1.png", "bulette2.png"],
            "cockatrice": ["cockatrice1.png", "cockatrice2.png", "cockatrice3.png"],
            "griffon": ["griffon1.png", "griffon2.png"],
            "hydra": ["hydra1.png", "hydra2.png"],
            "kraken": ["kraken1.png", "kraken2.png"],
            "manticore": ["manticore1.png", "manticore2.png"],
            "owlbear": ["owlbear1.png", "owlbear2.png"],
            "purple_worm": ["purple_worm1.png", "purple_worm2.png"],
            "tarrasque": ["tarrasque1.png", "tarrasque2.png"],
            "remorhaz" : ["remorhaz1.png", "remorhaz2.png"],
        },
        "dragon": {
            "kobold": ["kobold1.png", "kobold2.png", "kobold3.png"],
            "kobold_slinger": ["kobold_slinger.png"],
            "kobold_sorcerer": ["kobold_sorcerer1.png"],
            "kobold_inventor": ["kobold_inventor1.png", "kobold_inventor2.png"],
            "kobold_dragonshield": ["kobold_dragonshield1.png", "kobold_dragonshield2.png"],  
            "wyrmling": ["wyrmling1.png", "wyrmling2.png"],
            "wyvern": ["wyvern1.png", "wyvern2.png"],
            "young_dragon": ["young_dragon1.png", "young_dragon2.png"],
            "adult_dragon": ["adult_dragon1.png", "adult_dragon2.png"],
            "ancient_dragon": ["ancient_dragon1.png", "ancient_dragon2.png"],
            "dragon_turtle": ["dragon_turtle1.png", "dragon_turtle2.png"],
            "dragons_chosen": ["dragons_chosen1.png", "dragons_chosen2.png", "dragons_chosen3.png"],
            "behir": ["behir1.png", "behir2.png"],
            "greatwyrm": ["greatwyrm1.png", "greatwyrm2.png"],
        },
        "fae": {
            "blink_dog": ["blink_dog1.png", "blink_dog2.png"],
            "darkling": ["darkling1.png", "darkling2.png", "darkling3.png"],
            "darkling_elder": ["darkling_elder1.png", "darkling_elder2.png"],
            "dryad": ["dryad1.png", "dryad2.png"],
            "green_hag": ["green_hag1.png", "green_hag2.png"],
            "needle_blight": ["needle_blight1.png", "needle_blight2.png", "needle_blight3.png"],
            "quickling": ["quickling1.png", "quickling2.png"],
            "redcap": ["redcap1.png", "redcap2.png"],
            "shambling_mound": ["shambling_mound1.png", "shambling_mound2.png"],
            "treant": ["treant1.png", "treant2.png", "treant3.png"],
            "vine_blight": ["vine_blight1.png", "vine_blight2.png"],
            "yeth_hound": ["yeth_hound1.png", "yeth_hound2.png"],
            "yggdrasti": ["yggdrasti1.png", "yggdrasti2.png"],
        },
        "goblinoid": {
            "goblin": ["goblin1.png", "goblin2.png", "goblin3.png"],
            "goblin_archer": ["goblin_archer1.png", "goblin_archer2.png", "goblin_archer3.png"],
            "bugbear_warrior": ["bugbear_warrior1.png", "bugbear_warrior2.png"],
            "goblin_chieften": ["goblin_chieften1.png", "goblin_chieften2.png"],
            "worg_rider": ["worg_rider1.png", "worg_rider2.png"],
            "worg": ["worg1.png", "worg2.png"],
            "hobgoblin_captain": ["hobgoblin_captain1.png", "hobgoblin_captain2.png"],        
            "hobgoblin_warlord": ["hobgoblin_warlord1.png", "hobgoblin_warlord2.png"],        
            "hobgoblin": ["hobgoblin1.png", "hobgoblin2.png"],
            "orc_warrior": ["orc_warrior1.png", "orc_warrior2.png"],
            "troll": ["troll1.png", "troll2.png"],
            "dire_troll": ["dire_troll1.png", "dire_troll2.png"],
            "fomorian": ["fomorian1.png", "fomorian2.png"],
            "ogre": ["ogre1.png", "ogre2.png"],
            "oni": ["oni1.png", "oni2.png"],
        },
        "humanoid": {
            "bandit": ["bandit1.png", "bandit2.png"],
            "scout": ["scout1.png", "scout2.png"],
            "archer": ["archer1.png", "archer2.png"],
            "cultist": ["cultist1.png", "cultist2.png", "cultist3.png"],
            "berserker": ["berserker1.png", "berserker2.png"],
            "thief": ["thief1.png", "thief2.png", "thief3.png"],
            "bandit_captain": ["bandit1.png", "bandit2.png"],
            "assassin": ["assassin1.png", "assassin2.png"],
            "guard": ["guard1.png", "guard2.png", "guard3.png"],
            "cultist_fanatic": ["cultist_fanatic1.png", "cultist_fanatic2.png"],
            "knight": ["knight1.png", "knight2.png"],
            "guard_captain": ["guard_captain1.png", "guard_captain2.png"],
            "mage": ["mage1.png", "mage2.png"],
            "gladiator": ["gladiator1.png", "gladiator2.png"],
            "master_thief": ["master_thief1.png", "master_thief2.png"],
            "blackguard": ["blackguard1.png", "blackguard2.png"],
            "champion": ["champion1.png", "champion2.png"],
            "archmage": ["archmage1.png", "archmage2.png"],
            "warlord": ["warlord1.png", "warlord2.png"],
        },
        "undead": {
            "skeleton": ["skeleton1.png", "skeleton2.png", "skeleton3.png"],
            "death_knight": ["death_knight1.png", "death_knight2.png"],
            "lich": ["lich1.png", "lich2.png"],
            "necromancer": ["necromancer1.png", "necromancer2.png"],
            "banshee": ["banshee1.png", "banshee2.png"],
            "boneclaw": ["boneclaw1.png", "boneclaw2.png"],
            "deathlock_mastermind": ["deathlock_mastermind1.png", "deathlock_mastermind2.png"],
            "deathlock_wight": ["deathlock_wight2.png"],
            "deathlock": ["deathlock1.png", "deathlock2.png"],
            "ghast": ["ghast1.png", "ghast2.png"],
            "ghost_dragon": ["ghost_dragon1.png"],
            "ghoul": ["ghoul1.png", "ghoul2.png"],
            "skull_lord": ["skull_lord1.png", "skull_lord2.png"],
            "vampire_spawn": ["vampire_spawn1.png", "vampire_spawn2.png"],
            "vampire": ["vampire1.png", "vampire2.png", "vampire_lord1.png", "vampire_lord2.png"],
            "wraith": ["wraith2.png"],
            "zombie": ["zombie1.png", "zombie2.png"]
        },
    }

    @staticmethod
    def get_enemy_variants(category, base_name, folder_path=None):
        """
        Returns the list of filename variants for an enemy by checking the filesystem.
        If category is 'general' or missing, attempts to find the correct folder.
        """
        # 1. Resolve Category and Folder if not provided
        if not folder_path:
            if not category or category == "general":
                for cat, mapping in SpriteManager._enemy_mapping.items():
                    if base_name in mapping:
                        category = cat
                        break
                if not category or category == "general":
                    category = "humanoid" # Default fallback
            folder_path = os.path.join("assets", "sprites", "enemies", category)

        # 2. Check Filesystem for dynamic variants
        full_path = get_resource_path(folder_path)
        
        if os.path.exists(full_path):
            try:
                # Find all files starting with base_name and ending in .png
                # e.g., 'goblin1.png', 'goblin2.png'
                files = [f for f in os.listdir(full_path) 
                        if (f.lower().startswith(base_name.lower()) and f.lower().endswith(".png"))]
                
                if files:
                    return sorted(files)
            except Exception as e:
                print(f"[SpriteManager] Error scanning for variants of {base_name} in {folder_path}: {e}")

        # 3. Fallback to hardcoded mapping if filesystem scan fails
        category_map = SpriteManager._enemy_mapping.get(category, {})
        return category_map.get(base_name, [f"{base_name}.png"])

    @staticmethod
    def get_enemy_sprite(enemy_data, size=None):
        # 1. Check for Direct Path Override (e.g., Summons)
        folder = enemy_data.get('sprite_folder')
        filename = enemy_data.get('sprite') or enemy_data.get('sprite_filename')
        
        # 2. Priority Routing for Summons using provided folder
        if folder and filename:
            path = get_resource_path(os.path.join(folder, filename))
            if os.path.exists(path):
                if path in SpriteManager._cache:
                    return SpriteManager._cache[path]
                
                sprite = pygame.image.load(path).convert_alpha()
                if size:
                    sprite = pygame.transform.scale(sprite, size)
                SpriteManager._cache[path] = sprite
                return sprite

        # 3. Identify who we are and where we live (Standard Enemies)
        base_name = enemy_data.get('base_name', 'unknown').lower()
        category = enemy_data.get('category', 'general')

        # 4. Try to find the file variants dynamically
        try:
            variants = SpriteManager.get_enemy_variants(category, base_name)
            
            # If enemy_data has a specific filename, use it, else use the first variant
            filename = filename or variants[0] 

            path = get_resource_path(os.path.join("assets", "sprites", "enemies", category, filename))

            if not os.path.exists(path):
                raise FileNotFoundError

            # Cache check to save performance
            if path in SpriteManager._cache:
                return SpriteManager._cache[path]

            sprite = pygame.image.load(path).convert_alpha()
            if size:
                sprite = pygame.transform.scale(sprite, size)

            SpriteManager._cache[path] = sprite
            return sprite

        except Exception:
            # ONLY return the placeholder if the try block fails
            return SpriteManager._generate_error_placeholder(size)

    @staticmethod
    def _generate_error_placeholder(size):
        """Creates the Red 'X' box when a sprite is missing."""
        surf_size = size if size else (128, 128)
        placeholder = pygame.Surface(surf_size, pygame.SRCALPHA)
        # Draw a red border and an X
        rect = placeholder.get_rect()
        pygame.draw.rect(placeholder, (255, 0, 0), rect, 2)
        pygame.draw.line(placeholder, (255, 0, 0), (0, 0), (rect.width, rect.height), 2)      
        pygame.draw.line(placeholder, (255, 0, 0), (rect.width, 0), (0, rect.height), 2)      
        return placeholder

    @staticmethod
    def get_player_sprite(class_name, size=(192, 192), entity=None, variant='normal'):
        """Loads and returns a sprite variant (normal, grayscale, dead)."""
        class_name = class_name.lower()
        if class_name == "archer": class_name = "ranger"

        filename = f"{class_name}.png"
        
        # Summon Routing
        if entity and entity.get('is_summon'):
            filename = entity.get('sprite') or entity.get('sprite_filename') or filename
            if entity.get('is_enemy'):
                folder = os.path.join("assets", "sprites", "enemies", "summons")
            else:
                folder = os.path.join("assets", "sprites", "player_sprites", "summons")
            sprite_path = get_resource_path(os.path.join(folder, filename))
        else:
            sprite_path = get_resource_path(os.path.join("assets", "sprites", "player_sprites", filename))

        cache_key = (filename, size, variant)
        if cache_key in SpriteManager._cache:
            return SpriteManager._cache[cache_key]

        try:
            # 1. Get/Load base normal sprite
            base_key = (filename, size, 'normal')
            if base_key in SpriteManager._cache:
                base_surf = SpriteManager._cache[base_key]
            else:
                if not os.path.exists(sprite_path):
                    if class_name == "cleric":
                        sprite_path = get_resource_path(os.path.join("assets", "sprites", "player_sprites", "wizard2.png"))
                    elif class_name == "kobold_sorcerer":
                        sprite_path = get_resource_path(os.path.join("assets", "sprites", "player_sprites", "kobald_sorc.webp"))
                    else:
                        raise FileNotFoundError(f"No player sprite found for {class_name}")

                base_surf = pygame.image.load(sprite_path).convert_alpha()
                if size:
                    base_surf = pygame.transform.scale(base_surf, size)
                SpriteManager._cache[base_key] = base_surf

            if variant == 'normal':
                return base_surf

            # 2. Create and cache variant
            v_surf = base_surf.copy()
            if variant == 'grayscale':
                try:
                    v_surf = pygame.transform.grayscale(v_surf)
                except (AttributeError, pygame.error):
                    v_surf.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif variant == 'dead':
                v_surf.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            
            SpriteManager._cache[cache_key] = v_surf
            return v_surf

        except Exception:
            placeholder = pygame.Surface(size if size else (192, 192), pygame.SRCALPHA)       
            pygame.draw.rect(placeholder, (0, 0, 200), placeholder.get_rect(), 2)
            return placeholder
