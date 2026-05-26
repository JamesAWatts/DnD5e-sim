import pygame
import os
import random
import math
from core.game_rules.path_utils import get_resource_path
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_x, scale_y

class DieInstance:
    def __init__(self, value, pos, style="gothic", size=(90, 90)):
        self.value = value
        self.pos = list(pos)
        self.style = style
        self.size = size
        self.state = "ROLLING"
        self.alpha = 255
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = random.uniform(-10, 10)
        
        # Random trajectory
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(scale_x(15), scale_x(25))
        self.vel = [math.cos(angle) * speed, math.sin(angle) * speed]
        self.friction = 0.95
        self.current_frame = 1

class DiceAnimation:
    """
    Handles multiple physics-based d20 roll animations.
    The dice bounce off screen edges, settle on results, and fade out.
    """
    def __init__(self):
        self.dice = []
        self.is_active = False
        self.state = "INACTIVE" # "INACTIVE", "ROLLING", "SETTLED", "FADING"
        
        # Timers (in frames at 60 FPS)
        self.settle_duration = 30
        self.fade_duration = 60
        self.frame_delay = 3
        self.timer = 0
        
        self.sprite_cache = {}
        self.dice_size = (scale_x(90), scale_y(90))
        self.is_result_finalized = False
        self.stay_settled = False

    def get_style_from_actor(self, actor, party=None):
        """
        Determines the dice style based on the actor.
        Players/Player Summons: use 'dice_style' (defaults to 'gothic').
        Enemies/Enemy Summons: use 'category' (defaults to 'beast').
        """
        if not actor: return "gothic"
        if party is None: party = []
        
        # Determine if the actor is a player or player-aligned summon
        is_player = any(actor is p for p in party) or (actor.get('is_summon') and not actor.get('is_enemy_summon'))
        
        style = "gothic"
        if is_player:
            # Players can have custom dice styles, default to gothic
            style = actor.get('dice_style', 'gothic')
        else:
            # Enemies use their creature category for dice sets (beast, undead, dragon, etc.)
            # Default to 'beast' as requested if category is not found
            style = actor.get('category', 'beast')

        # Fallback if folder does not exist
        folder_path = get_resource_path(os.path.join('assets', 'sprites', 'dice', style))
        if not os.path.exists(folder_path):
            return "gothic" if is_player else "beast"

        return style

    def start_roll(self, value, style="gothic", pos=None):
        """Initiates a single dice roll."""
        if pos is None: pos = [SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2]
        self.dice = [DieInstance(value, pos, style, self.dice_size)]
        self.is_active = True
        self.state = "ROLLING"
        self.is_result_finalized = False

    def start_multi_roll(self, rolls, style="gothic"):
        """
        Initiates multiple dice rolls.
        rolls: list of (value, pos)
        """
        self.dice = [DieInstance(val, pos, style, self.dice_size) for val, pos in rolls]
        self.is_active = True
        self.state = "ROLLING"
        self.is_result_finalized = False

    def update(self, dt=0):
        if not self.is_active: return

        if self.state == "ROLLING":
            all_settled = True
            for d in self.dice:
                if d.state == "ROLLING":
                    d.pos[0] += d.vel[0]
                    d.pos[1] += d.vel[1]
                    d.rotation += d.rotation_speed
                    
                    # Bounce off edges
                    padding = d.size[0] // 2
                    if d.pos[0] < padding: d.pos[0] = padding; d.vel[0] *= -1
                    elif d.pos[0] > SCREEN_WIDTH - padding: d.pos[0] = SCREEN_WIDTH - padding; d.vel[0] *= -1
                    if d.pos[1] < padding: d.pos[1] = padding; d.vel[1] *= -1
                    elif d.pos[1] > SCREEN_HEIGHT - padding: d.pos[1] = SCREEN_HEIGHT - padding; d.vel[1] *= -1
                    
                    d.vel[0] *= d.friction
                    d.vel[1] *= d.friction
                    d.rotation_speed *= d.friction
                    
                    if pygame.time.get_ticks() // (self.frame_delay * 16) % 1 == 0:
                        d.current_frame = (d.current_frame % 11) + 1
                    
                    speed_sq = d.vel[0]**2 + d.vel[1]**2
                    if speed_sq < 0.5:
                        d.state = "SETTLED"
                
                if d.state == "ROLLING": all_settled = False
            
            if all_settled:
                self.state = "SETTLED"
                self.timer = self.settle_duration
        
        elif self.state == "SETTLED":
            if not self.stay_settled:
                self.timer -= 1
                if self.timer <= 0:
                    self.state = "FADING"
                    self.timer = self.fade_duration
                    self.is_result_finalized = True

        elif self.state == "FADING":
            self.timer -= 1
            alpha = int(255 * (self.timer / self.fade_duration))
            for d in self.dice: d.alpha = alpha
            if self.timer <= 0:
                self.is_active = False
                self.state = "INACTIVE"
                self.is_result_finalized = False

    def draw(self, surface):
        if not self.is_active: return
        for d in self.dice:
            if d.state == "ROLLING": filename = f"{d.style}_rolling{d.current_frame}.png"
            else: filename = f"{d.style}_{d.value}.png"
            
            sprite = self._get_sprite(d.style, filename)
            if sprite:
                if d.state == "ROLLING": draw_sprite = pygame.transform.rotate(sprite, d.rotation)
                else: draw_sprite = sprite
                
                rect = draw_sprite.get_rect(center=(int(d.pos[0]), int(d.pos[1])))
                if d.alpha < 255:
                    temp = draw_sprite.copy()
                    temp.fill((255, 255, 255, max(0, min(255, d.alpha))), special_flags=pygame.BLEND_RGBA_MULT)
                    surface.blit(temp, rect)
                else: surface.blit(draw_sprite, rect)

    def _get_sprite(self, style, filename):
        cache_key = f"{style}/{filename}"
        if cache_key not in self.sprite_cache:
            path = get_resource_path(os.path.join('assets', 'sprites', 'dice', style, filename))
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.smoothscale(img, self.dice_size)
                self.sprite_cache[cache_key] = img
            except: return None
        return self.sprite_cache.get(cache_key)
