import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.game_rules.save_manager import SaveManager

def test_autosave_logic():
    print("Testing Autosave Logic...")
    
    # Mock load_game_data
    original_load = SaveManager.load_game_data
    
    try:
        # Scenario 1: Slot 1 is empty
        SaveManager.load_game_data = MagicMock(side_effect=lambda slot: None if slot == 1 else {"name": "Other"})
        slot = SaveManager.find_autosave_slot("Player")
        print(f"Scenario 1 (Slot 1 empty): Expected 1, Got {slot}")
        assert slot == 1

        # Scenario 2: Slot 1 is "Other", Slot 2 is "Player"
        SaveManager.load_game_data = MagicMock(side_effect=lambda slot: {"name": "Other"} if slot == 1 else ({"name": "Player"} if slot == 2 else None))
        slot = SaveManager.find_autosave_slot("Player")
        print(f"Scenario 2 (Slot 2 matches): Expected 2, Got {slot}")
        assert slot == 2

        # Scenario 3: All slots "Other"
        SaveManager.load_game_data = MagicMock(return_value={"name": "Other"})
        slot = SaveManager.find_autosave_slot("Player")
        print(f"Scenario 3 (All occupied): Expected None, Got {slot}")
        assert slot is None

        # Scenario 4: All slots empty
        SaveManager.load_game_data = MagicMock(return_value=None)
        slot = SaveManager.find_autosave_slot("Player")
        print(f"Scenario 4 (All empty): Expected 1, Got {slot}")
        assert slot == 1

        print("\nAll tests passed successfully!")
        
    except AssertionError as e:
        print(f"\nTest failed!")
        raise e
    finally:
        SaveManager.load_game_data = original_load

if __name__ == "__main__":
    test_autosave_logic()
