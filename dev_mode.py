import pygame
import random

class DevTools:
    @staticmethod
    def apply_dev_action(action, game):
        """
        Applies a developer tool action to the game state.
        """
        p = game.player
        
        if action == "1,000 HP":
            p["max_hp"] = 1000
            p["current_hp"] = 1000
            p["hp"] = 1000 # Compat
            return "HP set to 1,000!"

        elif action == "10,000 Gold":
            inv = p.get("inventory_ref", {})
            inv["gold"] = inv.get("gold", 0) + 10000
            return "Added 10,000 Gold!"

        elif action == "Level Up":
            from core.players.leveler import xp_to_next_level
            from states.level_up import LevelUpState
            
            # Level up everyone in the party for dev mode
            for char in game.party:
                current_level = char.get('level', 1)
                char['xp'] = xp_to_next_level(current_level)
            
            game.change_state(LevelUpState(game, pygame.font.SysFont("Arial", 32), is_dev_mode=True))
            return "Party Level Up Triggered!"

        elif action == "RP+":
            # Add 25 RP to all categories in the bestiary
            categories = ['beast', 'dragon', 'fae', 'goblinoid', 'humanoid', 'undead']
            for cat in categories:
                game.bestiary_rp[cat] = game.bestiary_rp.get(cat, 0) + 25
            return "Added 25 RP to all categories!"

        elif action == "Max Level":
            from core.players.leveler import recalculate_stats
            from core.players.player import validate_player_data
            
            for char in game.party:
                char['xp'] = 300000
                char['level'] = 20
                # Assign 20 levels to their primary class
                primary_class = char.get('class', 'fighter').lower()
                char['class_levels'] = {primary_class: 20}
                
                recalculate_stats(char)
                validate_player_data(char)
                
                # Full Heal
                char['current_hp'] = char['max_hp']
                char['hp'] = char['max_hp']
                char['current_mp'] = char.get('max_mp', 0)
                char['current_sp'] = char.get('max_sp', 0)
                
            return "All party members set to Level 20!"

        elif action == "Restart Game":
            from states.class_select import ClassSelectState
            game.player = None
            game.change_state(ClassSelectState(game, pygame.font.SysFont("Arial", 32)))
            return "Game Restarted!"

        return None
