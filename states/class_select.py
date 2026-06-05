import pygame
from states.base_state import BaseState
from ui.menu import Menu
from graphics.backgrounds import BackgroundManager
from ui.panel import Panel, draw_text_outlined
from core.players.player import classes
from graphics.sprite_manager import SpriteManager
from core.game_rules.constants import scale_x, scale_y, COLOR_GOLD, COLOR_WHITE

class ClassSelectState(BaseState):
    def __init__(self, game, font, hiring=False):
        super().__init__(game, font)
        self.background = BackgroundManager.get_rest_bg()

        self.class_names = [c.title() for c in classes.keys()]
        # Anchored to left (x=135) and moved up (y=150)
        self.menu = Menu(self.class_names, self.fonts, width=250, pos=(135, 150))
        self.menu.font = self.fonts['medium']
        self.active_menu = self.menu
        self.sprite_cache = {}
        self.hiring = hiring
        self.stored_xp = 0 # Used for ReSpec
        
        # Determine start level for Hired Help
        party_lvl = sum(p.get('level', 1) for p in self.game.party)
        self.start_level = 1
        if party_lvl >= 46: self.start_level = 15
        elif party_lvl >= 31: self.start_level = 10
        elif party_lvl >= 16: self.start_level = 5
        elif party_lvl >= 6: self.start_level = 3

        self.details_panel = Panel(520, 90, 260, 420)

        # Wasm Optimization: Class Details Caching
        self._last_selected_idx = -1
        self._cached_details_surf = None

    def wrap_text(self, text, font, max_width):
        """Helper to wrap text into multiple lines."""
        words = text.split(' ')
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            if font.size(test_line)[0] <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        return lines

    def _update_details_cache(self, class_key, class_data):
        """Pre-renders the class details onto a cached surface."""
        # Panel inner width/height (approx)
        pw, ph = scale_x(260), scale_y(420)
        surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        
        y_off = 10
        # Title
        title = class_key.title()
        tw, _ = self.fonts['large'].size(title)
        draw_text_outlined(surf, title, self.fonts['large'], COLOR_GOLD, pw // 2 - tw // 2, y_off)
        y_off += 35
        
        # HP
        hp = class_data.get('hp', 10)
        draw_text_outlined(surf, f"HP: {hp}", self.font, (200, 50, 50), scale_x(15), y_off)
        y_off += 25
        
        # Resource
        caster_classes = ["wizard", "druid", "alchemist", "sorcerer", "cleric"]
        martial_classes = ["fighter", "monk", "ranger", "rogue"]
        if class_key in caster_classes:
            draw_text_outlined(surf, "MP: 1", self.font, (50, 100, 200), scale_x(15), y_off)
            y_off += 25
        elif class_key in martial_classes:
            draw_text_outlined(surf, "SP: 1", self.font, (255, 200, 0), scale_x(15), y_off)
            y_off += 25
            
        # Gear
        y_off += 5
        draw_text_outlined(surf, "Starting Gear:", self.font, COLOR_GOLD, scale_x(15), y_off)
        y_off += 25
        weapon = class_data.get('weapon', 'None').replace('_', ' ').title()
        armor = class_data.get('armor', 'None').replace('_', ' ').title()
        draw_text_outlined(surf, f"Weapon: {weapon}", self.font, COLOR_WHITE, scale_x(15), y_off)
        y_off += 20
        draw_text_outlined(surf, f"Armor: {armor}", self.font, COLOR_WHITE, scale_x(15), y_off)
        y_off += 30
        
        # Ability
        lvl1_data = class_data.get('levels', {}).get('1', {})
        ability_name = "None"
        if lvl1_data.get('skills'):
            ability_name = lvl1_data['skills'][0].replace('_', ' ').title()
            ability_label = "Starting Skill:"
        elif lvl1_data.get('spells'):
            ability_name = lvl1_data['spells'][0].replace('_', ' ').title()
            ability_label = "Starting Spell:"
        else:
            ability_label = "Starting Ability:"
            
        draw_text_outlined(surf, ability_label, self.font, COLOR_GOLD, scale_x(15), y_off)
        y_off += 25
        draw_text_outlined(surf, ability_name, self.font, COLOR_WHITE, scale_x(15), y_off)
        y_off += 35
        
        # Description
        draw_text_outlined(surf, "Description:", self.font, COLOR_GOLD, scale_x(15), y_off)
        y_off += 25
        
        flavor = class_data.get('flavor', '')
        desc = class_data.get('description', '')
        full_text = f"{flavor} {desc}"
        
        max_desc_width = pw - scale_x(25)
        desc_lines = self.wrap_text(full_text, self.font, max_desc_width)
        
        for line in desc_lines:
            draw_text_outlined(surf, line, self.font, COLOR_WHITE, scale_x(15), y_off)
            y_off += scale_y(24)
            
        self._cached_details_surf = surf

    def get_class_sprite(self, class_key):
        """Loads and returns the sprite for a given class."""
        return SpriteManager.get_player_sprite(class_key, size=(scale_x(256), scale_y(256)))

    def on_select(self, option):
        new_player = self.create_player(option)
        
        # If ReSpec, restore XP
        if self.stored_xp > 0:
            new_player['xp'] = self.stored_xp
            # Update level based on XP
            from core.players.leveler import get_total_level_for_xp, recalculate_stats
            new_player['level'] = get_total_level_for_xp(self.stored_xp)
            # Add class levels in the selected class? 
            # Or just set level and let them use the Hub "Level Up" button?
            # Actually, to make it clean, we'll set class_levels to {class: level} 
            # and recalculate.
            new_player['class_levels'] = {option.lower(): new_player['level']}
            recalculate_stats(new_player)

        if self.hiring:
            self.game.party.append(new_player)
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.fonts))
        else:
            self.game.player = new_player
            from .autosave_notice import AutoSaveNoticeState
            self.game.change_state(AutoSaveNoticeState(self.game, self.fonts))

    def create_player(self, class_name):
        from core.players.player import apply_weapon_to_player, apply_armor_to_player
        from core.players.leveler import load_player_classes, get_class_stats_at_level
        from core.players.player_inventory import create_inventory

        player_classes_data = load_player_classes()
        class_key = class_name.lower()
        
        # Start at self.start_level for hiring
        s_lvl = self.start_level if self.hiring and self.stored_xp == 0 else 1
        player_profile = get_class_stats_at_level(class_key, s_lvl, player_classes_data)

        player_profile['class'] = class_key
        
        if self.hiring:
            player_profile['name'] = getattr(self.game, 'party_member_name', 'Mercenary')
        else:
            player_profile['name'] = getattr(self.game, 'player_name', 'Adventurer')
            
        # Initial XP for start level
        from core.players.leveler import load_xp_table
        xp_table = load_xp_table()
        player_profile['xp'] = xp_table.get(str(s_lvl), 0)
        player_profile['level'] = s_lvl
        player_profile['kill_count'] = 0
        player_profile['total_gold_spent'] = 0
        player_profile['max_hp'] = player_profile.get('hp', 10)
        player_profile['hp'] = player_profile['max_hp']
        player_profile['current_hp'] = player_profile['max_hp']
        player_profile['base_hp'] = player_profile['max_hp']

        player_profile['class_levels'] = {class_key: s_lvl}

        from core.players.leveler import recalculate_stats
        recalculate_stats(player_profile)
        apply_weapon_to_player(player_profile)
        apply_armor_to_player(player_profile)

        player_profile['inventory_ref'] = self.game.inventory
        player_profile['rest_count'] = 0

        return player_profile

    def draw(self, screen):
        self.draw_background(screen)
        width, height = screen.get_size()
        
        # Menu pinned to the left side, vertically centered 
        self.active_menu.draw(screen)

        title_str = "Choose Your Class"
        tw, th = self.fonts['xlarge'].size(title_str)
        draw_text_outlined(screen, title_str, self.fonts['xlarge'], (255, 255, 255), width // 2 - tw // 2, 50)

        # Get current class
        if not self.menu.options:
            return
            
        selected_idx = self.menu.selected
        class_key = self.menu.options[selected_idx].lower()
        class_data = classes.get(class_key, {})

        # --- Draw Class Details Panel ---
        rect = self.details_panel.draw(screen)
        
        # Optimization: Re-render only on change
        if selected_idx != self._last_selected_idx:
            self._update_details_cache(class_key, class_data)
            self._last_selected_idx = selected_idx
            
        if self._cached_details_surf:
            screen.blit(self._cached_details_surf, (rect.x, rect.y))

        # Draw current class sprite
        sprite = self.get_class_sprite(class_key)
        if sprite:
            sw, sh = sprite.get_size()
            # Horizontally centered, Vertically in the lower portion
            screen.blit(sprite, (width // 2 - sw // 2, (height * 5 // 7) - (sh // 2)))

