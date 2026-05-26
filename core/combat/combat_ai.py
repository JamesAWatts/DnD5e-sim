import json
import os
import random
from core.game_rules.path_utils import get_resource_path

class CombatAI:
    _skills_cache = None
    _spells_cache = None
    _enemy_abilities_cache = None

    @classmethod
    def _load_data(cls):
        if cls._skills_cache is not None:
            return

        # Load Player Skills (shared)
        skills_path = get_resource_path(os.path.join('data', 'combat', 'skills.json'))
        with open(skills_path, 'r', encoding='utf-8-sig') as f:
            cls._skills_cache = json.load(f).get('skill_list', {})

        # Load Player Spells (shared)
        spells_path = get_resource_path(os.path.join('data', 'combat', 'spells.json'))
        with open(spells_path, 'r', encoding='utf-8-sig') as f:
            cls._spells_cache = json.load(f).get('spell_list', {})

        # Load Exclusive Enemy Abilities
        enemy_path = get_resource_path(os.path.join('data', 'combat', 'enemy_abilities.json'))
        with open(enemy_path, 'r', encoding='utf-8-sig') as f:
            cls._enemy_abilities_cache = json.load(f).get('ability_list', {})

    @classmethod
    def get_ability_data(cls, name):
        cls._load_data()
        
        # Normalize name for lookup
        lookup_name = name.lower().replace(" ", "_")
        
        # Check all three caches
        if lookup_name in cls._enemy_abilities_cache:
            return cls._enemy_abilities_cache[lookup_name]
        if lookup_name in cls._skills_cache:
            return cls._skills_cache[lookup_name]
        if lookup_name in cls._spells_cache:
            return cls._spells_cache[lookup_name]
            
        # Try raw name as fallback
        if name in cls._enemy_abilities_cache: return cls._enemy_abilities_cache[name]
        if name in cls._skills_cache: return cls._skills_cache[name]
        if name in cls._spells_cache: return cls._spells_cache[name]
        
        return None

    @classmethod
    def decide_action(cls, enemy, summons=None):
        """
        Reorganized AI Logic (Phased):
        PHASE 2: HP CHECK
        PHASE 3: HEAL (If Phase 2 is True)
        PHASE 4: SUMMON (If Phase 3 is False or not performed)
        PHASE 5: PLAN (Ignore summons here)
        PHASE 6: ACTION - Execute plan if affordable, else attack
        """
        current_hp = enemy.get('current_hp', 0)
        max_hp = enemy.get('max_hp', 1)
        heal_available = enemy.get('heal_available', True)
        
        # Prepare context for cost resolution
        from core.combat.combat_engine import CombatEngine
        prof = int(enemy.get('proficiency_bonus', 2))
        total_level = sum(enemy.get('class_levels', {}).values()) if enemy.get('class_levels') else enemy.get('level', 1)
        
        # Snapshot-aware resource values
        mp_val = int(enemy.get('standby_mp', enemy.get('current_mp', 0)))
        sp_val = int(enemy.get('standby_sp', enemy.get('current_sp', 0)))
        placeholders = {
            "{damage_die}": str(enemy.get('damage_die', enemy.get('die', 4))),
            "{level}": str(total_level),
            "{level/2}": str(total_level // 2),
            "{level/3}": str(total_level // 3),
            "{level/4}": str(total_level // 4),
            "{level/5}": str(total_level // 5),
            "{level2}": str(total_level // 2),
            "{prof}": str(prof),
            "{prof/2}": str(prof // 2),
            "{prof/3}": str(prof // 3),
            "{prof/4}": str(prof // 4),
            "{current_mp}": str(mp_val),
            "{current_mp/2}": str(mp_val // 2),
            "{current_sp}": str(sp_val),
            "{current_sp/2}": str(sp_val // 2)
        }

        def resolve_cost(raw_cost):
            if raw_cost is None: return 0
            try:
                resolved = CombatEngine._resolve_math(str(raw_cost), placeholders)
                if any(op in resolved for op in "+-*/"):
                    return int(eval(resolved))
                return int(resolved)
            except:
                return int(raw_cost) if str(raw_cost).isdigit() else 0

        # Helper to get best representative from a pool
        def get_best_in_pool(names, is_spell=False):
            best = None
            min_needed = 999
            for name in names:
                data = cls.get_ability_data(name)
                # Ignore heal and summon types in the general PLAN PHASE
                if not data or data.get('type') in ['heal', 'summon']: continue
                
                raw_cost = data.get('cost', 0)
                cost = resolve_cost(raw_cost)
                res_type = 'mp' if is_spell else 'sp'
                needed = max(0, cost - enemy.get(f'current_{res_type}', 0))
                
                if needed < min_needed:
                    min_needed = needed
                    best = {'name': name, 'data': data, 'cost': cost, 'needed': needed}
                elif needed == min_needed and best:
                    if cost > best['cost']:
                        best = {'name': name, 'data': data, 'cost': cost, 'needed': needed}
            return best

        best_skill = get_best_in_pool(enemy.get('skills', []), is_spell=False)
        best_spell = get_best_in_pool(enemy.get('spells', []), is_spell=True)

        # PHASE 2: HP CHECK
        should_heal = heal_available and current_hp <= (max_hp // 2)

        # PHASE 3: HEAL
        if should_heal:
            # Try to find a heal ability
            all_names = enemy.get('skills', []) + enemy.get('spells', [])
            heal_ability = None
            for name in all_names:
                data = cls.get_ability_data(name)
                if data and data.get('type') == 'heal':
                    heal_ability = {'name': name, 'data': data}
                    break
            
            if heal_ability:
                raw_cost = heal_ability['data'].get('cost', 0)
                cost = resolve_cost(raw_cost)
                res_type = heal_ability['data'].get('resource', 'mp')
                if enemy.get(f'current_{res_type}', 0) >= cost:
                    enemy['heal_available'] = False
                    return {'type': 'ability', 'name': heal_ability['name'], 'data': heal_ability['data']}
            
            # ELSE attack (if no heal found or can't afford)
            return {'type': 'attack'}

        # PHASE 4: SUMMON
        all_names = enemy.get('skills', []) + enemy.get('spells', [])
        summon_ability = None
        for name in all_names:
            data = cls.get_ability_data(name)
            if data and data.get('type') == 'summon':
                summon_ability = {'name': name, 'data': data}
                break
        
        if summon_ability:
            # Robust check for active summons belonging to this enemy
            is_summon_active = False
            if summons is not None:
                # Check if any alive summon belongs to this actor instance
                actor_id = id(enemy)
                is_summon_active = any(s.get('owner_id') == actor_id and s.get('current_hp', 0) > 0 for s in summons)
            else:
                # Fallback to internal flag if state not provided
                is_summon_active = enemy.get('summon_alive', False)

            if not is_summon_active:
                raw_cost = summon_ability['data'].get('cost', 0)
                cost = resolve_cost(raw_cost)
                res_type = summon_ability['data'].get('resource', 'sp') # Default to SP for summons usually
                # If current_res >= cost, set as plan and move to ACTION
                if enemy.get(f'current_{res_type}', 0) >= cost:
                    return {'type': 'ability', 'name': summon_ability['name'], 'data': summon_ability['data']}
                # Else move to PLAN (fall through)
        
        # PHASE 5: PLAN
        plan_type = None # 'skill' or 'spell'
        if best_skill and not best_spell: 
            plan_type = 'skill'
        elif best_spell and not best_skill: 
            plan_type = 'spell'
        elif best_skill and best_spell:
            sp_needed = best_skill['needed']
            mp_needed = best_spell['needed']
            
            if sp_needed < mp_needed:
                plan_type = 'skill'
            elif sp_needed > mp_needed:
                plan_type = 'spell'
            else:
                # Tie in resources needed: choose higher base cost
                sp_cost = best_skill['cost']
                mp_cost = best_spell['cost']
                if sp_cost > mp_cost:
                    plan_type = 'skill'
                elif sp_cost < mp_cost:
                    plan_type = 'spell'
                else:
                    # Absolute tie: coin toss
                    plan_type = 'skill' if random.randint(0, 1) == 0 else 'spell'

        # PHASE 6: ACTION
        if plan_type == 'skill':
            current_sp = enemy.get('current_sp', 0)
            cost = best_skill['cost']
            if current_sp >= cost:
                print(f"[AI] {enemy.get('name')} executing skill '{best_skill['name']}'")
                return {'type': 'ability', 'name': best_skill['name'], 'data': best_skill['data']}
            else:
                print(f"[AI] {enemy.get('name')} saving for skill '{best_skill['name']}' (Need {cost}, have {current_sp})")
                return {'type': 'attack'}
        elif plan_type == 'spell':
            current_mp = enemy.get('current_mp', 0)
            cost = best_spell['cost']
            if current_mp >= cost:
                print(f"[AI] {enemy.get('name')} executing spell '{best_spell['name']}'")
                return {'type': 'ability', 'name': best_spell['name'], 'data': best_spell['data']}
            else:
                print(f"[AI] {enemy.get('name')} saving for spell '{best_spell['name']}' (Need {cost}, have {current_mp})")
                return {'type': 'attack'}
        else:
            # Catch all for when a creature has no spell or skill
            # print(f"[AI] {enemy.get('name')} has no valid skills/spells plan, defaulting to attack.")
            return {'type': 'attack'}


    @classmethod
    def pick_target(cls, actor, targets, ability_data=None):
        """
        Picks a target from the provided list of targets (usually players + summons).
        Prioritizes:
        1. Taunter (if taunted)
        2. Low HP targets (if it's an attack/debuff)
        3. Random (fallback)
        """
        alive_targets = [t for t in targets if t.get('current_hp', 0) > 0]
        if not alive_targets:
            return None

        # 1. Check for Taunt
        if 'taunted' in actor.get('conditions', {}):
            taunter_id, _ = actor['conditions']['taunted']
            taunter = next((t for t in alive_targets if id(t) == taunter_id), None)
            if taunter:
                return taunter

        # 2. Logic-based selection
        # Priority: lowest HP percentage
        sorted_by_hp = sorted(alive_targets, key=lambda t: t.get('current_hp', 0) / max(1, t.get('max_hp', 1)))
        
        # 30% chance to be "smart" and target the weakest
        if random.random() < 0.3:
            return sorted_by_hp[0]
            
        return random.choice(alive_targets)
