from .player import validate_player_data

def get_party_level(party):
    """Calculates the total combined level of the party."""
    return sum(p.get('level', 1) for p in party)

def get_mercenary_starting_level(party_level):
    """Determines the starting level for newly hired mercenaries based on party progression."""
    if party_level >= 46: return 15
    elif party_level >= 31: return 10
    elif party_level >= 16: return 5
    elif party_level >= 6: return 3
    return 1

def get_rest_cost(party):
    """Rest cost scales with individual member levels (5g per level)."""
    return sum([5 * p.get('level', 1) for p in party])

def get_hire_cost(party_level):
    """Hire cost is 100g per level of the mercenary."""
    lvl = get_mercenary_starting_level(party_level)
    return lvl * 100

def get_feast_cost(party):
    """Feast cost is 100g per party member."""
    return len(party) * 100

def get_rumor_cost():
    """Flat cost for rumors."""
    return 50

def get_respec_cost():
    """Flat cost for respec training."""
    return 500

def apply_rest(game_manager):
    """
    Executes the rest logic: resets consecutive combats, restores all resources,
    and clears temporary buffs like feast bonuses or grind stones.
    """
    from core.combat.push_luck import PushLuckManager
    PushLuckManager.reset_streak(game_manager)
    
    party = game_manager.party
    lead = game_manager.player
    
    if lead and 'tavern_stats' in lead:
        lead['tavern_stats']['feast_used'] = False
        
    for p in party:
        p["current_hp"] = p.get("max_hp", 10)
        p["current_mp"] = p.get("max_mp", 0)
        p["current_sp"] = p.get("max_sp", 0)
        # Reset temporary buffs
        p['weapon_bonus'] = 0
        p['feast_bonus'] = 0
        p['hp_buff'] = 0
        validate_player_data(p)
        
    if lead:
        lead["rest_count"] = lead.get("rest_count", 0) + 1
    return "The party rests peacefully. All limits and temporary buffs reset."

def apply_feast(party, party_level):
    """
    Applies the feast buff to all party members. 
    Restores resources and provides a level-scaled HP buff and stat bonus.
    """
    # Feast scaling: Level 26 (base), 41 (+1), 51 (+2)
    mult = 5
    stat_bonus = 0
    if party_level >= 51:
        mult = 15
        stat_bonus = 2
    elif party_level >= 41:
        mult = 10
        stat_bonus = 1
        
    for p in party:
        p['current_hp'] = p.get('max_hp', 10)
        p['current_mp'] = p.get('max_mp', 0)
        p['current_sp'] = p.get('max_sp', 0)
        p['hp_buff'] = mult * p.get('level', 1)
        p['feast_bonus'] = stat_bonus
        
    msg = "The party feasts sumptuously."
    if stat_bonus > 0:
        msg += f" Everyone feels significantly tougher and more capable (+{stat_bonus} to stats)!"
    else:
        msg += " Everyone feels significantly tougher!"
    return msg

def get_rumor_info(game_manager):
    """
    Generates information about upcoming enemies.
    Returns (list of enemy types, encounter data).
    """
    from core.creatures.enemies import get_scaled_enemies
    import math
    
    party = game_manager.party
    total_level = get_party_level(party)
    party_size = len(party)
    encounter_level = math.ceil(total_level - (party_size / 2) + 1)
    
    next_enemies, category = get_scaled_enemies(encounter_level, 
                                              battle_count=game_manager.battle_counter + 1,
                                              party_size=party_size)
    types = [category]
    
    return types, next_enemies
