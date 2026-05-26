import random
import re


def roll_dice(dice_str):
    """
    Parses a complex dice string like '1d8+3d6+4', '2(1d6+2)', or '2*10' and returns the result.
    """
    if not dice_str:
        return 0

    # Clean string
    s = str(dice_str).lower().replace(" ", "")

    # 1. Handle Parentheses (recursive)
    import re
    while "(" in s:
        match = re.search(r"(\d*)\(([^()]+)\)", s)
        if match:
            mult_str, inner = match.groups()
            mult = int(mult_str) if mult_str else 1
            res = roll_dice(inner) * mult
            s = s[:match.start()] + str(res) + s[match.end():]
        else:
            # Try plain parentheses without leading multiplier
            match = re.search(r"\(([^()]+)\)", s)
            if match:
                res = roll_dice(match.group(1))
                s = s[:match.start()] + str(res) + s[match.end():]
            else: break

    # 2. Handle Multiplication/Division before Addition/Subtraction
    if '*' in s or '/' in s:
        parts = re.split(r"(\+|-)", s)
        for i in range(len(parts)):
            if parts[i] not in '+-' and any(op in parts[i] for op in "*/"):
                # Split the term into factors (e.g. '2*2d6' -> ['2', '*', '2d6'])
                factors = re.split(r"(\*|/)", parts[i])
                res = None
                for j in range(0, len(factors), 2):
                    term = factors[j]
                    val = roll_dice(term)
                    if res is None:
                        res = val
                    else:
                        op = factors[j-1]
                        if op == '*': res *= val
                        elif op == '/': res //= val if val else 1
                parts[i] = str(res)
        s = "".join(parts)

    # 3. Resolve Dice Patterns NdS
    s = s.replace("-", "+-")
    parts = s.split("+")
    total = 0
    for part in parts:
        if not part: continue
        
        # Handle simple multiplication like '2*d10' or '2*(10)' if they remained
        if '*' in part and 'd' not in part:
            try: total += int(eval(part)); continue
            except: pass

        match = re.match(r"(-?\d*)d(\d+)", part)
        if match:
            num_str, sides_str = match.groups()
            sides = int(sides_str)
            num = 1
            if num_str == '-': num = -1
            elif num_str: num = int(num_str)
            
            is_negative = num < 0
            num = abs(num)
            subtotal = sum(random.randint(1, sides) for _ in range(num))
            total += -subtotal if is_negative else subtotal
        else:
            try: total += int(part)
            except: pass
    return total


def roll_d20(advantage=0):
    """Roll d20. advantage=1: advantage, -1: disadvantage, 0: normal."""
    rolls = [random.randint(1, 20) for _ in range(2 if advantage != 0 else 1)]
    if advantage > 0:
        return max(rolls), rolls
    if advantage < 0:
        return min(rolls), rolls
    return rolls[0], rolls


def attack_roll(attack_bonus, enemy_ac, crit_range=(20,), advantage=0):
    attack_value, rolls = roll_d20(advantage)
    hit = False
    is_critical = attack_value in crit_range

    if attack_value == 1:
        # automatic miss
        hit = False
    elif is_critical:
        hit = True
    elif attack_value + attack_bonus >= enemy_ac:
        hit = True

    return {
        'roll': attack_value,
        'raw_rolls': rolls,
        'total': attack_value + attack_bonus,
        'hit': hit,
        'critical': is_critical,
        'enemy_ac': enemy_ac,
    }


def damage_roll(damage_die, attack_bonus, critical=False, player_data=None, target=None):
    """
    Calculate damage based on player class and stats.
    Returns (damage_amount, dice_string).
    """
    player_class = player_data.get('class', '') if player_data else ''
    eq_bonus = int(player_data.get('equipment_dmg_bonus', 0)) if player_data else 0
    total_bonus = attack_bonus + eq_bonus

    # Adamantite check: Target is immune to crit damage bonuses
    is_crit_immune = target.get('crit_immune', False) if target else False
    effective_crit = critical and not is_crit_immune

    # 1. Complex String Handling (e.g., "2d10")
    if isinstance(damage_die, str) and 'd' in damage_die:
        dice_str = damage_die
        if total_bonus != 0:
            dice_str += f"{'+' if total_bonus > 0 else ''}{total_bonus}"
        
        # Authentic 5e Crit: Roll dice twice
        if effective_crit:
            res1 = roll_dice(damage_die)
            res2 = roll_dice(damage_die)
            dice_str = f"({damage_die} + {damage_die}) [CRIT]"
            if total_bonus != 0:
                dice_str += f"{'+' if total_bonus > 0 else ''}{total_bonus}"
            return res1 + res2 + total_bonus, dice_str
            
        return roll_dice(damage_die) + total_bonus, dice_str

    # 2. Standard Numeric logic (monks, base weapons, etc.)
    sides = int(damage_die)
    if player_class in ('sorcerer', 'wizard', 'druid', 'alchemist'):
        count = player_data.get('cantrip_dice_rolled', 1)
        dice_str = f"{count}d{sides}"
        if total_bonus != 0:
            dice_str += f"{'+' if total_bonus > 0 else ''}{total_bonus}"
        
        if effective_crit:
            res = sum(random.randint(1, sides) for _ in range(count * 2))
            dice_str = f"{count*2}d{sides} [CRIT]"
            if total_bonus != 0: dice_str += f"{'+' if total_bonus > 0 else ''}{total_bonus}"
            return res + total_bonus, dice_str
            
        res = sum(random.randint(1, sides) for _ in range(count))
        return res + total_bonus, dice_str

    else:
        # Default (Fighter, Monk, etc.)
        dice_str = f"1d{sides}"
        if total_bonus != 0:
            dice_str += f"{'+' if total_bonus > 0 else ''}{total_bonus}"
            
        if effective_crit:
            res = random.randint(1, sides) + random.randint(1, sides)
            dice_str = f"2d{sides} [CRIT]"
            if total_bonus != 0: dice_str += f"{'+' if total_bonus > 0 else ''}{total_bonus}"
            return res + total_bonus, dice_str
            
        res = random.randint(1, sides)
        return res + total_bonus, dice_str


def combat_round(enemy_ac, attack_count, damage_die, attack_bonus, crit_on_19=False):     
    crit_range = (19, 20) if crit_on_19 else (20,)
    total_damage = 0
    results = []

    for i in range(attack_count):
        print(f"Attack {i+1}:")
        result = attack_roll(attack_bonus, enemy_ac, crit_range)
        if result['hit']:
            # damage_roll now returns (damage, dice_str)
            dmg, _ = damage_roll(damage_die, attack_bonus, critical=result['critical'])      
            total_damage += dmg
            status = 'CRITICAL HIT' if result['critical'] else 'HIT'
            print(f"  {status}! d20={result['roll']} (total {result['total']}), damage={dmg}")
        else:
            print(f"  MISS. d20={result['roll']} (total {result['total']})")
        results.append(result)

    print(f"Total damage this round: {total_damage}\n")
    return total_damage, results


def main():
    enemy_ac = int(input('Enter enemy armor class: '))
    attack_count = int(input('How many attacks this turn? '))
    damage_die = int(input('Damage die (4/6/8/10/12): '))
    proficiency = int(input('Proficiency bonus: '))
    weapon_mod = int(input('Weapon attack/damage modifier: '))
    attack_bonus = proficiency + weapon_mod
    crit_on_19 = input('Can crit on 19 (y/n)? ').strip().lower() in ('y', 'yes')

    print(f"Attack bonus: +{attack_bonus}\n")

    total_damage, _ = combat_round(enemy_ac, attack_count, damage_die, attack_bonus, crit_on_19)
    print(f"Final result: you dealt {total_damage} points of damage.")


if __name__ == '__main__':
    main()
