from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from core.players.player import classes

class ClassSelectState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        # Use manager to pick a random rest/selection background
        self.background = BackgroundManager.get_rest_bg()

        self.class_names = list(classes.keys())
        self.menu = Menu(self.class_names, font, width=250)
        self.active_menu = self.menu

    def on_select(self, option):
        self.game.player = self.create_player(option)

        from .hub import HubState
        self.game.change_state(HubState(self.game, self.font))

    def create_player(self, class_name):
        from core.players.player import apply_weapon_to_player, apply_armor_to_player
        from core.players.leveler import load_player_classes, get_class_stats_at_level
        from core.players.player_inventory import create_inventory

        # 1. Get initial class data from player_classes.json
        player_classes_data = load_player_classes()
        # Class names in the menu are likely capitalized, but keys in json might be lowercase
        class_key = class_name.lower()
        player_profile = get_class_stats_at_level(class_key, 1, player_classes_data)

        # 2. Set base attributes
        player_profile['class'] = class_key
        player_profile['xp'] = 0
        player_profile['level'] = 1
        player_profile['max_hp'] = player_profile.get('hp', 10)
        player_profile['hp'] = player_profile['max_hp'] # Compatibility with simulator
        player_profile['current_hp'] = player_profile['max_hp'] # Compatibility with Hub/Combat
        player_profile['base_hp'] = player_profile['max_hp']

        # Mana/MP for casters
        caster_classes = ["wizard", "druid", "alchemist", "sorcerer"]
        if class_key in caster_classes:
            player_profile['max_mp'] = 1
            player_profile['current_mp'] = 1
        else:
            player_profile['max_mp'] = 0
            player_profile['current_mp'] = 0
        
        # Track class levels for multiclassing support (used by leveler)
        player_profile['class_levels'] = {class_key: 1}

        # 3. Apply equipment stats
        apply_weapon_to_player(player_profile)
        apply_armor_to_player(player_profile)

        # 4. Initialize inventory
        player_inventory = create_inventory(player_profile)
        player_profile['inventory_ref'] = player_inventory
        
        # 5. Initialize other tracking stats
        player_profile['rest_count'] = 0

        return player_profile

    def draw(self, screen):
        super().draw(screen)
        width, height = screen.get_size()

        from interfaces.pygame.ui.panel import draw_text_outlined
        title_str = "Choose Your Class"
        tw, th = self.font.size(title_str)
        draw_text_outlined(screen, title_str, self.font, (255, 255, 255), width // 2 - tw // 2, 50)
