import pygame
import random
from states.base_state import BaseState
from ui.combat_menus import CombatMenuManager
from ui.combat_dialogue import CombatDialogueManager
from ui.dialogue_box import DialogueBox
from core.combat.combat_engine import CombatEngine
from graphics.vfx_manager import VFXManager
from core.combat.targeting import TargetingHelper
from core.players.player import load_consumables, load_spells, load_skills, load_summons
from core.combat.summoning_helper import SummoningHelper
from core.creatures.enemies import load_enemy_data

# Visual Managers
from graphics.backgrounds import BackgroundManager
from graphics.sprite_manager import SpriteManager
from graphics.floating_text import FloatingTextManager
from graphics.dice_animation import DiceAnimation
from graphics.projectile_manager import ProjectileManager
from graphics.combat_grid import CombatGridManager
from graphics.screen_shake import ScreenShake
from ui.combat_renderer import CombatRenderer
from core.combat.action_executor import ActionExecutor
from core.combat.action_builder import ActionBuilder
from core.combat.combat_ai import CombatAI
from core.combat.initiative_roller import InitiativeRoller

from core.game_rules.constants import scale_x, scale_y, COLOR_WHITE, COLOR_GOLD, SCREEN_WIDTH, SCREEN_HEIGHT

from core.combat.menu_controller import CombatMenuController, MenuState
from core.combat.targeting import TargetingHelper
from core.combat.combat_resolver import CombatResolver
from core.combat.combatant_factory import CombatantFactory
from core.combat.over_time import OverTimeProcessor

class CombatStateNew(BaseState):
    def __init__(self, game, font, player_data, enemy_data):
        super().__init__(game, font)

        # --- 1. DATA SETUP ---
        self.player = player_data
        self.party = game.party
        self.enemies = enemy_data
        self.summons = {}

        # Limit settings during combat
        self.settings_excluded_options = ["Save Game"]

        # Prepare combatant dictionaries (HP, MP, faction, etc.)
        CombatantFactory.prepare_for_combat(self.party, self.enemies)
        
        # Target Tracking
        self.active_target_list = []
        self.valid_target_tiles = []
        
        # Grid initialized by CombatGridManager
        self.combat_grid = []
        
        self.ability_registry = {}
        self._build_ability_registry()

        # --- 2. MANAGER INSTANTIATION ---
        self.font = font
        self.engine = CombatEngine()
        
        # Grid and Spatial Management
        self.grid_mgr = CombatGridManager(self)
        self.renderer = CombatRenderer(self)
        self.action_executor = ActionExecutor(self)
        
        # New Input Controller
        self.menu_controller = CombatMenuController(grid_bounds=(self.grid_width, self.grid_height))
        
        # Mini-font for resource bars
        self.mini_font = pygame.font.Font(None, scale_y(16))

        self.bg_mgr = BackgroundManager()
        self.sprite_mgr = SpriteManager()
        self.menu_mgr = CombatMenuManager(self)
        self.dialogue_box = DialogueBox(self.font)
        self.dialogue_mgr = CombatDialogueManager(self.dialogue_box)

        self.float_mgr = FloatingTextManager(self.font)
        self.dice_anim = DiceAnimation()
        self.projectile_mgr = ProjectileManager()
        self.vfx_mgr = VFXManager()
        self.shake_mgr = ScreenShake()

        # Initialization logic
        self.combat_is_resolved = False
        self.grid_mgr._initialize_positions()
        self._initialize_enemy_names()
        self._reset_combat_state()

        self.turn_queue = self._roll_initiative()
        self.current_actor = self.turn_queue[0] if self.turn_queue else None
        self.phase = 'START_TURN'
        self.phase_start_time = pygame.time.get_ticks()
        self.last_phase = 'START_TURN'

        self.dialogue_mgr.queue_message(f"Encountered: {', '.join([e['name'] for e in self.enemies])}!")

    def _check_combat_end(self):
        """Checks if all actors on either side are defeated."""
        if self.combat_is_resolved:
            return True

        living_party = [p for p in self.party if p.get('current_hp', 0) > 0]
        living_enemies = [e for e in self.enemies if e.get('current_hp', 0) > 0]
        
        if not living_party:
            self._handle_defeat()
            return True
        if not living_enemies:
            self._handle_victory()
            return True
        return False

    def _handle_victory(self):
        """Handles transition to hub after winning."""
        self.combat_is_resolved = True
        
        # Trigger Victory Jingle
        if self.game.music_manager:
            self.game.music_manager.play_state_music('victory')

        # Delegate reward distribution and dialogue to Resolver
        CombatResolver.apply_victory_rewards(self.game, self.party, self.enemies, self.dialogue_mgr)
        
        # State Transition (Delay via Phase)
        self.phase = 'VICTORY_DIALOGUE'

    def _handle_defeat(self):
        """Handles transition to main menu after losing."""
        self.combat_is_resolved = True
        print("[COMBAT] DEFEAT! The party has fallen.")

        # Cleanup Summons
        summons = [p for p in self.party if p.get('is_summon')]
        for s in summons:
            self.party.remove(s)
            owner_id = s.get('owner_id')
            if owner_id:
                for p in self.party:
                    if p.get('id') == owner_id:
                        p['summon_active'] = False
        
        # 8. Cleanse Party
        CombatResolver.cleanse_party(self.party)
        
        # Transition back to Title
        self.next_state = 'TITLE'
        self.done = True
        
        from .title import TitleState
        self.game.change_state(TitleState(self.game, self.font))

    def _build_ability_registry(self):
        """Caches ability data for quick lookups using DatabaseManager."""
        from core.game_rules.database_manager import db
        spells_db = db.get_spells()
        skills_db = db.get_skills()
        items_db = db.get_consumables()
        enemy_db = db.get_enemy_abilities()
        
        for actor in self.party + self.enemies:
            # 1. Standard Player/Class Abilities
            self._register_actor_abilities(actor, spells_db, skills_db, items_db)
            
            # 2. Enemy Unique Abilities
            if actor.get('is_enemy'):
                actor_id = id(actor)
                for ab_id in actor.get('abilities', []):
                    key = ab_id.lower().replace(' ', '_')
                    if key in enemy_db:
                        self.ability_registry[actor_id][key] = enemy_db[key]

    def _register_actor_abilities(self, actor, spells_db, skills_db, items_db):
        a_id = id(actor)
        self.ability_registry[a_id] = {}
        for sp in actor.get('spells', []):
            if sp in spells_db: self.ability_registry[a_id][sp] = spells_db[sp]
        for sk in actor.get('skills', []):
            if sk in skills_db: self.ability_registry[a_id][sk] = skills_db[sk]
        for item in actor.get('inventory', []):
            i_name = item.get('name') if isinstance(item, dict) else item
            if i_name in items_db: self.ability_registry[a_id][i_name] = items_db[i_name]

    def _get_current_target_list(self):
        """Bridge helper to fetch targets based on controller hover or confirmed target."""
        # Priority: confirmed target_grid > menu hover grid
        grid_pos = getattr(self, 'active_target_grid', None)
        if grid_pos is None:
            grid_pos = (self.menu_controller.cursor_grid_x, self.menu_controller.cursor_grid_y)
        
        tx, ty = grid_pos
        
        action_data = getattr(self, 'pending_action_data', None)
        if action_data is None:
            action_data = {}
            
        actor_faction = self.current_actor.get('faction', 'party')

        return TargetingHelper.get_affected_targets(
            action_data,
            tx, ty,
            self.combat_grid,
            self.grid_width,
            self.grid_height,
            actor_faction
        )

    def apply_flash_effect(self, sprite, frames, flash_type):
        """Applies a visual flash effect to a sprite (grayscale or color)."""
        new_s = sprite.copy()
        if flash_type == 'damage' and (frames // 6) % 2 == 1:
            try: return pygame.transform.grayscale(new_s)
            except: new_s.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)    
        return new_s

    def _reset_combat_state(self):
        self.active_target_grid = None
        self.active_target_list = []
        self.pending_action_data = None
        self.current_results = []
        self.menu_state = "MAIN"
        # Restore visual offsets and trackers
        self.attacker_offset = 0
        self.attacker_offset_y = 0
        self.target_offset_x = 0
        self.active_attacker = None
        self.active_target = None

    def update(self, events, dt):
        """Main Loop State Machine"""
        # Global Settings/Menu check from BaseState
        super().update(events, dt)

        # --- Phase Fail-safe Timer ---
        if self.phase != getattr(self, "last_phase", None):
            self.phase_start_time = pygame.time.get_ticks()
            self.last_phase = self.phase

        if self.phase in ["ANIMATING", "RESOLVING"]:
            if pygame.time.get_ticks() - self.phase_start_time > 5000:
                print(f"[FAIL-SAFE] Phase {self.phase} timed out! Force clearing...")
                self.vfx_mgr.active_effects = []
                self.dialogue_mgr.clear_queue()
                self.float_mgr.texts = []
                self.dice_anim.is_active = False
                self.projectile_mgr.projectiles = []
                self.phase = "END_TURN"

        # 1. Component Updates
        self.sprite_mgr.update(dt) 
        self.vfx_mgr.update(dt)
        self.dialogue_mgr.update(dt)
        self.float_mgr.update()
        self.dice_anim.update(dt)
        self.projectile_mgr.update()
        self.shake_mgr.update()

        # 2. Cleanup Visuals
        for a in self.party + self.enemies:
            if a.get('flash_frames', 0) > 0: a['flash_frames'] -= 1

        # 3. Terminal Transitions (High Priority)
        if self.phase in ['VICTORY_DIALOGUE', 'ESCAPE_DIALOGUE']:
            if not self.dialogue_mgr.is_busy():
                self.phase = 'TRANSITIONING' # Lockout to prevent multiple calls
                from .hub import HubState
                self.game.change_state(HubState(self.game, self.font))
                return

        # 4. Input & Execution Pauses (Return Trap)
        is_blocked = self.vfx_mgr.is_playing() or self.dialogue_mgr.is_busy() or self.dice_anim.is_active or not self.projectile_mgr.is_finished()
        
        if is_blocked:
            for event in events:
                # Let handle_events attempt to consume global/phase inputs
                if self.handle_events(event):
                    continue
                # If dialogue is active, ensure the box gets the events for sub-message progression
                if self.dialogue_box.current_message:
                    self.dialogue_box.handle_event(event)
            
            # SPECIAL CASE: If we are in MENU phase but BLOCKED by dialogue, 
            # we must return to prevent menu input from bleeding through, 
            # but we also need to ensure the dialogue is being drawn.
            return

        # 6. Phase Logic
        if self.phase == 'START_TURN': self._handle_start_turn()
        elif self.phase == 'MENU': self._handle_player_input(events)
        elif self.phase == 'TARGETING': self._handle_targeting_input(events)
        elif self.phase == "ENEMY_TURN": self._handle_enemy_ai()
        elif self.phase == "DICE_ROLLING": self._handle_dice_rolling()
        elif self.phase == "EXECUTION": self._execute_action()
        elif self.phase == "ANIMATING":
            if not self.vfx_mgr.is_busy() and not self.float_mgr.is_busy() and not self.sprite_mgr.is_busy():
                self.phase = 'DIALOGUE'
        elif self.phase == "DIALOGUE":
            if not self.dialogue_mgr.is_busy():
                self._handle_end_turn()
        elif self.phase == "WAITING_RESOLUTION":
            if not self.dialogue_mgr.is_busy() and not self.vfx_mgr.is_playing() and self.projectile_mgr.is_finished():
                self.phase = 'RESOLVING'
        elif self.phase == 'RESOLVING': self._handle_resolving()
        elif self.phase == 'END_TURN': self._handle_end_turn()

    def _handle_dice_rolling(self):
        """Monitors the dice animation and transitions to EXECUTION when complete."""
        if not self.dice_anim.is_active:
            self.phase = "EXECUTION"

    def handle_events(self, event):
        """Individual event processor for global and phase-specific inputs."""
        # --- DIALOGUE ADVANCEMENT (Fix for end-of-combat soft-lock) ---
        
        # FIX: Allow input whenever the dialogue manager is busy OR during specific dialogue phases.
        # This prevents deadlocks when a message pops up during the ANIMATING or EXECUTION phase.
        if self.dialogue_mgr.is_busy() or self.phase in ['DIALOGUE', 'VICTORY_DIALOGUE']:
            dbox = self.dialogue_mgr.dialogue_box
            
            is_confirm = False
            if event.type == pygame.KEYDOWN:
                if event.key in [pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER]:
                    is_confirm = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                is_confirm = True
                
            if is_confirm:
                # Smart typing skip
                if getattr(dbox, 'is_typing', False):
                    dbox.is_typing = False
                    dbox.index = len(dbox.current_message)
                    dbox.visible_text = dbox.current_message
                else:
                    self.dialogue_mgr.start_next()
                return True # Consume event
        return False

    def _handle_targeting_input(self, events):
        """Processes events for grid-based targeting."""
        # 1. Mouse Snapping (Only snap if mouse actually moved)
        mouse_pos = pygame.mouse.get_pos()
        last_mouse_pos = getattr(self, '_last_mouse_pos', (0,0))
        mouse_moved = mouse_pos != last_mouse_pos
        self._last_mouse_pos = mouse_pos

        if mouse_moved:
            gx, gy = self._get_grid_from_mouse(mouse_pos)
            if gx is not None and gy is not None:
                if (gx, gy) in self.valid_target_tiles:
                    self.menu_controller.set_hover_grid(gx, gy)

        # 2. Filter events for clicks in "dirt" (empty tiles)
        filtered_events = []
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mgx, mgy = self._get_grid_from_mouse(pygame.mouse.get_pos())
                if mgx is not None and mgy is not None and (mgx, mgy) not in self.valid_target_tiles:
                    msg = "Not a valid target."
                    print(f"[COMBAT] {msg} ({mgx}, {mgy})")
                    self.dialogue_mgr.queue_message(msg)
                    continue # Ignore this click
            filtered_events.append(event)

        # 3. Controller Input (Keys + Valid Clicks)
        # Use jump_to_next_valid for directional keys to skip empty tiles
        for event in filtered_events:
            if event.type == pygame.KEYDOWN and self.menu_controller.state == MenuState.SELECTING_TARGET:
                if event.key in [pygame.K_UP, pygame.K_w]:
                    self.grid_mgr.jump_to_next_valid(self.menu_controller, 'up')
                    continue
                elif event.key in [pygame.K_DOWN, pygame.K_s]:

                    self.grid_mgr.jump_to_next_valid(self.menu_controller, 'down')
                    continue
                elif event.key in [pygame.K_LEFT, pygame.K_a]:
                    self.grid_mgr.jump_to_next_valid(self.menu_controller, 'left')
                    continue
                elif event.key in [pygame.K_RIGHT, pygame.K_d]:
                    self.grid_mgr.jump_to_next_valid(self.menu_controller, 'right')
                    continue

        result = self.menu_controller.process_input(filtered_events)


        if result:
            if "target_grid" in result:
                # 1. Selection Constraint (Double check for safety)
                tx = self.menu_controller.cursor_grid_x
                ty = self.menu_controller.cursor_grid_y
                
                if (tx, ty) not in self.valid_target_tiles:
                    msg = "Not a valid target."
                    print(f"[COMBAT] {msg} ({tx}, {ty})")
                    self.dialogue_mgr.queue_message(msg)
                    # Revert the menu_controller state to TARGETING if finalize_turn reset it
                    self.menu_controller.state = MenuState.SELECTING_TARGET
                    self.menu_controller.selected_action = self.pending_action_data.get('name') if self.pending_action_data else "Attack"
                    return

                # 2. Entity Extraction
                # Use TargetingHelper to generate the list of affected entities
                target_list = TargetingHelper.get_affected_targets(
                    self.pending_action_data, tx, ty, self.combat_grid, 
                    self.grid_width, self.grid_height, self.current_actor.get('faction')
                )
                
                # 3. Empty Tile Failsafe
                if not target_list:
                    print(f"[COMBAT] Tile at ({tx}, {ty}) is empty or invalid for {self.pending_action_data.get('name')}!")
                    # Stay in TARGETING phase, do not advance turn
                    # Revert state
                    self.menu_controller.state = MenuState.SELECTING_TARGET
                    self.menu_controller.selected_action = self.pending_action_data.get('name') if self.pending_action_data else "Attack"
                    return
                
                # 4. Engine Hand-off
                # Calculate crit range based on RP before resolving
                # Note: We take the first target for category lookup for simplicity in AoE
                primary_target = target_list[0] if target_list else None
                c_range = self._calculate_crit_range(self.current_actor, primary_target) if primary_target else [20]
                
                results = self.engine.resolve_action(self.current_actor, self.pending_action_data, target_list, crit_range=c_range)
                
                # Screen Shake: Highest of Crit or Damage Magnitude
                max_mag = 0
                total_dmg = sum(res.get('damage', 0) for res in results)
                damage_mag = self.shake_mgr.get_magnitude_for_damage(total_dmg)
                
                if any(res.get('crit') for res in results):
                    self.shake_mgr.trigger(intensity=12, duration=25)
                elif damage_mag > 0:
                    self.shake_mgr.trigger_magnitude(damage_mag)
                
                # 5. Dice Animation Logic
                has_dice = False
                rolls = []
                
                # A. Attacker's attack roll
                if self.pending_action_data.get('type') == 'attack':
                    for res in results:
                        if 'roll' in res:
                            style = self.dice_anim.get_style_from_actor(self.current_actor, self.party)
                            start_pos = list(self.current_actor.get('screen_pos', (100, 300)))
                            rolls.append((res['roll'], start_pos))
                            has_dice = True
                            # Use the same style for all attack rolls in this multi-hit if any
                            self.dice_anim.start_multi_roll(rolls, style=style)
                            break 

                # B. Targets' saving throws
                if self.pending_action_data.get('type') == 'save':
                    save_rolls_by_style = {} # style -> list of (val, pos)
                    for res in results:
                        if 'save_roll' in res:
                            target_actor = res['target']
                            style = self.dice_anim.get_style_from_actor(target_actor, self.party)
                            t_pos = list(target_actor.get('screen_pos', (600, 300)))
                            if style not in save_rolls_by_style: save_rolls_by_style[style] = []
                            save_rolls_by_style[style].append((res['save_roll'], t_pos))
                            has_dice = True
                    
                    if save_rolls_by_style:
                        # For now, start_multi_roll only supports one style per call.
                        # We'll use the style of the first defender.
                        primary_style = list(save_rolls_by_style.keys())[0]
                        all_save_rolls = []
                        for s_rolls in save_rolls_by_style.values(): all_save_rolls.extend(s_rolls)
                        self.dice_anim.start_multi_roll(all_save_rolls, style=primary_style)

                if has_dice:
                    self.active_target_list = target_list
                    self.current_results = results
                    self.phase = "DICE_ROLLING"
                else:
                    # 6. Advance to Execution Phase
                    self.active_target_list = target_list
                    self.current_results = results
                    self.phase = "EXECUTION"
                return
        
        # 3. Handle Cancel (Manual Escape)
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.phase = "MENU"
                self._change_menu_state("MAIN")

    def _execute_action(self):
        """Delegates result application and visual sequencing to ActionExecutor."""
        self.action_executor.execute()

    def _execute_summon(self):
        """Delegates auto-placement and visual setup to ActionExecutor."""
        self.action_executor.execute_summon()

    def _get_grid_from_mouse(self, mouse_pos):
        return self.grid_mgr._get_grid_from_mouse(mouse_pos)

    def _handle_player_input(self, events):
        """Processes events via the CombatMenuManager when in the MENU phase."""
        action_result = self.menu_mgr.handle_input(events, self.menu_state)

        if action_result:
            if "change_state" in action_result:
                self._change_menu_state(action_result["change_state"])
                return

            if "action" in action_result:
                self._process_menu_action(action_result)
                return

    def _process_menu_action(self, action_dict):
        """Maps menu results to pending_action_data and transitions to targeting."""
        action_type = action_dict.get("action", "").upper()
        actor_id = id(self.current_actor)

        if action_type == "ATTACK":
            self.pending_action_data = ActionBuilder.build_basic_attack(self.current_actor)

            self.phase = "TARGETING"
            self.grid_mgr.generate_valid_target_map(self.pending_action_data, self.current_actor.get('faction'))
            self.menu_controller.state = MenuState.SELECTING_TARGET
            self.menu_controller.cursor_grid_x = 4 # Default to enemy frontline
            self.menu_controller.cursor_grid_y = 0
            self.grid_mgr.snap_to_nearest_valid(self.menu_controller)

        elif action_type in ["CAST_SPELL", "USE_SKILL", "USE_ITEM"]:
            ability_id = action_dict.get("ability_id", action_dict.get("item_name", ""))
            key = ability_id.lower().replace(' ', '_')
            
            ability_data = self.ability_registry.get(actor_id, {}).get(key, {})
            self.pending_action_data = ability_data or {"name": ability_id, "type": "attack"}

            # --- SUMMON INTERCEPT ---
            if self.pending_action_data.get('type') == 'summon':
                if self.current_actor.get('summon_active', False):
                    self.dialogue_mgr.queue_message(f"{self.current_actor['name']} already has an active summon group!")
                    self.phase = "MENU"
                    return
                self._execute_summon()
                return

            self.phase = "TARGETING"
            self.grid_mgr.generate_valid_target_map(self.pending_action_data, self.current_actor.get('faction'))
            self.menu_controller.state = MenuState.SELECTING_TARGET
            self.menu_controller.cursor_grid_x = 4
            self.menu_controller.cursor_grid_y = 0
            self.grid_mgr.snap_to_nearest_valid(self.menu_controller)

        elif action_type == "CANCEL":
            self.pending_action_data = None
            self._change_menu_state("MAIN")

        elif action_type == "RUN":
            self._handle_run_attempt()

    def _handle_run_attempt(self):
        """Calculates and resolves an escape attempt based on party/enemy strength."""
        living_party = [p for p in self.party if p.get('current_hp', 0) > 0 and not p.get('is_summon')]
        living_enemies = [e for e in self.enemies if e.get('current_hp', 0) > 0]
        
        if not living_party or not living_enemies:
            self.phase = "END_TURN"
            return

        # 1. Calculate Totals
        tpl = sum(p.get('level', 1) for p in living_party)
        tel = sum(e.get('level', 1) for e in living_enemies)
        
        # 2. Base Chance
        run_chance = 40.0
        run_lvl = tpl - tel
        
        # 3. Apply Scaling if party is stronger/equal or as per formula
        if run_lvl > 0:
            # run_scale = enemy_count / living_party_members
            run_scale = len(living_enemies) / len(living_party)
            run_chance += (run_lvl * run_scale)
        
        # Clamp chance
        run_chance = min(95.0, run_chance)
        
        print(f"[COMBAT] Run Attempt: TPL {tpl}, TEL {tel}, Scale {len(living_enemies)}/{len(living_party)}. Chance: {run_chance:.1f}%")

        # 4. Resolve
        roll = random.random() * 100
        if roll < run_chance:
            self.dialogue_mgr.queue_message("Successful escape! The party fled the battle.")
            self.phase = 'VICTORY_DIALOGUE' # Reuse victory transition to return to hub
            # Set a flag or ensure rewards are skipped? 
            # Actually VICTORY_DIALOGUE calls CombatResolver.apply_victory_rewards in _handle_victory.
            # I should probably use a dedicated ESCAPE_DIALOGUE or flag it.
            self.combat_is_resolved = True
            # Transition to Hub directly after dialogue
            self.phase = 'ESCAPE_DIALOGUE'
        else:
            self.dialogue_mgr.queue_message("Escape failed! The enemies block your path.")
            self.phase = 'DIALOGUE' # Ends turn after message

    def _change_menu_state(self, new_state):
        """Handles transitions between different menu levels."""
        self.menu_state = new_state
        actor = self.current_actor
        
        if new_state == "MAIN":
            self.menu_mgr.open_main_menu(actor)
        elif new_state in ["SPELLS", "SKILLS"]:
            category = "SPELL" if new_state == "SPELLS" else "SKILL"
            abilities = actor.get('spells', []) if new_state == "SPELLS" else actor.get('skills', [])
            
            disabled_indices = []
            if actor.get('summon_active', False):
                for i, ab_id in enumerate(abilities):
                    key = ab_id.lower().replace(' ', '_')
                    ab_data = self.ability_registry.get(id(actor), {}).get(key, {})
                    if ab_data.get('type') == 'summon':
                        disabled_indices.append(i)
            
            self.menu_mgr.open_ability_menu(category, abilities, disabled_indices)
        elif new_state == "ITEMS":
            inv_names = [i.get('name') if isinstance(i, dict) else i for i in actor.get('inventory', [])]
            self.menu_mgr.open_item_menu(inv_names)

    def _handle_resolving(self):
        self.phase = 'END_TURN'

    def _handle_start_turn(self):
        if not self.turn_queue: return
        self.current_actor = self.turn_queue[0]
        self.atk_made = 0 # Reset attack counter for multi-attack logic

        # --- 1. PRE-TURN CHECKS ---
        is_ai = self.current_actor.get('is_enemy', False) or self.current_actor.get('is_summon', False)
        is_stunned = 'stunned' in self.current_actor.get('conditions', {})

        # --- 2. Process Over-Time Effects (DoT/HoT) ---
        ot_results = OverTimeProcessor.process_effects(self.current_actor)
        for res in ot_results:
            self.dialogue_mgr.queue_message(res['msg'])

            # Visual Feedback
            v_rect = self.current_actor.get('_visual_rect')
            base_pos = self.current_actor.get('screen_pos', (400, 300))
            text_pos = (v_rect.centerx, v_rect.centery) if v_rect else (base_pos[0] + scale_x(60), base_pos[1] + scale_y(60))

            if res['type'] == 'dot':
                self.float_mgr.add(str(res['value']), text_pos, color_key="damage")
                self.current_actor['flash_frames'] = 30
            elif res['type'] == 'hot':
                self.float_mgr.add(str(res['value']), text_pos, color_key="heal")

        # Check if DoT defeated the actor
        if self.current_actor.get('current_hp', 1) <= 0:
            self.current_actor['is_alive'] = False
            self.dialogue_mgr.queue_message(f"{self.current_actor['name']} has succumbed to lingering damage!")
            self.phase = 'DIALOGUE'
            return

        # --- 3. EXECUTE STUN SKIP ---
        if is_stunned:
            self.dialogue_mgr.queue_message(f"{self.current_actor['name']} is stunned and skips their turn!")
            self.phase = 'DIALOGUE'
            return

        # --- 4. RESOURCE REGEN FOR AI & SUMMONS ---        is_ai = self.current_actor.get('is_enemy', False) or self.current_actor.get('is_summon', False)
        if is_ai:
            max_mp = self.current_actor.get('max_mp', 10)
            max_sp = self.current_actor.get('max_sp', 10)
            self.current_actor['current_mp'] = min(max_mp, self.current_actor.get('current_mp', 0) + 1)
            self.current_actor['current_sp'] = min(max_sp, self.current_actor.get('current_sp', 0) + 1)

        if self.current_actor in self.party:

            if self.current_actor.get('is_summon', False):
                # Auto-AI for Player Summons
                ai_result = CombatAI.decide_action(self.current_actor)
                
                # Deduct Cost: Handled by CombatEngine.resolve_action

                if ai_result.get('type') == 'attack':
                    self.pending_action_data = ActionBuilder.build_basic_attack(self.current_actor)
                else:
                    self.pending_action_data = ai_result.get('data', {})
                
                self.active_target_list = CombatAI.pick_target(self.current_actor, self.enemies, self.pending_action_data)
                if isinstance(self.active_target_list, dict):
                    self.active_target_list = [self.active_target_list]
                
                if self.active_target_list:
                    self.active_target_grid = (self.active_target_list[0]['grid_x'], self.active_target_list[0]['grid_y'])
                    
                    # --- DICE INTEGRATION FOR SUMMONS ---
                    c_range = self._calculate_crit_range(self.current_actor, self.active_target_list[0]) if self.active_target_list else [20]
                    results = self.engine.resolve_action(self.current_actor, self.pending_action_data, self.active_target_list, crit_range=c_range)
                    self.current_results = results
                    
                    # Screen Shake: Highest of Crit or Damage Magnitude
                    total_dmg = sum(res.get('damage', 0) for res in results)
                    damage_mag = self.shake_mgr.get_magnitude_for_damage(total_dmg)
                    
                    if any(res.get('crit') for res in results):
                        self.shake_mgr.trigger(intensity=12, duration=25)
                    elif damage_mag > 0:
                        self.shake_mgr.trigger_magnitude(damage_mag)
                    
                    has_dice = False
                    rolls = []
                    if self.pending_action_data.get('type') == 'attack':
                        for res in results:
                            if 'roll' in res:
                                style = self.dice_anim.get_style_from_actor(self.current_actor, self.party)
                                rolls.append((res['roll'], list(self.current_actor.get('screen_pos', (100, 300)))))
                                has_dice = True; self.dice_anim.start_multi_roll(rolls, style=style); break
                    elif self.pending_action_data.get('type') == 'save':
                        for res in results:
                            if 'save_roll' in res:
                                style = self.dice_anim.get_style_from_actor(res['target'], self.party)
                                rolls.append((res['save_roll'], list(res['target'].get('screen_pos', (600, 300)))))
                                has_dice = True
                        if has_dice: self.dice_anim.start_multi_roll(rolls, style=self.dice_anim.get_style_from_actor(results[0]['target'], self.party))

                    self.phase = "DICE_ROLLING" if has_dice else "EXECUTION"
                else:
                    self.phase = "END_TURN"
            else:
                self.phase = "MENU"
                self._change_menu_state("MAIN")
        else:
            self.phase = "ENEMY_TURN"

    def _handle_end_turn(self):
        """Advances the turn queue, cleaning up dead summons and resetting flags."""
        if self._check_combat_end(): return

        # --- SUMMON CLEANUP LOGIC ---
        # 1. Identify dead entities that were recently removed or marked dead
        dead_summons = [a for a in self.turn_queue if a.get('is_summon') and not a.get('is_alive', True)]
        
        # 2. For each dead summon, check its owner's status
        owners_to_check = set()
        for ds in dead_summons:
            owner_id = ds.get('owner_id')
            if owner_id:
                owners_to_check.add(owner_id)
        
        # 3. If an owner has NO living summons left, reset their flag
        for oid in owners_to_check:
            # Check turn_queue for any LIVING summon with this owner_id
            still_has_summons = any(
                a for a in self.turn_queue 
                if a.get('is_summon') and a.get('owner_id') == oid and a.get('is_alive', True)
            )
            
            if not still_has_summons:
                # Find the owner actor in party or enemies and reset flag
                for actor in self.party + self.enemies:
                    if actor.get('id') == oid:
                        actor['summon_active'] = False
                        print(f"[COMBAT] {actor['name']}'s summons are all gone. Flag reset.")
                        break

        # --- STANDARD TURN ADVANCEMENT ---
        living_found = False
        while not living_found:
            if self.turn_queue:
                actor = self.turn_queue.pop(0)
                self.turn_queue.append(actor)

            self.current_actor = self.turn_queue[0] if self.turn_queue else None

            if not self.current_actor: break
            if self.current_actor.get('is_alive', True):
                living_found = True
            else:
                # Check end again if we skip someone to prevent infinite loop
                if self._check_combat_end(): return

        self._reset_combat_state()
        self.phase = 'START_TURN'
    def draw(self, screen):
        # 0. Handle Screen Shake Offsets
        ox, oy = self.shake_mgr.get_offsets()
        
        # Create a temp surface for world-space layers that should shake
        world_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        
        # 1. Draw World-Space Layers to world_surf
        self.bg_mgr.draw(world_surf)
        
        # Sync targeted entities for SpriteManager before drawing sprites
        if self.phase == 'TARGETING':
            self.sprite_mgr.set_targeted_entities(self._get_current_target_list())
        else:
            self.sprite_mgr.set_targeted_entities([])

        self.sprite_mgr.draw_sprites(world_surf, self)
        self.projectile_mgr.draw(world_surf)
        self.vfx_mgr.draw(world_surf)
        self.float_mgr.draw(world_surf)
        self.renderer.draw_entity_bars(world_surf)
        
        if self.phase == 'TARGETING':
            self.renderer.draw_targeting_cursor(world_surf)
            
        # Debug Overlay (Shakes with world)
        if getattr(self.game, 'god_mode', False) or (self.game.debug_overlay and self.game.debug_overlay.visible):
            self.renderer.draw_debug_placement(world_surf)

        # 2. Blit world_surf to screen with offset
        screen.blit(world_surf, (ox, oy))

        # 3. Draw Static UI Layers (Do not shake)
        self.renderer.draw_turn_order(screen)
        
        if self.phase != 'MENU' or self.dialogue_mgr.is_busy():
            self.dialogue_mgr.draw(screen)

        if self.phase == 'MENU':
            self.menu_mgr.draw(screen, self.menu_state)

        self.draw_settings_button(screen)
        
        # Dice are usually top-layer and "floating", but let's keep them static for readability
        self.dice_anim.draw(screen)

    def _handle_enemy_ai(self):
        """Enemy AI Bridge: Picks a target and prepares an action."""
        enemy = self.current_actor
        
        # 1. Decide Action via AI (Pass summons for accurate decision making)
        summons_list = list(self.summons.values())
        ai_result = CombatAI.decide_action(enemy, summons=summons_list)

        # Deduct Cost: Handled by CombatEngine.resolve_action
        
        # 2. Extract Action Data
        if ai_result.get('type') == 'attack':
            self.pending_action_data = ActionBuilder.build_basic_attack(enemy)
        else:
            self.pending_action_data = ai_result.get('data', {})
            if 'name' not in self.pending_action_data:
                self.pending_action_data['name'] = ai_result.get('name', 'Ability')

        # --- SUMMON INTERCEPT ---
        if self.pending_action_data.get('type') == 'summon':
            # Safeguard against over-summoning (though AI should handle this)
            if enemy.get('summon_active', False):
                self.phase = "END_TURN"
                return
            self._execute_summon()
            return

        # 3. Target Selection
        living_party = [p for p in self.party if p.get('current_hp', 0) > 0]
        if living_party:
            target = CombatAI.pick_target(enemy, living_party, self.pending_action_data)
            if target:
                self.active_target_grid = (target['grid_x'], target['grid_y'])
                # Use TargetingHelper via bridge to expand AoE if necessary
                self.active_target_list = self._get_current_target_list()
                
                if self.active_target_list:
                    # --- DICE INTEGRATION FOR ENEMIES ---
                    # Calculate crit range (Enemies usually don't get RP bonuses, but logic is here for consistency)
                    c_range = self._calculate_crit_range(enemy, self.active_target_list[0]) if self.active_target_list else [20]
                    results = self.engine.resolve_action(enemy, self.pending_action_data, self.active_target_list, crit_range=c_range)
                    self.current_results = results
                    
                    # Screen Shake: Highest of Crit or Damage Magnitude
                    total_dmg = sum(res.get('damage', 0) for res in results)
                    damage_mag = self.shake_mgr.get_magnitude_for_damage(total_dmg)
                    
                    if any(res.get('crit') for res in results):
                        self.shake_mgr.trigger(intensity=12, duration=25)
                    elif damage_mag > 0:
                        self.shake_mgr.trigger_magnitude(damage_mag)
                    
                    has_dice = False
                    rolls = []
                    if self.pending_action_data.get('type') == 'attack':
                        for res in results:
                            if 'roll' in res:
                                style = self.dice_anim.get_style_from_actor(enemy, self.party)
                                rolls.append((res['roll'], list(enemy.get('screen_pos', (100, 300)))))
                                has_dice = True; self.dice_anim.start_multi_roll(rolls, style=style); break
                    elif self.pending_action_data.get('type') == 'save':
                        for res in results:
                            if 'save_roll' in res:
                                style = self.dice_anim.get_style_from_actor(res['target'], self.party)
                                rolls.append((res['save_roll'], list(res['target'].get('screen_pos', (600, 300)))))
                                has_dice = True
                        if has_dice: self.dice_anim.start_multi_roll(rolls, style=self.dice_anim.get_style_from_actor(results[0]['target'], self.party))

                    self.phase = "DICE_ROLLING" if has_dice else "EXECUTION"
                else:
                    self.phase = "END_TURN"
            else:
                self.phase = "END_TURN"
        else:
            self.phase = "END_TURN"

    def _calculate_crit_range(self, actor, target):
        """
        Determines the critical hit range based on Bestiary RP and the numerical crit_bonus.
        RP Thresholds: 20 RP (+1), 60 RP (+2), 100 RP (+3).
        """
        e_type = target.get('category', 'general')
        rp = self.game.bestiary_rp.get(e_type, 0)
        
        # 1. Base Crit Bonus from Actor Stats (Numerical)
        # Sum both runtime gear bonus and direct JSON tag for true stacking
        total_bonus = int(actor.get('crit_bonus', 0)) + int(actor.get('crit+', 0))
        
        # 2. Add RP Bonuses
        if rp >= 100: total_bonus += 3
        elif rp >= 60: total_bonus += 2
        elif rp >= 20: total_bonus += 1
        
        # 3. Generate Range (Cap at reasonable level, e.g. 10-20)
        total_bonus = min(total_bonus, 10)
        crit_range = list(range(20 - total_bonus, 21))
        
        return crit_range

    def _roll_initiative(self):
        """Rolls and sorts combatants for turn order."""
        return InitiativeRoller.roll_initiative(self.party, self.enemies)

    def _initialize_enemy_names(self):
        """Ensures duplicate enemy types have unique display names (e.g., Goblin A, Goblin B)."""
        name_counts = {}
        for e in self.enemies:
            # Store base name if not already present
            if 'base_name' not in e:
                e['base_name'] = e.get('name', 'Enemy')
            
            base_display_name = e['base_name'].replace('_', ' ').title()
            name_counts[base_display_name] = name_counts.get(base_display_name, 0) + 1
            
        name_trackers = {}
        for e in self.enemies:
            base_display_name = e['base_name'].replace('_', ' ').title()
            if name_counts[base_display_name] > 1:
                instance_idx = name_trackers.get(base_display_name, 0)
                suffix = f" {chr(65 + instance_idx)}"
                e["name"] = base_display_name + suffix
                name_trackers[base_display_name] = instance_idx + 1
            else:
                e["name"] = base_display_name
