from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.backgrounds import BackgroundManager
from core.players.player import load_weapons, load_armor, apply_weapon_to_player, apply_armor_to_player
from core.players.shop import load_consumables

class ShopState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_shop_bg()

        self.inventory = game.player.get("inventory_ref", {})
        if not self.inventory:
             self.inventory = game.player.get("inventory", {})

        self.mode = "MAIN"
        self.item_map = {}
        self.buy_category = None
        self.current_page = 0
        self.items_per_page = 10

        self.main_menu = Menu(["Buy", "Sell", "Back"], font, width=200, header="The Dragon's Hoard")
        self.active_menu = self.main_menu

    def refresh_buy_menu(self):
        options = ["Weapons", "Armor", "Consumables", "Back"]
        self.active_menu = Menu(options, self.font, width=200, header="What are you looking for?")

    def open_buy_category(self, category):
        if category == "weapons":
            data = load_weapons().get("weapon_list", {})
        elif category == "armor":
            data = load_armor()
        elif category == "consumables":
            data = load_consumables()
        else:
            return

        available = {k: v for k, v in data.items() if v.get('cost', 0) > 0}
        all_keys = sorted(available.keys())
        
        total_pages = (len(all_keys) + self.items_per_page - 1) // self.items_per_page
        if self.current_page >= total_pages: self.current_page = 0
        if self.current_page < 0: self.current_page = total_pages - 1

        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_keys = all_keys[start_idx:end_idx]

        options = []
        self.item_map = {}
        for k in page_keys:
            item = available[k]
            display_name = item.get('name', k.replace('_', ' ')).title()
            full_display = f"{display_name} ({item['cost']}g)"
            options.append(full_display)
            self.item_map[full_display] = k
            
        # Add Pagination/Footer options
        if total_pages > 1:
            options.append("Next Page")
            options.append("Previous Page")
        
        options.append("Return")
        
        header = f"{category.title()} (Page {self.current_page + 1}/{total_pages})"
        self.active_menu = Menu(options, self.font, width=350, header=header)

    def refresh_sell_list(self):
        # Sell junk logic
        junk_category = self.inventory.get('junk', {})
        total_junk = sum(junk_category.values()) if isinstance(junk_category, dict) else len(junk_category)
        
        if total_junk == 0:
            options = ["Back"]
            header = "You have no junk to sell."
        else:
            options = [f"Sell All Junk ({total_junk}g)", "Back"]
            header = f"Sell your junk items for 1g each?"
            
        self.active_menu = Menu(options, self.font, width=250, header=header)

    def on_select(self, option):
        if self.mode == "MAIN":
            if option == "Buy":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            elif option == "Sell":
                self.mode = "SELL"
                self.refresh_sell_list()
            elif option == "Back":
                from interfaces.pygame.states.hub import HubState
                self.game.change_state(HubState(self.game, self.font))

        elif self.mode == "BUY_CAT":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            else:
                self.mode = "BUY_ITEMS"
                self.buy_category = option.lower()
                self.current_page = 0
                self.open_buy_category(self.buy_category)

        elif self.mode == "BUY_ITEMS":
            if option == "Return":
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            elif option == "Next Page":
                self.current_page += 1
                self.open_buy_category(self.buy_category)
            elif option == "Previous Page":
                self.current_page -= 1
                self.open_buy_category(self.buy_category)
            elif option == "Back": # Fallback for old menus
                self.mode = "BUY_CAT"
                self.refresh_buy_menu()
            else:
                self.handle_buy(option)

        elif self.mode == "SELL":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            elif option.startswith("Sell All"):
                from core.players.shop import sell_junk
                sell_junk(self.inventory)
                self.refresh_sell_list()

    def handle_buy(self, display_name):
        item_key = self.item_map.get(display_name)
        if not item_key: return

        if self.buy_category == "weapons":
            data = load_weapons().get("weapon_list", {})
        elif self.buy_category == "armor":
            data = load_armor()
        else:
            data = load_consumables()

        item = data[item_key]
        cost = item['cost']
        
        # Check gold
        if self.game.god_mode or self.inventory.get('gold', 0) >= cost:
            if not self.game.god_mode:
                self.inventory['gold'] -= cost
            
            from core.players.player_inventory import add_item
            # Mapping Buy Categories to inventory keys (weapons -> weapon)
            inv_key = self.buy_category[:-1] if self.buy_category.endswith('s') else self.buy_category
            add_item(self.inventory, item_key, inv_key)
            
            # Refresh current page
            self.open_buy_category(self.buy_category)
        else:
            print("Not enough gold!")

    def draw(self, screen):
        # super().draw handles background and active_menu
        super().draw(screen)

        from interfaces.pygame.ui.panel import draw_text_outlined
        from core.game_rules.constants import SCREEN_WIDTH, COLOR_GOLD
        
        # Show Gold at the top
        gold_text = f"Gold: {self.inventory.get('gold', 0)}"
        gw, gh = self.font.size(gold_text)
        draw_text_outlined(screen, gold_text, self.font, COLOR_GOLD, (SCREEN_WIDTH // 2) - (gw // 2), 80)
