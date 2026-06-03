import pygame
import os
import json
import random
from .base_state import BaseState
from ui.menu import Menu
from graphics.backgrounds import BackgroundManager
from ui.panel import Panel, draw_text_outlined
from graphics.sprite_manager import SpriteManager
from core.game_rules.path_utils import get_resource_path
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y, COLOR_GOLD, COLOR_WHITE, COLOR_GRAY, SCALE_X, SCALE_Y

class BestiaryState(BaseState):
    _all_creature_types = None

    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_bestiary_bg()
        
        self.menu_state = "CHAPTERS"
        
        # --- Filter Chapters: Only show chapters with at least one discovered creature ---
        if BestiaryState._all_creature_types is None:
            c_path = get_resource_path(os.path.join('data', 'creatures'))
            if os.path.exists(c_path):
                BestiaryState._all_creature_types = [f.replace('.json', '') for f in os.listdir(c_path) if f.endswith('.json')]
            else:
                BestiaryState._all_creature_types = []
        
        self.creature_types = []
        for c_type in BestiaryState._all_creature_types:
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

        # pos=(400, 150) centers the 300px width menu horizontally (400 - 150 = 250 start_x)
        self.chapters_menu = Menu([t.title() for t in self.creature_types] + ["Back"], self.fonts['medium'], pos=(400, 150), header="Creature Chapters", width=300)
        self.active_menu = self.chapters_menu
        
        self.selected_type = None
        self.creatures_list = []
        
        self.current_creature_idx = 0

        # Tooltip State
        self.hover_rects = []
        self.active_tooltip = None
        
        # Pre-load item lookup for loot tooltips
        from core.game_rules.database_manager import db
        self.item_lookup = {}
        for cat in ['weapons', 'armor', 'shields', 'trinkets', 'consumables', 'junk']:
            items = db.get_data(cat)
            for item_id, item_data in items.items():
                self.item_lookup[item_id] = item_data

        self.build_spec_sheet_layout()

    def on_select(self, option):
        if self.menu_state == "CHAPTERS":
            if option == "Back":
                from .hub import HubState
                self.game.change_state(HubState(self.game, self.fonts))
            else:
                self.selected_type = option.lower()
                self.load_creatures_of_type(self.selected_type)
                if self.creatures_list:
                    self.current_creature_idx = 0
                    self.menu_state = "SPEC_SHEET"
                    self.active_menu = self.spec_nav_menu
        elif self.menu_state == "SPEC_SHEET":
            if option == "Previous":
                self.prev_creature()
            elif option == "Next":
                self.next_creature()
            elif option == "Return":
                self.menu_state = "CHAPTERS"
                self.active_menu = self.chapters_menu

    def load_creatures_of_type(self, creature_type):
        try:
            filepath = get_resource_path(os.path.join('data', 'creatures', f"{creature_type}.json"))
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.creatures_list = []
            
            for creature_id, stats in data.items():
                if isinstance(stats, dict):
                    rp = self.game.bestiary_rp.get(creature_id, 0)
                    if rp < 1:
                        continue

                    display_name = creature_id.replace('_', ' ').title()
                    stats['_id'] = creature_id
                    stats['_category'] = creature_type
                    stats['base_name'] = creature_id
                    stats['category'] = creature_type
                    stats['name'] = stats.get('name', display_name) 
                    
                    self.creatures_list.append(stats)
            
            self.creatures_list.sort(key=lambda x: (x.get('level', 1), x.get('name', '')))
            
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
        margin = 70
        inner_gap = 10 
        
        left_col_x = margin
        left_col_w = 180
        
        # Nav Menu height is roughly 110 with default padding
        nav_h = 110 
        
        sp_y = margin + nav_h # 70 + 110 = 180
        sp_h = 600 - sp_y - margin
        
        # Build Left Panel
        self.sprite_panel = Panel(left_col_x, sp_y, left_col_w, sp_h)
        # Compact Nav Menu: line_spacing=0, top_padding=5, bottom_padding=10
        # pos=(160, 75) so raw_y = 75 - 5 = 70
        self.spec_nav_menu = Menu(["Previous", "Next", "Return"], self.fonts['medium'], pos=(160, 75), width=left_col_w, enable_horizontal=False, line_spacing=0, top_padding=5, bottom_padding=10)
        
        # --- Right Column Math ---
        right_col_x = left_col_x + left_col_w + 20 
        right_col_w = 800 - right_col_x - margin 
        
        # Build Right Panels
        stats_y = margin
        stats_h = 160
        self.stats_panel = Panel(right_col_x, stats_y, right_col_w, stats_h)
        
        loot_y = stats_y + stats_h + inner_gap
        loot_h = 120
        self.loot_panel = Panel(right_col_x, loot_y, right_col_w, loot_h)
        
        ab_y = loot_y + loot_h + inner_gap
        ab_h = 600 - ab_y - margin 
        self.ability_panel = Panel(right_col_x, ab_y, right_col_w, ab_h)

    def update(self, events, dt):
        mouse_pos = pygame.mouse.get_pos()
        self.active_tooltip = None
        for rect, data in self.hover_rects:
            if rect.collidepoint(mouse_pos):
                self.active_tooltip = data
                break

        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.menu_state == "SPEC_SHEET":
                        self.menu_state = "CHAPTERS"
                        self.active_menu = self.chapters_menu
                    else:
                        from .hub import HubState
                        self.game.change_state(HubState(self.game, self.fonts))
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
        
        if self.menu_state == "CHAPTERS":
            self.chapters_menu.draw(screen)
                
        elif self.menu_state == "SPEC_SHEET":
            self.draw_spec_sheet(screen)
            self.draw_tooltip(screen)

    def draw_spec_sheet(self, screen):
        c = self.creatures_list[self.current_creature_idx]
        c_id = c.get('_id', '')
        rp = self.game.bestiary_rp.get(c_id, 0)
        self.hover_rects = []

        sprite_rect = self.sprite_panel.draw(screen)
        stats_rect = self.stats_panel.draw(screen)
        loot_rect = self.loot_panel.draw(screen)
        ability_rect = self.ability_panel.draw(screen)
        
        self.spec_nav_menu.draw(screen)
        
        sz = scale_x(180)
        from graphics.sprite_manager import SpriteManager
        raw_sprite = SpriteManager.get_enemy_sprite(c, size=(sz, sz))
        sprite_surface = None
        
        if isinstance(raw_sprite, pygame.Surface):
            sprite_surface = raw_sprite
        elif isinstance(raw_sprite, list) and len(raw_sprite) > 0:
            sprite_surface = raw_sprite[0]
        elif isinstance(raw_sprite, dict):
            idle_anim = raw_sprite.get('idle', [])
            if idle_anim and len(idle_anim) > 0:
                sprite_surface = idle_anim[0]
                
        if sprite_surface and isinstance(sprite_surface, pygame.Surface):
            try:
                flipped_sprite = pygame.transform.flip(sprite_surface, True, False)
                screen.blit(flipped_sprite, (sprite_rect.centerx - sz // 2, sprite_rect.centery - sz // 2))
            except Exception:
                draw_text_outlined(screen, "Flip Error", self.fonts['medium'], COLOR_WHITE, sprite_rect.x + scale_x(20), sprite_rect.y + scale_y(50))
        else:
            draw_text_outlined(screen, "No Image", self.fonts['medium'], COLOR_GRAY, sprite_rect.x + scale_x(50), sprite_rect.y + scale_y(100))
        
        rp_text = f"Research Points: {rp}"
        draw_text_outlined(screen, rp_text, self.fonts['medium'], COLOR_GOLD, sprite_rect.x + scale_x(15), sprite_rect.bottom - scale_y(25))
        
        stats_title = f"{c.get('name', 'Unknown')}'s Stats"
        draw_text_outlined(screen, stats_title, self.fonts['large'], COLOR_GOLD, stats_rect.x + scale_x(20), stats_rect.y + scale_y(15))
        
        if rp >= 5:
            draw_text_outlined(screen, f"Level: {c.get('level', '?')}", self.fonts['medium'], COLOR_WHITE, stats_rect.x + scale_x(20), stats_rect.y + scale_y(50))
            draw_text_outlined(screen, f"AC: {c.get('armor', '?')}", self.fonts['medium'], COLOR_WHITE, stats_rect.x + scale_x(200), stats_rect.y + scale_y(50))
            hp_val = str(c.get('hp', '?')) if rp >= 1 else "???"
            draw_text_outlined(screen, f"HP: {hp_val}", self.fonts['medium'], COLOR_WHITE, stats_rect.x + scale_x(20), stats_rect.y + scale_y(85))
            draw_text_outlined(screen, f"Proficiency: +{c.get('proficiency_bonus', '?')}", self.fonts['medium'], COLOR_WHITE, stats_rect.x + scale_x(200), stats_rect.y + scale_y(85))
            draw_text_outlined(screen, f"Attacks: {c.get('attack_count', 1)}", self.fonts['medium'], COLOR_WHITE, stats_rect.x + scale_x(20), stats_rect.y + scale_y(120))
            
            raw_die = c.get('die', '?')
            prof = c.get('proficiency_bonus', 0)
            dmg_str = f"1d{raw_die} + {prof}" if isinstance(raw_die, int) else f"{raw_die} + {prof}"
            draw_text_outlined(screen, f"Damage: {dmg_str}", self.fonts['medium'], COLOR_WHITE, stats_rect.x + scale_x(200), stats_rect.y + scale_y(120))
        else:
            hp_val = str(c.get('hp', '?')) if rp >= 1 else "???"
            draw_text_outlined(screen, f"HP: {hp_val}", self.fonts['medium'], COLOR_WHITE, stats_rect.x + scale_x(20), stats_rect.y + scale_y(50))
            draw_text_outlined(screen, "Kill more to reveal stats...", self.fonts['medium'], COLOR_GRAY, stats_rect.x + scale_x(20), stats_rect.y + scale_y(85))
            
        draw_text_outlined(screen, "Loot Drops", self.fonts['large'], COLOR_GOLD, loot_rect.x + scale_x(20), loot_rect.y + scale_y(15))
        reward = c.get('reward', {})
        loot_y_base = loot_rect.y + scale_y(55)
        draw_text_outlined(screen, f"Gold: {reward.get('gold', 0)}g", self.fonts['medium'], COLOR_WHITE, loot_rect.x + scale_x(20), loot_y_base)
        
        items_x = loot_rect.x + scale_x(200)
        curr_loot_y = loot_y_base
        for item_entry in reward.get('items', []):
            item_id = item_entry.get('name', '')
            item_name = item_id.replace('_', ' ').title()
            r = draw_text_outlined(screen, f"- {item_name}", self.fonts['medium'], COLOR_WHITE, items_x, curr_loot_y)
            item_data = self.item_lookup.get(item_id)
            if item_data:
                self.hover_rects.append((r, {'type': 'item', 'data': item_data}))
            curr_loot_y += scale_y(30)
            
        draw_text_outlined(screen, "Abilities", self.fonts['large'], COLOR_GOLD, ability_rect.x + scale_x(20), ability_rect.y + scale_y(15))
        if rp >= 10:
            ability_y = ability_rect.y + scale_y(50)
            abilities = c.get('skills', []) + c.get('spells', [])
            if not abilities:
                draw_text_outlined(screen, "None", self.fonts['medium'], COLOR_GRAY, ability_rect.x + scale_x(20), ability_y)
            else:
                from core.combat.combat_ai import CombatAI
                from core.combat.ability_baker import AbilityBaker
                for a_name in abilities[:2]: 
                    data = CombatAI.get_ability_data(a_name)
                    if not data or data.get('type') == 'heal': continue
                    name_disp = a_name.replace('_', ' ').title()
                    baked_data = AbilityBaker.bake_ability(data, c)
                    if rp >= 40:
                        die = baked_data.get('damage_die', baked_data.get('die', ''))
                        desc = baked_data.get('description', '')
                        r = draw_text_outlined(screen, f"{name_disp} ({die})", self.fonts['medium'], COLOR_GOLD, ability_rect.x + scale_x(20), ability_y)
                        self.hover_rects.append((r, {'type': 'ability', 'data': baked_data}))
                        ability_y += scale_y(25)
                        r2 = draw_text_outlined(screen, desc[:60] + ("..." if len(desc)>60 else ""), self.fonts['medium'], COLOR_WHITE, ability_rect.x + scale_x(30), ability_y)
                        self.hover_rects.append((r2, {'type': 'ability', 'data': baked_data}))
                        ability_y += scale_y(35)
                    else:
                        r = draw_text_outlined(screen, name_disp, self.fonts['medium'], COLOR_WHITE, ability_rect.x + scale_x(20), ability_y)
                        self.hover_rects.append((r, {'type': 'ability', 'data': baked_data}))
                        ability_y += scale_y(30)
        else:
            draw_text_outlined(screen, "Kill more to reveal abilities...", self.fonts['medium'], COLOR_GRAY, ability_rect.x + scale_x(20), ability_rect.y + scale_y(50))

    def draw_tooltip(self, screen):
        if not self.active_tooltip: return
        info = self.active_tooltip
        title, description, extra = "", "", ""
        if info['type'] == 'item':
            data = info['data']
            title = data.get('name', 'Item').replace('_', ' ').title()
            description = data.get('description', 'No description.')
            extra = f"Value: {data.get('cost', 0)} Gold"
        elif info['type'] == 'ability':
            data = info['data']
            title = data.get('name', 'Ability').replace('_', ' ').title()
            description = data.get('description', 'No description.')
            
        font = self.fonts['medium']
        tw = 300
        lines = [('title', title)]
        if extra: lines.append(('extra', extra))
        lines.append(('spacer', ''))
        
        words = str(description).split(' ')
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            w, _ = font.size(test_line)
            if w > scale_x(tw - 20):
                lines.append(('text', ' '.join(current_line)))
                current_line = [word]
            else:
                current_line.append(word)
        lines.append(('text', ' '.join(current_line)))
        
        line_h = font.get_height()
        th = len(lines) * line_h + scale_y(20)
        mouse_pos = pygame.mouse.get_pos()
        tx, ty = mouse_pos[0] + 20, mouse_pos[1] - th // 2
        if tx + scale_x(tw) > SCREEN_WIDTH: tx = mouse_pos[0] - scale_x(tw) - 20
        tx, ty = max(10, tx), max(10, min(ty, SCREEN_HEIGHT - th - 10))
        
        t_panel = Panel(tx / SCALE_X, ty / SCALE_Y, tw, th / SCALE_Y, bg_color=(20, 20, 30), alpha=240)
        t_rect = t_panel.draw(screen)
        curr_y = t_rect.y + scale_y(10)
        for l_type, l_text in lines:
            if l_type == 'title':
                draw_text_outlined(screen, l_text, font, COLOR_GOLD, t_rect.x + scale_x(10), curr_y)
            elif l_type == 'extra':
                draw_text_outlined(screen, l_text, font, (200, 200, 200), t_rect.x + scale_x(10), curr_y)
            elif l_type == 'text':
                draw_text_outlined(screen, l_text, font, COLOR_WHITE, t_rect.x + scale_x(10), curr_y)
            curr_y += line_h
