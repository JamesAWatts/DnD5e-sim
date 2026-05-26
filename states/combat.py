import pygame
import random
import os
import copy
import json
import math

from states.base_state import BaseState
from ui.menu import Menu
from ui.panel import Panel
from ui.dialogue_box import DialogueBox
from ui.bars import draw_bar
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y
from core.combat.attack_roller import attack_roll, damage_roll
from core.combat.combat_engine import CombatEngine
from core.players.player import load_consumables, load_spells, load_skills, validate_player_data
from core.game_rules.mana_check import ManaCheck
from ui.backgrounds import BackgroundManager
from graphics.sprite_manager import SpriteManager
from ui.floating_text import FloatingTextManager
from ui.dice_animation import DiceAnimation
from ui.projectile_manager import ProjectileManager
from graphics.vfx_manager import VFXManager
from ui.combat_menus import CombatMenuManager
from core.game_rules.path_utils import get_resource_path


class CombatJuiceManager:
    def __init__(self, combat_state):
        self.state = combat_state
        self.phase = 'IDLE' # 'MOVING', 'WAITING_FOR_DICE', 'WIGGLING', 'RETURNING', 'IDLE'
        self.attacker = None
        self.target = None
        self.start_pos = (0, 0)
        self.target_pos = (0, 0)
        self.lerp_t = 0.0
        self.wiggle_timer = 0
        self.direction = 1
        self.pending_dice = None
        self.pending_res = None

    def trigger_lunge(self, attacker, target, res, dice_info=None):
        self.attacker = attacker
        self.target = target
        self.pending_res = res
        self.pending_dice = dice_info
        
        # Determine start position
        is_player = any(attacker is p for p in self.state.party) or (attacker.get('is_summon') and not attacker.get('is_enemy_summon'))
        if is_player:
            self.start_pos = self.state.party_positions.get(id(attacker), (0,0))
            self.direction = 1
        else:
            self.start_pos = attacker.get('_combat_pos', (0,0))
            self.direction = -1
            
        # Target position
        is_aoe = isinstance(target, list)
        ref_target = target[0] if is_aoe else target
        
        if any(ref_target is p for p in self.state.party) or (ref_target.get('is_summon') and not ref_target.get('is_enemy_summon')):
            tx, ty = self.state.party_positions.get(id(ref_target), (0,0))
        else:
            tx, ty = ref_target.get('_combat_pos', (0,0))
            
        # Calculate target position (padded)
        padded_x = tx - (scale_x(40) * self.direction)
        self.target_pos = (padded_x, ty)
        
        self.phase = 'MOVING'
        self.lerp_t = 0.0
        self.state.active_attacker = attacker
        self.state.active_target = ref_target if not is_aoe else None

    def update(self, dt):
        if self.phase == 'IDLE': return
        
        if self.phase == 'MOVING':
            self._update_moving(dt)
        elif self.phase == 'WAITING_FOR_DICE':
            self._update_waiting()
        elif self.phase == 'WIGGLING':
            self._update_wiggling(dt)
        elif self.phase == 'RETURNING':
            self._update_returning(dt)

    def _update_moving(self, dt):
        self.lerp_t += 0.009 * dt
        if self.lerp_t >= 1.0:
            self.lerp_t = 1.0
            self.phase = 'WAITING_FOR_DICE'
            if self.pending_dice:
                if self.pending_dice.get('multi'):
                    self.state.dice_anim.start_multi_roll(self.pending_dice['rolls'], self.pending_dice['style'])
                else:
                    self.state.dice_anim.start_roll(self.pending_dice['value'], self.pending_dice['style'])
                self.state.dice_anim.stay_settled = True
            else:
                self.phase = 'WIGGLING'
                self.wiggle_timer = 10
                self._trigger_floating_effects()

        # Apply offsets
        self.state.attacker_offset = (self.target_pos[0] - self.start_pos[0]) * self.lerp_t
        self.state.attacker_offset_y = (self.target_pos[1] - self.start_pos[1]) * self.lerp_t

    def _update_waiting(self):
        if self.state.dice_anim.state == 'SETTLED':
            self.phase = 'WIGGLING'
            self.wiggle_timer = 10
            self._trigger_floating_effects()

    def _update_wiggling(self, dt):
        self.wiggle_timer -= (dt / 16.67)
        if self.wiggle_timer <= 0:
            self.phase = 'RETURNING'
            self.lerp_t = 0.0
            self.state.target_offset_x = 0
        else:
            mag = scale_x(8)
            off = mag if (int(self.wiggle_timer) // 2) % 2 == 0 else -mag
            max_off_x = self.target_pos[0] - self.start_pos[0]
            self.state.attacker_offset = max_off_x + (off * self.direction)
            self.state.target_offset_x = off

    def _update_returning(self, dt):
        self.lerp_t += 0.006 * dt
        if self.lerp_t >= 1.0:
            self.lerp_t = 1.0
            self.phase = 'IDLE'
            self.state.attacker_offset = 0
            self.state.attacker_offset_y = 0
            self.state.active_attacker = None
            self.state.active_target = None
        else:
            max_off_x = self.target_pos[0] - self.start_pos[0]
            max_off_y = self.target_pos[1] - self.start_pos[1]
            self.state.attacker_offset = max_off_x * (1.0 - self.lerp_t)
            self.state.attacker_offset_y = max_off_y * (1.0 - self.lerp_t)

    def _trigger_floating_effects(self):
        res = self.pending_res
        if not res: return
        target = self.target
        is_aoe = isinstance(target, list)
        targets_list = target if is_aoe else [target]
        
        saves_info = res.get('saves_info', {})
        if saves_info:
            for t in targets_list:
                info = saves_info.get(id(t))
                if info:
                    self.state.float_mgr.add("SAVE" if info['success'] else "FAIL", t['screen_pos'], color_key="save" if info['success'] else "fail")
                    dmg = res.get('damage_by_target', {}).get(id(t), 0)
                    if dmg > 0:
                        self.state.float_mgr.add(f"-{dmg}", t['screen_pos'], color_key="hit", delay=20)
                    t['flash_frames'] = 36
                    t['flash_type'] = 'damage'
        else:
            main_t = targets_list[0]
            if res.get('hit'):
                if res.get('critical'):
                    self.state.float_mgr.add("CRITICAL!", main_t['screen_pos'], color_key="crit")
                dmg = res.get('damage', 0)
                if dmg > 0:
                    self.state.float_mgr.add(f"-{dmg}", main_t['screen_pos'], color_key="hit")
                main_t['flash_frames'] = 36
                main_t['flash_type'] = 'damage'
            else:
                self.state.float_mgr.add("MISS", main_t['screen_pos'], color_key="miss")


class CombatState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.combat_engine = CombatEngine # Headless MVC: engine reference
        self.background = BackgroundManager.get_combat_bg()

        # Managers
        self.dialogue = DialogueBox(self.font)
        self.float_mgr = FloatingTextManager()
        self.dice_anim = DiceAnimation()
        self.projectile_mgr = ProjectileManager()
        self.vfx_mgr = VFXManager()
        self.juice_mgr = CombatJuiceManager(self)
        self.menu_manager = CombatMenuManager(self)

        self.party = game.party 
        self.enemies = game.enemies

        
        self._initialize_positions()
        self._initialize_enemy_names()
        self._initialize_combatants()
        self._initialize_registry()
        self._reset_combat_state()

        names = ", ".join([e["name"] for e in self.enemies])
        self.queue_message(f"Encountered: {names}!")
        self.start_next_message()

    def _initialize_positions(self):
        # Party
        sorted_party = sorted(self.party, key=lambda p: p.get('max_hp', 10), reverse=True)
        self.party_positions = {}
        for i, p in enumerate(sorted_party):
            col_idx = 2 - i
            base_x = scale_x(20) + (col_idx * scale_x(60))
            base_y = SCREEN_HEIGHT // 2 - scale_y(100) + (i * scale_y(50))
            p['screen_pos'] = (base_x + scale_x(48), base_y + scale_y(10))
            self.party_positions[id(p)] = (base_x, base_y)

        # Enemies (3 Columns)
        self.column_x = [
            SCREEN_WIDTH - scale_x(460), # Column 0 (Summon Column)
            SCREEN_WIDTH - scale_x(320), # Column 1 (Minion Column)
            SCREEN_WIDTH - scale_x(180)  # Column 2 (Leader/Boss Column)
        ]
        
        leader_unit = next((e for e in self.enemies if e.get('is_leader')), None)
        minions = [e for e in self.enemies if not e.get('is_leader')]

        if leader_unit:
            for i, m in enumerate(minions):
                if i < 4:
                    enemy_x = self.column_x[1] + (i * scale_x(20))
                    enemy_y = SCREEN_HEIGHT // 2 - scale_y(150) + (i * scale_y(80))
                    m['_combat_column'] = 1
                else:
                    extra_idx = i - 4
                    direction = -1 if extra_idx % 2 == 0 else 1
                    offset = ((extra_idx // 2) + 1) * scale_y(120)
                    enemy_x = self.column_x[2] + scale_x(20)
                    enemy_y = (SCREEN_HEIGHT // 2 - scale_y(60)) + (direction * offset)
                    m['_combat_column'] = 2
                m['_combat_pos'] = (enemy_x, enemy_y); m['screen_pos'] = (enemy_x + scale_x(62), enemy_y + scale_y(20))
            
            enemy_x = self.column_x[2]; enemy_y = SCREEN_HEIGHT // 2 - scale_y(60)
            leader_unit['_combat_pos'] = (enemy_x, enemy_y); leader_unit['screen_pos'] = (enemy_x + scale_x(62), enemy_y + scale_y(20)); leader_unit['_combat_column'] = 2
        else:
            for i, m in enumerate(minions):
                col_idx = i // 4; row_idx = i % 4
                target_x = self.column_x[col_idx + 1]
                enemy_x = target_x + (row_idx * scale_x(20)); enemy_y = SCREEN_HEIGHT // 2 - scale_y(150) + (row_idx * scale_y(80))
                m['_combat_pos'] = (enemy_x, enemy_y); m['screen_pos'] = (enemy_x + scale_x(62), enemy_y + scale_y(20)); m['_combat_column'] = col_idx + 1
        self.enemies.sort(key=lambda x: x.get('is_leader', False))

    def _initialize_enemy_names(self):
        name_counts = {}
        for e in self.enemies:
            e["enemy_type"] = e.get('base_name', e.get('name', 'enemy').lower().replace(' ', '_'))
            base_display_name = e.get('base_name', e['name']).replace('_', ' ').title()
            name_counts[base_display_name] = name_counts.get(base_display_name, 0) + 1
        name_trackers = {}
        for e in self.enemies:
            base_display_name = e.get('base_name', e['name']).replace('_', ' ').title()
            if name_counts[base_display_name] > 1:
                instance_idx = name_trackers.get(base_display_name, 0); suffix = f" {chr(65 + instance_idx)}"
                e["name"] = base_display_name + suffix; name_trackers[base_display_name] = instance_idx + 1
            else: e["name"] = base_display_name

    def _initialize_combatants(self):
        for p in self.party:
            buff = p.get('hp_buff', 0)
            p['max_hp_combat'] = int(p.get("max_hp", 10)) + buff
            p['current_hp'] = min(p['max_hp_combat'], int(p.get("current_hp", p.get("hp", 10))) + buff)
            p.setdefault("conditions", {})
        for e in self.enemies:
            e["current_hp"] = int(e.get("current_hp", e.get("hp", 10))); e["max_hp"] = int(e.get("hp", 10))
            lvl = e.get('level', 1); e["max_sp"] = 10; e["current_sp"] = (lvl + 3) // 4; e["max_mp"] = 10; e["current_mp"] = (lvl + 3) // 4
            e["heal_available"] = True; e["summon_alive"] = False; e.setdefault("conditions", {})
            filenames = SpriteManager._enemy_mapping.get(e["enemy_type"], [])
            e["sprite_filename"] = random.choice(filenames) if filenames else f"{e['enemy_type']}.png"

    def _initialize_registry(self):
        self.consumables_db = load_consumables()
        self._raw_spells_db = load_spells()
        self._raw_skills_db = load_skills()
        self.ability_registry = {}
        for actor in self.party + self.enemies: self._register_actor_abilities(actor)

    def _reset_combat_state(self):
        self.player_advantage = 0; self.enemy_advantage = 0; self.extra_damage_once = 0; self.original_attack_count = None
        self.turn_order = []; self.turn_index = 0; self.phase = "INITIATIVE"; self.round_number = 1
        self.pending_action = None; self.action_data = None; self.message_queue = []
        self.main_menu = None; self.target_menu = None; self.sub_menu = None; self.menu_state = "MAIN"; self.active_menu = None
        self.active_attacker = None; self.active_target = None; self.attacker_offset = 0; self.attacker_offset_y = 0; self.target_offset_x = 0
        self.summons = {}; self.attacks_made = 0; self.ability_hits_made = 0

    def _register_actor_abilities(self, actor):
        actor_id = id(actor); self.ability_registry[actor_id] = {}
        ability_names = list(set(actor.get('skills', []) + actor.get('spells', [])))
        from core.combat.combat_ai import CombatAI
        for name in ability_names:
            raw_data = EnemyAI.get_ability_data(name)
            if not raw_data: continue
            baked_data = copy.deepcopy(raw_data)
            res = self.combat_engine.resolve_ability(baked_data, actor, [actor], skip_cost=False)
            baked_data['cost'] = res['mana_cost']
            self.ability_registry[actor_id][name.lower().replace(' ', '_')] = baked_data

    @property
    def current_actor(self):
        if not self.turn_order: return None
        if self.turn_index >= len(self.turn_order): self.turn_index = 0
        return self.turn_order[self.turn_index]

    def get_living_players(self):
        living = [p for p in self.party if p.get('current_hp', 0) > 0]
        sum_p = [s for s in self.summons.values() if not s.get('is_enemy_summon') and s.get('current_hp', 0) > 0]
        return living + sum_p

    def get_living_enemies(self):
        living = [e for e in self.enemies if e.get('current_hp', 0) > 0]
        sum_e = [s for s in self.summons.values() if s.get('is_enemy_summon') and s.get('current_hp', 0) > 0]
        return living + sum_e

    def handle_summon(self, owner, ability_data):
        try:
            raw_types = ability_data.get('summon_type', 'wolf'); summon_types = raw_types if isinstance(raw_types, list) else [raw_types]
            owner_id = id(owner); is_enemy = any(id(owner) == id(e) for e in self.enemies)
            prof = int(owner.get('proficiency_bonus', 0))
            total_level = sum(owner.get('class_levels', {}).values()) if owner.get('class_levels') else owner.get('level', 1)
            mp_val = int(owner.get('standby_mp', owner.get('current_mp', 0))); sp_val = int(owner.get('standby_sp', owner.get('current_sp', 0)))
            placeholders = {
                "{damage_die}": str(owner.get('damage_die', owner.get('die', 4))), "{level}": str(total_level),
                "{level/2}": str(total_level // 2), "{prof}": str(prof), "{current_mp}": str(mp_val),
                "{current_mp/2}": str(mp_val // 2), "{current_sp}": str(sp_val), "{current_sp/2}": str(sp_val // 2)
            }
            context = {'level': total_level, 'prof': prof, 's_level': total_level, 's_prof': prof, 's_name': owner['name']}
            raw_count = ability_data.get('summon_count', 1); summon_count = 1
            if isinstance(raw_count, str):
                try:
                    resolved = self.combat_engine._resolve_math(raw_count, placeholders)
                    if not resolved.isdigit():
                        formula = raw_count.format(**context); summon_count = max(1, int(eval(formula, {"__builtins__": None}, context)))
                    else: summon_count = max(1, int(resolved))
                except: summon_count = 1
            else: summon_count = int(raw_count)

            to_remove = [sid for sid, s in self.summons.items() if s.get('owner_id') == owner_id]
            for sid in to_remove:
                old = self.summons[sid]; 
                if old in self.turn_order: self.turn_order.remove(old)
                del self.summons[sid]

            path = get_resource_path(os.path.join('data', 'combat', 'summons.json'))
            with open(path, 'r') as f:
                summons_db = json.load(f).get('summon_list', {})

            summons_created = []
            for s_type in summon_types:
                data = summons_db.get(s_type)
                if not data: continue
                for i in range(summon_count):
                    name = data.get('name_template', "{owner_name}'s Summon").format(**context)
                    if summon_count > 1: name = f"{name} {chr(65+i)}"
                    folder = data.get('sprite_folder', os.path.join("assets", "sprites", "player_sprites", "summons") if not is_enemy else os.path.join("assets", "sprites", "enemies", "summons"))
                    category = "humanoid"
                    if "enemies" in folder: 
                        parts = folder.replace("\\", "/").split("/")
                        try: category = parts[parts.index("enemies")+1]
                        except: pass
                    elif "player_sprites" in folder and "summons" not in folder: category = "player"

                    summon = {
                        'name': name, 'is_summon': True, 'owner_id': owner_id, 'is_enemy_summon': is_enemy,
                        'conditions': {}, 'enemy_type': s_type, 'level': total_level, 'proficiency_bonus': prof,
                        'sprite_filename': random.choice(data.get('sprites', ['default.png'])), 'sprite_folder': folder,
                        'sprite_category': category, 'inventory_ref': owner.get('inventory_ref', {})
                    }
                    for stat, val in data.get('stats', {}).items():
                        if isinstance(val, str):
                            res_s = val.format(**context)
                            try: summon[stat] = int(eval(res_s, {"__builtins__": None}, {})) if any(c in res_s for c in "+-*/()") else int(res_s)
                            except: summon[stat] = res_s
                        else: summon[stat] = val
                    summon['max_hp'] = int(summon.get('hp', 10)); summon['current_hp'] = summon['max_hp']
                    summon['max_mp'] = 10; summon['current_mp'] = prof // 2; summon['max_sp'] = 10; summon['current_sp'] = prof // 2
                    prev = summons_created[-1] if summons_created else owner
                    if prev in self.turn_order: self.turn_order.insert(self.turn_order.index(prev) + 1, summon)
                    summons_created.append(summon)

            for i, summon in enumerate(summons_created):
                if not is_enemy:
                    owner_pos = self.party_positions.get(owner_id, (scale_x(100), scale_y(100)))
                    col = i // 2; row = i % 2; offset_x = scale_x(140 + col * 60); offset_y = scale_y(50 + row * 60)
                    summon_pos = (owner_pos[0] + offset_x, owner_pos[1] + offset_y)
                    summon['screen_pos'] = (summon_pos[0] + scale_x(48), summon_pos[1] + scale_y(10)); self.party_positions[id(summon)] = summon_pos
                else:
                    base_x = self.column_x[0]; center_y = SCREEN_HEIGHT // 2; spread_y = scale_y(300)
                    y_offset = (i / (len(summons_created) - 1)) * spread_y - (spread_y / 2) if len(summons_created) > 1 else random.randint(-scale_y(150), scale_y(150))
                    x_jitter = random.randint(-scale_x(30), scale_x(30)); summon_x = base_x + x_jitter; summon_y = center_y + y_offset
                    summon['screen_pos'] = (summon_x + scale_x(62), summon_y + scale_y(20)); self.party_positions[id(summon)] = (summon_x, summon_y); summon['_combat_column'] = 0
                self.summons[id(summon)] = summon
            if summons_created: owner['summon_alive'] = True; self.queue_message(f"{owner['name']} summoned {len(summons_created)} creature(s)!")
        except Exception as e: print(f"Error in handle_summon: {e}")

    def on_select(self, option):
        states = {"MAIN": self.handle_main_menu, "SPELL": self.handle_spell_menu, "SKILL": self.handle_skill_menu, "ITEM": self.handle_item_menu, "TARGETING": self.handle_targeting, "TARGET_COLUMN": self.handle_target_column}
        handler = states.get(self.menu_state)
        if handler: handler(option)

    def update(self, events, dt):
        self.vfx_mgr.update(dt)
        if self.vfx_mgr.is_playing(): return

        self.float_mgr.update(); self.dice_anim.update(); self.projectile_mgr.update(); self.juice_mgr.update(dt)
        for a in self.party + self.enemies: 
            if a.get('flash_frames', 0) > 0: a['flash_frames'] -= 1
            
        if self.dialogue.current_message:
            self._update_dialogue(events)
            return

        if self._check_animations_active(events): return

        phase_map = {
            "INITIATIVE": self.handle_initiative, "TURN_START": self.process_turn_start,
            "PLAYER_TURN": lambda: self._handle_player_turn(events),
            "ENEMY_TURN": self.handle_enemy_turn, "CHECK_END": self.check_combat_end,
            "RESOLVE_VICTORY": self._update_victory_phase
        }
        handler = phase_map.get(self.phase)
        if handler: handler()

    def _update_dialogue(self, events):
        if self.active_attacker and self.juice_mgr.phase == 'IDLE' and self.projectile_mgr.is_finished():
            direction = 1 if any(self.active_attacker is p for p in self.party) else -1
            self.attacker_offset = scale_x(20) * direction
        self.dialogue.update()
        for event in events:
            if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                was_typing = self.dialogue.is_typing; self.dialogue.handle_event(event)
                if not was_typing and not self.dialogue.current_message:
                    pending = getattr(self, '_pending_dice_result', None)
                    if pending and pending.get('trigger_dice_after'):
                        self._trigger_post_dialogue_dice(pending); return 
                    if self.juice_mgr.phase == 'IDLE' and self.projectile_mgr.is_finished():
                        self.active_attacker = None; self.attacker_offset = 0
                    if self.message_queue: self.start_next_message()
                    elif self.phase == "END_COMBAT": self.exit_to_hub()
                    elif self.phase == "LEVEL_UP":
                        from states.level_up import LevelUpState
                        self.game.change_state(LevelUpState(self.game, self.font, player=getattr(self, '_levelup_starter', None)))

    def _trigger_post_dialogue_dice(self, pending):
        res = pending['res']; targets = pending['target']; is_aoe = isinstance(targets, list); targets_list = targets if is_aoe else [targets]
        rolls = []
        saves_info = res.get('saves_info', {})
        for t in targets_list:
            info = saves_info.get(id(t))
            if info: rolls.append((info['roll'], t['screen_pos']))
        
        # If it's a save, the targets are rolling, so use the defender's style.
        # Otherwise, use the attacker's style.
        is_save = pending.get('is_save', False)
        roller = targets_list[0] if (is_save and targets_list) else pending['actor']
        
        style = self.dice_anim.get_style_from_actor(roller, self.party)
        dice_info = {'multi': True, 'rolls': rolls, 'style': style}
        if pending.get('is_physical'): self.juice_mgr.trigger_lunge(pending['actor'], targets, res, dice_info)
        else:
            if dice_info.get('multi'): self.dice_anim.start_multi_roll(dice_info['rolls'], dice_info['style'])
            else: self.dice_anim.start_roll(dice_info['value'], dice_info['style'])
            self.dice_anim.stay_settled = True
            if pending.get('is_ranged'): self._spawn_projectiles(pending['actor'], targets, res)
        pending['trigger_dice_after'] = False 

    def _check_animations_active(self, events):
        if self.dice_anim.is_active:
            if self.dice_anim.state == "SETTLED" and self.dice_anim.stay_settled:
                for event in events:
                    if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                        self.dice_anim.stay_settled = False; self.dice_anim.timer = 0
            if getattr(self.dice_anim, 'is_result_finalized', False): self._waiting_for_dice = True
            else: return True
        if self.juice_mgr.phase != 'IDLE' or not self.projectile_mgr.is_finished(): return True
        if getattr(self, '_waiting_for_dice', False): self._finalize_dice_resolution(); return True
        return False

    def _finalize_dice_resolution(self):
        self._waiting_for_dice = False
        pending = getattr(self, '_pending_dice_result', None)
        if pending:
            actor = pending['actor']; target = pending['target']; res = pending['res']; is_aoe = isinstance(target, list); targets_list = target if is_aoe else [target]
            is_physical = pending.get('is_physical', False); already_floated = is_physical
            if self.juice_mgr.phase == 'IDLE': self.active_attacker = None; self.active_target = None
            if pending.get('is_save'):
                self._save_dialogue_phase = 1; results = self.format_combat_message(res, actor, target); self.queue_message(results); self._save_dialogue_phase = 0
                if not already_floated:
                    saves_info = res.get('saves_info', {})
                    for t in targets_list:
                        info = saves_info.get(id(t))
                        if info:
                            self.float_mgr.add("SAVE" if info['success'] else "FAIL", t['screen_pos'], color_key="save" if info['success'] else "fail")
                            dmg = res.get('damage_by_target', {}).get(id(t), 0)
                            if dmg > 0: self.float_mgr.add(f"-{dmg}", t['screen_pos'], color_key="hit", delay=60)
                            t['flash_frames'] = 36; t['flash_type'] = 'damage'
                for effect, val in res.get('effects', []):
                    if effect not in ['dot', 'heal_attacker', 'extra_dmg']:
                        first_failed = next((t for t in targets_list if not res.get('saves_info', {}).get(id(t), {}).get('success', True)), None)
                        if first_failed:
                            is_buff = effect.lower() in ['advantage', 'invisible', 'hot', 'shielded', 'swift', 'vex', 'lifesteal']
                            self.float_mgr.add(effect.upper(), first_failed['screen_pos'], color_key="buff" if is_buff else "debuff", delay=60 if already_floated else 120)
            else:
                if not already_floated:
                    if res.get('hit') or res.get('damage', 0) > 0:
                        for t in targets_list:
                            dmg = res.get('damage_by_target', {}).get(id(t), res.get('damage', 0)); is_crit = res.get('critical', False)
                            if dmg > 0: self.float_mgr.add(f"-{dmg}", t['screen_pos'], color_key="crit" if is_crit else "hit")
                            t['flash_frames'] = 36; t['flash_type'] = 'crit' if is_crit else 'damage'
                    elif not res.get('hit'):
                        for t in targets_list: self.float_mgr.add("Miss", t['screen_pos'], color_key="miss")
                self.queue_message(pending.get('msg', "Action resolved."))
            if self.pending_action == "ATTACK": self.apply_attack_effects(res, target if not is_aoe else target[0])
            else: self.apply_ability_effects(res, targets_list, actor)
            del self._pending_dice_result
        self.start_next_message()
        if hasattr(self, '_pending_dice_followup'):
            followup = self._pending_dice_followup; del self._pending_dice_followup; followup()

    def _update_victory_phase(self):
        if not self.dialogue.current_message and not self.message_queue:
            self.handle_victory(); self.start_next_message()

    # --- Headless MVC: Combat Resolution Helper ---
    def _apply_combat_results(self, actor, targets, ability_data):
        """
        Consolidated helper for engine math, HP updates, and basic visuals.
        """
        is_first = self.ability_hits_made == 0
        should_hold = (any(actor is p for p in self.party) or (actor.get('is_summon') and not actor.get('is_enemy_summon'))) and self.pending_action in ["ATTACK", "SPELL", "SKILL", "ABILITY"]

        if self.pending_action == "ATTACK":
            t = targets[0]; adv = self._calculate_advantage(actor)
            crit_range = self._calculate_crit_range(actor, t)
            res = self.combat_engine.resolve_attack(actor, t, advantage=adv, float_mgr=None if should_hold else self.float_mgr, crit_range=crit_range)
            t['current_hp'] = max(0, t['current_hp'] - res['damage'])
            if not should_hold:
                if res['hit'] or res['damage'] > 0: t['flash_frames'] = 36; t['flash_type'] = 'crit' if res.get('critical') else 'damage'
                self.apply_attack_effects(res, t)
            return res
        
        # Ability (Spell/Skill/Enemy)
        res = self.combat_engine.resolve_ability(ability_data, actor, targets, float_mgr=None if should_hold else self.float_mgr, skip_cost=not is_first)
        res['ability_name'] = ability_data.get('name', self.action_data)
        
        if is_first:
            if ability_data.get('type') == 'summon': self.handle_summon(actor, ability_data)

        dmg_map = res.get('damage_by_target', {}); heal_map = res.get('healing_by_target', {}); hits_map = res.get('hits_by_target', {})
        for t in targets:
            tid = id(t); dmg = dmg_map.get(tid, 0); hit = hits_map.get(tid, 0) > 0
            if dmg > 0: t['current_hp'] = max(0, t['current_hp'] - dmg)
            if not should_hold:
                if hit: t['flash_frames'] = 36; t['flash_type'] = 'damage'
                heal = heal_map.get(tid, res['healing'] if len(targets) == 1 else 0)
                if heal > 0: t['current_hp'] = min(t.get('max_hp_combat', t.get('max_hp', 10)), t['current_hp'] + heal)
        
        if not should_hold: self.apply_ability_effects(res, targets, actor)
        return res

    def _calculate_advantage(self, actor):
        adv = 0; conds = actor.get('conditions', {})
        if 'advantage' in conds: adv += 1
        if 'disadvantage' in conds or 'poisoned' in conds or 'blinded' in conds: adv -= 1
        return max(-1, min(1, adv))

    def _calculate_crit_range(self, actor, target):
        e_type = target.get('enemy_type', target.get('name', 'enemy').lower().replace(' ', '_'))
        rp = self.game.bestiary_rp.get(e_type, 0); crit_range = [20]
        if rp >= 100: crit_range = [17, 18, 19, 20]
        elif rp >= 60: crit_range = [18, 19, 20]
        elif rp >= 20: crit_range = [19, 20]
        if actor.get('crit_on_18'): crit_range = list(set(crit_range + [18, 19, 20]))
        elif actor.get('crit_on_19'): crit_range = list(set(crit_range + [19, 20]))
        return crit_range

    def _get_ability_data(self, actor):
        if self.pending_action == "ABILITY" and hasattr(self, '_enemy_current_action'):
            reg = self.ability_registry.get(id(actor), {})
            return reg.get(self._enemy_current_action.get('name', '').lower().replace(' ', '_')) or self._enemy_current_action.get('data')
        elif self.pending_action.startswith(("SPELL", "SKILL", "ABILITY")):
            key = self.action_data.lower().replace(" ", "_")
            data = self.ability_registry.get(id(actor), {}).get(key)
            if not data: from core.combat.combat_ai import CombatAI; data = EnemyAI.get_ability_data(key)
            return data
        return None

    def execute_action(self, actor, target):
        self.active_attacker = actor; ability_data = self._get_ability_data(actor)
        
        # Handle Items separately
        if self.pending_action.startswith("ITEM"):
            t = target[0] if isinstance(target, list) else target
            item_name = self.action_data; item_data = self.consumables_db.get(item_name.lower().replace(' ', '_'))
            res = self.combat_engine.resolve_item(item_data, t)
            t['current_hp'] = min(t.get('max_hp_combat', t.get('max_hp', 10)), t['current_hp'] + res.get('hp_gain', 0))
            if t.get('max_mp', 0) > 0: t['current_mp'] = min(t['max_mp'], t.get('current_mp', 0) + res.get('mana_gain', 0))
            if t.get('max_sp', 0) > 0: t['current_sp'] = min(t['max_sp'], t.get('current_sp', 0) + res.get('stamina_gain', 0))
            from core.players.player_inventory import remove_item
            remove_item(self.game.player['inventory_ref'], item_name.lower().replace(' ', '_'), "consumable")
            res['item_name'] = item_name; res['hit'] = True; self.phase = "CHECK_END"; return res

        # Determine Final Targets
        is_e = any(id(e) == id(actor) for e in self.enemies) or actor.get('is_enemy_summon')
        if ability_data and ability_data.get('saoe'): targets = self.get_living_players() if is_e else self.get_living_enemies()
        elif ability_data and ability_data.get('aoe') and not isinstance(target, list):
            if ability_data.get('type') == 'heal': targets = self.get_living_enemies() if is_e else self.get_living_players()
            else: targets = self.get_living_players() if is_e else self.get_living_enemies()
        else: targets = target if isinstance(target, list) else [target]

        # VFX Routing Block
        is_p_actor = any(actor is p for p in self.party) or (actor.get('is_summon') and not actor.get('is_enemy_summon'))
        start_pos = self.party_positions.get(id(actor), (0,0)) if is_p_actor else actor.get('_combat_pos', (0,0))
        start_pos = (start_pos[0] + scale_x(64), start_pos[1] + scale_y(64))

        if ability_data and ability_data.get('saoe'):
            self.vfx_mgr.play_effect(ability_data, start_pos, (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            return self._apply_combat_results(actor, targets, ability_data)
        elif ability_data and ability_data.get('aoe'):
            avg_x = sum(t['screen_pos'][0] for t in targets) / len(targets)
            avg_y = sum(t['screen_pos'][1] for t in targets) / len(targets)
            self.vfx_mgr.play_effect(ability_data, start_pos, (avg_x, avg_y))
            return self._apply_combat_results(actor, targets, ability_data)
        else:
            # Single or loop-based
            res = None
            for t in targets:
                if ability_data: self.vfx_mgr.play_effect(ability_data, start_pos, t['screen_pos'])
                res = self._apply_combat_results(actor, [t], ability_data)
            return res

    def handle_initiative(self):
        combatants = []
        for p in self.party:
            roll = random.randint(1, 20) + int(p.get("proficiency_bonus", 0)) + int(p.get("initiative_boost", 0))
            combatants.append({'actor': p, 'init': roll})
        for e in self.enemies:
            roll = random.randint(1, 20) + (int(e.get("proficiency_bonus", 0)) // 2) + int(e.get("initiative_boost", 0))
            combatants.append({'actor': e, 'init': roll})
        combatants.sort(key=lambda c: (-c['init'], c['actor'].get('current_hp', 0), c['actor'].get('name', '')))
        self.turn_order = [c['actor'] for c in combatants]; self.turn_index = 0
        self.queue_message("Turn Order: " + " > ".join([a['name'] for a in self.turn_order]))
        self.phase = "TURN_START"; self.start_next_message()

    def process_turn_start(self):
        actor = self.current_actor
        if actor['current_hp'] <= 0:
            if actor.get('is_summon') and id(actor) in self.summons:
                owner_id = actor.get('owner_id'); del self.summons[id(actor)]
                if not any(s.get('owner_id') == owner_id for s in self.summons.values()):
                    for p_o in self.party + self.enemies:
                        if id(p_o) == owner_id: p_o['summon_alive'] = False; break
            self.phase = "CHECK_END"; self.start_next_message(); return
        
        self._process_conditions(actor)

        # Start of turn resource regeneration
        if actor.get('mp'):
            actor['current_mp'] = min(actor.get('max_mp', 10), actor.get('current_mp', 0) + 1)
        if actor.get('sp'):
            actor['current_sp'] = min(actor.get('max_sp', 10), actor.get('current_sp', 0) + 1)

        is_p = any(actor is p for p in self.party); is_ps = actor.get('is_summon') and not actor.get('is_enemy_summon')
        if int(actor.get('conditions', {}).get('stunned', 0)) > 0:            self.queue_message(f"{actor['name']} is stunned!"); actor['conditions']['stunned'] -= 1
            if actor['conditions']['stunned'] <= 0: del actor['conditions']['stunned']
            self.phase = "CHECK_END"; self.start_next_message(); return
        
        actor['standby_mp'] = actor.get('current_mp', 0); actor['standby_sp'] = actor.get('current_sp', 0)
        self._register_actor_abilities(actor)
        if is_p or is_ps: self.phase = "PLAYER_TURN"; self.setup_player_menu(actor)
        else: self.phase = "ENEMY_TURN"; self.setup_enemy_turn(actor)

    def _process_conditions(self, actor):
        conds = actor.get('conditions', {})
        for c_type, msg in [('dots', 'DOT'), ('hots', 'HP')]:
            total = 0; applied = []; expired = []
            for name, (dice, dur) in conds.get(c_type, {}).items():
                val = self.combat_engine.roll_dice(dice); total += val; applied.append(name)
                if dur > 1: conds[c_type][name] = (dice, dur - 1)
                else: expired.append(name)
            if total > 0:
                if c_type == 'dots': actor['current_hp'] = max(0, actor['current_hp'] - total); actor['flash_frames'] = 36; actor['flash_type'] = 'damage'
                else: actor['current_hp'] = min(actor.get('max_hp_combat', actor.get('max_hp', 10)), actor['current_hp'] + total)
                self.queue_message(f"{actor['name']} {'took' if c_type=='dots' else 'regained'} {total} {msg} from {', '.join(applied)}.")
            for name in expired: del conds[c_type][name]
        
        expired_conds = []
        for cond, duration in conds.items():
            if cond in ['dots', 'hots', 'stunned']: continue
            if isinstance(duration, int) and duration > 0:
                conds[cond] -= 1
                if conds[cond] <= 0: expired_conds.append(cond)
            elif isinstance(duration, (list, tuple)) and len(duration) > 1:
                val, dur = duration
                if isinstance(dur, int) and dur > 0:
                    new_dur = dur - 1
                    if new_dur <= 0: expired_conds.append(cond)
                    else: conds[cond] = (val, new_dur)
        for cond in expired_conds: del conds[cond]; self.queue_message(f"{actor['name']}'s {cond.title()} effect faded.")

    def setup_player_menu(self, actor):
        opts = ["Attack"]
        if actor.get("skills"): opts.append("Skill")
        if actor.get("spells") or actor.get("class") in ["wizard", "druid", "alchemist", "sorcerer", "cleric"]: opts.append("Spell")
        opts.append("Item")
        if not actor.get('is_summon'): opts.append("Run")
        self.main_menu = Menu(opts, self.font, header=f"{actor['name']}'s Turn", pos=(400, 480))
        self.menu_state = "MAIN"; self.active_menu = self.main_menu; self.attacks_made = 0; self.ability_hits_made = 0

    def setup_enemy_turn(self, actor):
        self.attacks_made = 0; self.ability_hits_made = 0; self.pending_action = None; self.action_data = None

    def format_combat_message(self, res, actor, target):
        att_name = actor.get('name', 'Attacker'); is_aoe = isinstance(target, list); targets = target if is_aoe else [target]
        saves = res.get('saves_info', {})
        if saves:
            if not getattr(self, '_save_dialogue_phase', 0):
                dc = saves[list(saves.keys())[0]].get('dc', 10); t_name = "Party" if is_aoe else targets[0]['name']
                return f"{att_name} used {res.get('ability_name', 'Ability')} on {t_name}. Roll a {dc} or higher to make your save."
            if self._save_dialogue_phase == 1:
                msgs = []
                for t in targets:
                    info = saves.get(id(t))
                    if not info: continue
                    m = f"{t['name']} rolled a {info['roll']}. {'SAVED!' if info['success'] else 'FAILED!'}"
                    if info['success']:
                        if res.get('damage_by_target', {}).get(id(t), 0) > 0: m += " Take half damage"
                        has_eff = any(e[0] not in ['dot', 'heal_attacker', 'extra_dmg'] for e in res.get('effects', []))
                        if has_eff: m += f" and resist {res.get('effects', [['eff']])[0][0].replace('_',' ').title()}!"
                        else: m += "."
                    msgs.append(m)
                return msgs

        pre = f"{att_name} is attacking, .." if self.pending_action == "ATTACK" else f"{att_name} used {res.get('ability_name', 'Ability')}, .."
        if self.pending_action and self.pending_action.startswith("ITEM"):
            pre = f"{att_name} used {res.get('item_name', 'Item')} on {targets[0].get('name', 'Target')}, .."
            for r in ['hp', 'mana', 'stamina']:
                if res.get(f'{r}_gain', 0) > 0: return f"{pre} restoring {res[f'{r}_gain']} {r.upper().replace('MANA','MP').replace('STAMINA','SP')}."
            return f"{pre} it worked."

        if res.get('healing', 0) > 0 and res.get('damage', 0) <= 0: return f"{pre} restoring {res['healing']} HP."
        status = "CRITICAL Hit!" if res.get('critical') else ("Hit!" if res.get('hit') else "Miss.")
        body = f"{att_name} attacked with a {res['total_roll']}. {status}" if 'roll' in res else f"{att_name} attacked {targets[0]['name'] if not is_aoe else 'everyone'} and {status}"
        if res.get('hit'):
            if res.get('damage', 0) > 0: body += f", dealing {res['damage']} damage."
            from core.combat.combat_engine import get_advantage_desc
            parts = []
            for e, v in res.get('effects', []):
                subj = att_name if e.lower() in ['vex', 'swift', 'advantage', 'invisible', 'lifesteal', 'player_advantage', 'heal_attacker', 'extra_dmg', 'hot'] else (targets[0]['name'] if not is_aoe else 'everyone')
                disp = e.replace('_', ' ').title()
                if e in ['player_advantage', 'enemy_advantage']: disp, _ = get_advantage_desc(v)
                parts.append(f"{disp} applied to {subj}.")
            if parts: body += f" {' '.join(parts)}"
        return f"{pre} {body}"

    def add_status_floating_text(self, target, res):
        pos = target['screen_pos']
        for r, k in [('hp', 'hp_gain'), ('mana', 'mana_gain'), ('stamina', 'stamina_gain')]:
            if res.get(k, 0) > 0: self.float_mgr.add(f"+{res[k]} {r.upper().replace('MANA','MP').replace('STAMINA','SP')}", pos, color_key="heal" if r=='hp' else "resource")
        if res.get('healing', 0) > 0 and not res.get('hp_gain'): self.float_mgr.add(f"+{res['healing']} HP", pos, color_key="heal")
        for e, v in res.get('effects', []):
            if e in ['dot', 'heal_attacker', 'extra_dmg', 'player_advantage', 'enemy_advantage']: continue
            is_b = e.lower() in ['advantage', 'invisible', 'hot', 'shielded', 'swift', 'vex', 'lifesteal']
            self.float_mgr.add(e.upper().replace('_',' '), pos, color_key="buff" if is_b else "debuff", delay=40)

    def _spawn_projectiles(self, actor, target, res):
        is_p = any(actor is p for p in self.party) or (actor.get('is_summon') and not actor.get('is_enemy_summon'))
        start_pos = self.party_positions.get(id(actor), (0,0)) if is_p else actor.get('_combat_pos', (0,0))
        start_pos = (start_pos[0] + scale_x(64), start_pos[1] + scale_y(64))

        cls = actor.get('class', 'fighter')
        if isinstance(cls, list): cls = random.choice(cls)
        m = {'ranger': 'ranger', 'sorcerer': 'sorcerer', 'wizard': 'wizard', 'cleric': 'cleric', 'druid': 'wizard', 'paladin': 'cleric', 'warlock': 'sorcerer', 'alchemist': 'sorcerer'}
        eff = m.get(cls.lower(), 'ranger')

        targets = target if isinstance(target, list) else [target]
        for t in targets:
            is_hit = res.get('hit', True)
            if res.get('saves_info'):
                info = res['saves_info'].get(id(t))
                if info and info['success'] and res.get('damage_by_target', {}).get(id(t), 0) == 0: is_hit = False
            self.projectile_mgr.spawn(start_pos, t.get('screen_pos', (0,0)), eff, is_hit)

    def process_action_result(self, actor, target, res):
        is_p = any(actor is p for p in self.party) or (actor.get('is_summon') and not actor.get('is_enemy_summon'))
        data = self._get_ability_data(actor)
        is_physical = self.pending_action in ["ATTACK", "SKILL", "ABILITY"]
        is_ranged = data.get('ranged', False) if data else False

        if res.get('saves_info'):
            self._save_dialogue_phase = 0; self._pending_dice_result = {'actor': actor, 'target': target, 'res': res, 'is_save': True, 'is_physical': is_physical, 'is_ranged': is_ranged, 'trigger_dice_after': True}
            self.queue_message(self.format_combat_message(res, actor, target)); self.start_next_message(); return True

        msg = self.format_combat_message(res, actor, target); roll_val = res.get('roll')
        style = self.dice_anim.get_style_from_actor(actor, self.party)
        
        if is_physical:
            d_info = {'value': roll_val, 'style': style} if roll_val is not None else None
            self._pending_dice_result = {'actor': actor, 'target': target, 'res': res, 'msg': msg, 'is_physical': True}; self.juice_mgr.trigger_lunge(actor, target, res, d_info); return True

        if roll_val is not None:
            self.dice_anim.start_roll(roll_val, style); self.dice_anim.stay_settled = True
            self._pending_dice_result = {'actor': actor, 'target': target, 'res': res, 'msg': msg, 'is_physical': False, 'is_ranged': is_ranged}
            if is_ranged: self._spawn_projectiles(actor, target, res)
            return True

        if is_ranged: self._spawn_projectiles(actor, target, res)
        for t in (target if isinstance(target, list) else [target]):
            self.add_status_floating_text(t, res)
            if not is_ranged and (res.get('hit') or res.get('damage', 0) > 0): t['flash_frames'] = 36; t['flash_type'] = 'damage'
        self.queue_message(msg); return is_ranged

    def handle_enemy_turn(self):
        actor = self.current_actor; from core.combat.combat_ai import CombatAI
        if self.attacks_made == 0 and self.ability_hits_made == 0:
            action = EnemyAI.decide_action(actor, summons=self.summons.values())
            self.pending_action = "ATTACK" if action['type'] == 'attack' else "ABILITY"; self.action_data = action.get('name') if action['type'] == 'ability' else None; self._enemy_current_action = action
        else: action = self._enemy_current_action
        ps = self.get_living_players()
        if action['type'] == 'ability':
            if action['data'].get('type') == 'heal': targets = [actor]
            elif action['data'].get('saoe') or action['data'].get('aoe'): targets = ps
            else:
                t = EnemyAI.pick_target(actor, ps, action['data'])
                if not t: self.phase = "CHECK_END"; return
                targets = [t]
        else:
            t = EnemyAI.pick_target(actor, ps)
            if not t: self.phase = "CHECK_END"; return
            targets = [t]

        multi = action.get('data', {}).get('saoe') or action.get('data', {}).get('aoe')
        t_obj = targets if multi else targets[0]; res = self.execute_action(actor, t_obj); is_anim = self.process_action_result(actor, t_obj, res)

        should_end = True
        mx = int(actor.get('attack_count', 1))
        if any(p['current_hp'] > 0 for p in ps):
            if action['type'] == 'attack':
                self.attacks_made += 1
                if self.attacks_made < mx: should_end = False
            elif action['type'] == 'ability' and action['data'].get('use_attack_count'):
                self.ability_hits_made += 1
                if self.ability_hits_made < mx: should_end = False

        if should_end:
            if self.original_attack_count is not None: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
        else:
            self.phase = "ENEMY_TURN"
        if not is_anim: self.start_next_message()
    def apply_ability_effects(self, res, targets, actor=None):
        failed = res.get('failed_saves_by_target', {}); name = res.get('ability_name', 'Ability').title(); src = actor if actor else self.current_actor
        for eff, val in res['effects']:
            for t in targets:
                if failed.get(id(t), 0) > 0 or not res.get('saves_info'):
                    if eff == 'stunned': t['conditions']['stunned'] = val
                    elif eff == 'taunted': t['conditions']['taunted'] = (id(src), val)
                    elif eff == 'dot':
                        if 'dots' not in t['conditions']: t['conditions']['dots'] = {}
                        t['conditions']['dots'][name] = val
                    elif eff == 'hot':
                        if 'hots' not in t['conditions']: t['conditions']['hots'] = {}
                        t['conditions']['hots'][name] = val
                    elif eff == 'heal_attacker':
                        mx = src.get('max_hp_combat', src.get('max_hp', 10)); src['current_hp'] = min(mx, src['current_hp'] + val)

    def apply_attack_effects(self, res, target):
        for eff, val in res['effects']:
            if eff == 'stunned': target['conditions']['stunned'] = val
            elif eff == 'poisoned': target['conditions']['poisoned'] = val
            elif eff == 'vex': self.current_actor['conditions']['advantage'] = val
            elif eff == 'sap': target['conditions']['disadvantage'] = val
            elif eff == 'dot':
                if 'dots' not in target['conditions']: target['conditions']['dots'] = {}
                n = self.current_actor.get('weapon', 'Poison'); target['conditions']['dots'][n] = val
            elif eff == 'heal_attacker':
                mx = self.current_actor.get('max_hp_combat', self.current_actor.get('max_hp', 10)); self.current_actor['current_hp'] = min(mx, self.current_actor['current_hp'] + val)

    def start_targeting(self, action_type, data=None):
        self.pending_action = action_type; self.action_data = data
        if action_type.endswith("_FRIENDLY"): opts = [t['name'] for t in self.get_living_players()]
        else:
            opts = [f"{i+1}. {e['name']}" for i, e in enumerate(self.enemies) if e['current_hp'] > 0]
            opts += [f"S. {s['name']}" for s in self.summons.values() if s.get('is_enemy_summon') and s['current_hp'] > 0]
        if not opts: self.queue_message("No targets!"); self.phase = "CHECK_END"; self.start_next_message(); return
        self.menu_manager.open_target_menu(opts); self.menu_state = "TARGETING"

    def handle_spell_menu(self, option):
        actor = self.current_actor; key = option.lower().replace(" ", "_"); data = self.ability_registry.get(id(actor), {}).get(key)
        if not data: from core.combat.combat_ai import CombatAI; data = EnemyAI.get_ability_data(key)
        if actor.get('current_mp', 0) < data.get("cost", 0): self.queue_message("Not enough MP!"); self.start_next_message(); return
        if data.get('saoe'):
            ts = self.get_living_enemies(); self.pending_action = "SPELL"; self.action_data = option; res = self.execute_action(actor, ts); is_anim = self.process_action_result(actor, ts, res)
            if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
            if not is_anim: self.start_next_message()
        elif data.get('aoe'):
            self.pending_action = "SPELL"; self.action_data = option
            self.menu_manager.open_column_menu(); self.menu_state = "TARGET_COLUMN"
        elif data.get('type') == 'summon':
            ts = self.get_living_players(); self.pending_action = "SPELL"; self.action_data = option; res = self.execute_action(actor, ts); is_anim = self.process_action_result(actor, ts, res)
            if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
            if not is_anim: self.start_next_message()
        elif data.get('type') == 'heal': self.start_targeting("SPELL_FRIENDLY", option)
        else: self.start_targeting("SPELL", option)

    def handle_skill_menu(self, option):
        actor = self.current_actor; key = option.lower().replace(" ", "_"); data = self.ability_registry.get(id(actor), {}).get(key)
        if not data: from core.combat.combat_ai import CombatAI; data = EnemyAI.get_ability_data(key)
        if actor.get('current_sp', 0) < data.get("cost", 0): self.queue_message("Not enough SP!"); self.start_next_message(); return
        if data.get('saoe'):
            ts = self.get_living_enemies(); self.pending_action = "SKILL"; self.action_data = option; res = self.execute_action(actor, ts); is_anim = self.process_action_result(actor, ts, res)
            if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
            if not is_anim: self.start_next_message()
        elif data.get('aoe'):
            self.pending_action = "SKILL"; self.action_data = option
            self.menu_manager.open_column_menu(); self.menu_state = "TARGET_COLUMN"
        elif data.get('type') == 'summon':
            ts = self.get_living_players(); self.pending_action = "SKILL"; self.action_data = option; res = self.execute_action(actor, ts); is_anim = self.process_action_result(actor, ts, res)
            if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
            if not is_anim: self.start_next_message()
        elif data.get('type') == 'heal': self.start_targeting("SKILL_FRIENDLY", option)
        else: self.start_targeting("SKILL", option)

    def handle_item_menu(self, option):
        self.start_targeting("ITEM_FRIENDLY", option.split(" (x")[0])

    def handle_targeting(self, option):
        actor = self.current_actor; target = None
        if self.pending_action.endswith("_FRIENDLY"): target = next(t for t in self.get_living_players() if t['name'] == option)
        elif option.startswith("S. "): target = next(s for s in self.summons.values() if s['name'] == option[3:])
        else: target = self.enemies[int(option.split(".")[0]) - 1]
        res = self.execute_action(actor, target); is_anim = self.process_action_result(actor, target, res)
        end = True; mx = int(actor.get('attack_count', 1))
        if any(e['current_hp'] > 0 for e in self.get_living_enemies()):
            if self.pending_action == "ATTACK":
                self.attacks_made += 1
                if self.attacks_made < mx: end = False
            elif self.pending_action.startswith(("SPELL", "SKILL")):
                reg = self.ability_registry.get(id(actor), {})
                if reg.get(self.action_data.lower().replace(" ", "_"), {}).get('use_attack_count'):
                    self.ability_hits_made += 1
                    if self.ability_hits_made < mx: end = False
        if end:
            if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
            if not is_anim: self.start_next_message(); self.check_combat_end()
        else:
            if is_anim: self._pending_dice_followup = lambda: self.start_targeting(self.pending_action, self.action_data)
            else: self.start_next_message(); self.start_targeting(self.pending_action, self.action_data)

    def next_turn(self):
        self.turn_index += 1
        if self.turn_index >= len(self.turn_order): self.turn_index = 0; self.round_number += 1
        self.phase = "TURN_START"

    def get_next_living_actor(self):
        for i in range(1, len(self.turn_order) + 1):
            a = self.turn_order[(self.turn_index + i) % len(self.turn_order)]
            if a.get('current_hp', 0) > 0: return a
        return None

    def check_combat_end(self):
        from core.players.player_inventory import add_item
        dead = [p for p in self.party if p.get('current_hp', 0) <= 0 and not p.get('is_summon')]
        for p in dead:
            if self.party.index(p) == 0: continue
            self.queue_message(f"{p['name']} has fallen!"); rec = []
            for s in ['weapon', 'armor', 'shield', 'trinket']:
                item = p.get(s); 
                if item: add_item(self.game.inventory, item, s if s!='trinket' else 'trinket'); rec.append(item.replace('_',' ').title())
            if rec: self.queue_message(f"Recovered: {', '.join(rec)}")
            self.party.remove(p)
            if p in self.turn_order: self.turn_order.remove(p)
        if not self.get_living_enemies(): self.queue_message("Victory!"); self.phase = "RESOLVE_VICTORY"
        elif not self.get_living_players(): self.queue_message("Defeat..."); self.phase = "END_COMBAT"
        else: self.next_turn()
        self.start_next_message()

    def handle_victory(self):
        cc = self.game.consecutive_combats; bonus = 1.0 + min(0.5, (cc-1)*0.1) if cc > 1 else 1.0
        if cc > 1: self.queue_message(f"CC #{cc}! Bonus: {int((bonus-1)*100)}%")
        total_xp = int(sum(e.get("xp", 0) for e in self.enemies) * bonus); xp_per = total_xp // len(self.party) if self.party else 0
        from core.players.leveler import update_xp_and_level
        levelup_p = None
        for p in self.party: 
            if update_xp_and_level(p, xp_per): 
                if levelup_p is None: levelup_p = p
        if xp_per > 0: self.queue_message(f"Each party member gained {xp_per} XP!")
        
        party_lvl = sum(p.get('level', 1) for p in self.party); rp = 1 if party_lvl < 41 else (2 if party_lvl < 51 else 3)
        for enemy in self.enemies:
            if enemy.get('current_hp', 0) <= 0:
                et = enemy.get('enemy_type', enemy.get('name', 'enemy').lower().replace(' ', '_'))
                self.game.bestiary_rp[et] = self.game.bestiary_rp.get(et, 0) + rp
        self.process_loot(bonus)
        if levelup_p: self.queue_message("LEVEL UP!"); self.phase = "LEVEL_UP"; self._levelup_starter = levelup_p
        else: self.phase = "END_COMBAT"

    def handle_victory(self, bonus=1.0):
        from core.players.player_inventory import add_item
        loot = self.combat_engine.generate_loot(self.enemies); inv = self.game.inventory
        loot_gold = int(loot['gold'] * bonus); inv['gold'] = inv.get('gold', 0) + loot_gold

        # Cleanse party effects
        from core.combat.combat_resolver import CombatResolver
        CombatResolver.cleanse_party(self.party)

        cc = self.game.consecutive_combats
        if cc >= 3: 
            p = random.choice(["healing_potion", "mana_potion", "stamina_potion"]); add_item(inv, p, "consumable"); self.queue_message(f"CC Reward: {p.replace('_',' ').title()}!")
        if cc >= 4: add_item(inv, "grind_stone", "consumable"); self.queue_message("CC Reward: Grind Stone!")
        if cc >= 6:
            max_v = sum(e.get('level', 1) for e in self.enemies) * 50
            try:
                path = get_resource_path(os.path.join('data', 'items', 'junk.json'))
                with open(path, 'r') as f: db = json.load(f).get('junk_list', {})
                valid = [k for k, v in db.items() if v.get('cost', 0) <= max_v]
                if valid: j = random.choice(valid); add_item(inv, j, "junk"); self.queue_message(f"CC Reward: {j.replace('_',' ').title()}!")
            except: pass
        for t, n in loot['items']: add_item(inv, n, t)
        if loot_gold > 0: self.queue_message(f"Gained {loot_gold} gold!")
        for m in loot['messages']: self.queue_message(m)

    def exit_to_hub(self):
        # Cleanse party effects before leaving
        from core.combat.combat_resolver import CombatResolver
        CombatResolver.cleanse_party(self.party)

        for p in self.party: validate_player_data(p)
        if all(p['current_hp'] <= 0 for p in self.party):
            from states.game_over import GameOverState
            self.game.change_state(GameOverState(self.game, self.font))
        else:
            from .hub import HubState
            self.game.change_state(HubState(self.game, self.font))

    def queue_message(self, text):
        if isinstance(text, list): self.message_queue.extend(text)
        else: self.message_queue.append(text)

    def start_next_message(self, skip_typing=False):
        if self.message_queue:
            msg = self.message_queue.pop(0)
            if isinstance(msg, list): self.message_queue = msg[1:] + self.message_queue; msg = msg[0]
            self.dialogue.set_messages(str(msg), skip_typing=skip_typing)

    def handle_target_column(self, option):
        if option == "Back": self.menu_state = "MAIN"; self.active_menu = self.main_menu
        else:
            col = int(option.split(" ")[1]) - 1; actor = self.current_actor
            targets = [e for e in self.get_living_enemies() if e.get('_combat_column') == col]
            if not targets: self.queue_message(f"No enemies in Column {col+1}!"); self.start_next_message(); return
            res = self.execute_action(actor, targets); is_anim = self.process_action_result(actor, targets, res)
            if self.original_attack_count: actor['attack_count'] = self.original_attack_count; self.original_attack_count = None
            self.phase = "CHECK_END"
            if not is_anim: self.start_next_message()

    def draw(self, screen):
        screen.blit(self.background, (0, 0))
        from ui.panel import draw_text_outlined
        from core.game_rules.constants import COLOR_WHITE, COLOR_GOLD, COLOR_BLUE, COLOR_YELLOW
        
        if self.phase == "PLAYER_TURN" and self.menu_state == "TARGET_COLUMN":
            pulse = (math.sin(pygame.time.get_ticks() * 0.005) + 1) / 2; alpha = int(50 + pulse * 100)
            sel = self.active_menu.selected
            if sel < 3:
                tx = self.column_x[sel]; r = pygame.Rect(tx - scale_x(10), scale_y(50), scale_x(140), SCREEN_HEIGHT - scale_y(100))
                ov = pygame.Surface((r.width, r.height), pygame.SRCALPHA); ov.fill((255, 255, 0, alpha)); screen.blit(ov, r.topleft)

        draw_text_outlined(screen, f"Round: {self.round_number}", self.font, COLOR_WHITE, scale_x(20), scale_y(20))
        draw_text_outlined(screen, f"Active: {self.current_actor['name'] if self.current_actor else 'None'}", self.font, COLOR_GOLD, scale_x(20), scale_y(45))
        next_a = self.get_next_living_actor(); draw_text_outlined(screen, f"Next: {next_a['name'] if next_a else 'None'}", self.font, COLOR_WHITE, scale_x(20), scale_y(70))
        
        # Draw Actors
        for p in sorted(self.party, key=lambda p: self.party_positions[id(p)][1]):
            bx, by = self.party_positions[id(p)]; dx = bx + (self.attacker_offset if self.active_attacker is p else (self.target_offset_x if self.active_target is p else 0)); dy = by + (self.attacker_offset_y if self.active_attacker is p else 0)
            s = SpriteManager.get_player_sprite(p.get('class', 'fighter'), size=(scale_x(128), scale_y(128)))
            if p['current_hp'] <= 0: s = s.copy(); s.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif p.get('flash_frames', 0) > 0: s = self.apply_flash_effect(s, p['flash_frames'], p.get('flash_type', 'damage'))
            screen.blit(s, (dx, dy))

        for summon in self.summons.values():
            if summon['current_hp'] <= 0: continue
            bx, by = self.party_positions[id(summon)]; dx = bx + (self.attacker_offset if self.active_attacker is summon else (self.target_offset_x if self.active_target is summon else 0)); dy = by + (self.attacker_offset_y if self.active_attacker is summon else 0)
            sz = (scale_x(100), scale_y(100)); cat = summon.get('sprite_category', "humanoid")
            if cat == "player": s = SpriteManager.get_player_sprite(summon.get('sprite_filename', "").replace(".png", ""), size=sz)
            elif "enemies" in summon.get('sprite_folder', "") and "summons" not in summon.get('sprite_folder', ""):
                s = SpriteManager.get_enemy_sprite(summon, size=sz)
            else:
                try: path = get_resource_path(os.path.join(summon.get('sprite_folder', ""), summon.get('sprite_filename', ""))); s = pygame.image.load(path).convert_alpha(); s = pygame.transform.scale(s, sz)
                except: s = pygame.Surface(sz, pygame.SRCALPHA); c = (200, 100, 100) if summon.get('is_enemy_summon') else (100, 100, 200); pygame.draw.circle(s, c, (sz[0]//2, sz[1]//2), sz[0]//3)
            if summon.get('flash_frames', 0) > 0: s = self.apply_flash_effect(s, summon['flash_frames'], summon.get('flash_type', 'damage'))
            screen.blit(s, (dx, dy))

        for e in self.enemies:
            ex, ey = e.get('_combat_pos', (0, 0)); dx = ex + (self.attacker_offset if self.active_attacker is e else (self.target_offset_x if self.active_target is e else 0)); dy = ey + (self.attacker_offset_y if self.active_attacker is e else 0)
            sz = int(125 * 1.3 if e.get('is_leader') else 125); s = SpriteManager.get_enemy_sprite(e, size=(scale_x(sz), scale_y(sz)))
            if e["current_hp"] <= 0: s = s.copy(); s.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif e.get('flash_frames', 0) > 0: s = self.apply_flash_effect(s, e['flash_frames'], e.get('flash_type', 'damage'))
            screen.blit(s, (dx, dy))

        # Bars
        hovered = self._get_hovered_target()
        for p in self.party:
            bx, by = self.party_positions[id(p)]; dx = bx + (self.attacker_offset if self.active_attacker is p else (self.target_offset_x if self.active_target is p else 0)); bx, by = dx + scale_x(10), by - scale_y(30)
            draw_bar(screen, bx, by, scale_x(100), scale_y(15), p['current_hp'], p.get('max_hp_combat', 10), (200, 50, 50), self.font)
            cy = by + scale_y(18)
            if p.get('mp') and p.get('max_mp', 0) > 0: draw_bar(screen, bx, cy, scale_x(100), scale_y(10), p.get('current_mp', 0), p['max_mp'], COLOR_BLUE, self.font); cy += scale_y(12)
            if p.get('sp') and p.get('max_sp', 0) > 0: draw_bar(screen, bx, cy, scale_x(100), scale_y(10), p.get('current_sp', 0), p['max_sp'], COLOR_YELLOW, self.font)
            if self.current_actor is p: pygame.draw.polygon(screen, (255, 255, 0), [(bx+scale_x(40), by-scale_y(10)), (bx+scale_x(60), by-scale_y(10)), (bx+scale_x(50), by)])

        for summon in self.summons.values():
            if summon['current_hp'] <= 0: continue
            bx, by = self.party_positions[id(summon)]; dx = bx + (self.attacker_offset if self.active_attacker is summon else (self.target_offset_x if self.active_target is summon else 0)); bx, by = dx + scale_x(10), by - scale_y(25)
            draw_bar(screen, bx, by, scale_x(80), scale_y(10), summon['current_hp'], summon['max_hp'], (200, 50, 50), self.font); cy = by + scale_y(12)
            if summon.get('mp') and summon.get('max_mp', 0) > 0: draw_bar(screen, bx, cy, scale_x(80), scale_y(8), summon.get('current_mp', 0), summon['max_mp'], COLOR_BLUE, self.font); cy += scale_y(10)
            if summon.get('sp') and summon.get('max_sp', 0) > 0: draw_bar(screen, bx, cy, scale_x(80), scale_y(8), summon.get('current_sp', 0), summon['max_sp'], COLOR_YELLOW, self.font)
            if self.current_actor is summon: pygame.draw.polygon(screen, (255, 255, 0), [(bx+scale_x(30), by-scale_y(10)), (bx+scale_x(50), by-scale_y(10)), (bx+scale_x(40), by)])

        for e in self.enemies:
            ex, ey = e.get('_combat_pos', (0, 0)); dx = ex + (self.attacker_offset if self.active_attacker is e else (self.target_offset_x if self.active_target is e else 0)); dy = ey + (self.attacker_offset_y if self.active_attacker is e else 0)
            sz = int(125 * 1.3 if e.get('is_leader') else 125); bw = scale_x(80); bx = dx + (scale_x(sz) - bw) // 2; by = dy + scale_y(sz) + scale_y(5); alpha = 255 if (hovered is e or self.active_target is e) else 100
            et = e.get('enemy_type', e.get('name', 'enemy').lower().replace(' ', '_')); show = self.game.bestiary_rp.get(et, 0) >= 1
            draw_bar(screen, bx, by, bw, scale_y(10), e["current_hp"], e["max_hp"], (200, 50, 50), self.font, show_numbers=show, alpha=alpha); cy = by
            if e.get('max_mp', 0) > 0 and e.get('mp'): cy += scale_y(12); draw_bar(screen, bx, cy, bw, scale_y(8), e.get('current_mp', 0), e['max_mp'], COLOR_BLUE, self.font, alpha=alpha)
            if e.get('max_sp', 0) > 0 and e.get('sp'): cy += scale_y(10); draw_bar(screen, bx, cy, bw, scale_y(8), e.get('current_sp', 0), e['max_sp'], COLOR_YELLOW, self.font, alpha=alpha)
            if self.current_actor is e: cx = bx + bw // 2; ty = by - scale_y(5); pygame.draw.polygon(screen, (255, 255, 0), [(cx-scale_x(10), ty-scale_y(10)), (cx+scale_x(10), ty-scale_y(10)), (cx, ty)])

        if self.phase == "PLAYER_TURN" and not self.dialogue.current_message:
            if self.menu_state == "TARGETING" and self.active_menu and hovered:
                tx, ty = hovered['screen_pos']; b = math.sin(pygame.time.get_ticks() * 0.01) * scale_y(10); ay = ty - scale_y(80) + b; pts = [(tx-scale_x(10), ay), (tx+scale_x(10), ay), (tx, ay+scale_y(20))]
                pygame.draw.polygon(screen, COLOR_GOLD, pts); pygame.draw.polygon(screen, COLOR_WHITE, pts, 2)
            if self.active_menu: self.active_menu.draw(screen, 400, 500)
        self.dialogue.draw(screen); self.float_mgr.draw(screen); self.dice_anim.draw(screen); self.projectile_mgr.draw(screen); self.vfx_mgr.draw(screen)

    def _get_hovered_target(self):
        if self.phase == "PLAYER_TURN" and not self.dialogue.current_message and self.menu_state == "TARGETING" and self.active_menu:
            sel = self.active_menu.selected
            if sel < len(self.active_menu.options) and self.active_menu.options[sel] != "Back":
                opt = self.active_menu.options[sel]
                if self.pending_action.endswith("_FRIENDLY"): return next((p for p in self.party if p['name'] == opt), None)
                elif opt.startswith("S. "): return next((s for s in self.summons.values() if s['name'] == opt[3:]), None)
                else: 
                    try: return self.enemies[int(opt.split(".")[0]) - 1]
                    except: pass
        return None

    def apply_flash_effect(self, sprite, frames, flash_type):
        new_s = sprite.copy()
        if flash_type == 'damage' and (frames // 6) % 2 == 1:
            try: return pygame.transform.grayscale(new_s)
            except: new_s.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
        elif flash_type == 'crit':
            cyc = (frames // 4) % 3
            if cyc == 1:
                try: return pygame.transform.grayscale(new_s)
                except: new_s.fill((100, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif cyc == 2: new_s.fill((255, 100, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return new_s
