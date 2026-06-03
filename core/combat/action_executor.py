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
                    # Mark as dying to hide normal sprite and show silhouette
                    target['is_dying'] = True 
                    state.dialogue_mgr.queue_message(f"{target['name']} has been defeated!")
                    
                    # 1. Trigger physical loot drop (starts inactive/static)
                    if target.get('is_enemy'):
                        state.loot_mgr.trigger_drop(target)
                    
                    # 2. Queue Static Death VFX (Silhouette)
                    state.vfx_mgr.play_death_vfx(target, is_static=True)

                    # Pop from turn queue immediately
                    if target in state.turn_queue:
                        state.turn_queue.remove(target)
                
                state.vfx_mgr.play_effect(state.pending_action_data, state.current_actor.get('screen_pos', (0,0)), target_pos)
                state.float_mgr.add(str(dmg), text_pos, color_key="crit" if res.get('crit') else "damage")

            elif heal > 0:
                target['current_hp'] = min(target.get('max_hp', 100), target.get('current_hp', 0) + heal)
                state.float_mgr.add(str(heal), text_pos, color_key="heal")

            # Apply Resource Gains and Buffs
            from core.players.player import apply_consumable_effect
            apply_consumable_effect(target, res)
            
            if res.get('mana_gain', 0) > 0:
                state.float_mgr.add(str(res['mana_gain']), text_pos, color_key="mana")
            if res.get('stamina_gain', 0) > 0:
                state.float_mgr.add(str(res['stamina_gain']), text_pos, color_key="stamina")
            if res.get('bonus_gain', 0) > 0:
                state.float_mgr.add("BUFF", text_pos, color_key="buff")
            if res.get('attack_gain', 0) > 0:
                state.float_mgr.add("HASTE", text_pos, color_key="buff")
            
            if res.get('miss'):
                state.float_mgr.add("Miss", text_pos, color_key="miss")
                if not is_aoe:
                    state.dialogue_mgr.queue_message(f"{target['name']} evaded the attack!")

            # Apply Effects
            res_effects = res.get('effects', [])
            if res_effects:
                from core.combat.over_time import OverTimeProcessor
                for effect in res_effects:
                    # Determine if effect targets the source (e.g. Vex, Lifesteal) or the target
                    effect_recipient = state.current_actor if effect.get('target_source') else target
                    
                    # 1. Immediate Special Effects
                    eff_type = effect.get('type')
                    if eff_type == 'immediate_damage':
                        val = effect.get('value', 0)
                        old_hp = target.get('current_hp', 0)
                        target['current_hp'] = max(0, old_hp - val)
                        state.float_mgr.add(str(val), text_pos, color_key="damage")
                        if target['current_hp'] <= 0 and old_hp > 0:
                            target['is_alive'] = False
                            state.dialogue_mgr.queue_message(f"{target['name']} has been defeated!")
                            if target in state.turn_queue:
                                state.turn_queue.remove(target)
                    
                    elif eff_type == 'heal_attacker':
                        val = effect.get('value', 0)
                        state.current_actor['current_hp'] = min(state.current_actor.get('max_hp', 100), state.current_actor.get('current_hp', 0) + val)
                        # Use actor's visual position
                        a_rect = state.current_actor.get('_visual_rect')
                        a_pos = (a_rect.centerx, a_rect.centery) if a_rect else state.current_actor.get('screen_pos', (0,0))
                        state.float_mgr.add(str(val), a_pos, color_key="heal")

                    elif eff_type == 'swift':
                        # Mark that we've triggered swift this turn to avoid infinite attacks
                        if not state.current_actor.get('_swift_triggered'):
                            state.current_actor['_swift_triggered'] = True
                            # We'll increment the local max_atks later in the multi-attack logic

                    # 2. Standard Over-Time/Condition Effects
                    effect['source_ability'] = ability_name
                    refreshed = OverTimeProcessor.apply_effect(effect_recipient, effect, source=state.current_actor)
                    eff_name = effect.get('name', 'Effect').replace('_', ' ').title()

                    if eff_type == 'dot': dot_duration = effect.get('duration', 0)
                    elif eff_type == 'hot': hot_duration = effect.get('duration', 0)

                    if eff_name not in all_res_effects: all_res_effects.append(eff_name)

                    if state.float_mgr:
                        recipient_rect = effect_recipient.get('_visual_rect')
                        recipient_pos = (recipient_rect.centerx, recipient_rect.centery) if recipient_rect else effect_recipient.get('screen_pos', (0,0))
                        float_text = f"{eff_name.upper()}+" if refreshed else eff_name.upper()
                        state.float_mgr.add(float_text, recipient_pos, color_key="effect")

            # --- Advantage Next Consumption ---
            # 1. Consumption from Target (Next hit on them)
            if target.get('_consume_advantage_next'):
                target['active_effects'] = [e for e in target.get('active_effects', []) if e.get('type') != 'advantage_next']
                if 'advantage_next' in target.get('conditions', {}):
                    del target['conditions']['advantage_next']
                del target['_consume_advantage_next']

            # 2. Consumption from Attacker (Vex-style)
            if state.current_actor.get('_consume_advantage_next'):
                state.current_actor['active_effects'] = [e for e in state.current_actor.get('active_effects', []) if e.get('type') != 'advantage_next']
                if 'advantage_next' in state.current_actor.get('conditions', {}):
                    del state.current_actor['conditions']['advantage_next']
                del state.current_actor['_consume_advantage_next']

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
            if state.current_actor.get('_swift_triggered'):
                max_atks += 1
        elif action.get('use_attack_count'):
            # Support both 'attack_count_overide' (legacy typo) and 'attack_count_override'
            override = action.get('attack_count_override', action.get('attack_count_overide'))
            base_count = int(state.current_actor.get('attack_count', 1))
            
            if isinstance(override, str):
                if override.startswith('+'):
                    max_atks = base_count + int(override[1:])
                elif override.startswith('-'):
                    max_atks = max(1, base_count - int(override[1:]))
                elif override.startswith('*'):
                    max_atks = base_count * int(override[1:])
                else:
                    try: max_atks = int(override)
                    except: max_atks = base_count
            elif isinstance(override, (int, float)):
                max_atks = int(override)
            else:
                max_atks = base_count

        if state.atk_made < max_atks:
            print(f"[COMBAT] Multi-hit triggered: {state.atk_made}/{max_atks} complete.")
            
            if state._check_combat_end(): return

            state.current_results = []
            state.active_target_list = []
            state.active_target_grid = None
            
            # Use 'is_summon' flag to ensure player summons use AI re-targeting
            is_player_controlled = (state.current_actor in state.party) and not state.current_actor.get('is_summon')
            
            if is_player_controlled:
                state.phase = "TARGETING"
                state.grid_mgr.generate_valid_target_map()
                state.menu_controller.state = MenuState.SELECTING_TARGET
                state.grid_mgr.snap_to_nearest_valid(state.menu_controller)
            else:
                # AI controlled (Enemy or Summon) re-target
                from core.combat.combat_ai import CombatAI
                
                # Identify opposing faction
                is_party = (state.current_actor in state.party)
                opposing_list = state.enemies if is_party else state.party
                living_opponents = [e for e in opposing_list if e.get('current_hp', 0) > 0]
                
                if living_opponents:
                    # Pick a new target for the EXISTING action
                    target = CombatAI.pick_target(state.current_actor, living_opponents, state.pending_action_data)
                    if target:
                        state.active_target_list = [target]
                        state.active_target_grid = (target['grid_x'], target['grid_y'])
                        # Go back to EXECUTION for the next hit
                        state.phase = "EXECUTION"
                    else:
                        state.phase = "END_TURN"
                else:
                    state.phase = "END_TURN"
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
        
        # Deduct Cost (Summons skip CombatEngine.resolve_action)
        cost_raw = current_action.get('cost', 0)
        if cost_raw:
            try:
                # Resolve placeholders for cost if it's a string formula
                prof = int(state.current_actor.get('proficiency_bonus', 0))
                total_level = sum(state.current_actor.get('class_levels', {}).values()) if state.current_actor.get('class_levels') else state.current_actor.get('level', 1)
                placeholders = {
                    "{level}": str(total_level),
                    "{prof}": str(prof),
                    "{damage_die}": str(state.current_actor.get('damage_die', state.current_actor.get('die', 4))),
                }
                
                # Simple math resolution
                cost_str = str(cost_raw)
                for k, v in placeholders.items():
                    cost_str = cost_str.replace(k, v)
                
                # Eval safely if it looks like math
                if any(op in cost_str for op in "+-*/"):
                    from core.combat.combat_engine import CombatEngine
                    cost_str = CombatEngine._resolve_math(cost_str, {}) # Re-use engine helper if needed
                    cost = int(eval(cost_str, {"__builtins__": None}, {}))
                else:
                    cost = int(cost_str)
                
                if cost > 0:
                    res_type = current_action.get('resource', 'mp').lower()
                    res_key = f"current_{res_type}"
                    state.current_actor[res_key] = max(0, state.current_actor.get(res_key, 0) - cost)
                    print(f"[COMBAT] {state.current_actor['name']} paid {cost} {res_type.upper()} for summon.")
            except Exception as e:
                print(f"[COMBAT] Failed to deduct summon cost: {e}")

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
