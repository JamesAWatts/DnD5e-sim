from core.combat.reward_calculator import calculate_combat_rewards

class CombatResolver:
    """
    Handles the resolution of combat outcomes, including reward distribution
    and inventory management.
    """
    @staticmethod
    def apply_combat_rewards(game_instance, party, enemies, dialogue_mgr, is_flee=False):
        """
        Calculates and applies XP, Gold, and items to the game state.
        Supports both full victory and successful flee (only dead enemies).
        """
        from core.combat.push_luck import PushLuckManager
        
        # 0. Filter for dead enemies only
        dead_enemies = [e for e in enemies if e.get('current_hp', 0) <= 0]
        if not dead_enemies:
            if is_flee:
                dialogue_mgr.queue_message("Escaped with no kills. No rewards gained.")
            return None

        # 1. Calculate base rewards for ONLY dead enemies
        rewards = calculate_combat_rewards(dead_enemies)
        
        # 2. Apply "Push Your Luck" bonuses
        multiplier = PushLuckManager.get_bonus_multiplier(game_instance.consecutive_combats)
        xp_gain = int(rewards['total_xp'] * multiplier)
        gold_gain = int(rewards['total_gold'] * multiplier)
        items_gained = rewards['items']
        
        # 3. Build and Queue Dialogue Messages
        if is_flee:
            victory_msgs = [f"Escaped! Rewards for {len(dead_enemies)} defeated foes:"]
        else:
            victory_msgs = ["VICTORY! All enemies defeated."]
        
        # Streak messages and item rewards
        PushLuckManager.process_consecutive_rewards(game_instance, dialogue_mgr)
        
        victory_msgs.append(f"Gained {xp_gain} XP and {gold_gain} Gold.")
        
        if items_gained:
            item_list = ", ".join([i['name'].replace('_', ' ').title() for i in items_gained])
            victory_msgs.append(f"Found Loot: {item_list}")
            
        dialogue_mgr.queue_message(victory_msgs)

        # 4. Filter Party (Remove Summons)
        summons = [p for p in party if p.get('is_summon')]
        for s in summons:
            if s in party:
                party.remove(s)
            # Reset summon_active flag on owners
            owner_id = s.get('owner_id')
            if owner_id:
                for p in party:
                    if p.get('id') == owner_id:
                        p['summon_active'] = False

        # 5. Update party data (XP distribution)
        from core.players.leveler import update_xp_and_level
        for p in party:
            update_xp_and_level(p, xp_gain)
            
        # 6. Update Bestiary RP
        party_lvl = sum(p.get('level', 1) for p in party)
        if party_lvl <= 10: rp_to_award = 1
        elif party_lvl <= 20: rp_to_award = 2
        elif party_lvl <= 30: rp_to_award = 3
        elif party_lvl <= 40: rp_to_award = 4
        elif party_lvl <= 50: rp_to_award = 5
        else: rp_to_award = 6
        
        for enemy in dead_enemies:
            et = enemy.get('base_name', enemy.get('enemy_type', enemy.get('name', 'enemy').lower().replace(' ', '_')))
            game_instance.bestiary_rp[et] = game_instance.bestiary_rp.get(et, 0) + rp_to_award

        # 7. Update inventory (Gold and Items)
        game_instance.inventory['gold'] = game_instance.inventory.get('gold', 0) + gold_gain
        
        if items_gained:
            from core.players.player_inventory import add_item
            for item_info in items_gained:
                name = item_info['name']
                itype = item_info['type']
                add_item(game_instance.inventory, name, itype)
        
        # 8. Cleanse Party (Remove all status effects)
        CombatResolver.cleanse_party(party)
        
        return rewards

    @staticmethod
    def cleanse_party(party):
        """
        Removes all active effects and conditions from the party members.
        This ensures no combat-only effects persist into the Hub.
        """
        for p in party:
            p['active_effects'] = []
            p['conditions'] = {}
            
            # Clear specific combat flags
            flags_to_clear = [
                'advantage_next', 
                '_consume_advantage_next', 
                'summon_active', 
                'summon_alive',
                'hp_buff',
                'advantage',
                'disadvantage'
            ]
            for flag in flags_to_clear:
                if flag in p:
                    del p[flag]
