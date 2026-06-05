import pygame
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD, COLOR_WHITE, SCALE_X, SCALE_Y
from ui.panel import Panel, draw_text_outlined

from core.players.player import get_weapon_display_name, get_armor_display_name

class InventoryPanel:
    def __init__(self, font, weapons_db, armor_db, shields_db, trinkets_db):
        # Support both single font and multi-font dict
        if isinstance(font, dict):
            self.fonts = font
            self.font = font.get('medium')
            # Ensure 'title' exists in fonts dict
            if 'title' not in self.fonts:
                self.fonts['title'] = self.fonts.get('large', self.font)
        else:
            self.font = font
            self.fonts = {'small': font, 'medium': font, 'large': font, 'title': font}

        self.weapons_db = weapons_db
        self.armor_db = armor_db
        self.shields_db = shields_db
        self.trinkets_db = trinkets_db
        self.hovered_item = None
        
        # Wasm Optimization: Text Cache
        self._text_cache = {}

    def _get_cached_text(self, text, font, color):
        """Retrieves or renders a text surface from cache."""
        cache_key = f"{text}_{id(font)}_{color}"
        if cache_key not in self._text_cache:
            tw, th = font.size(text)
            surf = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
            draw_text_outlined(surf, text, font, color, 5, 5)
            self._text_cache[cache_key] = surf
        return self._text_cache[cache_key]

    def draw(self, screen, player):
        if not player: return

        # Panel Dimensions (RAW 800x600)
        raw_pw, raw_ph = 250, 510
        # Panel Position (Right Side RAW)
        raw_px, raw_py = 520, 50

        panel = Panel(
            raw_px, raw_py, raw_pw, raw_ph,
            bg_color=(30, 30, 50),
            border_color=COLOR_GOLD,
            border_width=3,
            alpha=220
        )
        rect = panel.draw(screen)

        # Content
        line_h = self.font.get_height()
        small_line_h = self.fonts['medium'].get_height() - scale_y(2)
        curr_y = rect.y + scale_y(20)
        center_x = rect.centerx

        # Name & Class
        name_str = f"{player.get('name', 'Player')} - Lvl {player.get('level', 1)}"
        name_surf = self._get_cached_text(name_str, self.font, COLOR_WHITE)
        screen.blit(name_surf, (center_x - name_surf.get_width() // 2, curr_y - 5))
        curr_y += line_h
        
        class_str = player.get('class', 'Fighter').title()
        class_surf = self._get_cached_text(class_str, self.fonts['medium'], COLOR_GOLD)
        screen.blit(class_surf, (center_x - class_surf.get_width() // 2, curr_y - 5))
        curr_y += self.fonts['medium'].get_height() + scale_y(10)

        # AC & Spell DC & Proficiency (Using small font for details)
        ac_str = f"Armor Class: {player.get('ac', 10)}"
        ac_surf = self._get_cached_text(ac_str, self.fonts['medium'], COLOR_WHITE)
        screen.blit(ac_surf, (rect.x + scale_x(15) - 5, curr_y - 5))
        curr_y += small_line_h

        prof_str = f"Proficiency: +{player.get('proficiency_bonus', 2)}"
        prof_surf = self._get_cached_text(prof_str, self.fonts['medium'], COLOR_WHITE)
        screen.blit(prof_surf, (rect.x + scale_x(15) - 5, curr_y - 5))
        curr_y += small_line_h

        ss_str = f"Spell DC: +{player.get('spell_save', 0)}"
        ss_surf = self._get_cached_text(ss_str, self.fonts['medium'], COLOR_WHITE)
        screen.blit(ss_surf, (rect.x + scale_x(15) - 5, curr_y - 5))
        curr_y += small_line_h

        # Sneak Attack (Rogue only)
        rogue_level = player.get('class_levels', {}).get('rogue', 0)
        if rogue_level > 0:
            sa_dice = (rogue_level + 1) // 2
            sa_str = f"Sneak Attack: {sa_dice}d6"
            sa_surf = self._get_cached_text(sa_str, self.fonts['medium'], COLOR_WHITE)
            screen.blit(sa_surf, (rect.x + scale_x(15) - 5, curr_y - 5))
            curr_y += small_line_h

        curr_y += scale_y(20)

        # Equipment
        eq = ["weapon", "armor", "shield", "trinket"]
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_item = None
        
        for slot in eq:
            item_key = player.get(slot, 'none')
            
            label = f"{slot.title()}: "
            
            if slot == 'weapon':
                val_str = get_weapon_display_name(player, item_key)
            elif slot == 'armor':
                val_str = get_armor_display_name(player, item_key)
            else:
                val_str = item_key.replace('_', ' ').title()
            
            # Draw label
            lx = rect.x + scale_x(15)
            label_surf = self._get_cached_text(label, self.fonts['medium'], COLOR_GOLD)
            screen.blit(label_surf, (lx - 5, curr_y - 5))
            
            # Draw value and check for hover
            vx = lx + label_surf.get_width() - 10
            val_surf = self._get_cached_text(val_str, self.fonts['medium'], COLOR_WHITE)
            val_rect = screen.blit(val_surf, (vx, curr_y - 5))
            
            if val_rect.collidepoint(mouse_pos):
                # Map to DB
                if slot == 'weapon': self.hovered_item = (self.weapons_db.get(item_key), 'weapon')
                elif slot == 'armor': self.hovered_item = (self.armor_db.get(item_key), 'armor')
                elif slot == 'shield': self.hovered_item = (self.shields_db.get(item_key), 'shield')
                elif slot == 'trinket': self.hovered_item = (self.trinkets_db.get(item_key), 'trinket')
            
            curr_y += small_line_h + scale_y(4)

        # Buffs
        curr_y += scale_y(12)
        buff_header_surf = self._get_cached_text("Active Buffs:", self.fonts['medium'], COLOR_GOLD)
        screen.blit(buff_header_surf, (rect.x + scale_x(15) - 5, curr_y - 5))
        curr_y += small_line_h + scale_y(4)
        
        # Aggregated Buffs
        totals = {
            'Health': 0,
            'Stamina': 0,
            'Attack': 0,
            'Damage': 0,
            'Spell Resist': 0,
            'Initiative': 0,
            'Damage Resist': 0
        }
        special_buffs = []

        # Aggregate stats from all equipment
        for db, slot in [(self.trinkets_db, 'trinket'), (self.shields_db, 'shield'), (self.armor_db, 'armor')]:
            stats = db.get(player.get(slot, 'none'), {})
            totals['Health'] += stats.get('bonus_hp', 0)
            totals['Stamina'] += stats.get('bonus_sp', 0)
            totals['Attack'] += stats.get('bonus_atk', 0)
            totals['Damage'] += stats.get('bonus_dmg', 0)
            totals['Spell Resist'] += stats.get('spell_resist', 0)
            totals['Initiative'] += stats.get('initiative_boost', 0)
            totals['Damage Resist'] += stats.get('damage_resist', 0)

        # Format display list
        display_buffs = []
        for stat, val in totals.items():
            if val > 0:
                display_buffs.append(f"{stat} +{val}")
        
        display_buffs.extend(special_buffs)

        if not display_buffs:
            none_surf = self._get_cached_text("None", self.fonts['medium'], (150, 150, 150))
            screen.blit(none_surf, (rect.x + scale_x(30) - 5, curr_y - 5))
        else:
            for b in display_buffs:
                b_text = f"• {b}"
                b_surf = self._get_cached_text(b_text, self.fonts['medium'], (200, 255, 200))
                screen.blit(b_surf, (rect.x + scale_x(25) - 5, curr_y - 5))
                curr_y += small_line_h

    def draw_tooltip(self, screen):
        if not self.hovered_item or not self.hovered_item[0]: return
        
        item_data, item_type = self.hovered_item
        text = item_data.get('description', 'No description.')
        
        # Add stats to text
        if item_type == 'weapon':
            text += f" (D{item_data.get('die', 4)}, {item_data.get('on_hit_effect', 'none').title()})"
        elif item_type == 'armor':
            text += f" (AC: {item_data.get('ac', 10)}, {item_data.get('type', 'none').title()})"
        elif item_type == 'shield':
            text += f" (AC: +{item_data.get('ac', 0)})"
            
        mouse_pos = pygame.mouse.get_pos()
        
        tw, th = 300, 120
        tx, ty = mouse_pos[0] + 20, mouse_pos[1] + 20
        
        # Wrap text (using large font for tooltip description)
        font = self.fonts['large']
        words = text.split(' ')
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            w, _ = font.size(test_line)
            if w > scale_x(tw - 20):
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                current_line.append(word)
        lines.append(' '.join(current_line))
        
        th = len(lines) * font.get_height() + scale_y(30)
        
        # Clamp to screen
        if tx + scale_x(tw) > SCREEN_WIDTH: tx = mouse_pos[0] - scale_x(tw) - 20
        if ty + scale_y(th) > SCREEN_HEIGHT: ty = mouse_pos[1] - scale_y(th) - 20

        t_panel = Panel(
            tx / SCALE_X, ty / SCALE_Y, 
            tw, th / SCALE_Y,
            bg_color=(20, 20, 30), border_color=COLOR_GOLD, alpha=240
        )
        t_rect = t_panel.draw(screen)
        
        for i, line in enumerate(lines):
            draw_text_outlined(screen, line, font, COLOR_WHITE, t_rect.x + scale_x(10), t_rect.y + scale_y(10) + i * font.get_height())
