import pygame
import random
from core.combat.menu_controller import MenuState
from core.combat.summoning_helper import SummoningHelper
from core.game_rules.constants import scale_x, scale_y

class ActionExecutor:
    """
    Handles the application of combat results, visual sequencing, 
    and multi-hit logic.
    """
    def __init__(self, state):
        self.state = state

    def _format_names(self, names):
        if not names: return ""
        if len(names) == 1: return names[0]
        if len(names) == 2: return f"{names[0]} and {names[1]}"
        return ", ".join(names[:-1]) + ", and " + names[-1]

    def execute(self):
        """
        Applies damage/healing, triggers visuals, and manages multi-attack flow.
        """
        state = self.state
        if not state.pending_action_data:
            print("[COMBAT] Execution failed: No pending action.")
            state.phase = "END_TURN"
            return

        # 1. Resolve results if needed
        if not state.current_results:
            targets = getattr(state, 'active_target_list', [])
            if not targets:
                targets = state._get_current_target_list()
            
            if targets:
                state.current_results = state.engine.resolve_action(state.current_actor, state.pending_action_data, targets)
            else:
                print(f"[COMBAT] Execution failed: No targets for {state.pending_action_data.get('name')}")
                state.phase = "END_TURN"
                return

        # --- VISUALS: Trigger Lunge ---
        state.sprite_mgr.trigger_lunge(state.current_actor)

        # --- DIALOGUE: Queue Action Start ---
        is_aoe = state.pending_action_data.get('aoe', False)
        ability_name = state.pending_action_data.get('name', 'Ability').replace('_', ' ').title()
        target_name = "Multiple Targets" if is_aoe or len(state.active_target_list) > 1 else (state.active_target_list[0]['name'] if state.active_target_list else "Unknown")
        state.dialogue_mgr.queue_action_start(state.current_actor['name'], state.pending_action_data, target_name)

        # 2. Apply Results
        print(f"\n--- Action Execution: {ability_name} ---")
        
        saved_names = []
        failed_names = []
        healed_names = []
        consolidated_damage = 0
        consolidated_healing = 0
        all_res_effects = []
        dot_duration = 0
        hot_duration = 0

        for res in state.current_results:
            target = res['target']
            dmg = res.get('damage', 0)
            heal = res.get('healing', 0)
            
            # --- VISUALS: Positions ---
            target_pos = target.get('screen_pos', (0,0))
            v_rect = target.get('_visual_rect')
            text_pos = (v_rect.centerx, v_rect.centery) if v_rect else (target_pos[0] + scale_x(60), target_pos[1] + scale_y(60))

            # --- Consolidation Tracking ---
            if is_aoe:
                si_map = res.get('save_info', {})
                si = si_map.get(id(target))
                if si:
                    if si.get('success'):
                        saved_names.append(target['name'])
                    else:
                        failed_names.append(target['name'])
                        consolidated_damage = max(consolidated_damage, dmg)
                else:
                    failed_names.append(target['name'])
                    consolidated_damage = max(consolidated_damage, dmg)
            else:
                if dmg > 0:
                    failed_names.append(target['name'])
                    consolidated_damage = max(consolidated_damage, dmg)
                if heal > 0:
                    healed_names.append(target['name'])
                    consolidated_healing = max(consolidated_healing, heal)

            if dmg > 0:
                old_hp = target.get('current_hp', 0)
                target['current_hp'] = max(0, old_hp - dmg)
                if target['current_hp'] <= 0 and old_hp > 0:
                    target['is_alive'] = False
                    state.dialogue_mgr.queue_message(f"{target['name']} has been defeated!")
                
                state.vfx_mgr.play_effect(state.pending_action_data, state.current_actor.get('screen_pos', (0,0)), target_pos)
                state.float_mgr.add(str(dmg), text_pos, color_key="crit" if res.get('crit') else "damage")

            elif heal > 0:
                target['current_hp'] = min(target.get('max_hp', 100), target.get('current_hp', 0) + heal)
                state.float_mgr.add(str(heal), text_pos, color_key="heal")
            
            elif res.get('miss'):
                state.float_mgr.add("Miss", text_pos, color_key="miss")
                if not is_aoe:
                    state.dialogue_mgr.queue_message(f"{target['name']} evaded the attack!")

            # Apply Effects
            res_effects = res.get('effects', [])
            if res_effects:
                from core.combat.over_time import OverTimeProcessor
                for effect in res_effects:
                    refreshed = OverTimeProcessor.apply_effect(target, effect, source=state.current_actor)
                    eff_name = effect.get('name', 'Effect').replace('_', ' ').title()
                    eff_type = effect.get('type')

                    if eff_type == 'dot': dot_duration = effect.get('duration', 0)
                    elif eff_type == 'hot': hot_duration = effect.get('duration', 0)

                    if eff_name not in all_res_effects: all_res_effects.append(eff_name)

                    if state.float_mgr:
                        float_text = f"{eff_name.upper()}+" if refreshed else eff_name.upper()
                        state.float_mgr.add(float_text, text_pos, color_key="effect")

            # --- Advantage Next Consumption ---
            if target.get('_consume_advantage_next'):
                # Force-expire advantage_next from active_effects list
                target['active_effects'] = [e for e in target.get('active_effects', []) if e.get('type') != 'advantage_next']
                # Sync conditions dict
                if 'advantage_next' in target.get('conditions', {}):
                    del target['conditions']['advantage_next']
                del target['_consume_advantage_next']

        # --- Queue Consolidated Dialogue ---
        all_eff_names = [e.replace('_', ' ').title() for e in all_res_effects]
        eff_str = f" and had {', '.join(all_eff_names)} applied" if all_eff_names else ""

        if is_aoe:
            if saved_names:
                names = self._format_names(saved_names)
                state.dialogue_mgr.queue_message(f"{names} made their save, taking half damage.")
            
            if failed_names:
                names = self._format_names(failed_names)
                msg = f"{ability_name} dealt {consolidated_damage} to {names}{eff_str}."
                if dot_duration > 0:
                    msg += f" They will continue taking damage for {dot_duration} turns."
                state.dialogue_mgr.queue_message(msg)
            elif all_eff_names:
                # AOE with no damage but status effects (e.g. AOE Stun or Buff)
                names = self._format_names([r['target']['name'] for r in state.current_results])
                state.dialogue_mgr.queue_message(f"{ability_name} applied {', '.join(all_eff_names)} to {names}!")

            if healed_names:
                names = self._format_names(healed_names)
                msg = f"{ability_name} healed {names} for {consolidated_healing} HP."
                if hot_duration > 0:
                    msg += f" They will continue healing for {hot_duration} turns."
                state.dialogue_mgr.queue_message(msg)
        else:
            # Single Target Consolidation
            target_name = failed_names[0] if failed_names else (healed_names[0] if healed_names else (state.current_results[0]['target']['name'] if state.current_results else None))
            if target_name:
                if consolidated_damage > 0:
                    msg = f"{ability_name} dealt {consolidated_damage} to {target_name}{eff_str}."
                    if dot_duration > 0:
                        msg += f" {target_name} will continue taking damage for {dot_duration} turns."
                    state.dialogue_mgr.queue_message(msg)
                elif consolidated_healing > 0:
                    msg = f"{ability_name} healed {target_name} for {consolidated_healing} HP."
                    if hot_duration > 0:
                        msg += f" {target_name} will continue healing for {hot_duration} turns."
                    state.dialogue_mgr.queue_message(msg)
                elif all_eff_names:
                    # Pure status/buff
                    state.dialogue_mgr.queue_message(f"{ability_name} applied {', '.join(all_eff_names)} to {target_name}!")

        # 3. Handle Multi-Attack Logic
        state.atk_made += 1
        
        # Determine max attacks
        max_atks = 1
        action = state.pending_action_data
        
        if action.get('name') == "Attack":
            max_atks = int(state.current_actor.get('attack_count', 1))
        elif action.get('use_attack_count'):
            override = action.get('attack_count_overide')
            if override is not None:
                max_atks = int(override)
            else:
                max_atks = int(state.current_actor.get('attack_count', action.get('attack_count', 1)))

        if state.atk_made < max_atks:
            print(f"[COMBAT] Multi-hit triggered: {state.atk_made}/{max_atks} complete.")
            
            if state._check_combat_end(): return

            state.current_results = []
            state.active_target_list = []
            state.active_target_grid = None
            
            if state.current_actor in state.party:
                state.phase = "TARGETING"
                state.grid_mgr.generate_valid_target_map()
                state.menu_controller.state = MenuState.SELECTING_TARGET
                state.grid_mgr.snap_to_nearest_valid(state.menu_controller)
            else:
                state.phase = "ENEMY_TURN" 
        else:
            if state._check_combat_end(): return
            
            state.active_target_list = []
            state.active_target_grid = None
            state.pending_action_data = None
            state.current_results = []
            state.grid_mgr.sync_combat_grid()
            
            state.phase = 'ANIMATING'

    def execute_summon(self):
        """
        Detects summon type, skips targeting, and uses SummoningHelper to spawn units.
        """
        state = self.state
        if not state.pending_action_data: return
        
        from core.players.player import load_summons
        from core.combat.combatant_factory import CombatantFactory

        # 1. Detect and Load
        current_action = state.pending_action_data
        summons_db = load_summons()
        
        # 2. Create Summons
        new_entities = SummoningHelper.create_summons(current_action, state.current_actor, summons_db)
        if not new_entities:
            state.dialogue_mgr.queue_message(f"{state.current_actor['name']}'s summon failed!")
            state.phase = "ANIMATING"
            return

        # 3. Determine Faction and placement targets
        is_party = (state.current_actor in state.party)
        ally_list = state.party if is_party else state.enemies
        
        # target_col: Party usually 1, Enemy usually 3
        target_col = current_action.get('target_col', 1 if is_party else 3)
        max_slots = 3 if is_party else 4

        # 4. Place Summons
        # Ensure caster has a unique ID (should be set by create_summons, but double-check)
        if 'id' not in state.current_actor:
            state.current_actor['id'] = f"actor_{id(state.current_actor)}_{random.randint(1000, 9999)}"
        caster_id = state.current_actor['id']

        placed_entities = SummoningHelper.place_summons(new_entities, ally_list, target_col, max_slots, caster_id)
        
        if not placed_entities:
            state.dialogue_mgr.queue_message("No room to summon!")
            state.phase = "ANIMATING"
            return

        # 5. Initialize and Add to Combat
        for summon in placed_entities:
            # We treat them as a mini-party or mini-enemy group for initialization
            temp_list = [summon]
            CombatantFactory.prepare_for_combat(temp_list if is_party else [], [] if is_party else temp_list)
            
            # Delegate Visual Positioning to Grid Manager
            state.grid_mgr.assign_summon_visual_position(summon)
            
        # Add to active ally list using extend as requested
        ally_list.extend(placed_entities)

        # 6. Inject directly into the turn order (turn_queue)
        # Find the caster's position and insert the summons immediately after them
        if state.current_actor in state.turn_queue:
            caster_idx = state.turn_queue.index(state.current_actor)
            for i, summon in enumerate(placed_entities):
                state.turn_queue.insert(caster_idx + 1 + i, summon)

        # 7. Update Grid and Presentation
        state.current_actor['summon_active'] = True
        state.grid_mgr.sync_combat_grid()
        state.dialogue_mgr.queue_message(f"{state.current_actor['name']} summoned {len(placed_entities)} units!")
        
        # Cleanup
        state.pending_action_data = None
        state.phase = 'ANIMATING'
