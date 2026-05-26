import json
import os
from .storage_adapter import StorageManager

class SaveManager:
    # Initialize the adapter instance
    _storage = StorageManager()

    @staticmethod
    def save_game(slot, party, inventory=None, battle_counter=0, bestiary_rp=None):
        # Ensure it's a list
        if not isinstance(party, list):
            party = [party]

        lead = party[0] if party else {}
        
        # If inventory is not provided, try to get it from the lead's ref
        if inventory is None and lead:
            inventory = lead.get('inventory_ref', {})

        raw_save_data = {
            "is_party_save": True,
            "party": party,
            "inventory": inventory, # Global Inventory
            "battle_counter": battle_counter,
            "bestiary_rp": bestiary_rp or {},
            "name": lead.get('name', 'Unknown'),
            "level": lead.get('level', 1)
        }
        
        # Use StorageManager to serialize and save
        return SaveManager._storage.save(slot, raw_save_data)

    @staticmethod
    def load_game_data(slot):
        """Returns the full save dictionary or None."""
        return SaveManager._storage.load(slot)

    @staticmethod
    def load_game(slot):
        data = SaveManager.load_game_data(slot)
        if not data:
            return None
            
        # Check for new party format
        if isinstance(data, dict) and data.get("is_party_save"):
            party = data.get("party", [])
            # Fallback to lead player's inventory_ref if global inventory is missing
            inventory = data.get("inventory")
            if inventory is None and party:
                inventory = party[0].get('inventory_ref', {})
            
            if inventory is None:
                inventory = {
                    'gold': 0, 'weapon': {}, 'armor': {}, 'shield': {},
                    'trinket': {}, 'consumable': {}, 'junk': {}, 'key_items': {}
                }

            # --- Stat Synchronization & Clamping ---
            from core.players.player import validate_player_data
            
            for p in party:
                # 1. Sync inventory reference
                p['inventory_ref'] = inventory
                
                # 2. Capture saved resources
                saved_hp = p.get('current_hp', p.get('hp', 10))
                saved_mp = p.get('current_mp', 0)
                saved_sp = p.get('current_sp', 0)
                
                # 3. Recalculate stats based on current class/level/gear
                validate_player_data(p)
                
                # 4. Restore and clamp saved values (Prevents reloading from healing the player)
                p['current_hp'] = min(saved_hp, p.get('max_hp', 10))
                p['hp'] = p['current_hp'] # Sync legacy hp key
                p['current_mp'] = min(saved_mp, p.get('max_mp', 0))
                p['current_sp'] = min(saved_sp, p.get('max_sp', 0))

            return party
        # Old single-player save (directly a dict)
        elif isinstance(data, dict):
            # For very old saves, the dict IS the player.
            inventory = data.get('inventory_ref', {
                'gold': 0, 'weapon': {}, 'armor': {}, 'shield': {},
                'trinket': {}, 'consumable': {}, 'junk': {}, 'key_items': {}
            })
            
            from core.players.player import validate_player_data
            data['inventory_ref'] = inventory
            
            saved_hp = data.get('current_hp', data.get('hp', 10))
            saved_mp = data.get('current_mp', 0)
            saved_sp = data.get('current_sp', 0)
            
            validate_player_data(data)
            
            data['current_hp'] = min(saved_hp, data.get('max_hp', 10))
            data['hp'] = data['current_hp']
            data['current_mp'] = min(saved_mp, data.get('max_mp', 0))
            data['current_sp'] = min(saved_sp, data.get('max_sp', 0))
            
            return [data]
        return None

    @staticmethod
    def get_slot_info(slot):
        # We need the raw data for slot info to be efficient, or just use load_game
        # load_game now returns a list of players
        party = SaveManager.load_game(slot)
        if not party:
            return "Empty Slot"
        
        lead = party[0] if party else {}
        name = lead.get('name', 'Unknown')
        level = lead.get('level', 1)
        party_size = len(party)
        size_str = f" (Party: {party_size})" if party_size > 1 else ""
        return f"{name}, Level {level}{size_str}"

    @staticmethod
    def delete_save(slot):
        return SaveManager._storage.delete(slot)
