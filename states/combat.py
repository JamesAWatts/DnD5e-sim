import pygame
import random
import os

from game.states.base_state import BaseState
from game.ui.menu import Menu
from game.ui.panel import Panel
from game.ui.dialogue_box import DialogueBox
from game.ui.bars import draw_bar
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y
from combat.attack_roller import attack_roll, damage_roll
from simulator import load_consumables, load_spells
from game.mana_check import ManaCheck
from game.ui.backgrounds import BackgroundManager


class CombatState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_combat_bg()

        self.dialogue = DialogueBox(self.font)

        self.player = game.player
        self.enemies = game.enemies

        # --- Player stats ---
        self.player_hp = int(self.player.get("current_hp", self.player.get("hp", 1)))
        self.player_max_hp = int(self.player.get("max_hp", self.player.get("hp", 1)))
        self.player_mp = int(self.player.get("current_mp", 0))
        self.player_max_mp = int(self.player.get("max_mp", 0))

        # --- Enemy setup ---
        for e in self.enemies:
            e["current_hp"] = int(e.get("current_hp", e.get("hp", 10)))
            e["max_hp"] = int(e.get("hp", 10))

        # --- Combat stats ---
        self.p_attack_count = int(self.player.get("attack_count", 1))
        self.p_bonus = int(self.player.get("proficiency_bonus", 0)) + int(self.player.get("weapon_bonus", 0))
        self.p_die = int(self.player.get("damage_die", 6))
        self.player_armor = int(self.player.get("armor", 10))

        # --- Data ---
        self.consumables_db = load_consumables()
        self.spells_db = load_spells()

        # --- Effects ---
        self.player_advantage = 0
        self.extra_damage_once = 0

        # --- Menus ---
        self.main_menu = Menu(["Attack", "Spell", "Item", "Run"], font)
        self.target_menu = None
        self.sub_menu = None

        self.menu_state = "MAIN"
        self.active_menu = self.main_menu

        # --- Flow ---
        self.phase = "INITIATIVE"
        self.pending_action = None
        self.action_data = None

        # --- Messages ---
        self.message_queue = []

        names = ", ".join([e["name"] for e in self.enemies])
        self.queue_message(f"Encountered: {names}!")
        self.start_next_message()

    # ========================
    # BASESTATE HOOK
    # ========================
    def on_select(self, option):
        if self.menu_state == "MAIN":
            self.handle_main_menu(option)
        elif self.menu_state == "SPELL":
            self.handle_spell_menu(option)
        elif self.menu_state == "ITEM":
            self.handle_item_menu(option)
        elif self.menu_state == "TARGETING":
            self.handle_targeting(option)

    # ========================
    # UPDATE LOOP
    # ========================
    def update(self, events):
        # --- Dialogue blocks input ---
        if self.dialogue.current_message:
            self.dialogue.update()

            for event in events:
                if event.type == pygame.KEYDOWN:
                    was_typing = self.dialogue.is_typing
                    self.dialogue.handle_event(event)

                    if not was_typing and not self.dialogue.current_message:
                        if self.message_queue:
                            self.start_next_message()
                        elif self.phase == "END_COMBAT":
                            self.exit_to_hub()
            return

        # --- Combat phases ---
        if self.phase == "INITIATIVE":
            self.handle_initiative()

        elif self.phase == "PLAYER_TURN":
            super().update(events)

        elif self.phase == "ENEMY_TURN":
            self.handle_enemy_turn()

        elif self.phase == "CHECK_END":
            self.check_combat_end()

    # ========================
    # MENU HANDLERS
    # ========================
    def handle_main_menu(self, option):
        if option == "Attack":
            self.start_targeting("ATTACK")

        elif option == "Spell":
            spells = self.player.get("spells", [])
            if spells:
                disabled = ManaCheck.get_disabled_spell_indices(self.player_mp, spells, self.spells_db)
                self.sub_menu = Menu(spells + ["Back"], self.font, disabled_indices=disabled)
                self.menu_state = "SPELL"
                self.active_menu = self.sub_menu
            else:
                self.queue_message("No spells!")
                self.start_next_message()

        elif option == "Item":
            items = self.player.get("inventory_ref", {}).get("consumable", [])
            if items:
                self.sub_menu = Menu(items + ["Back"], self.font)
                self.menu_state = "ITEM"
                self.active_menu = self.sub_menu
            else:
                self.queue_message("No items!")
                self.start_next_message()

        elif option == "Run":
            if random.random() < 0.4:
                self.queue_message("Escaped!")
                self.phase = "END_COMBAT"
            else:
                self.queue_message("Failed escape!")
                self.phase = "ENEMY_TURN"
            self.start_next_message()

    def handle_spell_menu(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        else:
            if not ManaCheck.can_cast(self.player_mp, option, self.spells_db):
                self.queue_message("Not enough mana")
                self.start_next_message()
            else:
                self.start_targeting("SPELL", option)

    def handle_item_menu(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        else:
            if "potion" in option.lower():
                self.use_item(option, None)
                self.menu_state = "MAIN"
                self.active_menu = self.main_menu
                self.phase = "ENEMY_TURN"
            else:
                self.start_targeting("ITEM", option)

    def handle_targeting(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        else:
            idx = int(option.split(".")[0]) - 1
            self.execute_targeted_action(idx)

            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
            self.phase = "ENEMY_TURN"

    # ========================
    # FLOW HELPERS
    # ========================
    def start_targeting(self, action_type, data=None):
        alive = [i for i, e in enumerate(self.enemies) if e["current_hp"] > 0]
        if not alive:
            return

        options = [f"{i+1}. {self.enemies[i]['name']}" for i in alive] + ["Back"]

        self.target_menu = Menu(options, self.font)
        self.menu_state = "TARGETING"
        self.active_menu = self.target_menu

        self.pending_action = action_type
        self.action_data = data

    def handle_initiative(self):
        max_e_bonus = max([int(e.get("bonus", 0)) for e in self.enemies])
        p_init = random.randint(1, 20) + int(self.player.get("proficiency_bonus", 0))
        e_init = random.randint(1, 20) + max_e_bonus

        self.queue_message(f"Initiative: You {p_init}, Enemies {e_init}")
        self.phase = "PLAYER_TURN" if p_init >= e_init else "ENEMY_TURN"
        self.start_next_message()

    def handle_enemy_turn(self):
        for i, enemy in enumerate(self.enemies):
            if enemy["current_hp"] > 0:
                self.enemy_attack(enemy, i)

        self.start_next_message()
        self.phase = "CHECK_END"

    # ========================
    # ACTIONS
    # ========================
    def execute_targeted_action(self, target_idx):
        if self.pending_action == "ATTACK":
            self.player_attack(target_idx)
        elif self.pending_action == "SPELL":
            self.cast_spell(self.action_data, target_idx)
        elif self.pending_action == "ITEM":
            self.use_item(self.action_data, target_idx)

    def player_attack(self, target_idx):
        enemy = self.enemies[target_idx]
        total_damage = 0

        for _ in range(self.p_attack_count):
            attack = attack_roll(self.p_bonus, int(enemy.get("armor", 10)))

            if attack["hit"]:
                dmg = damage_roll(self.p_die, self.p_bonus, attack["critical"])
                total_damage += dmg
                self.queue_message(f"Hit for {dmg}!")
            else:
                self.queue_message("Missed!")

        enemy["current_hp"] = max(0, enemy["current_hp"] - total_damage)
        self.start_next_message()

    def enemy_attack(self, enemy, index):
        attack = attack_roll(int(enemy.get("bonus", 0)), self.player_armor)

        if attack["hit"]:
            dmg = damage_roll(int(enemy.get("die", 6)), int(enemy.get("bonus", 0)), attack["critical"])
            self.player_hp = max(0, self.player_hp - dmg)
            self.queue_message(f"{enemy['name']} hits for {dmg}!")
        else:
            self.queue_message(f"{enemy['name']} missed!")

    def cast_spell(self, spell_name, target_idx):
        spell_key = spell_name.lower().replace(" ", "_")
        spell_data = self.spells_db.get(spell_key, {})
        mana_cost = spell_data.get("level", 0)

        if self.player_mp >= mana_cost:
            self.player_mp -= mana_cost
            enemy = self.enemies[target_idx]
            dmg = random.randint(5, 15)
            enemy["current_hp"] -= dmg
            self.queue_message(f"{spell_name} dealt {dmg} damage! ({mana_cost} MP used)")
        else:
            self.queue_message("Not enough mana!")
        
        self.start_next_message()

    def use_item(self, item_name, target_idx):
        heal = max(10, self.player_max_hp // 2)
        self.player_hp = min(self.player_max_hp, self.player_hp + heal)
        self.queue_message(f"Healed for {heal} HP!")
        self.start_next_message()

    # ========================
    # END / CHECK
    # ========================
    def check_combat_end(self):
        if all(e["current_hp"] <= 0 for e in self.enemies):
            self.queue_message("Victory!")
            self.phase = "END_COMBAT"
            self.start_next_message()
        elif self.player_hp <= 0:
            self.queue_message("Defeat...")
            self.phase = "END_COMBAT"
            self.start_next_message()
        else:
            self.phase = "PLAYER_TURN"

    def exit_to_hub(self):
        self.game.player["current_hp"] = self.player_hp
        self.game.player["current_mp"] = self.player_mp

        if self.player_hp <= 0:
            from game.states.game_over import GameOverState
            self.game.change_state(GameOverState(self.game, self.font))
        else:
            # Tell manager to pick a new town/hub background for next visit
            BackgroundManager.refresh_hub_bg(self.game.player)
            
            from game.states.hub import HubState
            self.game.change_state(HubState(self.game, self.font))

    # ========================
    # MESSAGES
    # ========================
    def queue_message(self, text):
        self.message_queue.append(text)

    def start_next_message(self):
        if self.message_queue:
            self.dialogue.set_messages([self.message_queue.pop(0)])

    # ========================
    # DRAW (UNCHANGED)
    # ========================
    def draw(self, screen):
        self.draw_background(screen)

        px = scale_x(40)
        py = scale_y(40)

        from game.ui.panel import draw_text_outlined
        draw_text_outlined(screen, self.player.get("name", "Player"), self.font, (255,255,255), px, py)

        # Player HP Bar
        draw_bar(screen, px, py + scale_y(30), scale_x(200), scale_y(25),
                 self.player_hp, self.player_max_hp, (200,50,50), self.font)
        
        # Player MP Bar
        if self.player_max_mp > 0:
            from constants import COLOR_BLUE
            draw_bar(screen, px, py + scale_y(65), scale_x(200), scale_y(25),
                     self.player_mp, self.player_max_mp, COLOR_BLUE, self.font)

        ex = SCREEN_WIDTH - scale_x(260)

        for i, enemy in enumerate(self.enemies):
            y_off = scale_y(50) + (i * scale_y(80))
            name_str = enemy["name"]
            tw, th = self.font.size(name_str)
            draw_text_outlined(screen, name_str, self.font, (255,255,255), ex, y_off - scale_y(25))

            draw_bar(screen, ex, y_off, scale_x(200), scale_y(25),
                     enemy["current_hp"], enemy["max_hp"], (200,50,50), self.font)

        # =========================
        # MENU LAYOUT (Bottom Left + Expanding Right)
        # =========================
        if self.phase == "PLAYER_TURN" and not self.dialogue.current_message:

            width, height = screen.get_size()

            # --- MAIN MENU ---
            main_menu = self.main_menu
            main_width = main_menu.get_width()
            main_height = len(main_menu.options) * scale_y(30) + scale_y(20)

            main_x = scale_x(80) + main_width // 2
            main_y = height - main_height - scale_y(20)

            main_menu.draw(screen, main_x, main_y)

            # --- SUB MENU ---
            if self.active_menu != self.main_menu and self.active_menu:

                submenu = self.active_menu
                submenu_width = submenu.get_width()

                sub_x = main_x + (main_width // 2) + (submenu_width // 2) + scale_x(80)
                sub_y = main_y

                submenu.draw(screen, sub_x, sub_y)

        self.dialogue.draw(screen)