import pygame
import os
import json
import random
from .base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.graphics.backgrounds import BackgroundManager
from interfaces.pygame.ui.panel import Panel, draw_text_outlined
from interfaces.pygame.graphics.sprite_manager import SpriteManager
from core.game_rules.path_utils import get_resource_path
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y, COLOR_GOLD, COLOR_WHITE, COLOR_GRAY

class BestiaryState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_bestiary_bg()
        
        self.menu_state = "CHAPTERS"
        
        # --- Filter Chapters: Only show chapters with at least one discovered creature ---
        all_types = [f.replace('.json', '') for f in os.listdir(get_resource_path(os.path.join('data', 'creatures'))) if f.endswith('.json')]
        self.creature_types = []
        
        for c_type in all_types:
            # Load the JSON for this type to see if any creature within it has RP >= 1
            try:
                filepath = get_resource_path(os.path.join('data', 'creatures', f"{c_type}.json"))
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                has_discovered = False
                for creature_id in data.keys():
                    if self.game.bestiary_rp.get(creature_id, 0) >= 1:
                        has_discovered = True
                        break
                
                if has_discovered:
                    self.creature_types.append(c_type)
            except:
                continue

        self.chapters_menu = Menu([t.title() for t in self.creature_types] + ["Back"], font, header="Creature Chapters", width=300)
        self.active_menu = self.chapters_menu
        
        self.selected_type = None
        self.creatures_list = []
        self.creatures_menu = None
        
        self.current_creature_idx = 0

        self.build_spec_sheet_layout()

    def on_select(self, option):
        if self.menu_state == "CHAPTERS":
            if option == "Back":
                from .hub import HubState
                self.game.change_state(HubState(self.game, self.font))
            else:
                self.selected_type = option.lower()
                self.load_creatures_of_type(self.selected_type)
                self.menu_state = "CREATURES"
                self.active_menu = self.creatures_menu
        elif self.menu_state == "CREATURES":
            if option == "Back":
                self.menu_state = "CHAPTERS"
                self.active_menu = self.chapters_menu
            else:
                # Find index
                for i, c in enumerate(self.creatures_list):
                    if c['name'].replace('_', ' ').title() == option.split(" (Lv")[0]:
                        self.current_creature_idx = i
                        break
                self.menu_state = "SPEC_SHEET"
                self.active_menu = self.spec_nav_menu
        elif self.menu_state == "SPEC_SHEET":
            if option == "Previous":
                self.prev_creature()
            elif option == "Next":
                self.next_creature()
            elif option == "Return":
                self.menu_state = "CREATURES"
                self.active_menu = self.creatures_menu

    def load_creatures_of_type(self, creature_type):
        try:
            filepath = get_resource_path(os.path.join('data', 'creatures', f"{creature_type}.json"))
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.creatures_list = []
            
            # --- THE FIX: Using the Top-Level Keys ---
            # Your JSON is beautifully structured as { "creature_id": { stats } }
            for creature_id, stats in data.items():
                if isinstance(stats, dict):
                    # --- RP Check: Only show if discovered (RP >= 1) ---
                    rp = self.game.bestiary_rp.get(creature_id, 0)
                    if rp < 1:
                        continue

                    # 1. Generate the display name from the key (e.g., "deep_roathe" -> "Deep Roathe")
                    display_name = creature_id.replace('_', ' ').title()
                    
                    # 2. Inject the ID and Name into the dictionary so the rest of the UI works
                    stats['_id'] = creature_id
                    stats['_category'] = creature_type
                    
                    # Ensure fields needed by SpriteManager are present
                    stats['base_name'] = creature_id
                    stats['category'] = creature_type
                    
                    # If you ever DO manually add a 'name' key, it will use that, otherwise it uses the generated one
                    stats['name'] = stats.get('name', display_name) 
                    
                    self.creatures_list.append(stats)
            
            # --- DEBUG FALLBACK ---
            if not self.creatures_list:
                print(f"\nDEBUG: Loaded {creature_type}.json but found 0 creatures!")
            
            # Sort by Level first, then Name
            self.creatures_list.sort(key=lambda x: (x.get('level', 1), x.get('name', '')))
            
            # Rebuild Menu safely
            options = [c['name'] for c in self.creatures_list] + ["Back"]
            self.creatures_menu = Menu(options, self.font, header=f"{creature_type.title()} Creatures", width=300)
            self.active_menu = self.creatures_menu
            self.menu_state = "CREATURE_LIST"
            
        except Exception as e:
            print(f"Error loading bestiary category {creature_type}: {e}")

    def next_creature(self):
        if self.current_creature_idx < len(self.creatures_list) - 1:
            self.current_creature_idx += 1

    def prev_creature(self):
        if self.current_creature_idx > 0:
            self.current_creature_idx -= 1

    def build_spec_sheet_layout(self):
        # --- Base Layout Math (UNSCALED) ---
        # Buffer increased by 50px (from 20 to 70)
        margin = 70
        inner_gap = 20
        
        left_col_x = margin
        left_col_w = 180
        
        # Nav Menu will be drawn at y=margin (70)
        nav_h = 130 
        
        sp_y = margin + nav_h + inner_gap
        sp_h = 600 - sp_y - margin # 600 - 70 - 130 - 20 - 70 = 310
        
        # Build Left Panel
        self.sprite_panel = Panel(left_col_x, sp_y, left_col_w, sp_h)
        self.spec_nav_menu = Menu(["Previous", "Next", "Return"], self.font, width=left_col_w)
        
        # --- Right Column Math ---
        right_col_x = left_col_x + left_col_w + inner_gap
        right_col_w = 800 - right_col_x - margin # 800 - 70 - 180 - 20 - 70 = 460
        
        # Build Right Panels
        stats_y = margin
        stats_h = 140
        self.stats_panel = Panel(right_col_x, stats_y, right_col_w, stats_h)
        
        loot_y = stats_y + stats_h + inner_gap
        loot_h = 100
        self.loot_panel = Panel(right_col_x, loot_y, right_col_w, loot_h)
        
        ab_y = loot_y + loot_h + inner_gap
        ab_h = 600 - ab_y - margin # 600 - 70 - 140 - 20 - 100 - 20 - 70 = 180
        self.ability_panel = Panel(right_col_x, ab_y, right_col_w, ab_h)

    def update(self, events, dt):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.menu_state == "SPEC_SHEET":
                        self.menu_state = "CHAPTERS"
                        self.active_menu = self.chapters_menu
                    elif self.menu_state == "CREATURES":
                        self.menu_state = "CHAPTERS"
                        self.active_menu = self.chapters_menu
                    else:
                        from .hub import HubState
                        self.game.change_state(HubState(self.game, self.font))
                    return
                
                if self.menu_state == "SPEC_SHEET":
                    if event.key == pygame.K_LEFT:
                        self.prev_creature()
                    elif event.key == pygame.K_RIGHT:
                        self.next_creature()
        
        super().update(events, dt)

    def draw(self, screen):
        self.draw_background(screen)
        self.draw_settings_button(screen)
        
        if self.menu_state in ["CHAPTERS", "CREATURES"]:
            # Main Chapters Menu - Anchored left within 70px margin
            # Width 300, so center is 70 + 150 = 220
            # Start Y 85 gives a panel top at 70
            self.chapters_menu.draw(screen, 220, 85)
            
            if self.menu_state == "CREATURES" and self.creatures_menu:
                # Submenu - Drawn to the right of the chapters menu
                # Center is 220 + 150 + 20 + 150 = 540
                self.creatures_menu.draw(screen, 540, 85)
                
        elif self.menu_state == "SPEC_SHEET":
            self.draw_spec_sheet(screen)

    def draw_spec_sheet(self, screen):
        c = self.creatures_list[self.current_creature_idx]
        c_id = c.get('_id', '')
        rp = self.game.bestiary_rp.get(c_id, 0)
        
        # 1. Draw Panels & Catch their perfectly scaled Rects!
        sprite_rect = self.sprite_panel.draw(screen)
        stats_rect = self.stats_panel.draw(screen)
        loot_rect = self.loot_panel.draw(screen)
        ability_rect = self.ability_panel.draw(screen)
        
        # 2. Draw Nav Menu (RAW center_x=160, start_y=85 for top=70)
        self.spec_nav_menu.draw(screen, 160, 85)
        
        # 3. Draw Sprite safely
        sz = scale_x(180)
        from interfaces.pygame.graphics.sprite_manager import SpriteManager
        raw_sprite = SpriteManager.get_enemy_sprite(c, size=(sz, sz))
        sprite_surface = None
        
        # Extract the actual Surface
        if isinstance(raw_sprite, pygame.Surface):
            sprite_surface = raw_sprite
        elif isinstance(raw_sprite, list) and len(raw_sprite) > 0:
            sprite_surface = raw_sprite[0]
        elif isinstance(raw_sprite, dict):
            idle_anim = raw_sprite.get('idle', [])
            if idle_anim and len(idle_anim) > 0:
                sprite_surface = idle_anim[0]
                
        # Draw the sprite using the dynamically scaled rect
        if sprite_surface and isinstance(sprite_surface, pygame.Surface):
            try:
                flipped_sprite = pygame.transform.flip(sprite_surface, True, False)
                screen.blit(flipped_sprite, (sprite_rect.centerx - sz // 2, sprite_rect.centery - sz // 2))
            except Exception as e:
                # FIXED: Removed self.
                draw_text_outlined(screen, "Flip Error", self.font, COLOR_WHITE, sprite_rect.x + scale_x(20), sprite_rect.y + scale_y(50))
        else:
            # FIXED: Removed self.
            draw_text_outlined(screen, "No Image", self.font, COLOR_GRAY, sprite_rect.x + scale_x(50), sprite_rect.y + scale_y(100))
        
        # 4. Draw RP
        rp_text = f"Research Points: {rp}"
        draw_text_outlined(screen, rp_text, self.font, COLOR_GOLD, sprite_rect.x + scale_x(15), sprite_rect.bottom - scale_y(25))
        
        # 5. Stats
        stats_title = f"{c.get('name', 'Unknown')}'s Stats"
        draw_text_outlined(screen, stats_title, self.font, COLOR_GOLD, stats_rect.x + scale_x(20), stats_rect.y + scale_y(15))
        
        if rp >= 5:
            draw_text_outlined(screen, f"Level: {c.get('level', '?')}", self.font, COLOR_WHITE, stats_rect.x + scale_x(20), stats_rect.y + scale_y(50))
            draw_text_outlined(screen, f"AC: {c.get('armor', '?')}", self.font, COLOR_WHITE, stats_rect.x + scale_x(200), stats_rect.y + scale_y(50))
            hp_val = str(c.get('hp', '?')) if rp >= 1 else "???"
            draw_text_outlined(screen, f"HP: {hp_val}", self.font, COLOR_WHITE, stats_rect.x + scale_x(20), stats_rect.y + scale_y(80))
            draw_text_outlined(screen, f"Proficiency: +{c.get('proficiency_bonus', '?')}", self.font, COLOR_WHITE, stats_rect.x + scale_x(200), stats_rect.y + scale_y(80))
            draw_text_outlined(screen, f"Attacks: {c.get('attack_count', 1)}", self.font, COLOR_WHITE, stats_rect.x + scale_x(20), stats_rect.y + scale_y(110))
            draw_text_outlined(screen, f"Damage: {c.get('die', '?')}", self.font, COLOR_WHITE, stats_rect.x + scale_x(200), stats_rect.y + scale_y(110))
        else:
            hp_val = str(c.get('hp', '?')) if rp >= 1 else "???"
            draw_text_outlined(screen, f"HP: {hp_val}", self.font, COLOR_WHITE, stats_rect.x + scale_x(20), stats_rect.y + scale_y(50))
            draw_text_outlined(screen, "Kill more to reveal stats...", self.font, COLOR_GRAY, stats_rect.x + scale_x(20), stats_rect.y + scale_y(80))
            
        # 6. Loot
        draw_text_outlined(screen, "Loot Drops", self.font, COLOR_GOLD, loot_rect.x + scale_x(20), loot_rect.y + scale_y(15))
        reward = c.get('reward', {})
        loot_y = loot_rect.y + scale_y(45)
        draw_text_outlined(screen, f"Gold: {reward.get('gold', 0)}g", self.font, COLOR_WHITE, loot_rect.x + scale_x(20), loot_y)
        loot_y += scale_y(25)
        for item in reward.get('items', []):
            item_name = item.get('name', '').replace('_', ' ').title()
            draw_text_outlined(screen, f"- {item_name}", self.font, COLOR_WHITE, loot_rect.x + scale_x(20), loot_y)
            loot_y += scale_y(25)
            
        # 7. Abilities
        draw_text_outlined(screen, "Abilities", self.font, COLOR_GOLD, ability_rect.x + scale_x(20), ability_rect.y + scale_y(15))
        if rp >= 10:
            ability_y = ability_rect.y + scale_y(45)
            abilities = c.get('skills', []) + c.get('spells', [])
            if not abilities:
                draw_text_outlined(screen, "None", self.font, COLOR_GRAY, ability_rect.x + scale_x(20), ability_y)
            else:
                from core.combat.combat_ai import CombatAI
                for a_name in abilities[:3]: 
                    data = CombatAI.get_ability_data(a_name)
                    if not data or data.get('type') == 'heal': continue
                    
                    name_disp = a_name.replace('_', ' ').title()
                    if rp >= 40:
                        die = data.get('damage_die', data.get('die', ''))
                        desc = data.get('description', '')
                        draw_text_outlined(screen, f"{name_disp} ({die})", self.font, COLOR_GOLD, ability_rect.x + scale_x(20), ability_y)
                        ability_y += scale_y(20)
                        draw_text_outlined(screen, desc[:60] + ("..." if len(desc)>60 else ""), self.font, COLOR_WHITE, ability_rect.x + scale_x(30), ability_y, size=scale_y(14))
                        ability_y += scale_y(30)
                    else:
                        draw_text_outlined(screen, name_disp, self.font, COLOR_WHITE, ability_rect.x + scale_x(20), ability_y)
                        ability_y += scale_y(25)
        else:
            draw_text_outlined(screen, "Kill more to reveal abilities...", self.font, COLOR_GRAY, ability_rect.x + scale_x(20), ability_rect.y + scale_y(45))