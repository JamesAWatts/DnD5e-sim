class ManaCheck:
    @staticmethod
    def get_disabled_spell_indices(current_mana, spell_list, spells_db):
        """
        Returns a list of indices of spells that the player cannot afford.
        spell_list: List of spell names the player has.
        spells_db: Dictionary containing spell data (keyed by lower_case_name).
        """
        disabled_indices = []
        for i, spell_name in enumerate(spell_list):
            spell_key = spell_name.lower().replace(" ", "_")
            spell_data = spells_db.get(spell_key)
            if spell_data:
                # Assuming 'level' is the mana cost as per user request
                mana_cost = spell_data.get("level", 0)
                if current_mana < mana_cost:
                    disabled_indices.append(i)
        return disabled_indices

    @staticmethod
    def can_cast(current_mana, spell_name, spells_db):
        """
        Returns True if the player can afford the spell, False otherwise.
        """
        spell_key = spell_name.lower().replace(" ", "_")
        spell_data = spells_db.get(spell_key)
        if spell_data:
            mana_cost = spell_data.get("level", 0)
            return current_mana >= mana_cost
        return True # If spell not found, assume free or handled elsewhere
