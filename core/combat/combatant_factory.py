class CombatantFactory:
    """
    Handles the preparation and formatting of entity dictionaries for combat.
    """
    @staticmethod
    def prepare_for_combat(party, enemies):
        """
        Initializes HP, MP, SP, and faction flags for all combatants.
        Ensures all entities have required keys for the combat engine.
        """
        # 1. Prepare Party Members
        for p in party:
            p.update({
                'is_enemy': False, 
                'faction': 'party', 
                'is_alive': True
            })
            # Ensure name exists
            if 'name' not in p:
                p['name'] = p.get('class', 'Hero').title()

            # Resource Setup
            max_hp = p.get('max_hp', p.get('hp', 10))
            p['max_hp'] = max_hp
            p['current_hp'] = p.get('current_hp', max_hp)

            max_mp = p.get('max_mp', p.get('mp', 0))
            p['max_mp'] = max_mp
            p['current_mp'] = p.get('current_mp', max_mp)
            p['mp'] = max_mp > 0

            max_sp = p.get('max_sp', p.get('sp', 0))
            p['max_sp'] = max_sp
            p['current_sp'] = p.get('current_sp', max_sp)
            p['sp'] = max_sp > 0

        # 2. Prepare Enemies
        for e in enemies:
            e.update({
                'is_enemy': True, 
                'faction': 'enemy', 
                'is_alive': True
            })
            # Ensure name exists
            if 'name' not in e:
                e['name'] = "Enemy"

            # Resource Setup
            max_hp = e.get('max_hp', e.get('hp', 10))
            e['max_hp'] = max_hp
            e['current_hp'] = e.get('current_hp', max_hp)

            prof = e.get('proficiency_bonus', 1)
            e['mp'] = len(e.get('spells', [])) > 0
            e['sp'] = len(e.get('skills', [])) > 0

            if e['mp']:
                e['max_mp'] = 10
                e['current_mp'] = prof // 2
            else:
                e['max_mp'] = 0
                e['current_mp'] = 0

            if e['sp']:
                e['max_sp'] = 10
                e['current_sp'] = prof // 2
            else:
                e['max_sp'] = 0
                e['current_sp'] = 0
