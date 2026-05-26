import random

class PushLuckManager:
    """
    Manages the 'Push Your Luck' mechanic, providing bonuses for consecutive victories
    without resting.
    """
    
    @staticmethod
    def get_bonus_multiplier(consecutive_combats):
        """Calculates the XP and Gold multiplier based on consecutive wins."""
        if consecutive_combats <= 1:
            return 1.0
        # 10% bonus per combat after the first, capped at 50%
        return 1.0 + min(0.5, (consecutive_combats - 1) * 0.1)

    @staticmethod
    def process_consecutive_rewards(game_instance, dialogue_mgr):
        """
        Handles the distribution of bonus items and messages based on consecutive wins.
        """
        from core.players.player_inventory import add_item
        
        cc = game_instance.consecutive_combats
        if cc < 2:
            return

        bonus_percent = int((PushLuckManager.get_bonus_multiplier(cc) - 1) * 100)
        dialogue_mgr.queue_message(f"Consecutive Battle #{cc}! Bonus: +{bonus_percent}%")

        inv = game_instance.inventory
        
        # CC 3+: Random Potion
        if cc >= 3:
            potions = ["healing_potion", "mana_potion", "stamina_potion"]
            p = random.choice(potions)
            add_item(inv, p, "consumable")
            dialogue_mgr.queue_message(f"Streak Reward: {p.replace('_',' ').title()}!")

        # CC 4+: Grind Stone
        if cc >= 4:
            add_item(inv, "grind_stone", "consumable")
            dialogue_mgr.queue_message("Streak Reward: Grind Stone!")

        # CC 6+: Random Junk Item (Valuable)
        if cc >= 6:
            # Note: Best to avoid heavy file I/O here, but keeping logic consistent with legacy
            from core.game_rules.path_utils import get_resource_path
            import os
            import json
            
            try:
                # Approximate value based on current encounter difficulty if possible, 
                # but we'll use a standard high-tier junk logic.
                path = get_resource_path(os.path.join('data', 'items', 'junk.json'))
                with open(path, 'r') as f:
                    db = json.load(f).get('junk_list', {})
                
                # Filter for items that feel like a "reward"
                valid = [k for k, v in db.items() if v.get('cost', 0) >= 100]
                if valid:
                    j = random.choice(valid)
                    add_item(inv, j, "junk")
                    dialogue_mgr.queue_message(f"Streak Reward: {j.replace('_',' ').title()}!")
            except Exception as e:
                print(f"PushLuck Error: Could not load junk rewards: {e}")

    @staticmethod
    def reset_streak(game_instance):
        """Resets the consecutive combat counter (called when resting)."""
        game_instance.consecutive_combats = 0
