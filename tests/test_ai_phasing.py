import json
import os
import sys
import random

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.combat.combat_ai import CombatAI

def test_skeleton_turn_1():
    print("\n--- Testing Skeleton Turn 1 (Bone Toss) ---")
    # Skeleton is level 1, starting SP should be (1+3)//4 = 1
    # Turn 1 regen +1 = 3 SP (if starting at 2). Bone Toss cost is 3.
    enemy = {
        "name": "skeleton",
        "level": 1,
        "hp": 6, "max_hp": 6, "current_hp": 6,
        "skills": ["bone_toss"],
        "spells": [],
        "current_sp": 2, "max_sp": 10,
        "current_mp": 1, "max_mp": 10,
        "heal_available": True
    }
    
    # Phase 1: Standby Regen
    enemy['current_sp'] += 1
    enemy['current_mp'] += 1
    
    print(f"Skeleton resources after regen: SP={enemy['current_sp']}")
    
    action = CombatAI.decide_action(enemy)
    print(f"Skeleton Action: {action['type']} - {action.get('name', 'N/A')}")
    
    assert action['type'] == 'ability'
    assert action['name'] == 'bone_toss'
    print("SUCCESS: Skeleton used Bone Toss immediately.")

def test_medusa_priority():
    print("\n--- Testing Medusa Priority (Spell vs Skill) ---")
    # Medusa level 12, starting resources (12+3)//4 = 3
    # Turn 1 regen +1 = 4 SP / 4 MP
    # Petrifying Gaze (Spell) cost 4, Poison Strike (Skill) cost 2
    # Both ready, should pick Gaze (Higher cost)
    enemy = {
        "name": "medusa",
        "level": 12,
        "hp": 155, "max_hp": 155, "current_hp": 155,
        "skills": ["poison_strike"],
        "spells": ["petrifying_gaze"],
        "current_sp": 3, "max_sp": 10,
        "current_mp": 3, "max_mp": 10,
        "heal_available": True
    }
    
    enemy['current_sp'] += 1
    enemy['current_mp'] += 1
    
    action = CombatAI.decide_action(enemy)
    print(f"Medusa Action (both ready): {action.get('name')}")
    assert action['name'] == 'petrifying_gaze'
    print("SUCCESS: Medusa prioritized higher cost spell.")

def test_healing_priority():
    print("\n--- Testing Healing Phase ---")
    # Harpy level 3, heal_available=True, HP <= 50%
    enemy = {
        "name": "harpy",
        "level": 3,
        "hp": 24, "max_hp": 24, "current_hp": 12, # 50%
        "skills": ["screech"],
        "spells": ["lesser_heal"],
        "current_sp": 5, "max_sp": 10,
        "current_mp": 5, "max_mp": 10,
        "heal_available": True
    }
    
    action = CombatAI.decide_action(enemy)
    print(f"Harpy Action (HP 50%): {action.get('name')}")
    assert action['name'] == 'lesser_heal'
    assert enemy['heal_available'] == False
    
    # Next turn, heal should be unavailable even if low HP
    action2 = CombatAI.decide_action(enemy)
    print(f"Harpy Action (Next Turn, HP 50%): {action2.get('name')}")
    assert action2['name'] != 'lesser_heal'
    print("SUCCESS: Healing prioritized and consumed correctly.")

def test_resource_saving():
    print("\n--- Testing Phase 5 (Saving for Plan) ---")
    # Goblin level 2, Heavy Strikes cost 1, but let's mock it as cost 5
    enemy = {
        "name": "goblin",
        "level": 2,
        "hp": 10, "max_hp": 10, "current_hp": 10,
        "skills": ["heavy_strikes"],
        "spells": [],
        "current_sp": 0, "max_sp": 10,
        "current_mp": 0, "max_mp": 10,
        "heal_available": True
    }
    
    # Mock ability cost to 5
    original_get_data = CombatAI.get_ability_data
    def mock_get_data(name):
        data = original_get_data(name).copy()
        if name == 'heavy_strikes': data['cost'] = 5
        return data
    
    CombatAI.get_ability_data = mock_get_data
    
    # Turn 1: Regen to 1 SP. Need 5. Should attack.
    enemy['current_sp'] += 1
    action = CombatAI.decide_action(enemy)
    print(f"Goblin Action (1/5 SP): {action['type']}")
    assert action['type'] == 'attack'
    
    # Restore original method
    CombatAI.get_ability_data = original_get_data
    print("SUCCESS: Goblin saved resources correctly.")

if __name__ == "__main__":
    try:
        test_skeleton_turn_1()
        test_medusa_priority()
        test_healing_priority()
        test_resource_saving()
        print("\nALL AI PHASING TESTS PASSED!")
    except AssertionError as e:
        print(f"\nTEST FAILED!")
        sys.exit(1)
    except Exception as e:
        print(f"\nAN ERROR OCCURRED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
