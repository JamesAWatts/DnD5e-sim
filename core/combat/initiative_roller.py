import random
from core.combat.attack_roller import roll_d20

class InitiativeRoller:
    """
    Standalone module for handling 5e-style initiative resolution.
    """
    @staticmethod
    def roll_initiative(party, enemies):
        """
        Rolls initiative for all combatants and returns a sorted list.
        
        Args:
            party (list): List of player/ally actor dictionaries.
            enemies (list): List of enemy actor dictionaries.
            
        Returns:
            list: The combined list of actors sorted by initiative (highest first).
        """
        all_actors = party + enemies
        
        for actor in all_actors:
            # 1. Roll 1d20
            roll, _ = roll_d20()
            
            # 2. Add Initiative Bonus
            # Hierarchy: 'initiative' -> 'dexterity' (mod) -> 0
            bonus = actor.get('initiative', 0)
            if bonus == 0 and 'dexterity' in actor:
                # Standard 5e dexterity modifier calculation: (dex - 10) // 2
                dex = int(actor['dexterity'])
                bonus = (dex - 10) // 2
            
            actor['initiative_roll'] = roll + bonus
            
        # 3. Sort by initiative_roll descending
        # Ties are implicitly handled by the stability of the sort or 
        # could be randomized further if needed.
        sorted_actors = sorted(all_actors, key=lambda a: a['initiative_roll'], reverse=True)
        
        return sorted_actors
