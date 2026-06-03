import json
import os
import random
from core.game_rules.path_utils import get_resource_path

from core.game_rules.database_manager import db

def load_enemy_data(category=None):
    """
    Loads enemy data from DatabaseManager cache. 
    """
    if category:
        return db.get_creatures(category)
    else:
        # Fallback to humanoid if no category provided
        return db.get_creatures('humanoid')

def get_scaled_enemies(player_level=1, battle_count=0, category=None, party_size=1):
    """
    Phased Budget Encounter System:
    PHASE 1: CATEGORY selection.
    PHASE 2: BUDGET determination.
    PHASE 3: LEADER selection (Every 5th battle).
    PHASE 4: MINION filling.
    PHASE 5: DENSITY check (Ensures at least 1 enemy per 2 party members).
    """
    # PHASE 1: CATEGORY
    if category is None:
        category_map = {
            1: 'beast',
            2: 'dragon',
            3: 'fae',
            4: 'goblinoid',
            5: 'humanoid',
            6: 'undead'
        }
        cat_roll = random.randint(1, 6)
        category = category_map[cat_roll]
    
    enemy_data = load_enemy_data(category)
    if not enemy_data:
        # Fallback to humanoid if chosen cat is empty
        enemy_data = load_enemy_data('humanoid')
        category = 'humanoid'

    all_enemies = list(enemy_data.items())
    
    # PHASE 2: BUDGET
    budget = player_level
    min_density = max(1, party_size // 2)
    encounter = []

    # Decide if this is a Boss Fight (Every 5th battle)
    is_boss_fight = (battle_count > 0 and battle_count % 5 == 0)

    if is_boss_fight:
        # PHASE 3: LEADER (Boss)
        # Rule: (2*budget)/3 to get leader_floor, then pick one between floor and budget
        leader_floor = (2 * budget) // 3
        eligible_leaders = [e for e in all_enemies if leader_floor <= e[1].get('level', 1) <= budget]
        
        if not eligible_leaders:
            eligible_leaders = sorted([e for e in all_enemies if e[1].get('level', 1) <= budget], 
                                     key=lambda x: x[1].get('level', 1), reverse=True)[:3]
            
        if not eligible_leaders:
            humanoid_data = load_enemy_data('humanoid')
            eligible_leaders = [list(humanoid_data.items())[0]]

        l_name, l_stats = random.choice(eligible_leaders)
        leader = l_stats.copy()
        leader['base_name'] = l_name
        leader['name'] = l_name.replace('_', ' ').title()
        leader['is_leader'] = True
        leader['category'] = category
        
        encounter.append(leader)
        current_budget = budget - leader.get('level', 1)
    else:
        # NO LEADER PHASE - Just Minions
        current_budget = budget

    # PHASE 4: MINIONS
    # Fill remaining budget with up to 7 more minions (max 8 total)
    max_enemies = 8
    # SAFETY: Sort affordable to avoid checking non-affordable in a tight loop if logic fails
    all_enemies_sorted = sorted(all_enemies, key=lambda x: x[1].get('level', 1))
    
    while current_budget > 0 and len(encounter) < max_enemies:
        affordable = [e for e in all_enemies_sorted if e[1].get('level', 1) <= current_budget]
        if not affordable:
            break
            
        m_name, m_stats = random.choice(affordable)
        # Ensure we are actually reducing budget or meeting a termination condition
        m_lvl = max(1, m_stats.get('level', 1))
        
        minion = m_stats.copy()
        minion['base_name'] = m_name
        minion['name'] = m_name.replace('_', ' ').title()
        minion['is_leader'] = False
        minion['category'] = category
        
        encounter.append(minion)
        current_budget -= m_lvl

    # PHASE 5: DENSITY CHECK
    # If the budget ran out but we haven't met minimum density, force-spawn low-cost fillers.
    if len(encounter) < min_density:
        # Get tier 1 (Level 1) enemies for this category
        tier_1 = [e for e in all_enemies if e[1].get('level', 1) <= 1]
        if not tier_1:
            # Absolute fallback: Sort by level and take the weakest 3
            tier_1 = sorted(all_enemies, key=lambda x: x[1].get('level', 1))[:3]
            
        while len(encounter) < min_density and len(encounter) < max_enemies:
            m_name, m_stats = random.choice(tier_1)
            minion = m_stats.copy()
            minion['base_name'] = m_name
            minion['name'] = m_name.replace('_', ' ').title()
            minion['is_leader'] = False
            minion['category'] = category
            encounter.append(minion)
            print(f"[DEBUG] Density rule forced spawn: {m_name}")

    # Safety check: if somehow empty, add at least one
    if not encounter:
        m_name, m_stats = all_enemies[0]
        minion = m_stats.copy()
        minion['base_name'] = m_name
        minion['name'] = m_name.replace('_', ' ').title()
        minion['is_leader'] = False
        minion['category'] = category
        encounter.append(minion)

    battle_type = "BOSS" if is_boss_fight else "STANDARD"
    print(f"[DEBUG] Generated {battle_type} encounter (Battle #{battle_count}) from '{category}' category. Budget: {budget}, Density: {len(encounter)}")
    return encounter, category
