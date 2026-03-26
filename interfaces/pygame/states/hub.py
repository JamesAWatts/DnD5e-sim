from .base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager

class HubState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)

        # Get persistent hub background from manager
        self.background = BackgroundManager.get_hub_bg(game.player)

        options = ["Fight", "Shop", "Rest", "Inventory", "Retire"]
        if game.god_mode:
            options += ["Level Up", "Invincible"]

        self.menu = Menu(options, font, width = 50)
        self.active_menu = self.menu

    def on_select(self, option):
        if option == "Fight":
            from interfaces.cli.main import load_enemy_data, get_scaled_enemy
            enemy_data = load_enemy_data()
            enemy_name, enemy_profile = get_scaled_enemy(enemy_data, self.game.player.get('level', 1))
            
            # Prepare enemy for combat
            e_profile = enemy_profile.copy()
            e_profile["name"] = enemy_name.title()
            self.game.enemies = [e_profile]

            from .combat import CombatState
            self.game.change_state(CombatState(self.game, self.font))

        elif option == "Shop":
            from .shop_state import ShopState
            self.game.change_state(ShopState(self.game, self.font))

        elif option == "Inventory":
            from .inventory_state import InventoryState
            self.game.change_state(InventoryState(self.game, self.font))

        elif option == "Retire":
            from .game_over import GameOverState
            self.game.change_state(GameOverState(self.game, self.font, retired=True))

        elif option == "Rest":
            p = self.game.player

            # Ensure inventory_ref actually exists
            if "inventory_ref" not in p:
                print("DEBUG: No inventory_ref found on player!")
                return

            inv = p["inventory_ref"]  # ✅ direct reference

            cost = 5 + p.get("rest_count", 0)

            if self.game.god_mode or inv.get("gold", 0) >= cost:
                if not self.game.god_mode:
                    inv["gold"] -= cost

                # Heal player
                p["current_hp"] = p.get("max_hp", 10)
                p["current_mp"] = p.get("max_mp", 0)

                # Track usage
                p["rest_count"] = p.get("rest_count", 0) + 1

                print(f"DEBUG: Rested! HP/MP restored. Gold now: {inv.get('gold', 0)}")
            else:
                print("DEBUG: Not enough gold to rest")

    def draw(self, screen):
        # --- Draw background FIRST ---
        self.draw_background(screen)

        width, height = screen.get_size()

        from interfaces.pygame.ui.panel import draw_text_outlined
        from core.game_rules.constants import scale_x, scale_y, COLOR_BLUE

        # --- Title ---
        title_str = "Adventure Hub"
        tw, th = self.font.size(title_str)
        draw_text_outlined(
            screen,
            title_str,
            self.font,
            (255, 255, 255),
            width // 2 - tw // 2,
            scale_y(40)
        )

        # --- Player Bars (Top Left) ---
        from interfaces.pygame.ui.bars import draw_bar

        p = self.game.player
        if p:
            px = scale_x(40)
            py = scale_y(40)

            # HP Bar
            draw_bar(
                screen,
                px,
                py,
                scale_x(200),
                scale_y(25),
                p.get("current_hp", p.get("hp", 10)),
                p.get("max_hp", 10),
                (200, 50, 50),
                self.font
            )

            # MP Bar
            if p.get("max_mp", 0) > 0:
                draw_bar(
                    screen,
                    px,
                    py + scale_y(35),
                    scale_x(200),
                    scale_y(25),
                    p.get("current_mp", 0),
                    p.get("max_mp", 0),
                    COLOR_BLUE,
                    self.font
                )

        # --- MENU (Bottom Center) ---
        if self.active_menu:
            menu_height = len(self.active_menu.options) * scale_y(30) + scale_y(10)
            menu_center_x = width // 2
            menu_start_y = height - menu_height - scale_y(10)
            # Auto-size based on longest option
            
            self.active_menu.draw(screen, menu_center_x, menu_start_y)
