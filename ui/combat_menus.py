import pygame
import os
from ui.menu import Menu
from ui.panel import Panel, draw_text_outlined
from core.game_rules.constants import scale_x, scale_y, COLOR_WHITE, COLOR_GOLD, COLOR_ROYAL_BLUE, FONT_PATH
from core.game_rules.path_utils import get_resource_path
from core.combat.ability_baker import AbilityBaker

class AbilityDescriptionBox:
    def __init__(self, font, rect_tuple, state=None):
        """
        rect_tuple = (raw_x, raw_y, raw_w, raw_h) in base 800x600 space.
        """
        self.font = font
        self.state = state
        # Initialize panel with raw coordinates (Panel handles scaling)
        rx, ry, rw, rh = rect_tuple
        self.panel = Panel(rx, ry, rw, rh, bg_color=(20, 20, 40), alpha=235, border_color=COLOR_GOLD)

        # Wasm Optimization: Tracker Caching
        self._last_ability_name = None
        self._cached_desc_surface = None

    def draw(self, screen, baked_ability):
        if not baked_ability: return

        # Draw panel and get its SCREEN-SPACE rect
        rect = self.panel.draw(screen)

        name = baked_ability.get('name', 'Ability').title()
        
        # Wasm Optimization: Re-render only on change
        if name != self._last_ability_name:
            self._render_to_cache(baked_ability, rect)
            self._last_ability_name = name

        if self._cached_desc_surface:
            screen.blit(self._cached_desc_surface, (rect.x, rect.y))

    def _render_to_cache(self, baked_ability, rect):
        """Pre-renders the entire description box content to a surface."""
        # Create a surface matching the panel's screen-space size
        surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        
        name = baked_ability.get('name', 'Ability').title()
        cost = baked_ability.get('cost', 0)
        
        # Smart Resource Type: Use 'resource' key if present, otherwise infer from menu state
        res_type_raw = baked_ability.get('resource')
        if res_type_raw:
            res_type = res_type_raw.upper()
        else:
            # Fallback to current menu context if state is available
            if hasattr(self.state, 'menu_state'):
                if self.state.menu_state == "SPELLS":
                    res_type = "MP"
                elif self.state.menu_state == "SKILLS":
                    res_type = "SP"
                else:
                    res_type = "SP"
            else:
                res_type = "SP"

        a_type = baked_ability.get('type', 'Attack').title()
        desc = baked_ability.get('description', 'No description available.')

        # Dynamically replace bracketed placeholders with actual values
        for key, value in baked_ability.items():
            placeholder = f"{{{key}}}"
            if placeholder in desc:
                desc = desc.replace(placeholder, str(value))

        # Append cost to description
        if cost > 0:
            desc += f" (Cost: {cost} {res_type})"

        # Name
        draw_text_outlined(surf, name, self.font, COLOR_GOLD, scale_x(15), scale_y(12))

        # Cost and Type
        info_text = f"{cost} {res_type} | {a_type}"
        medium_font = self.state.fonts['medium'] if hasattr(self.state, 'fonts') else self.font
        
        # Affordability check for coloring
        res_key = f"current_{res_type.lower()}"
        current_val = self.state.current_actor.get(res_key, 0) if hasattr(self, 'state') else 999
        cost_color = (200, 200, 200)
        if current_val < cost:
            cost_color = (255, 100, 100) # Soft Red

        draw_text_outlined(surf, info_text, medium_font, cost_color, scale_x(15), scale_y(42))

        # Description (Wrapped)
        desc_y = scale_y(75)
        words = desc.split(' ')
        line = ""
        for word in words:
            test_line = line + word + " "
            if medium_font.size(test_line)[0] < rect.width - scale_x(30):
                line = test_line
            else:
                draw_text_outlined(surf, line, medium_font, COLOR_WHITE, scale_x(15), desc_y)
                desc_y += scale_y(medium_font.get_height() + 1)
                line = word + " "
        draw_text_outlined(surf, line, medium_font, COLOR_WHITE, scale_x(15), desc_y)
        
        self._cached_desc_surface = surf


class CombatMenuManager:
    def __init__(self, combat_state):
        self.state = combat_state
        self.font = combat_state.font
        self.main_menu = None
        self.sub_menu = None
        self.target_menu = None
        self.active_menu = None
        self.current_actor = None
        # PASS RAW COORDINATES HERE (515, 415, 280, 180) - NO scale_x/y!
        # Anchored to bottom-right: 800-280-5=515, 600-180-5=415
        self.desc_box = AbilityDescriptionBox(self.font, (515, 415, 280, 180), state=combat_state)
        
        # UI Anchors (RAW 800x600 space)
        self.BASE_X = 5 # Left anchor (will be clamped/centered appropriately)
        self.BASE_Y = 590 # Bottom anchor (will be clamped appropriately)

    def open_main_menu(self, actor=None):
        """Initializes the main action menu for the player's turn at bottom-left."""
        if actor is None:
            actor = self.state.current_actor
        self.current_actor = actor
        
        # Column 1: Combat Actions
        col1 = ["Attack"]
        if actor.get("skills"): col1.append("Skill")
        if actor.get("spells") or actor.get("class") in ["wizard", "druid", "alchemist", "sorcerer", "cleric"]: col1.append("Spell")
        
        # Column 2: Utility Actions
        col2 = ["Item"]
        if not actor.get('is_summon'): col2.append("Run")

        opts = col1 + col2
        # Anchor to bottom-left area, extended width to 140
        self.main_menu = Menu(opts, self.font, header=f"{actor['name']}", pos=(self.BASE_X, self.BASE_Y), columns=[col1, col2], width=140)
        self.active_menu = self.main_menu
        self.sub_menu = None
        self.target_menu = None
        return self.active_menu

    def handle_input(self, events, current_menu_state):
        """Processes events and returns the player's choice as a dictionary."""
        if not self.active_menu:
            return None

        selection = None
        for event in events:
            # 1. Keyboard Selection
            res = self.active_menu.handle_event(event)
            if res:
                selection = res
                break

            # 2. Mouse Selection
            if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION]:
                mouse_pos = pygame.mouse.get_pos()
                mouse_click = (event.type == pygame.MOUSEBUTTONDOWN)
                idx = self.active_menu.handle_mouse(mouse_pos, mouse_click)
                if idx is not None and mouse_click:
                    selection = self.active_menu.options[idx]
                    break

        if not selection:
            return None

        # Return Choice/Action dictionary
        if selection == "Back" or selection == "BACK":
            if self.target_menu:
                self.target_menu = None
                self.active_menu = self.sub_menu if self.sub_menu else self.main_menu
            elif self.sub_menu:
                self.sub_menu = None
                self.active_menu = self.main_menu
            
            state_map = {"MAIN": "MAIN", "SKILLS": "MAIN", "SPELLS": "MAIN", "ITEMS": "MAIN", "TARGETING": "MAIN"}
            return {"change_state": state_map.get(current_menu_state, "MAIN")}

        if current_menu_state == "MAIN":
            if selection == "Attack": return {"action": "ATTACK"}
            elif selection == "Skill": return {"change_state": "SKILLS"}
            elif selection == "Spell": return {"change_state": "SPELLS"}
            elif selection == "Item": return {"change_state": "ITEMS"}
            elif selection == "Run": return {"action": "RUN"}

        elif current_menu_state in ["SPELLS", "SKILLS"]:
            if selection == "Back": 
                self.sub_menu = None
                self.active_menu = self.main_menu
                return {"change_state": "MAIN"}
            else: 
                act = "CAST_SPELL" if current_menu_state == "SPELLS" else "USE_SKILL"
                return {"action": act, "ability_id": selection}

        elif current_menu_state == "ITEMS":
            if selection == "Back":
                self.sub_menu = None
                self.active_menu = self.main_menu
                return {"change_state": "MAIN"}
            return {"action": "USE_ITEM", "item_name": selection}

        elif current_menu_state == "TARGETING":
            # This state is now handled by the grid targeting system in CombatState
            return None

        return None

    def draw(self, screen, current_menu_state):
        """Renders the menu cascade (Main -> Sub -> Target)."""
        # 1. Always draw main menu if it exists
        if self.main_menu:
            self.main_menu.draw(screen)

        # 2. Draw Sub-menu if active
        if self.sub_menu:
            self.sub_menu.draw(screen)
            
            # Draw descriptions for sub-menu items
            if current_menu_state in ["SPELLS", "SKILLS"] and self.sub_menu.selected < len(self.sub_menu.options):
                opt_name = self.sub_menu.options[self.sub_menu.selected]
                if opt_name != "Back":
                    key = opt_name.lower().replace(' ', '_')
                    actor_id = id(self.current_actor)
                    raw_ability = self.state.ability_registry.get(actor_id, {}).get(key)      
                    if raw_ability:
                        baked = AbilityBaker.bake_ability(raw_ability, self.current_actor)    
                        self.desc_box.draw(screen, baked)

        # 3. Draw Target menu if active
        if self.target_menu:
            self.target_menu.draw(screen)

    # --- UI Creation Helpers ---
    def _calculate_cascade_pos(self, parent_menu, next_options=None, header=None):
        """
        Helper to find the next X position in the cascade.
        Ensures next_menu starting_x = parent_right + padding.
        """
        if not parent_menu: 
            return (self.BASE_X, self.BASE_Y)
            
        # Get parent's right edge in raw space (includes clamping)
        parent_rect = parent_menu.get_raw_rect()
        parent_right = parent_rect.right
        
        # Accurately calculate width of next menu
        next_w = 120 
        if next_options:
            next_w = Menu.calculate_raw_width(self.font, next_options, header=header)

        # Padding between menus as requested
        PADDING = 20
        
        # Since Menu.draw uses raw_pos[0] as center_x:
        # center_x = parent_right + padding + (next_width / 2)
        next_center_x = parent_right + PADDING + (next_w // 2)
        
        return (next_center_x, self.BASE_Y)

    def open_ability_menu(self, category, abilities, disabled_indices=None):
        if disabled_indices is None:
            disabled_indices = []
            
        actor = self.current_actor
        actor_id = id(actor)
        
        # Automatically calculate disabled indices based on cost
        for i, ab_id in enumerate(abilities):
            key = ab_id.lower().replace(' ', '_')
            ab_data = self.state.ability_registry.get(actor_id, {}).get(key, {})
            if ab_data:
                # 1. Check for Active Summons (already logic for this)
                if ab_data.get('type') == 'summon' and actor.get('summon_active', False):
                    if i not in disabled_indices: disabled_indices.append(i)
                    continue

                # 2. Check Resource Cost
                baked = AbilityBaker.bake_ability(ab_data, actor)
                cost = baked.get('cost', 0)
                res_type = baked.get('resource', 'mp').lower()
                res_key = f"current_{res_type}"
                current_val = actor.get(res_key, 0)
                
                if current_val < cost:
                    if i not in disabled_indices: disabled_indices.append(i)

        header = "Cast Spell" if category == "SPELL" else "Use Skill"
        opts = [s.replace('_', ' ').title() for s in abilities] + ["Back"]
        pos = self._calculate_cascade_pos(self.main_menu, opts, header=header)
        self.sub_menu = Menu(opts, self.font, disabled_indices=disabled_indices, header=header, pos=pos)
        self.active_menu = self.sub_menu
        return self.active_menu

    def open_item_menu(self, items):
        header = "Use Item"
        opts = items + ["Back"]
        pos = self._calculate_cascade_pos(self.main_menu, opts, header=header)
        self.sub_menu = Menu(opts, self.font, header=header, pos=pos)
        self.active_menu = self.sub_menu
        return self.active_menu

    def open_target_menu(self, options, header="Target?"):
        parent = self.sub_menu if self.sub_menu else self.main_menu
        opts = options + ["Back"]
        pos = self._calculate_cascade_pos(parent, opts, header=header)
        self.target_menu = Menu(opts, self.font, header=header, pos=pos)
        self.active_menu = self.target_menu
        return self.active_menu

    def open_column_menu(self):
        parent = self.sub_menu if self.sub_menu else self.main_menu
        header = "Target Column?"
        opts = ["Column 1", "Column 2", "Column 3", "Back"]
        pos = self._calculate_cascade_pos(parent, opts, header=header)
        self.target_menu = Menu(opts, self.font, header=header, pos=pos, initial_selection=1)
        self.active_menu = self.target_menu
        return self.active_menu
