import pygame
import random
import os
from core.game_rules.path_utils import get_resource_path
from core.game_rules.constants import scale_x, scale_y, SCALE_X, SCALE_Y

class ActiveLoot:
    def __init__(self, sprite, start_pos, target_y):
        self.sprite = sprite
        self.rect = sprite.get_rect(center=start_pos)
        self.pos_y = float(self.rect.centery)
        self.target_y = target_y
        self.velocity_y = -2.0  # Slight initial "pop" upward
        self.gravity = 0.25
        self.is_grounded = False
        self.is_active = False # Hidden/Static until death vfx starts dissipating

    def start_drop(self):
        self.is_active = True

    def update(self, dt):
        if self.is_active and not self.is_grounded:
            # Gravity-based falling animation
            self.velocity_y += self.gravity
            self.pos_y += self.velocity_y
            
            if self.pos_y >= self.target_y:
                self.pos_y = self.target_y
                self.is_grounded = True
            
            self.rect.centery = int(self.pos_y)

    def draw(self, screen):
        # Optional: Only draw if active, but since it's under VFX it can draw
        screen.blit(self.sprite, self.rect)

class LootDropManager:
    def __init__(self):
        self.active_drops = []
        self.loot_sprites = {}
        self._load_assets()

    def _load_assets(self):
        """Pre-loads the loot icons from assets/sprites/loot/"""
        categories = ['gold', 'weapon', 'armor', 'shield', 'trinket', 'consumable', 'junk']
        for cat in categories:
            path = get_resource_path(f"assets/sprites/loot/{cat}.png")
            if os.path.exists(path):
                img = pygame.image.load(path).convert_alpha()
                # Scale loot to a standard 32x32 scaled to screen
                self.loot_sprites[cat] = pygame.transform.scale(img, (scale_x(32), scale_y(32)))
            else:
                # Fallback placeholder if sprite is missing
                surf = pygame.Surface((scale_x(20), scale_y(20)))
                surf.fill((255, 215, 0) if cat == 'gold' else (150, 150, 150))
                self.loot_sprites[cat] = surf

    def trigger_drop(self, enemy):
        """Rolls for loot and initializes the ActiveLoot object."""
        reward_data = enemy.get('reward', {})
        
        # Collect potential loot sources: gold, item_1, item_2
        possible_keys = []
        if reward_data.get('gold'): possible_keys.append('gold')
        
        items = reward_data.get('items', [])
        if len(items) > 0: possible_keys.append('item_1')
        if len(items) > 1: possible_keys.append('item_2')

        if not possible_keys: return None

        # Randomly select one reward to drop
        selected_key = random.choice(possible_keys)
        loot_type = 'gold'
        
        if selected_key != 'gold':
            # It's an item, determine type for sprite mapping
            item_idx = 0 if selected_key == 'item_1' else 1
            item_entry = items[item_idx]
            
            # Lookup the item's type from its data structure
            loot_type = item_entry.get('type', 'junk').lower()
            if loot_type.endswith('s'): loot_type = loot_type[:-1] # Handle plurals (weapons -> weapon)

        sprite = self.loot_sprites.get(loot_type, self.loot_sprites['junk'])
        
        # Calculate positions from enemy visual rect or screen_pos
        v_rect = enemy.get('_visual_rect')
        if v_rect:
            start_pos = v_rect.center
            target_y = v_rect.bottom - scale_y(10) # Fall to feet level
        else:
            sx, sy = enemy.get('screen_pos', (400, 300))
            start_pos = (sx + scale_x(60), sy + scale_y(60))
            target_y = sy + scale_y(110)

        new_drop = ActiveLoot(sprite, start_pos, target_y)
        self.active_drops.append(new_drop)
        return selected_key

    def update(self, dt):
        for drop in self.active_drops:
            drop.update(dt)

    def draw(self, screen):
        for drop in self.active_drops:
            screen.blit(drop.sprite, drop.rect)
