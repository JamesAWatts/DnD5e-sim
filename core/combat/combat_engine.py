import random
from .attack_roller import attack_roll, damage_roll

class CombatEngine:
    @staticmethod
    def resolve_attack(attacker, target, advantage=0):
        """
        Resolves a single attack from attacker to target.
        attacker: dict containing proficiency_bonus, weapon_bonus, damage_die, on_hit_effect, etc.
        target: dict containing ac.
        advantage: 1 for advantage, -1 for disadvantage, 0 for normal.
        """
        prof = int(attacker.get('proficiency_bonus', 0))
        w_bonus = int(attacker.get('weapon_bonus', 0))
        attack_bonus = prof + w_bonus
        
        target_ac = int(target.get('ac', 10))
        
        # Determine crit range (some classes or effects might change this)
        crit_range = (20,)
        if attacker.get('crit_on_19'):
            crit_range = (19, 20)

        res = attack_roll(attack_bonus, target_ac, crit_range=crit_range, advantage=advantage)
        
        damage = 0
        effects = []
        
        if res['hit']:
            damage = damage_roll(attacker.get('damage_die', 4), w_bonus, critical=res['critical'], player_data=attacker)
            
            # Handle on-hit effects
            effect_type = attacker.get('on_hit_effect', '').lower()
            if effect_type == 'vex':
                effects.append(('player_advantage', 1))
            elif effect_type == 'sap':
                effects.append(('enemy_advantage', -1))
            elif effect_type == 'lifesteal':
                heal_amt = max(1, damage // 2)
                effects.append(('heal_attacker', heal_amt))
            elif effect_type == 'poison':
                effects.append(('msg', "Poisoned!"))
        else:
            # Handle miss effects (like Graze)
            effect_type = attacker.get('on_hit_effect', '').lower()
            if effect_type == 'graze':
                graze_dmg = prof
                effects.append(('msg', f"Graze dealt {graze_dmg} damage"))
                damage = graze_dmg

        return {
            'hit': res['hit'],
            'damage': damage,
            'critical': res['critical'],
            'roll': res['roll'],
            'effects': effects
        }

    @staticmethod
    def resolve_spell(spell_data, caster, target):
        """
        Resolves a spell cast.
        spell_data: dict from spells.json
        caster: player/creature data
        target: target data
        """
        mana_cost = spell_data.get('level', 0)
        damage = 0
        healing = 0
        effects = []
        msg = f"Casting {spell_data.get('name', 'Spell')}..."

        effect_type = spell_data.get('effect_type', '')
        power = spell_data.get('power', 0)
        
        if effect_type == 'damage':
            # Simplified: power is number of d6
            damage = sum(random.randint(1, 6) for _ in range(max(1, power)))
        elif effect_type == 'healing':
            healing = sum(random.randint(1, 4) for _ in range(max(1, power)))
        elif effect_type == 'utility':
            if 'disadvantage' in spell_data.get('description', '').lower():
                effects.append(('enemy_advantage', -1))
        
        return {
            'mana_cost': mana_cost,
            'damage': damage,
            'healing': healing,
            'effects': effects,
            'msg': msg
        }

    @staticmethod
    def resolve_item(item_data, user):
        """
        Resolves item usage.
        item_data: dict from consumables.json
        user: player/creature data
        """
        hp_gain = item_data.get('hp_gain', 0)
        bonus_gain = item_data.get('bonus_gain', 0)
        attack_gain = item_data.get('attack_gain', 0)
        extra_damage = item_data.get('extra_damage', 0)
        
        msg = f"Used {item_data.get('name', 'Item')}. {item_data.get('description', '')}"
        
        return {
            'hp_gain': hp_gain,
            'bonus_gain': bonus_gain,
            'attack_gain': attack_gain,
            'extra_damage': extra_damage,
            'msg': msg
        }

    @staticmethod
    def generate_loot(enemies):
        """
        Generates loot after defeating enemies.
        """
        total_gold = 0
        items = []
        messages = []
        
        for enemy in enemies:
            # Gold based on enemy HP/level
            gold = random.randint(5, 15) + (enemy.get('hp', 10) // 5)
            total_gold += gold
            
            # Chance for item
            if random.random() < 0.3:
                # Randomly pick a category and item (simplified)
                item_types = ['consumable', 'junk']
                t = random.choice(item_types)
                if t == 'consumable':
                    item_name = random.choice(['healing_potion', 'mana_potion'])
                else:
                    item_name = 'goblin_ear'
                items.append((t, item_name))
                messages.append(f"Found {item_name.replace('_', ' ')}!")

        messages.append(f"Gained {total_gold} gold!")
        
        return {
            'gold': total_gold,
            'items': items,
            'messages': messages
        }

def simulate_combat():
    attacker = {
        "proficiency_bonus": 2,
        "weapon_bonus": 3,
        "damage_die": 6,
        "on_hit_effect": "lifesteal"
    }

    target = {
        "ac": 12
    }

    result = CombatEngine.resolve_attack(attacker, target)
    return result
