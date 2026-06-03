import re

class AbilityBaker:
    """
    Utility to pre-process ability data dictionaries, resolving static character variables
    into literal values while preserving dynamic tags for real-time evaluation.
    """
    
    STATIC_VARS = ['prof', 'level', 'damage_die', 'max_hp', 'max_mp']
    DYNAMIC_VARS = ['current_mp', 'current_hp']

    @staticmethod
    def bake_ability(ability_data, actor):
        """
        Recursively searches ability_data for string formulas and resolves static placeholders.
        Performs two passes to ensure cross-references like {duration} are resolved after 
        their own formulas (e.g. {prof/2}) are calculated.
        """
        if not isinstance(ability_data, dict):
            return ability_data

        # Pass 1: Resolve Character Stats (prof, level, etc.)
        baked = {}
        for key, value in ability_data.items():
            if isinstance(value, dict):
                baked[key] = AbilityBaker.bake_ability(value, actor)
            elif isinstance(value, list):
                baked[key] = [AbilityBaker.bake_ability(v, actor) if isinstance(v, dict) else v for v in value]
            elif isinstance(value, str):
                baked[key] = AbilityBaker._bake_string(value, actor)
            else:
                baked[key] = value
        
        # Pass 2: Resolve Cross-References within the dict (e.g. {effect} in description)
        # We only do this for top-level strings like 'description'
        final_baked = baked.copy()
        for key, value in baked.items():
            if isinstance(value, str) and '{' in value:
                # Use regex to find tags that match keys in our baked dict
                def cross_ref_replacer(match):
                    tag = match.group(1).lower().strip()
                    if tag in baked:
                        return str(baked[tag])
                    return match.group(0)
                
                final_baked[key] = re.sub(r'\{([^{}]+)\}', cross_ref_replacer, value)

        return final_baked

    @staticmethod
    def _bake_string(formula, actor):
        if '{' not in formula:
            return formula

        # 1. Prepare Static Values
        prof = int(actor.get('proficiency_bonus', 0))
        level = sum(actor.get('class_levels', {}).values()) if actor.get('class_levels') else actor.get('level', 1)
        damage_die = actor.get('damage_die', actor.get('die', 4))
        max_hp = actor.get('max_hp', 10)
        max_mp = actor.get('max_mp', 0)

        static_map = {
            'prof': prof,
            'level': level,
            'damage_die': str(damage_die),
            'max_hp': max_hp,
            'max_mp': max_mp
        }

        # 2. Replace Static Placeholders
        def static_replacer(match):
            tag = match.group(1).lower().strip()
            # Direct match
            if tag in static_map:
                return str(static_map[tag])
            
            # Handle common variants like {level/2}
            for key in static_map:
                if tag.startswith(key) and any(op in tag for op in "/+*-"):
                    # Attempt a partial resolution if it only contains this static key and numbers
                    # e.g. "level / 2"
                    try:
                        expr = tag.replace(key, str(static_map[key]))
                        # Safe eval for simple arithmetic
                        allowed = "0123456789+-*/() "
                        if all(c in allowed for c in expr):
                            return str(int(eval(expr, {"__builtins__": None}, {})))
                    except:
                        pass
            
            return match.group(0) # Preserve dynamic or unknown tags

        # Resolve {tag}
        resolved = re.sub(r'\{([^{}]+)\}', static_replacer, formula)

        # 3. Evaluate math if the string no longer contains any braces
        # If it still has braces (dynamic tags), we leave it for the engine to handle just-in-time.
        if '{' not in resolved:
            try:
                # If it looks like a math expression (not a dice string or name)
                if any(c in resolved for c in "+-*/") and 'd' not in resolved.lower():
                    allowed = "0123456789+-*/(). "
                    if all(c in allowed or c.isspace() for c in resolved):
                        return str(int(eval(resolved, {"__builtins__": None}, {})))
            except:
                pass
                
        return resolved
