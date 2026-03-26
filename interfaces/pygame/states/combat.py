import pygame
import random
import os

from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.panel import Panel
from interfaces.pygame.ui.dialogue_box import DialogueBox
from interfaces.pygame.ui.bars import draw_bar
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y
from core.combat.attack_roller import attack_roll, damage_roll
from core.combat.combat_engine import CombatEngine
from interfaces.cli.main import load_consumables, load_spells
from core.game_rules.mana_check import ManaCheck
from interfaces.pygame.ui.backgrounds import BackgroundManager
from interfaces.pygame.graphics.enemy_sprites import SpriteManager


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

        # --- Data ---
        self.consumables_db = load_consumables()
        self.spells_db = load_spells()

        # --- Effects ---
        self.player_advantage = 0
        self.enemy_advantage = 0
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
                        elif self.phase == "LEVEL_UP":
                            from interfaces.pygame.states.level_up import LevelUpState
                            self.game.change_state(LevelUpState(self.game, self.font))
            return

        # --- Combat phases ---
        if self.phase == "INITIATIVE":
            self.handle_initiative()

        elif self.phase == "PLAYER_TURN":
            super().update(events)

        elif self.phase == "ENEMY_TURN":
            self.handle_enemy_turn()

        elif self.phase == "RESOLVE_VICTORY":
            if not self.dialogue.current_message and not self.message_queue:
                self.handle_victory()
                self.start_next_message()

        elif self.phase == "CHECK_END":
            self.check_combat_end()

    def process_loot(self):
        loot_results = CombatEngine.generate_loot(self.enemies)
        
        inventory = self.game.player.setdefault("inventory_ref", {})
        inventory.setdefault("gold", 0)
        
        inventory["gold"] += loot_results["gold"]
        for item_type, item_name in loot_results["items"]:
            category = inventory.setdefault(item_type, {})
            
            if item_name in category:
                category[item_name] += 1
            else:
                category[item_name] = 1

        for msg in loot_results["messages"]:
            self.queue_message(msg)

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
                self.sub_menu = Menu(spells + ["Back"], self.font, disabled_indices=disabled, header="Cast Spell")
                self.menu_state = "SPELL"
                self.active_menu = self.sub_menu
            else:
                self.queue_message("No spells!")
                self.start_next_message()

        elif option == "Item":
            inventory = self.player.get("inventory_ref", {})
            consumables = inventory.get("consumable", {})
            if consumables:
                # Show name (xCount)
                items_with_counts = [f"{name.replace('_', ' ').title()} (x{count})" for name, count in consumables.items()]
                self.sub_menu = Menu(items_with_counts + ["Back"], self.font, header="Use Item")
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
            spell_key = option.lower().replace(" ", "_")
            spell_data = self.spells_db.get(spell_key, {})
            if not ManaCheck.can_cast(self.player_mp, option, self.spells_db):
                self.queue_message("Not enough mana")
                self.start_next_message()
            else:
                # Decide targeting based on effect
                if spell_data.get('effect_type') == 'healing':
                    self.start_targeting("SPELL_PLAYER", option)
                else:
                    self.start_targeting("SPELL", option)

    def handle_item_menu(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        else:
            # strip (xN) if present
            display_name = option.split(" (x")[0]
            item_key = display_name.lower().replace(' ', '_')
            item_data = self.consumables_db.get(item_key)
            
            if item_data:
                # Healing or buff items target the player
                if item_data.get('hp_gain', 0) > 0 or item_data.get('bonus_gain', 0) > 0 or item_data.get('attack_gain', 0) > 0:
                    self.start_targeting("ITEM_PLAYER", display_name)
                else:
                    self.start_targeting("ITEM", display_name)
            else:
                self.queue_message("Item data missing!")
                self.start_next_message()

    def handle_targeting(self, option):
        if option == "Back":
            self.menu_state = "MAIN"
            self.active_menu = self.main_menu
        else:
            if self.pending_action in ["SPELL_PLAYER", "ITEM_PLAYER"]:
                # Single player targeting for now
                self.execute_targeted_action(None) # None means player
                self.menu_state = "MAIN"
                self.active_menu = self.main_menu
                self.phase = "ENEMY_TURN"
            else:
                # Safer targeting extraction
                try:
                    idx_str = option.split(".")[0]
                    idx = int(idx_str) - 1
                    self.execute_targeted_action(idx)
                    self.menu_state = "MAIN"
                    self.active_menu = self.main_menu
                    self.phase = "ENEMY_TURN"
                except (ValueError, IndexError):
                    self.queue_message("Invalid target!")
                    self.start_next_message()

    # ========================
    # FLOW HELPERS
    # ========================
    def start_targeting(self, action_type, data=None):
        if action_type in ["SPELL_PLAYER", "ITEM_PLAYER"]:
            options = [self.player.get("name", "Player")] + ["Back"]
        else:
            alive_indices = [i for i, e in enumerate(self.enemies) if e["current_hp"] > 0]
            if not alive_indices:
                return
            options = [f"{i+1}. {self.enemies[i]['name']}" for i in alive_indices] + ["Back"]

        header = "Target?"
        if action_type == "ATTACK":
            header = "Attack Whom?"
        elif action_type in ["SPELL", "SPELL_PLAYER"]:
            header = f"Cast {data} on?"
        elif action_type in ["ITEM", "ITEM_PLAYER"]:
            header = f"Use {data} on?"

        self.target_menu = Menu(options, self.font, header=header)
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
        elif self.pending_action in ["SPELL", "SPELL_PLAYER"]:
            self.cast_spell(self.action_data, target_idx)
        elif self.pending_action in ["ITEM", "ITEM_PLAYER"]:
            self.use_item(self.action_data, target_idx)

    def player_attack(self, target_idx):
        enemy = self.enemies[target_idx]
        total_damage = 0

        for _ in range(self.p_attack_count):
            res = CombatEngine.resolve_attack(self.player, enemy, advantage=self.player_advantage)
            self.player_advantage = 0
            
            if res['hit']:
                dmg = res['damage']
                if self.extra_damage_once > 0:
                    dmg += self.extra_damage_once
                    self.extra_damage_once = 0
                total_damage += dmg
                self.queue_message(f"Hit for {dmg}!")
            else:
                self.queue_message("Missed!")
            
            for effect, val in res['effects']:
                if effect == 'player_advantage': self.player_advantage = val; self.queue_message("Vex: Advantage next!")
                elif effect == 'enemy_advantage': self.enemy_advantage = val; self.queue_message("Sap: Enemy disadvantage!")
                elif effect == 'heal_attacker':
                    self.player_hp = min(self.player_max_hp, self.player_hp + val)
                    self.queue_message(f"Lifesteal: +{val} HP")
                elif effect == 'msg': self.queue_message(val)

        enemy["current_hp"] = max(0, enemy["current_hp"] - total_damage)
        self.start_next_message()

    def enemy_attack(self, enemy, index):
        res = CombatEngine.resolve_attack(enemy, self.player, advantage=self.enemy_advantage)
        self.enemy_advantage = 0

        if res['hit']:
            dmg = res['damage']
            self.player_hp = max(0, self.player_hp - dmg)
            self.queue_message(f"{enemy['name']} hits for {dmg}!")
        else:
            self.queue_message(f"{enemy['name']} missed!")
            
        for effect, val in res['effects']:
            if effect == 'player_advantage': self.enemy_advantage = val
            elif effect == 'enemy_advantage': self.player_advantage = val
            elif effect == 'msg': self.queue_message(val)

    def cast_spell(self, spell_name, target_idx):
        spell_key = spell_name.lower().replace(" ", "_")
        spell_data = self.spells_db.get(spell_key, {})
        
        if self.player_mp >= spell_data.get('level', 0):
            # If target_idx is None, target is self (player)
            target = self.player if target_idx is None else self.enemies[target_idx]
            res = CombatEngine.resolve_spell(spell_data, self.player, target)
            self.player_mp -= res['mana_cost']
            
            if res['damage'] > 0 and target_idx is not None:
                enemy = self.enemies[target_idx]
                enemy['current_hp'] = max(0, enemy['current_hp'] - res['damage'])
                self.queue_message(f"Dealt {res['damage']} damage!")
            
            if res['healing'] > 0:
                self.player_hp = min(self.player_max_hp, self.player_hp + res['healing'])
                self.queue_message(f"Healed for {res['healing']} HP!")
                
            for effect, val in res['effects']:
                if effect == 'enemy_advantage': self.enemy_advantage = val; self.queue_message("Enemy Disadvantaged!")
            
            self.queue_message(res['msg'])
        else:
            self.queue_message("Not enough mana!")
        
        self.start_next_message()

    def use_item(self, item_name, target_idx):
        # target_idx is ignored for now as most items are player-focused (healing/buffs)
        item_key = item_name.lower().replace(' ', '_')
        item_data = self.consumables_db.get(item_key)
        
        if item_data:
            res = CombatEngine.resolve_item(item_data, self.player)
            self.queue_message(res['msg'])
            
            if res['hp_gain'] > 0:
                self.player_hp = min(self.player_max_hp, self.player_hp + res['hp_gain'])
                self.queue_message(f"Healed for {res['hp_gain']} HP!")
            
            if res['bonus_gain'] > 0:
                self.player['weapon_bonus'] = self.player.get('weapon_bonus', 0) + res['bonus_gain']
                self.queue_message(f"Bonus +{res['bonus_gain']}!")
            
            if res['attack_gain'] > 0:
                self.p_attack_count += res['attack_gain']
                self.queue_message(f"+{res['attack_gain']} Attacks!")
            
            if res['extra_damage'] > 0:
                self.extra_damage_once += res['extra_damage']
                self.queue_message(f"Next hit +{res['extra_damage']}!")
                
            # Remove from inventory using count-based system
            from core.players.player_inventory import remove_item
            remove_item(self.player.get("inventory_ref", {}), item_key, "consumable")
        else:
            self.queue_message("Item failed!")
            
        self.start_next_message()

    # ========================
    # END / CHECK
    # ========================
    def handle_victory(self):
        total_xp = sum(e.get("xp", 0) for e in self.enemies)

        from core.players.leveler import update_xp_and_level
        level_up_available = update_xp_and_level(self.game.player, total_xp)

        self.queue_message(f"You gained {total_xp} XP!")

        # 🆕 ADD THIS LINE
        self.process_loot()

        from core.players.leveler import xp_to_next_level
        next_xp = xp_to_next_level(self.game.player["xp"])

        if next_xp is not None:
            self.queue_message(f"{next_xp} XP until next level.")

        if level_up_available:
            self.queue_message("LEVEL UP!")
            self.phase = "LEVEL_UP"
        else:
            self.phase = "END_COMBAT"

    def check_combat_end(self):
        if all(e["current_hp"] <= 0 for e in self.enemies):
            self.queue_message("Victory!")
            self.phase = "RESOLVE_VICTORY"
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
            from interfaces.pygame.states.game_over import GameOverState
            self.game.change_state(GameOverState(self.game, self.font))
        else:
            # Tell manager to pick a new town/hub background for next visit
            BackgroundManager.refresh_hub_bg(self.game.player)
            
            from interfaces.pygame.states.hub import HubState
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

        from interfaces.pygame.ui.panel import draw_text_outlined
        draw_text_outlined(screen, self.player.get("name", "Player"), self.font, (255,255,255), px, py)

        # Player HP Bar
        draw_bar(screen, px, py + scale_y(30), scale_x(200), scale_y(25),
                 self.player_hp, self.player_max_hp, (200,50,50), self.font)
        
        # Player MP Bar
        if self.player_max_mp > 0:
            from core.game_rules.constants import COLOR_BLUE
            draw_bar(screen, px, py + scale_y(65), scale_x(200), scale_y(25),
                     self.player_mp, self.player_max_mp, COLOR_BLUE, self.font)

        # Draw Player Sprite
        player_class = self.player.get("class", "fighter")
        player_sprite = SpriteManager.get_player_sprite(player_class, size=(scale_x(256), scale_y(256)))
        if player_sprite:
            screen.blit(player_sprite, (scale_x(100), SCREEN_HEIGHT // 2 - scale_y(128)))

        ex = SCREEN_WIDTH - scale_x(260)

        for i, enemy in enumerate(self.enemies):
            y_off = scale_y(50) + (i * scale_y(80))
            name_str = enemy["name"]
            tw, th = self.font.size(name_str)
            draw_text_outlined(screen, name_str, self.font, (255,255,255), ex, y_off - scale_y(25))

            draw_bar(screen, ex, y_off, scale_x(200), scale_y(25),
                     enemy["current_hp"], enemy["max_hp"], (200,50,50), self.font)

            # Draw Enemy Sprite
            # We use the name to look up the sprite (lowercased)
            enemy_key = enemy["name"].lower().replace(" ", "_")
            enemy_sprite = SpriteManager.get_enemy_sprite(enemy_key, size=(scale_x(192), scale_y(192)))
            if enemy_sprite:
                # Stagger enemies slightly if there are multiple
                enemy_x = SCREEN_WIDTH - scale_x(450) - (i * scale_x(40))
                enemy_y = SCREEN_HEIGHT // 2 - scale_y(96) + (i * scale_y(40))
                
                # Darken dead enemies
                if enemy["current_hp"] <= 0:
                    enemy_sprite = enemy_sprite.copy()
                    enemy_sprite.fill((50, 50, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
                
                screen.blit(enemy_sprite, (enemy_x, enemy_y))

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