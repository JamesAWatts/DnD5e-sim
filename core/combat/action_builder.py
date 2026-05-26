class ActionBuilder:
    """
    Utility class for constructing standard combat actions.
    """
    @staticmethod
    def build_basic_attack(actor):
        """
        Constructs a standard 'Attack' action dictionary based on actor stats.
        
        Args:
            actor (dict): The entity dictionary containing weapon and proficiency bonuses.
            
        Returns:
            dict: { 'name': 'Attack', 'type': 'attack', 'damage': formula_string }
        """
        # 1. Extract bonuses
        w_bonus = int(actor.get('weapon_bonus', 0))
        prof = int(actor.get('proficiency_bonus', 0))
        total_bonus = w_bonus + prof
        
        # 2. Format damage die (handles both '1d6' and 6 formats)
        die = actor.get('damage_die', actor.get('die', '1d6'))
        if isinstance(die, int):
            die = f"1d{die}"
            
        # 3. Construct formula string
        formula = f"{die} + {total_bonus}"
        
        action = {
            "name": "Attack",
            "type": "attack",
            "aoe": False,
            "damage": formula
        }

        # 4. Pass through lingering effects (DOT)
        if actor.get('dot'):
            action['dot'] = True
            action['dot_dice'] = actor.get('dot_dice', '1d4')
            action['duration'] = actor.get('duration', 3)
            
        return action
