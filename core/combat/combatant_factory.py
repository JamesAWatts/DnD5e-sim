import random
from graphics.sprite_manager import SpriteManager

class CombatantFactory:
    """
    Handles the preparation and formatting of entity dictionaries for combat.
    """
    @staticmethod
    def prepare_for_combat(party, enemies):
        """
        Initializes HP, MP, SP, and faction flags for all combatants.
        Ensures all entities have required keys for the combat engine.
        Also handles sprite variant cycling for groups of identical enemies.
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

            # AC Mapping (Player AC is calculated in player.py and stored in p['ac'])
            # We preserve this value unless it's missing (fallback to 10)
            p['ac'] = int(p.get('ac', 10))

            # Resource Setup
            max_hp = int(p.get('max_hp', p.get('hp', 10)))
            p['max_hp'] = max_hp
            p['current_hp'] = int(p.get('current_hp', max_hp))
            if p['current_hp'] <= 0: p['current_hp'] = 1 # Safety for combat

            max_mp = p.get('max_mp', p.get('mp', 0))
            p['max_mp'] = max_mp
            p['current_mp'] = p.get('current_mp', max_mp)
            p['mp'] = max_mp > 0

            max_sp = p.get('max_sp', p.get('sp', 0))
            p['max_sp'] = max_sp
            p['current_sp'] = p.get('current_sp', max_sp)
            p['sp'] = max_sp > 0

        # 2. Group enemies by base_name for sprite cycling
        enemy_groups = {}
        for e in enemies:
            bn = e.get('base_name', 'unknown')
            if bn not in enemy_groups:
                enemy_groups[bn] = []
            enemy_groups[bn].append(e)

        # 3. Prepare Enemies
        for bn, group in enemy_groups.items():
            # Determine variants for this group
            if group:
                cat = group[0].get('category', 'general')
                variants = SpriteManager.get_enemy_variants(cat, bn)
                
                # Pick a random starting index
                start_idx = random.randint(0, len(variants) - 1)
                
                for i, e in enumerate(group):
                    # Cycle variants starting from start_idx
                    v_idx = (start_idx + i) % len(variants)
                    e['sprite_filename'] = variants[v_idx]
                    
                    e.update({
                        'is_enemy': True, 
                        'faction': 'enemy', 
                        'is_alive': True
                    })
                    # Ensure name exists
                    if 'name' not in e:
                        e['name'] = bn.replace('_', ' ').title()

                    # Resource Setup
                    max_hp = e.get('max_hp', e.get('hp', 10))
                    e['max_hp'] = max_hp
                    e['current_hp'] = e.get('current_hp', max_hp)

                    # AC Mapping (JSON uses 'armor', engine uses 'ac')
                    e['ac'] = e.get('ac', e.get('armor', 10))

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
