import random
import json
import os
from .attack_roller import attack_roll, damage_roll, roll_dice, roll_d20

# Load combat effects for descriptions
EFFECTS_DATA = {}
try:
    # Adjust path to reach data/combat/combat_effects.json from core/combat/
    effects_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'combat', 'combat_effects.json')
    if os.path.exists(effects_path):
        with open(effects_path, 'r') as f:
            EFFECTS_DATA = json.load(f)
except Exception:
    pass

def get_effect_desc(effect_name):
    effect_name = effect_name.lower()
    # Check Conditions first
    conds = EFFECTS_DATA.get("Conditions", {})
    if effect_name in conds:
        return conds[effect_name]
    # Check Weapon effects
    weap = EFFECTS_DATA.get("Weapon_effefts", {}) # Note: typo in JSON 'Weapon_effefts'       
    if effect_name in weap:
        return weap[effect_name]
    return ""

def get_advantage_desc(power):
    """Returns (type, duration_desc) for advantage/disadvantage."""
    duration = abs(int(power))
    adv_type = "Advantage" if int(power) > 0 else "Disadvantage"
    return adv_type, f"for {duration} round{'s' if duration > 1 else ''}"

class CombatEngine:
    @staticmethod
    def get_total_attack_bonus(actor):
        """Calculates total attack bonus: Proficiency + Weapon + Equipment + Feast."""
        prof = int(actor.get('proficiency_bonus', 0))
        w_bonus = int(actor.get('weapon_bonus', 0))
        eq_atk = int(actor.get('equipment_atk_bonus', 0))
        f_bonus = int(actor.get('feast_bonus', 0))
        return prof + w_bonus + eq_atk + f_bonus

    @staticmethod
    def get_attack_advantage(attacker, target):
        """Consolidates advantage/disadvantage logic based on conditions and status."""
        adv = 0
        a_conds = attacker.get('conditions', {})
        t_conds = target.get('conditions', {})
        
        if 'advantage' in a_conds: adv += 1
        if 'disadvantage' in a_conds: adv -= 1
        if 'blind' in a_conds: adv -= 1
        if 'blind' in t_conds: adv += 1
        
        if 'frightened' in a_conds:
            source_id, _ = a_conds['frightened']
            if id(target) == source_id: adv -= 1
            
        if 'advantage_next' in t_conds:
            adv += 1
            
        return adv

    @staticmethod
    def resolve_action(actor, action_data, target_list, crit_range=[20]):
        """
        Pure data-focused action resolution with accuracy and damage math.
        """
        if not action_data or not target_list:
            return []

        results = []
        
        # 1. Prepare Placeholders
        prof = int(actor.get('proficiency_bonus', 0))
        total_level = sum(actor.get('class_levels', {}).values()) if actor.get('class_levels') else actor.get('level', 1)
        
        placeholders = {
            "{damage_die}": str(actor.get('damage_die', actor.get('die', 4))),
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
        }

        # 2. Determine base formulas
        a_type = action_data.get('type', 'attack')
        if a_type == 'heal':
            damage_formula = action_data.get('damage', 0)
            healing_formula = action_data.get('healing', action_data.get('dice', 0))
        else:
            damage_formula = action_data.get('damage', action_data.get('dice', 0))
            healing_formula = action_data.get('healing', 0)

        mana_gain_formula = action_data.get('mana_gain', 0)
        stamina_gain_formula = action_data.get('stamina_gain', 0)
        bonus_gain_formula = action_data.get('bonus_gain', 0)
        attack_gain_formula = action_data.get('attack_gain', 0)

        # 3. Deduct Cost
        cost_raw = action_data.get('cost', 0)
        cost = 0
        if cost_raw:
            try:
                resolved_cost = CombatEngine._resolve_math(str(cost_raw), placeholders)
                cost = int(eval(resolved_cost, {"__builtins__": None}, {})) if any(op in resolved_cost for op in "+-*/") else int(resolved_cost)
            except:
                cost = int(cost_raw) if str(cost_raw).isdigit() else 0

        if cost > 0:
            res_type = action_data.get('resource', 'mp')
            res_key = f"current_{res_type}"
            actor[res_key] = max(0, actor.get(res_key, 0) - cost)
        
        # Loop through all targets
        for target in target_list:
            is_hit = True
            is_crit = False
            roll_info = {}
            res_payload = {
                "target": target,
                "type": action_data.get('damage_type', 'physical')
            }
            
            a_type = action_data.get('type', 'attack')

            # --- 4. ACCURACY CHECK ---
            if a_type == 'attack':
                atk_bonus = CombatEngine.get_total_attack_bonus(actor)
                adv = CombatEngine.get_attack_advantage(actor, target)
                ac = int(target.get('ac', 10))
                
                # Check for stunned auto-crit (Melee only)
                if 'stunned' in target.get('conditions', {}) and actor.get('attack_range', 1) <= 3:
                    is_hit = True
                    is_crit = True
                    roll_val, _ = roll_d20(advantage=adv)
                    roll_info = {'roll': roll_val, 'hit': True, 'critical': True, 'total': roll_val + atk_bonus}
                else:
                    res = attack_roll(atk_bonus, ac, crit_range=tuple(crit_range), advantage=adv)
                    is_hit = res['hit']
                    is_crit = res['critical']
                    roll_info = res
                
                res_payload.update({
                    'roll': roll_info['roll'],
                    'total_roll': roll_info['total'],
                    'crit': is_crit
                })
                if not is_hit:
                    res_payload['miss'] = True

            elif a_type == 'save':
                dc = CombatEngine.compute_spell_dc(actor)
                resist = CombatEngine.compute_spell_resist(target)
                difficulty = max(0, dc - resist)
                
                roll, _ = roll_d20()
                passed = roll >= difficulty
                roll_info = {'save_roll': roll, 'success': passed, 'dc': difficulty}
                
                res_payload['save_roll'] = roll
                res_payload['save_info'] = {id(target): roll_info}
                # Saves always "hit" but damage may be halved later
                is_hit = True

            # --- 5. DAMAGE / HEALING / RESOURCE RESOLUTION ---
            damage = 0
            if is_hit:
                if damage_formula:
                    d_form = CombatEngine._resolve_math(str(damage_formula), placeholders)
                    d_form = CombatEngine.evaluate_dynamic_tags(d_form, actor, target)
                    damage = CombatEngine._parse_math_string(actor, d_form)
                    
                    if is_crit:
                        # Critical Hit: Double the dice roll (unless target is crit_immune)
                        if not target.get('crit_immune'):
                            damage += CombatEngine._parse_math_string(actor, d_form)
                    
                    # Half damage on successful save
                    if a_type == 'save' and roll_info.get('success'):
                        damage //= 2

            healing = 0
            if healing_formula:
                h_form = CombatEngine._resolve_math(str(healing_formula), placeholders)
                h_form = CombatEngine.evaluate_dynamic_tags(h_form, actor, target)
                healing = CombatEngine._parse_math_string(actor, h_form)

            mana_gain = 0
            if mana_gain_formula:
                m_form = CombatEngine._resolve_math(str(mana_gain_formula), placeholders)
                mana_gain = CombatEngine._parse_math_string(actor, m_form)

            stamina_gain = 0
            if stamina_gain_formula:
                s_form = CombatEngine._resolve_math(str(stamina_gain_formula), placeholders)
                stamina_gain = CombatEngine._parse_math_string(actor, s_form)

            bonus_gain = 0
            if bonus_gain_formula:
                b_form = CombatEngine._resolve_math(str(bonus_gain_formula), placeholders)
                bonus_gain = CombatEngine._parse_math_string(actor, b_form)

            attack_gain = 0
            if attack_gain_formula:
                at_form = CombatEngine._resolve_math(str(attack_gain_formula), placeholders)
                attack_gain = CombatEngine._parse_math_string(actor, at_form)

            # --- 6. EFFECTS (DOT/HOT) ---
            effects = []
            # Only apply secondary effects if hit (and if save, it must have failed)
            if is_hit and (a_type != 'save' or not roll_info.get('success')):
                for eff_type in ['dot', 'hot']:
                    if action_data.get(eff_type):
                        dur_raw = action_data.get('duration', 3)
                        try:
                            dur_res = CombatEngine._resolve_math(str(dur_raw), placeholders)
                            duration = int(eval(dur_res, {"__builtins__": None}, {})) if any(op in dur_res for op in "+-*/") else int(dur_res)
                        except:
                            duration = 3

                        # Fetch dice from hot_dice/dot_dice, falling back to main dice formula
                        dice_raw = action_data.get(f'{eff_type}_dice', action_data.get('dice', '1d6'))
                        dice = CombatEngine._resolve_math(str(dice_raw), placeholders)
                        
                        # Force 'hot' type for heal abilities
                        actual_type = 'hot' if a_type == 'heal' else eff_type

                        effects.append({
                            'name': action_data.get('name', 'Lingering Effect'),
                            'type': actual_type,
                            'dice': dice,
                            'duration': duration
                        })

                # --- 7. STATUS EFFECTS (effect, effect2, effect3) ---
                for e_key in ['effect', 'effect2', 'effect3']:
                    effect_name = action_data.get(e_key)
                    if effect_name:
                        # Resolve duration
                        dur_raw = action_data.get('duration', 1)
                        try:
                            dur_res = CombatEngine._resolve_math(str(dur_raw), placeholders)
                            duration = int(eval(dur_res, {"__builtins__": None}, {})) if any(op in dur_res for op in "+-*/") else int(dur_res)
                        except:
                            duration = 1
                        
                        # Resolve power
                        power_raw = action_data.get('power', 0)
                        power = 0
                        try:
                            pow_res = CombatEngine._resolve_math(str(power_raw), placeholders)
                            power = int(eval(pow_res, {"__builtins__": None}, {})) if any(op in pow_res for op in "+-*/") else int(pow_res)
                        except:
                            power = 0

                        # Standardize name (blinded -> blind, poisoned -> poison)
                        eff_type = effect_name.lower()
                        if eff_type == 'blinded': eff_type = 'blind'
                        if eff_type == 'poisoned': eff_type = 'poison'

                        effects.append({
                            'name': effect_name,
                            'type': eff_type,
                            'duration': duration,
                            'value': power
                        })

            res_payload.update({
                "damage": damage,
                "healing": healing,
                "mana_gain": mana_gain,
                "stamina_gain": stamina_gain,
                "bonus_gain": bonus_gain,
                "attack_gain": attack_gain,
                "effects": effects
            })
            results.append(res_payload)

        return results

    @staticmethod
    def _parse_math_string(actor, formula):
        """
        Safely parses JSON math strings (e.g., '1d8 + 5' or '2 * 10').
        Handles dice notation and basic math via attack_roller helper.
        """
        if not formula:
            return 0
        if isinstance(formula, int):
            return formula
        if not isinstance(formula, str):
            try: return int(formula)
            except: return 0

        # Handle dice notation and basic math via attack_roller helper
        processed = formula.upper()
        from .attack_roller import roll_dice
        try:
            return roll_dice(processed)
        except:
            return 0

    @staticmethod
    def evaluate_dynamic_tags(formula_string, actor, target):
        """
        Resolves dynamic tags like {current_mp} just-in-time using the actor's current state. 
        """
        if not isinstance(formula_string, str) or '{' not in formula_string:
            return formula_string

        # Swap out {current_mp} for actor['mp'] (using 'current_mp' per codebase convention)  
        mp = actor.get('current_mp', actor.get('mp', 0))
        hp = actor.get('current_hp', actor.get('hp', 0))

        res = formula_string.replace("{current_mp}", str(mp))
        res = res.replace("{current_hp}", str(hp))

        return res

    @staticmethod
    def _trigger_on_hit_effects(attacker, target, damage, hit=True):
        """Helper to collect on-hit (and on-miss) weapon effects."""
        effects = []
        messages = []
        
        effect_type = attacker.get('on_hit_effect', '').lower()
        duration = int(attacker.get('duration', 1))
        prof = int(attacker.get('proficiency_bonus', 0))
        attacker_name = attacker.get('name', 'Attacker')
        target_name = target.get('name', 'Target')

        if hit:
            if effect_type == 'vex':
                # Vex: hits grant self advantage on next attack
                effects.append({'name': 'Vex', 'type': 'advantage_next', 'duration': duration, 'target_source': True})
                messages.append(f"Vex applied to {attacker_name}.")
            elif effect_type == 'sap':
                # Sap: hits give enemy disadvantage on their next attack
                effects.append({'name': 'Sap', 'type': 'disadvantage_next', 'duration': duration})
                messages.append(f"Sap applied to {target_name}.")
            elif effect_type == 'poison':
                effects.append({'name': 'Poisoned', 'type': 'poisoned', 'duration': duration})
                messages.append(f"Poisoned applied to {target_name}.")
            elif effect_type == 'lifesteal':
                heal_amt = max(1, damage // 2)
                effects.append({'name': 'Lifesteal', 'type': 'heal_attacker', 'value': heal_amt, 'target_source': True})
                messages.append(f"Lifesteal applied to {attacker_name}.")
            elif effect_type == 'swift':
                # Swift: attack_count += 1, only triggers once per turn
                effects.append({'name': 'Swift', 'type': 'swift', 'target_source': True})
                messages.append(f"{attacker_name} gained an extra attack!")
        else:
            # Handle miss effects
            if effect_type == 'graze':
                graze_dmg = max(1, prof // 2)
                effects.append({'name': 'Graze', 'type': 'immediate_damage', 'value': graze_dmg})
                messages.append(f"Graze applied to {target_name}, dealing {graze_dmg} damage.")

        return effects, messages

    @staticmethod
    def resolve_attack(attacker, target, advantage=0, debug=None, float_mgr=None, extra_damage=0, crit_range=[]):
        """
        Resolves a single attack from attacker to target.
        attacker: dict containing proficiency_bonus, weapon_bonus, damage_die, on_hit_effect, etc.
        target: dict containing ac.
        advantage: 1 for advantage, -1 for disadvantage, 0 for normal.
        """
        # Unified bonus calculation: Proficiency + Weapon/Item + Equipment + Feast
        prof = int(attacker.get('proficiency_bonus', 0))
        w_bonus = int(attacker.get('weapon_bonus', 0))
        eq_atk = int(attacker.get('equipment_atk_bonus', 0))
        f_bonus = int(attacker.get('feast_bonus', 0))
        attack_bonus = prof + w_bonus + eq_atk + f_bonus

        target_ac = int(target.get('ac', 10))
        target_pos = target.get('screen_pos', (400, 300))

        attacker_name = attacker.get('name', 'Attacker')
        target_name = target.get('name', 'Target')
        
        # --- Advantage/Disadvantage Logic (Consolidated) ---
        atk_adv = int(advantage)
        target_conds = target.get('conditions', {})
        attacker_conds = attacker.get('conditions', {})

        # 1. Blinded: Attacker has Disadvantage, Targets have Advantage to be hit
        if 'blind' in attacker_conds: atk_adv -= 1
        if 'blind' in target_conds: atk_adv += 1

        # 2. Frightened: Disadvantage when attacking the source
        if 'frightened' in attacker_conds:
            source_id, _ = attacker_conds['frightened']
            if id(target) == source_id:
                atk_adv -= 1
            # Inverse: Source has advantage against target
            if id(attacker) == source_id:
                atk_adv += 1

        # 3. Advantage Next: Grants advantage to the next attacker
        if 'advantage_next' in target_conds:
            atk_adv += 1
            # Mark for removal after this resolution
            target['_consume_advantage_next'] = True
            
        if 'advantage_next' in attacker_conds:
            atk_adv += 1
            # Mark for removal after this resolution (applied to self)
            attacker['_consume_advantage_next'] = True

        # 4. Standard Advantage/Disadvantage buffs
        if 'advantage' in attacker_conds: atk_adv += 1
        if 'disadvantage' in attacker_conds: atk_adv -= 1

        # Determine crit range
        base_crit = [20]
        if attacker.get('crit_on_18'): base_crit = [18, 19, 20]
        elif attacker.get('crit_on_19'): base_crit = [19, 20]
        actual_crit = list(set(base_crit + list(crit_range)))

        res = attack_roll(attack_bonus, target_ac, crit_range=tuple(actual_crit), advantage=atk_adv)

        # --- Stunned Auto-Crit Trigger ---
        if 'stunned' in target_conds:
            is_melee = False
            r_val = attacker.get('weapon_range', attacker.get('attack_range', 1))
            if r_val <= 3: # Changed from < 3 to <= 3 to include standard 5e 10ft reach or just be safer
                is_melee = True

            if is_melee:
                res['hit'] = True
                res['critical'] = True

        damage = 0
        effects = []
        messages = []

        status = "hit" if res['hit'] else "missed"
        if res['critical']: status = "CRITICAL hit"

        msg = f"{attacker_name} attacked {target_name} and {status}"

        if res['hit']:
            # For damage, we use weapon_bonus + Feast.
            # For enemies (who lack weapon_bonus), proficiency_bonus acts as their primary modifier.
            primary_mod = w_bonus if w_bonus != 0 else prof
            dmg_mod = primary_mod + f_bonus

            # Fallback to 'die' if 'damage_die' is missing (for enemies)
            damage_die = attacker.get('damage_die', attacker.get('die', 4))

            # Resolve dynamic tags right before damage roll
            damage_die = CombatEngine.evaluate_dynamic_tags(damage_die, attacker, target)     

            damage, dice_str = damage_roll(damage_die, dmg_mod, critical=res['critical'], player_data=attacker, target=target)

            # Add bonus_dmg (used by summons)
            b_dmg = int(attacker.get('bonus_dmg', 0))
            if b_dmg > 0:
                damage += b_dmg
                dice_str += f" + {b_dmg} (Summon Bonus)"

            if extra_damage > 0:
                damage += extra_damage
                dice_str += f" + {extra_damage} (Bonus)"

            if damage > 0:
                msg += f", dealing {damage} damage."
            else:
                msg += "."

            if float_mgr:
                # Phasing for basic attacks (attack type)
                EFFECT_DELAY = 50
                
                if res['critical']:
                    float_mgr.add("CRIT!", target_pos, "crit", rise_speed=2.0, delay=0)
                else:
                    float_mgr.add("HIT", target_pos, "hit", delay=0)

                if damage > 0:
                    float_mgr.add(f"-{damage}", target_pos, "damage", rise_speed=1.5, delay=0)

            if debug:
                debug.set("Last Damage", damage)
                debug.log(f"Hit! Roll: {res['roll']} vs AC {target_ac}")

            # Trigger On-Hit Weapon Effects
            w_effects, w_msgs = CombatEngine._trigger_on_hit_effects(attacker, target, damage, hit=True)
            effects.extend(w_effects)
            messages.extend(w_msgs)

            # Handle weapon-based DOT
            if attacker.get('dot'):
                dot_val = attacker.get('dot_dice', 4)
                # Ensure it's a dice string
                if isinstance(dot_val, int): dot_val = f"1d{dot_val}"
                elif isinstance(dot_val, str) and 'd' not in dot_val: dot_val = f"1d{dot_val}"

                # DOT duration is handled separately in effects
                effects.append({'name': 'Lingering Damage', 'type': 'dot', 'dot_dice': str(dot_val), 'duration': duration})
                msg += f" Lingering damage applied to {target_name}."

            # Handle weapon enchantments
            enchant = attacker.get('weapon_enchantment')
            if enchant == 'lifesteal':
                heal_amt = max(1, damage // 2)
                effects.append({'name': 'Lifesteal', 'type': 'heal_attacker', 'value': heal_amt})
                msg += f" Lifesteal applied to {attacker_name}."
            elif enchant == 'fire':
                fire_dmg = random.randint(1, 4)
                effects.append({'name': 'Fire', 'type': 'extra_dmg', 'value': fire_dmg})
                msg += f" Fire applied to {target_name}."
                if float_mgr: float_mgr.add(f"-{fire_dmg}", target_pos, (255, 128, 0), delay=EFFECT_DELAY)        
            elif enchant == 'frost':
                effects.append({'name': 'Chilled', 'type': 'enemy_advantage', 'value': -1}) # Slow effect
                msg += f" Frost applied to {target_name}."
                if float_mgr: float_mgr.add("CHILLED", target_pos, (100, 200, 255), delay=EFFECT_DELAY)
            elif enchant == 'silence':
                # DC 12 Silence save
                save_roll, _ = roll_d20()
                if save_roll < 12:
                    effects.append({'name': 'Silence', 'type': 'silence', 'duration': 1})
                    msg += f" Silence applied to {target_name}."
                    if float_mgr: float_mgr.add("SILENCED", target_pos, "effect", delay=EFFECT_DELAY)
                else:
                    msg += f" {target_name} resisted Silence."

        else:
            msg += "."
            if float_mgr:
                float_mgr.add("MISS", target_pos, "miss", delay=0)
            if debug:
                debug.log(f"Missed! Roll: {res['roll']} vs AC {target_ac}")
            # Handle miss effects (like Graze)
            effect_type = attacker.get('on_hit_effect', '').lower()
            if effect_type == 'graze':
                graze_dmg = max(1, prof // 2)
                damage = graze_dmg
                msg += f" Graze applied to {target_name}, dealing {graze_dmg} damage."        
                if float_mgr: float_mgr.add(f"-{graze_dmg}", target_pos, "damage")

        messages.append(msg)

        return {
            'hit': res['hit'],
            'damage': damage,
            'critical': res['critical'],
            'roll': res['roll'],
            'attack_bonus': attack_bonus,
            'total_roll': res['total'],
            'effects': effects,
            'msg': messages,
            'attacker_name': attacker_name,
            'target_name': target_name
        }

    @staticmethod
    def compute_spell_dc(caster, ability_bonus=0):
        """
        Calculates Spell DC: 8 + proficiency + bonus from items + feast bonus + optional ability bonus.
        If 'spell_dc' is already defined (e.g. for enemies), use that as the base.
        Clamped between 0 and 20.
        """
        base_dc = caster.get('spell_dc')
        if base_dc is not None:
            return max(0, min(20, int(base_dc) + ability_bonus))

        prof = int(caster.get('proficiency_bonus', 0))
        # 'spell_save' is currently used in player_data for equipment bonus
        item_bonus = int(caster.get('spell_save', 0))
        f_bonus = int(caster.get('feast_bonus', 0))

        dc = 8 + prof + item_bonus + f_bonus + ability_bonus
        return max(0, min(20, dc))

    @staticmethod
    def compute_spell_resist(target):
        """
        Calculates Spell Resist. For players, it comes from items. For enemies, it's a base value.
        Clamped between 0 and 20.
        """
        resist = int(target.get('spell_resist', 0))
        return max(0, min(20, resist))

    @staticmethod
    def _resolve_math(input_str, placeholders):
        """Helper to replace placeholders and evaluate math in a string."""
        if not isinstance(input_str, str):
            return str(input_str)

        result = input_str

        # 0. Handle Nested Dice (e.g. 2d{damage_die} where damage_die is 2d10)
        # If {damage_die} placeholder is a dice string, "d{damage_die}" should become "*({damage_die})"
        dd_val = placeholders.get("{damage_die}")
        if dd_val and 'd' in str(dd_val):
             result = result.replace("d{damage_die}", f"*({dd_val})")

        # 1. Prepare an Evaluation Context from placeholders (e.g. {prof} -> prof=4)
        eval_context = {}
        for k, v in placeholders.items():
            clean_key = k.strip("{}")
            # Only add simple alphabetic keys (prof, level, damage_die) to context
            # to avoid confusing eval with keys like "level/2"
            if clean_key.isalpha():
                try:
                    eval_context[clean_key] = int(v)
                except:
                    eval_context[clean_key] = v

        # 2. Replace all named placeholders (direct exact match)
        for ph, val in placeholders.items():
            result = result.replace(ph, str(val))

        import re
        # 3. Resolve all remaining {math} blocks explicitly
        def eval_block(match):
            expr = match.group(0).strip("{}")
            try:
                # Use the eval_context so {prof/3} works if 'prof' is defined
                return str(int(eval(expr, {"__builtins__": None}, eval_context)))
            except:
                # If eval fails, maybe it's still a placeholder or complex string
                return match.group(0)

        result = re.sub(r"\{[^\}]+\}", eval_block, result)

        # 4. Handle dice strings and general arithmetic
        # We split by + and - to evaluate terms, but preserve 'd' for dice
        parts = re.split(r"(\+|-)", result)
        resolved_parts = []

        for part in parts:
            if not part or part in "+-":
                resolved_parts.append(part)
                continue

            if 'd' in part:
                # Handle dice notation XdY where X and Y might still be math like (4+1)       
                d_match = re.split(r"(d)", part) # Split by 'd' but keep it
                sub_resolved = []
                for sub in d_match:
                    if sub == 'd' or not sub:
                        sub_resolved.append(sub)
                        continue
                    # Try to eval the count or side if it has math characters
                    if any(c in sub for c in "()*/"):
                        try:
                            # Sanitize sub for safety
                            cleaned = "".join(c for c in sub if c in "0123456789+-*/(). ")    
                            val = str(int(eval(cleaned, {"__builtins__": None}, {})))
                            sub_resolved.append(val)
                        except:
                            sub_resolved.append(sub)
                    else:
                        sub_resolved.append(sub)
                resolved_parts.append("".join(sub_resolved))
            else:
                # Pure math part
                if any(c in part for c in "()*/"):
                    try:
                        cleaned = "".join(c for c in part if c in "0123456789+-*/(). ")       
                        val = str(int(eval(cleaned, {"__builtins__": None}, {})))
                        resolved_parts.append(val)
                    except:
                        resolved_parts.append(part)
                else:
                    resolved_parts.append(part)

        return "".join(resolved_parts)

    @staticmethod
    def resolve_ability(ability_data, caster, targets, debug=None, float_mgr=None, skip_cost=False, crit_range=[20]):
        """
        Resolves a single iteration of an ability (skill or spell) cast against one or more targets.
        targets: can be a single target dict or a list of target dicts.
        skip_cost: if True, returns 0 mana_cost (for multi-hit abilities where cost is paid upfront).
        """
        # Ensure targets is a list
        if not isinstance(targets, list):
            targets = [targets]

        is_aoe = ability_data.get('aoe', False) or ability_data.get('saoe', False)
        # If not AOE, we only hit the first target in the list
        active_targets = targets if is_aoe else [targets[0]]

        # Check 'cost' (skills/spells)
        mana_cost_raw = 0 if skip_cost else ability_data.get('cost', 0)

        # Prepare placeholders for all resolutions
        prof = int(caster.get('proficiency_bonus', 0))
        total_level = sum(caster.get('class_levels', {}).values()) if caster.get('class_levels') else caster.get('level', 1)

        # Snapshot-aware resource values
        mp_val = int(caster.get('standby_mp', caster.get('current_mp', 0)))
        sp_val = int(caster.get('standby_sp', caster.get('current_sp', 0)))

        placeholders = {
            "{damage_die}": str(caster.get('damage_die', caster.get('die', 4))),
            "{level}": str(total_level),
            "{level/2}": str(total_level // 2),
            "{level/3}": str(total_level // 3),
            "{level/4}": str(total_level // 4),
            "{level2}": str(total_level // 2),
            "{prof}": str(prof),
            "{prof/2}": str(prof // 2),
            "{prof/4}": str(prof // 4),
        }

        mana_cost = 0
        if mana_cost_raw:
            try:
                # Resolve math/placeholders in cost (e.g. "{prof}/2 + 1")
                resolved_cost = CombatEngine._resolve_math(str(mana_cost_raw), placeholders)  
                if any(op in resolved_cost for op in "+-*/"):
                    mana_cost = int(eval(resolved_cost, {"__builtins__": None}, {}))
                else:
                    mana_cost = int(resolved_cost)
            except:
                # Fallback to 0 or raw int if possible
                mana_cost = int(mana_cost_raw) if str(mana_cost_raw).isdigit() else 0

        total_damage = 0
        total_healing = 0
        all_effects = []
        msg_parts = []

        caster_name = caster.get('name', 'Caster')
        target_names = ", ".join([t.get('name', 'Target') for t in active_targets])

        name = ability_data.get('name', 'Ability')
        resource_type = ability_data.get('resource', 'mp')

        if debug:
            debug.set("Last Ability", name)

        spell_type = ability_data.get('type', 'attack')
        dice_str = ability_data.get('dice', '')

        hits_by_target = {id(t): 0 for t in active_targets}
        damage_by_target = {id(t): 0 for t in active_targets}
        healing_by_target = {id(t): 0 for t in active_targets}
        failed_saves_by_target = {id(t): 0 for t in active_targets}
        rolls_by_target = {}
        saves_info = {} # Map of tid -> {'roll': int, 'success': bool, 'dc': int}

        # Pre-roll damage for save-type abilities (standard 5e: roll once for all targets)    
        damage_roll = 0
        if spell_type == "save" and dice_str:
            current_dice = CombatEngine._resolve_math(dice_str, placeholders)
            current_dice = CombatEngine.evaluate_dynamic_tags(current_dice, caster, active_targets[0])
            damage_roll = roll_dice(current_dice)

        for target in active_targets:
            tid = id(target)
            target_pos = target.get('screen_pos', (400, 300))

            # Determine Dice (skipped if already rolled for save)
            current_dice = dice_str
            if spell_type != "save":
                if ability_data.get('use_damage_die'):
                    # Monk-style damage die scaling
                    die = caster.get('damage_die', caster.get('die', 4))
                    if isinstance(die, str) and 'd' in die:
                        current_dice = die
                    else:
                        current_dice = f"1d{die}"
                    w_bonus = int(caster.get('weapon_bonus', 0))
                    f_bonus = int(caster.get('feast_bonus', 0))
                    total_bonus = w_bonus + prof + f_bonus

                    # Level scaling: {damage_die} + {player_level / 2}
                    if ability_data.get('bonus_per_level'):
                        level_bonus = total_level // 2
                        total_bonus += level_bonus

                    if total_bonus != 0:
                        current_dice += f"{'+' if total_bonus > 0 else ''}{total_bonus}"      

                # Resolve placeholders and math in the determined dice string
                if current_dice:
                    current_dice = CombatEngine._resolve_math(current_dice, placeholders)     
                    current_dice = CombatEngine.evaluate_dynamic_tags(current_dice, caster, target)

            # Resolve by Type
            f_bonus = int(caster.get('feast_bonus', 0))
            if spell_type == "attack":
                atk_bonus = CombatEngine.get_total_attack_bonus(caster)
                ac = int(target.get('ac', 10))
                adv = CombatEngine.get_attack_advantage(caster, target)
                
                res = attack_roll(atk_bonus, ac, crit_range=tuple(crit_range), advantage=adv)
                roll = res['roll']
                rolls_by_target[tid] = roll

                if res['hit']:
                    dmg = roll_dice(current_dice) if current_dice else 0
                    
                    # Handle Critical Hit Damage for Spells
                    if res['critical'] and not target.get('crit_immune'):
                        dmg += roll_dice(current_dice) if current_dice else 0
                        
                    dmg *= ability_data.get('multiplier', 1)
                    # Add feast bonus to damage if it's an attack ability
                    dmg += f_bonus
                    damage_by_target[tid] += dmg
                    hits_by_target[tid] += 1
                    failed_saves_by_target[tid] += 1
                    if float_mgr: float_mgr.add(f"-{dmg}", target_pos, "damage", delay=DAMAGE_DELAY)

                    # Trigger Weapon On-Hit Effects for attack abilities
                    w_effects, w_msgs = CombatEngine._trigger_on_hit_effects(caster, target, dmg, hit=True)
                    all_effects.extend(w_effects)
                    msg_parts.extend(w_msgs)
                else:
                    if float_mgr: float_mgr.add("MISS", target_pos, "miss")
                    # Handle graze on miss for abilities
                    w_effects, w_msgs = CombatEngine._trigger_on_hit_effects(caster, target, 0, hit=False)
                    all_effects.extend(w_effects)
                    msg_parts.extend(w_msgs)

            elif spell_type == "save":
                # Resolve ability-specific DC bonus
                ability_dc_bonus = ability_data.get('bonus_spell_save', 0)
                if ability_dc_bonus:
                    try:
                        ability_dc_bonus = int(CombatEngine._resolve_math(str(ability_dc_bonus), placeholders))
                    except:
                        ability_dc_bonus = 0

                spell_dc = CombatEngine.compute_spell_dc(caster, ability_bonus=int(ability_dc_bonus))

                # Blindness grants disadvantage to saves
                save_adv = 0
                if 'blind' in target.get('conditions', {}):
                    save_adv = -1

                roll, _ = roll_d20(advantage=save_adv)
                spell_resist = CombatEngine.compute_spell_resist(target)
                difficulty = max(0, min(20, spell_dc - spell_resist))

                failed = roll < difficulty
                saves_info[tid] = {'roll': roll, 'success': not failed, 'dc': difficulty, 'damage_roll': damage_roll}

                if failed:
                    dmg = damage_roll
                    dmg *= ability_data.get('multiplier', 1)
                    damage_by_target[tid] += dmg
                    hits_by_target[tid] += 1
                    failed_saves_by_target[tid] += 1
                    if float_mgr:
                        float_mgr.add("FAIL", target_pos, "fail")
                        if dmg > 0: float_mgr.add(f"-{dmg}", target_pos, "damage", delay=DAMAGE_DELAY)
                else:
                    dmg = damage_roll // 2
                    dmg *= ability_data.get('multiplier', 1)
                    damage_by_target[tid] += dmg
                    hits_by_target[tid] += 1
                    if float_mgr:
                        float_mgr.add("SAVE", target_pos, "save")
                        if dmg > 0: float_mgr.add(f"-{dmg}", target_pos, "damage", delay=DAMAGE_DELAY)

            elif spell_type == "auto":
                threshold = ability_data.get('hp_threshold')
                is_below = True
                if threshold and target.get('current_hp', target.get('hp', 999)) > threshold: 
                    is_below = False

                if is_below:
                    dmg = ability_data.get('threshold_damage')
                    if dmg is None:
                        dmg = roll_dice(current_dice) if current_dice else 0

                    damage_by_target[tid] += dmg * ability_data.get('multiplier', 1)
                    hits_by_target[tid] += 1
                    failed_saves_by_target[tid] += 1
                    if float_mgr and dmg > 0:
                        float_mgr.add(f"-{dmg}", target_pos, "damage", delay=DAMAGE_DELAY)
                else:
                    dmg = ability_data.get('else_damage', 0)
                    if dmg > 0:
                        damage_by_target[tid] += dmg * ability_data.get('multiplier', 1)      
                        hits_by_target[tid] += 1
                        # Do not increment failed_saves_by_target so effects don't apply if above threshold
                        if float_mgr:
                            float_mgr.add(f"-{dmg}", target_pos, "damage", delay=DAMAGE_DELAY)

            elif spell_type == "heal":
                heal_amt = roll_dice(current_dice) if current_dice else 0
                heal_amt *= ability_data.get('multiplier', 1)
                total_healing += heal_amt
                healing_by_target[tid] += heal_amt
                hits_by_target[tid] += 1
                failed_saves_by_target[tid] += 1

                if float_mgr:
                    float_mgr.add(f"+{heal_amt}", target_pos, "heal")

            elif spell_type == "buff":
                hits_by_target[tid] += 1
                failed_saves_by_target[tid] += 1

            elif spell_type == "summon":
                hits_by_target[tid] += 1
                failed_saves_by_target[tid] += 1

        # Consolidate results
        total_hits = sum(hits_by_target.values())
        total_damage = sum(damage_by_target.values())
        total_failed_saves = sum(failed_saves_by_target.values())

        # Resolve duration and power placeholders
        duration_raw = ability_data.get('duration', 1)
        duration = 1
        try:
            resolved_dur = CombatEngine._resolve_math(str(duration_raw), placeholders)        
            if any(op in resolved_dur for op in "+-*/"):
                duration = int(eval(resolved_dur, {"__builtins__": None}, {}))
            else:
                duration = int(resolved_dur)
        except:
            try: duration = int(duration_raw)
            except: duration = 1

        # Apply Effects (only if at least one hit landed and save failed)
        if total_failed_saves > 0:
            # Gather all effect keys
            effect_keys = ['effect', 'effect2', 'effect3']
            for e_key in effect_keys:
                effect_name = ability_data.get(e_key)
                if effect_name:
                    power_raw = ability_data.get('power', 0)
                    power = 0
                    try:
                        resolved_power = CombatEngine._resolve_math(str(power_raw), placeholders)
                        if any(op in resolved_power for op in "+-*/"):
                            power = int(eval(resolved_power, {"__builtins__": None}, {}))     
                        else:
                            power = int(resolved_power)
                    except:
                        try: power = int(power_raw)
                        except: power = 0

                    all_effects.append({'name': effect_name, 'type': effect_name.lower(), 'duration': duration, 'value': power})

                    if float_mgr:
                        # Find the first valid target position for effect display
                        target_pos = active_targets[0].get('screen_pos', (400, 300))
                        float_mgr.add(effect_name.upper(), target_pos, "effect")

            # Handle DOT/HOT
            has_dot = ability_data.get('dot')
            has_hot = ability_data.get('hot')

            if has_dot or has_hot:
                dot_duration_raw = ability_data.get('duration', 3)
                dot_duration = 3
                try:
                    resolved_dot_dur = CombatEngine._resolve_math(str(dot_duration_raw), placeholders)
                    if any(op in resolved_dot_dur for op in "+-*/"):
                        dot_duration = int(eval(resolved_dot_dur, {"__builtins__": None}, {}))
                    else:
                        dot_duration = int(resolved_dot_dur)
                except:
                    try: dot_duration = int(dot_duration_raw)
                    except: dot_duration = 3

                if has_hot or ability_data.get('type') == 'heal':
                    effect_type = 'hot'
                    dice = ability_data.get('hot_dice', ability_data.get('dot_dice', '1d6'))  
                else:
                    effect_type = 'dot'
                    dice = ability_data.get('dot_dice', '1d6')

                # Resolve placeholders and math in dice string
                dice = CombatEngine._resolve_math(dice, placeholders)

                # Store info in effects to be handled by combat state
                all_effects.append({'name': effect_type.upper(), 'type': effect_type, 'dot_dice': dice, 'duration': dot_duration})

        # Handle Lifesteal / on_hit_effect for abilities
        if total_damage > 0:
            if ability_data.get('on_hit_effect') == 'lifesteal':
                heal_amt = max(1, total_damage // 2)
                all_effects.append({'name': 'Lifesteal', 'type': 'heal_attacker', 'value': heal_amt})

        # Build message
        status = "hit" if total_hits > 0 else "missed"
        msg = f"{caster_name} used {name} on {target_names} and {status}"
        if total_hits > 0:
            if total_damage > 0:
                msg += f", dealing {total_damage} damage."
            elif total_healing > 0:
                msg += f", restoring {total_healing} HP."
            else:
                msg += "."

            for effect in all_effects:
                # Simple logic for internal messages
                msg += f" {effect['name'].replace('_', ' ').title()} applied."
        else:
            msg += "."
        msg_parts.append(msg)

        if mana_cost > 0:
            res_key = f"current_{resource_type}"
            caster[res_key] = max(0, caster.get(res_key, 0) - mana_cost)

        res_dict = {
            'mana_cost': mana_cost,
            'damage': total_damage,
            'healing': total_healing,
            'damage_by_target': damage_by_target, # Map of id(target) -> damage
            'healing_by_target': healing_by_target, # Map of id(target) -> healing
            'hits_by_target': hits_by_target, # Map of id(target) -> hits
            'failed_saves_by_target': failed_saves_by_target,
            'saves_info': saves_info,
            'effects': all_effects,
            'hit': total_hits > 0,
            'msg': msg_parts,
            'attacker_name': caster_name,
            'target_names': target_names,
            'ability_name': name
        }

        # For "attack" types, return the first roll for the UI to animate
        if spell_type == "attack" and rolls_by_target:
            first_tid = list(rolls_by_target.keys())[0]
            roll_val = rolls_by_target[first_tid]
            res_dict['roll'] = roll_val

            # Calculate total_bonus as requested: {item_bonus+proficiency+bonus+feast}        
            # In our engine: proficiency_bonus + weapon_bonus + equipment_atk_bonus + feast_bonus
            w_bonus = int(caster.get('weapon_bonus', 0))
            eq_atk = int(caster.get('equipment_atk_bonus', 0))
            f_bonus = int(caster.get('feast_bonus', 0))
            total_bonus = prof + w_bonus + eq_atk + f_bonus
            res_dict['attack_bonus'] = total_bonus
            res_dict['total_roll'] = roll_val + total_bonus

        return res_dict

    @staticmethod
    def resolve_item(item_data, user):
        """
        Resolves item usage.
        item_data: dict from consumables.json
        user: player/creature data
        """
        hp_gain = item_data.get('hp_gain', 0)
        mana_gain = item_data.get('mana_gain', 0)
        stamina_gain = item_data.get('stamina_gain', 0)
        bonus_gain = item_data.get('bonus_gain', 0)
        attack_gain = item_data.get('attack_gain', 0)
        extra_damage = item_data.get('extra_damage', 0)

        # Map effect_type/value if they exist
        e_type = item_data.get('effect_type')
        val = item_data.get('value', 0)
        if e_type == 'heal': hp_gain = val
        elif e_type == 'restore_mana': mana_gain = val
        elif e_type == 'restore_stamina': stamina_gain = val
        elif e_type == 'buff_bonus': bonus_gain = val
        elif e_type == 'buff_attacks': attack_gain = val
        elif e_type == 'extra_damage': extra_damage = val
        elif e_type == 'temp_weapon_buff': bonus_gain = val

        display_name = item_data.get('name', 'Item').replace('_', ' ').title()
        msg = f"Used {display_name}. {item_data.get('description', '')}"

        return {
            'hp_gain': hp_gain,
            'mana_gain': mana_gain,
            'stamina_gain': stamina_gain,
            'bonus_gain': bonus_gain,
            'attack_gain': attack_gain,
            'extra_damage': extra_damage,
            'msg': msg
        }

    @staticmethod
    def generate_loot(enemies):
        """
        Generates loot after defeating enemies.
        Always drops reward gold + scaling bonus.
        50% chance per enemy to drop one of its reward items.
        """
        total_gold = 0
        items = []
        messages = []

        for enemy in enemies:
            # 1. Gold: Use defined reward gold + a scaling level bonus
            reward_data = enemy.get('reward', {})
            base_gold = reward_data.get('gold', 10)

            # Add some randomness and scaling to make it feel more frequent/rewarding
            scaling_bonus = random.randint(5, 15) + (enemy.get('level', 1) * 2)
            gold_dropped = base_gold + scaling_bonus
            total_gold += gold_dropped

            # 2. Items: 50/50 chance to drop one of the items in the reward list
            reward_items = reward_data.get('items', [])
            if reward_items and random.random() < 0.5:
                # Pick one item from the reward list
                item = random.choice(reward_items)

                if isinstance(item, dict):
                    i_name = item.get('name')
                    i_type = item.get('type', 'junk')
                    if i_name:
                        items.append((i_type, i_name))
                        messages.append(f"Found {i_name.replace('_', ' ').title()}!")
                else:
                    # Fallback for old string format
                    items.append(('junk', item))
                    messages.append(f"Found {item.replace('_', ' ').title()}!")

            # 3. Extra Chance for Potion (Bonus)
            if random.random() < 0.2:
                potion = random.choice(['healing_potion', 'mana_potion', 'stamina_potion'])   
                items.append(('consumable', potion))
                messages.append(f"Found {potion.replace('_', ' ').title()}!")

        messages.append(f"Gained {total_gold} gold!")

        return {
            'gold': total_gold,
            'items': items,
            'messages': messages
        }
