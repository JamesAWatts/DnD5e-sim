from core.combat.reward_calculator import calculate_combat_rewards

class CombatResolver:
    """
    Handles the resolution of combat outcomes, including reward distribution
    and inventory management.
    """
    @staticmethod
    def apply_victory_rewards(game_instance, party, enemies, dialogue_mgr):
        """
        Calculates and applies XP, Gold, and items to the game state.
        Queues victory narrative to the dialogue manager.
        """
        from core.combat.push_luck import PushLuckManager
        
        # 1. Calculate base rewards using the reward calculator
        rewards = calculate_combat_rewards(enemies)
        
        # 2. Apply "Push Your Luck" bonuses
        multiplier = PushLuckManager.get_bonus_multiplier(game_instance.consecutive_combats)
        xp_gain = int(rewards['total_xp'] * multiplier)
        gold_gain = int(rewards['total_gold'] * multiplier)
        items_gained = rewards['items']
        
        # 3. Build and Queue Dialogue Messages
        victory_msgs = ["VICTORY! All enemies defeated."]
        
        # Streak messages and item rewards
        PushLuckManager.process_consecutive_rewards(game_instance, dialogue_mgr)
        
        victory_msgs.append(f"Gained {xp_gain} XP and {gold_gain} Gold.")
        
        if items_gained:
            item_list = ", ".join([i.replace('_', ' ').title() for i in items_gained])
            victory_msgs.append(f"Found Loot: {item_list}")
            
        dialogue_mgr.queue_message(victory_msgs)

        # 4. Filter Party (Remove Summons)
        # We modify the list in-place because it is a reference shared with game_instance.party
        summons = [p for p in party if p.get('is_summon')]
        for s in summons:
            party.remove(s)
            # Reset summon_active flag on owners
            owner_id = s.get('owner_id')
            if owner_id:
                for p in party:
                    if p.get('id') == owner_id:
                        p['summon_active'] = False

        # 5. Update party data (XP distribution)
        for p in party:
            p['xp'] = p.get('xp', 0) + xp_gain
            
        # 6. Update Bestiary RP
        # Calculate RP to award per defeated enemy based on total party level (Alpha Scaling)
        party_lvl = sum(p.get('level', 1) for p in party)
        if party_lvl <= 10:
            rp_to_award = 1
        elif party_lvl <= 20:
            rp_to_award = 2
        elif party_lvl <= 30:
            rp_to_award = 3
        elif party_lvl <= 40:
            rp_to_award = 4
        elif party_lvl <= 50:
            rp_to_award = 5
        else:
            rp_to_award = 6
        
        for enemy in enemies:
            if enemy.get('current_hp', 0) <= 0:
                # Use base_name (exact JSON key) as the identifier for bestiary
                et = enemy.get('base_name', enemy.get('enemy_type', enemy.get('name', 'enemy').lower().replace(' ', '_')))
                game_instance.bestiary_rp[et] = game_instance.bestiary_rp.get(et, 0) + rp_to_award

        # 7. Update inventory (Gold and Items)
        game_instance.inventory['gold'] = game_instance.inventory.get('gold', 0) + gold_gain
        
        if items_gained:
            # Ensure 'junk' category exists
            if 'junk' not in game_instance.inventory:
                game_instance.inventory['junk'] = {}
                
            for item in items_gained:
                game_instance.inventory['junk'][item] = game_instance.inventory['junk'].get(item, 0) + 1
        
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
