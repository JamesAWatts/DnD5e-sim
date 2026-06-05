import pygame
import random
import math
from .base_state import BaseState
from ui.menu import Menu
from graphics.backgrounds import BackgroundManager
from ui.panel import Panel, draw_text_outlined
from ui.inventory_panel import InventoryPanel
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD, COLOR_WHITE
from core.players.player import load_weapons, load_armor, load_trinkets, load_shields, validate_player_data
from graphics.sprite_manager import SpriteManager
from ui.save_indicator import SaveIndicator
from core.game_rules.save_manager import SaveManager

class HubState(BaseState):
    def __init__(self, game, font, previous_state_name=None):
        super().__init__(game, font)
        
        # Determine previous state for autosave logic
        if previous_state_name is None:
            # If we're being instantiated while another state is active
            if self.game.state:
                prev_class = type(self.game.state).__name__
                if "CombatState" in prev_class: previous_state_name = "COMBAT_STATE"
                elif "LevelUpState" in prev_class: previous_state_name = "LEVEL_UP_STATE"
            
            # Fallback to GameManager's tracked previous state if still None
            if previous_state_name is None:
                previous_state_name = getattr(self.game, 'previous_state_name', None)
        
        self.save_indicator = SaveIndicator()

        # Ensure player data is valid and stats are recalculated
        for p in self.game.party:
            try:
                validate_player_data(p)
            except Exception as e:
                print(f"[HUB] Error validating player {p.get('name')}: {e}")
            
        # --- Autosave Evaluation ---
        self.alert_dialogue = None
        if previous_state_name in ["COMBAT_STATE", "LEVEL_UP_STATE"]:
            player_name = self.game.party[0].get('name', 'Unknown') if self.game.party else "Unknown"
            
            # 1st try current slot if it's set and matches
            current_slot = getattr(self.game, 'current_save_slot', None)
            best_slot = None
            
            if current_slot:
                data = SaveManager.load_game_data(current_slot)
                if not data or data.get('name') == player_name:
                    best_slot = current_slot
            
            # If no current slot match, find best slot 1-3
            if not best_slot:
                best_slot = SaveManager.find_autosave_slot(player_name)
            
            if best_slot:
                # Store current slot for future autosaves
                self.game.current_save_slot = best_slot
                # Trigger silent save (Asynchronous for Web/Wasm performance)
                import asyncio
                asyncio.create_task(SaveManager.save_game_async(
                    best_slot, self.game.party, 
                    battle_counter=self.game.battle_counter, 
                    bestiary_rp=self.game.bestiary_rp
                ))
                self.save_indicator.trigger()
            else:
                # Autosave failed - Notify player
                from ui.dialogue_box import DialogueBox
                self.alert_dialogue = DialogueBox(self.fonts['medium'])
                self.alert_dialogue.set_messages([
                    "Autosave failed. Please create a save for your character."
                ])

        # Get persistent hub background from manager
        self.background = BackgroundManager.get_hub_bg(self.game.player)

        # --- Feature Unlock Check (MVC) ---
        options = self.game.get_unlocked_hub_features()

        self.menu = Menu(options, font, width=150, pos=(120, 200), enable_horizontal=False)
        
        # --- Cheat Code Setup ---
        self.cheat_code = [pygame.K_UP, pygame.K_UP, pygame.K_DOWN, pygame.K_DOWN, 
                           pygame.K_LEFT, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_RIGHT]
        self.current_input_sequence = []
        
        self.sub_menu = None
        self.menu_state = "MAIN"
        self.active_menu = self.menu
        self.selected_index = 0 # Currently viewed party member
        
        # Load data for inventory panel
        weapons_db = load_weapons()
        armor_db = load_armor()
        shields_db = load_shields()
        trinkets_db = load_trinkets()
        
        self.inventory_panel = InventoryPanel(self.fonts, weapons_db, armor_db, shields_db, trinkets_db)

        # Pre-cache player sprites to prevent thread-blocking in render loop
        self.cached_active_sprites = {}
        self.cached_inactive_sprites = {}
        for char in self.game.party:
            p_class = char.get("class", "fighter")
            if p_class not in self.cached_active_sprites:
                # Active sprite (Large)
                sprite = SpriteManager.get_player_sprite(p_class, size=(scale_x(256), scale_y(256)))
                self.cached_active_sprites[p_class] = sprite
                
                # Inactive sprite (Small + Grayscale)
                inactive = SpriteManager.get_player_sprite(p_class, size=(scale_x(152), scale_y(152)))
                if inactive:
                    try:
                        # Attempt standard grayscale
                        gs_inactive = pygame.transform.grayscale(inactive)
                    except (AttributeError, pygame.error):
                        # Fallback for older pygame or specific WASM environments
                        gs_inactive = inactive.copy()
                        gs_inactive.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    self.cached_inactive_sprites[p_class] = gs_inactive

        # --- Transition State for Web/Wasm Performance ---
        self.is_transitioning = False
        self.transition_start_time = 0
        self.pending_combat_data = None

        # --- Text Caching for Wasm ---
        self._text_cache = {}
        self._static_surfs = {}
        self._cache_static_text()

    def _cache_static_text(self):
        """Pre-renders static UI labels."""
        # Title
        title_str = "Adventure Hub"
        tw, th = self.fonts['large'].size(title_str)
        surf = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
        draw_text_outlined(surf, title_str, self.fonts['large'], (255, 255, 255), 5, 5)
        self._static_surfs['title'] = surf

    def _get_cached_text(self, text, font_key, color):
        """Helper to retrieve or render text surfaces from cache."""
        cache_key = f"{text}_{font_key}_{color}"
        if cache_key not in self._text_cache:
            font = self.fonts[font_key]
            tw, th = font.size(text)
            surf = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
            draw_text_outlined(surf, text, font, color, 5, 5)
            self._text_cache[cache_key] = surf
        return self._text_cache[cache_key]

    def on_select(self, option):
        if self.menu_state == "MAIN":
            self.handle_main_menu(option)
        elif self.menu_state == "DEV":
            self.handle_dev_menu(option)

    def update(self, events, dt):
        # --- Alert Handling ---
        if self.alert_dialogue:
            for event in events:
                self.alert_dialogue.handle_event(event)
            self.alert_dialogue.update()
            if self.alert_dialogue.finished:
                self.alert_dialogue = None
            return # Block other input while alert is active

        # Check for cheat code keys and character switching
        for event in events:
            if event.type == pygame.KEYDOWN:
                # Character Switching (Left/Right Arrow)
                if event.key == pygame.K_LEFT:
                    self.selected_index = (self.selected_index - 1) % len(self.game.party)
                elif event.key == pygame.K_RIGHT:
                    self.selected_index = (self.selected_index + 1) % len(self.game.party)

                # Cheat Code Detection
                if event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                    self.current_input_sequence.append(event.key)
                    # Keep only the last N keys where N is the length of the cheat code
                    if len(self.current_input_sequence) > len(self.cheat_code):
                        self.current_input_sequence.pop(0)
                    
                    # Check for match
                    if self.current_input_sequence == self.cheat_code:
                        if "Dev Tools" not in self.menu.options:
                            print("DEV: Dev Tools Unlocked!")
                            new_options = list(self.menu.options)
                            new_options.append("Dev Tools")
                            self.menu.set_options(new_options)
                            self.current_input_sequence = [] # Reset after success
                else:
                    # Any other key resets the sequence
                    self.current_input_sequence = []

        self.save_indicator.update(dt)
        
        # --- Web-Safe Transition Execution ---
        if self.is_transitioning:
            if pygame.time.get_ticks() - self.transition_start_time >= 1000:
                self.is_transitioning = False # Reset to prevent double-trigger
                if self.pending_combat_data:
                    p, enemies = self.pending_combat_data
                    from states.combat_state import CombatState
                    self.game.change_state(CombatState(self.game, self.fonts, player_data=p, enemy_data=enemies), transition_type='fade')
                    self.pending_combat_data = None
                return # Exit early to allow state change

        super().update(events, dt)

    def handle_main_menu(self, option):
        p = self.game.party[self.selected_index]
        if option == "Fight":
            # 1. Determine category and fetch enemies
            if hasattr(self.game, 'next_encounter') and self.game.next_encounter:
                enemies = self.game.next_encounter
                # If Rumors has a category stored, use it, else default to 'general'
                category = getattr(self.game, 'next_category', 'general')
                self.game.next_encounter = None 
            else:
                from core.creatures.enemies import get_scaled_enemies
                encounter_level = self.game.calculate_encounter_level()
                enemies, category = get_scaled_enemies(encounter_level, 
                                                     battle_count=self.game.battle_counter,
                                                     party_size=len(self.game.party))

            # 2. Tag every enemy with the category for the SpriteManager
            for e in enemies:
                e['category'] = category

            # 3. Transition to combat
            self.game.battle_counter += 1
            self.game.consecutive_combats = getattr(self.game, 'consecutive_combats', 0) + 1
            self.game.enemies = enemies
            
            try:
                from states.combat_state import CombatState
                # Transition to combat
                self.game.change_state(CombatState(self.game, self.fonts, player_data=p, enemy_data=enemies), transition_type='fade')
            except Exception as e:
                print(f"[HUB] CRITICAL ERROR Transitioning to Combat: {e}")

        elif option == "Shop":
            from .shop_state import ShopState
            self.game.change_state(ShopState(self.game, self.fonts, player=p))

        elif option == "Inventory":
            from .inventory_state import InventoryState
            # Pass selected character to inventory
            self.game.change_state(InventoryState(self.game, self.fonts, player=p))

        elif option == "Bestiary":
            from .bestiary import BestiaryState
            self.game.change_state(BestiaryState(self.game, self.fonts))

        elif option == "Tavern":
            from .tavern import TavernState
            self.game.change_state(TavernState(self.game, self.fonts))

        elif option == "Dev Tools":
            dev_options = ["1,000 HP", "10,000 Gold", "Level Up", "Max Level", "RP+", "Restart Game", "Back"]
            self.sub_menu = Menu(dev_options, self.font, header="Dev Tools")
            self.menu_state = "DEV"
            self.active_menu = self.sub_menu

    def handle_dev_menu(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.menu
        else:
            from Dev_Mode import DevTools
            # Apply to selected character
            msg = DevTools.apply_dev_action(option, self.game)
            if msg:
                print(f"DEV: {msg}")
            
            if option != "Restart Game":
                pass

    def draw(self, screen):
        # --- Draw background ---
        self.draw_background(screen)
        self.draw_settings_button(screen)

        width, height = screen.get_size()
        p = self.game.party[self.selected_index]

        # --- Title ---
        title_surf = self._static_surfs['title']
        title_y = scale_y(40)
        screen.blit(title_surf, (width // 2 - title_surf.get_width() // 2, title_y))
        
        # --- Gold ---
        gold_val = p.get('inventory_ref', {}).get('gold', 0)
        gold_str = f"Gold: {gold_val}"
        gold_surf = self._get_cached_text(gold_str, 'medium', COLOR_GOLD)
        gold_y = title_y + title_surf.get_height() + scale_y(5)
        screen.blit(gold_surf, (width // 2 - gold_surf.get_width() // 2, gold_y))

        # --- Player Bars (Top Center) ---
        from ui.bars import draw_bar

        if p:
            bx = width // 2 - scale_x(100)
            by = gold_y + gold_surf.get_height() + scale_y(15)

            cur_hp = min(p.get("max_hp", 10), p.get("current_hp", p.get("hp", 10)))
            draw_bar(screen, bx, by, scale_x(200), scale_y(25),
                     cur_hp, p.get("max_hp", 10), (200, 50, 50), self.fonts['medium'])

            if p.get("max_mp", 0) > 0:
                cur_mp = min(p.get("max_mp", 0), p.get("current_mp", 0))
                draw_bar(screen, bx, by + scale_y(30), scale_x(200), scale_y(25),
                         cur_mp, p.get("max_mp", 0), (50, 100, 200), self.fonts['medium'])
            
            if p.get("max_sp", 0) > 0:
                y_off = scale_y(60) if p.get("max_mp", 0) > 0 else scale_y(30)
                cur_sp = min(p.get("max_sp", 0), p.get("current_sp", 0))
                draw_bar(screen, bx, by + y_off, scale_x(200), scale_y(25),
                         cur_sp, p.get("max_sp", 0), (255, 200, 0), self.fonts['medium'])

            # --- XP Bar ---
            from core.players.leveler import load_xp_table, get_total_level_for_xp
            xp_table = load_xp_table()
            total_xp = p.get('xp', 0)
            current_lvl = get_total_level_for_xp(total_xp)
            
            # Progress within current level
            xp_this_lvl = xp_table.get(str(current_lvl), 0)
            next_lvl_str = str(current_lvl + 1)
            
            if next_lvl_str in xp_table:
                xp_needed_total = xp_table[next_lvl_str]
                xp_in_level = total_xp - xp_this_lvl
                xp_needed_in_level = xp_needed_total - xp_this_lvl
                
                # Calculate Y offset for XP bar (after HP, MP/SP)
                if p.get("max_mp", 0) > 0 and p.get("max_sp", 0) > 0:
                    xp_y_off = scale_y(90)
                elif p.get("max_mp", 0) > 0 or p.get("max_sp", 0) > 0:
                    xp_y_off = scale_y(60)
                else:
                    xp_y_off = scale_y(30)
                
                # Draw Teal XP Bar
                draw_bar(screen, bx, by + xp_y_off, scale_x(200), scale_y(25),
                         xp_in_level, xp_needed_in_level, (0, 128, 128), self.fonts['medium'])

        # --- Draw Party Characters (Rotating Dish) ---
        num_party = len(self.game.party)
        
        # Shift the entire platter left by 50px
        platter_center_x = width // 2 - scale_x(50)
        
        # Determine side indices
        left_idx = (self.selected_index - 1) % num_party
        right_idx = (self.selected_index + 1) % num_party

        # 1. Draw Left/Right (Inactive) Characters first for depth
        if num_party > 1:
            side_indices = []
            if num_party == 2:
                side_indices = [(right_idx, False)] # Just one on the right
            else:
                side_indices = [(left_idx, True), (right_idx, False)]

            for idx, is_left in side_indices:
                char = self.game.party[idx]
                bx_off = -scale_x(160) if is_left else scale_x(160)
                by_off = -scale_y(50)
                
                p_class = char.get("class", "fighter")
                inactive_sprite = self.cached_inactive_sprites.get(p_class)
                if inactive_sprite:
                    sw, sh = inactive_sprite.get_size()
                    screen.blit(inactive_sprite, (platter_center_x + bx_off - sw // 2, height - sh - scale_y(60) + by_off))

        # 2. Draw Active Character (Front and Center)
        player_class = p.get("class", "fighter")
        sprite = self.cached_active_sprites.get(player_class)
        if sprite:
            sw, sh = sprite.get_size()
            char_x = platter_center_x - sw // 2
            char_y = height - sh - scale_y(20)
            screen.blit(sprite, (char_x, char_y))

            # --- Floating Navigation Arrows (Tightened) ---
            if num_party > 1:
                arrow_float = math.sin(pygame.time.get_ticks() * 0.005) * scale_x(5)
                ay = char_y + sh // 2
                
                # Left Arrow - 0px outside
                alx = char_x - arrow_float
                pygame.draw.polygon(screen, COLOR_GOLD, [
                    (alx, ay), (alx + scale_x(15), ay - scale_y(12)), (alx + scale_x(15), ay + scale_y(12))
                ])
                
                # Right Arrow - 0px outside
                arx = char_x + sw + arrow_float
                pygame.draw.polygon(screen, COLOR_GOLD, [
                    (arx, ay), (arx - scale_x(15), ay - scale_y(12)), (arx - scale_x(15), ay + scale_y(12))
                ])

        # --- Player Info Panel (Right Side) - Drawn AFTER characters for layering ---
        self.inventory_panel.draw(screen, p)

        # --- MENU (Left Aligned) ---
        if self.active_menu:
            self.active_menu.draw(screen, 120, 250)
            
        # --- Tooltip (Draw LAST) ---
        self.inventory_panel.draw_tooltip(screen)

        # --- Save Indicator ---
        self.save_indicator.draw(screen)

        # --- Alert Dialogue ---
        if self.alert_dialogue:
            self.alert_dialogue.draw(screen)