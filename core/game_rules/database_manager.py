import json
import os
import sys
from core.game_rules.path_utils import get_resource_path

class DatabaseManager:
    """
    Singleton manager for pre-loading and caching JSON data.
    Optimized for WebAssembly to avoid repeated synchronous disk reads.
    """
    _instance = None
    _data = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Pre-loads all critical JSON files into memory."""
        print("[DB] Initializing Database Manager...")
        
        # Combat Data
        self._data['skills'] = self._load_json('combat', 'skills.json', 'skill_list')
        self._data['spells'] = self._load_json('combat', 'spells.json', 'spell_list')
        self._data['summons'] = self._load_json('combat', 'summons.json', 'summon_list')
        self._data['enemy_abilities'] = self._load_json('combat', 'enemy_abilities.json', 'ability_list')
        self._data['combat_effects'] = self._load_json('combat', 'combat_effects.json')

        # Items Data
        self._data['weapons'] = self._load_json('items', 'weapons.json', 'weapon_list')
        self._data['armor'] = self._load_json('items', 'armor.json', 'armor_list')
        self._data['shields'] = self._load_json('items', 'shields.json', 'shield_list')
        self._data['trinkets'] = self._load_json('items', 'trinkets.json', 'trinket_list')
        self._data['consumables'] = self._load_json('items', 'consumables.json', 'consumable_list')

        # Player Data
        self._data['classes'] = self._load_json('players', 'player_classes.json')
        self._data['xp_table'] = self._load_json('players', 'xp_table.json')

        # Creatures (Categories)
        self._data['creatures'] = {}
        for cat in ['beast', 'dragon', 'fae', 'goblinoid', 'humanoid', 'undead']:
            self._data['creatures'][cat] = self._load_json('creatures', f'{cat}.json')

        print("[DB] Initialization Complete.")

    def _load_json(self, folder, filename, root_key=None):
        """Helper to load a JSON file with error handling."""
        path = get_resource_path(os.path.join('data', folder, filename))
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                if root_key:
                    return data.get(root_key, {})
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[DB] WARNING: Failed to load {path}. Error: {e}")
            return {}

    def get_data(self, key, subkey=None):
        """Retrieves cached data."""
        base = self._data.get(key, {})
        if subkey:
            return base.get(subkey, {})
        return base

    def get_skills(self): return self.get_data('skills')
    def get_spells(self): return self.get_data('spells')
    def get_enemy_abilities(self): return self.get_data('enemy_abilities')
    def get_summons(self): return self.get_data('summons')
    def get_weapons(self): return self.get_data('weapons')
    def get_armor(self): return self.get_data('armor')
    def get_shields(self): return self.get_data('shields')
    def get_trinkets(self): return self.get_data('trinkets')
    def get_consumables(self): return self.get_data('consumables')
    def get_classes(self): return self.get_data('classes')
    def get_creatures(self, category): return self.get_data('creatures', category)

# Global instance for easy access
db = DatabaseManager()
