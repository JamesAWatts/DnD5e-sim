import random
from .attack_roller import roll_dice

class OverTimeProcessor:
    """
    Handles processing of Damage over Time (DoT) and Heal over Time (HoT) effects.
    """
    @staticmethod
    def apply_effect(actor, new_effect, source=None):
        """
        Adds a new effect to the actor, or refreshes the duration if an effect
        with the same name already exists.
        """
        if 'active_effects' not in actor:
            actor['active_effects'] = []
            
        # Ensure 'conditions' dict exists for rapid lookup during combat
        if 'conditions' not in actor:
            actor['conditions'] = {}
            
        name = new_effect.get('name', 'Effect')
        eff_type = new_effect.get('type', 'dot').lower()
        duration = new_effect.get('duration', 3)
        
        # Metadata for source-dependent effects (Taunt, Frightened)
        source_id = id(source) if source else new_effect.get('source_id')
        if source_id:
            new_effect['source_id'] = source_id

        # 1. Special Case: Remove Conditions
        if eff_type == "remove_conditions":
            actor['active_effects'] = []
            actor['conditions'] = {}
            return False # Not a refresh

        # 2. Check for existing effect with same name
        for existing in actor['active_effects']:
            if existing.get('name') == name:
                existing['duration'] = duration
                if source_id: existing['source_id'] = source_id
                # Sync conditions dict: (source_id, duration)
                actor['conditions'][eff_type] = (existing.get('source_id'), duration)
                return True

        # 3. Add as new
        actor['active_effects'].append(new_effect)
        actor['conditions'][eff_type] = (new_effect.get('source_id'), duration)
        return False

    @staticmethod
    def process_effects(actor):
        """
        Processes all active effects for a given actor.
        Ticks down durations and syncs the 'conditions' helper dict.
        """
        if 'active_effects' not in actor:
            actor['active_effects'] = []
        if 'conditions' not in actor:
            actor['conditions'] = {}
            
        active = actor['active_effects']
        if not active:
            actor['conditions'] = {}
            return []
            
        results = []
        remaining = []
        new_conditions = {}
        
        # Track advantage_next for start-of-turn cleanup
        if 'advantage_next' in actor['conditions']:
            results.append({
                'type': 'expiry',
                'name': 'Advantage Next',
                'msg': f"The opening on {actor['name']} has closed."
            })
            # It will be naturally filtered out since we don't add it to remaining/new_conditions
        
        for effect in active:
            eff_type = effect.get('type', 'dot').lower()
            if eff_type == 'advantage_next':
                continue # Expired at start of turn as requested
                
            dice = effect.get('dice', effect.get('dot_dice', '1d4'))
            name = effect.get('name', 'Effect')
            source_id = effect.get('source_id')
            
            # 1. Handle value application for DOT/HOT
            if eff_type in ['dot', 'hot']:
                value = 0
                try:
                    if isinstance(dice, int): value = dice
                    else: value = roll_dice(dice)
                except: value = 1
                    
                old_hp = actor.get('current_hp', 0)
                if eff_type == 'dot':
                    actor['current_hp'] = max(0, old_hp - value)
                    results.append({'type': 'dot', 'value': value, 'name': name, 'msg': f"{actor['name']} took {value} {name} damage!"})
                elif eff_type == 'hot':
                    max_hp = actor.get('max_hp', 100)
                    actor['current_hp'] = min(max_hp, old_hp + value)
                    results.append({'type': 'hot', 'value': value, 'name': name, 'msg': f"{actor['name']} healed {value} from {name}!"})
                
            # 2. Tick duration
            duration = effect.get('duration', 1)
            duration -= 1
            effect['duration'] = duration
            
            if duration > 0:
                remaining.append(effect)
                new_conditions[eff_type] = (source_id, duration)
            else:
                results.append({'type': 'expiry', 'name': name, 'msg': f"The {name} effect on {actor['name']} has ended."})
                
        actor['active_effects'] = remaining
        actor['conditions'] = new_conditions
        return results
