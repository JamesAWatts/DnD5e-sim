import pygame
import math
import random
from core.game_rules.constants import scale_x, scale_y, SCREEN_WIDTH, SCREEN_HEIGHT

class VisualEffect:
    """Base class for all visual effects."""
    def __init__(self, vfx_data, start_pos, target_pos, scale_mult=1.0):
        self.vfx_data = vfx_data
        self.pos = pygame.Vector2(start_pos)
        self.target_pos = pygame.Vector2(target_pos)
        self.color = self._parse_color(vfx_data.get('color', 'white'))
        # Base scale from JSON * dynamic multiplier from cost/level
        self.scale = vfx_data.get('scale', 1.0) * scale_mult
        self.finished = False
        self.particles = []
        self.timer = 0

    def _parse_color(self, color_data):
        if isinstance(color_data, (list, tuple)):
            return color_data
        try:
            return pygame.Color(color_data)
        except:
            return (255, 255, 255)

    def update(self, dt):
        pass

    def draw(self, screen):
        pass

class LightningStrikeEffect(VisualEffect):
    def __init__(self, vfx_data, start_pos, target_pos, scale_mult=1.0):
        super().__init__(vfx_data, start_pos, target_pos, scale_mult)
        self.target_x = target_pos[0]
        self.screen_height = 720 # Default
        try:
             self.screen_height = pygame.display.get_surface().get_height()
        except: pass
        
        self.frame = 0
        self.max_frames = 40
        
        # Hold the jagged points
        self.bolt_points = self._generate_bolt()

    def _generate_bolt(self):
        """Generates a random jagged line from the top of the screen to the bottom."""
        points = [(self.target_x, 0)]
        current_y = 0
        
        while current_y < self.screen_height:
            current_y += random.randint(30, 80) # Move down in chunks
            # Random horizontal drift
            current_x = self.target_x + random.randint(-40, 40) 
            points.append((current_x, current_y))
            
        return points

    def update(self, dt):
        self.frame += 1
        if self.frame > self.max_frames:
            self.finished = True
            
        if self.frame > 15 and self.frame % 4 == 0:
            self.bolt_points = self._generate_bolt()

    def draw(self, screen):
        if self.frame <= 15:
            progress = self.frame / 15
            current_top_y = self.pos.y - (self.pos.y * progress)
            # Scaling thickness
            pygame.draw.line(screen, self.color, (int(self.pos.x), int(self.pos.y)), (int(self.pos.x), int(current_top_y)), int(4 * self.scale))

        elif self.frame > 15:
            if self.frame in [16, 18, 22, 28]:
                flash_surf = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
                flash_surf.fill((255, 255, 255, 120))
                screen.blit(flash_surf, (0, 0))

            if len(self.bolt_points) > 1:
                # Scaling thickness
                pygame.draw.lines(screen, self.color, False, self.bolt_points, int(8 * self.scale))
                pygame.draw.lines(screen, (255, 255, 255), False, self.bolt_points, int(3 * self.scale))

class MeteorStormEffect:
    def __init__(self, scale=1.0):
        self.frame = 0
        self.max_frames = 90  # A long, cinematic 1.5 second animation
        self.is_finished = False
        
        # Generate 6-10 meteors
        num_meteors = random.randint(6, 10)
        self.meteors = []
        for _ in range(num_meteors):
            # Start way off-screen top/right
            start_x = random.randint(SCREEN_WIDTH // 2, SCREEN_WIDTH + 400)
            start_y = random.randint(-400, -50)
            
            # End way off-screen bottom/left
            target_x = start_x - random.randint(600, 1000)
            target_y = start_y + random.randint(600, 1000)
            
            # Stagger their start times so they rain down sequentially
            delay = random.randint(0, 40)
            
            self.meteors.append({
                'start': (start_x, start_y),
                'target': (target_x, target_y),
                'delay': delay,
                'radius': random.randint(20, 45) * scale,
                'progress': 0.0
            })
    def draw(self, screen):
        # 1. Darken the screen to make the meteors pop (Cinematic dimming)
        dim_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim_alpha = min(150, self.frame * 5) if self.frame < 60 else max(0, (90 - self.frame) * 5)
        dim_surf.fill((0, 0, 0, dim_alpha))
        screen.blit(dim_surf, (0, 0))

        # 2. Draw Meteors
        for m in self.meteors:
            if self.frame > m['delay'] and m['progress'] <= 1.2:
                # Interpolate position
                curr_x = m['start'][0] + (m['target'][0] - m['start'][0]) * m['progress']
                curr_y = m['start'][1] + (m['target'][1] - m['start'][1]) * m['progress']
                
                # Draw the glowing aura (orange)
                pygame.draw.circle(screen, (255, 100, 0), (int(curr_x), int(curr_y)), int(m['radius'] * 1.5))
                # Draw the hot core (yellow/white)
                pygame.draw.circle(screen, (255, 200, 50), (int(curr_x), int(curr_y)), int(m['radius']))
            
                # Screen flash on impact
                if 0.95 <= m['progress'] <= 1.05:
                    flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                    flash.fill((255, 200, 150, 80)) # Blinding orange/white flash
                    screen.blit(flash, (0, 0))

    def update(self, dt):
        self.frame += 1
        if self.frame > self.max_frames:
            self.is_finished = True
            
        for m in self.meteors:
            if self.frame > m['delay']:
                # Move fast! Reaches target in 15 frames once started
                m['progress'] += (1.0 / 15.0)

class ProjectileEffect(VisualEffect):
    def __init__(self, vfx_data, start_pos, target_pos, scale_mult=1.0):
        super().__init__(vfx_data, start_pos, target_pos, scale_mult)
        self.speed = scale_x(15)
        self.hit_triggered = False
        direction = (self.target_pos - self.pos)
        if direction.length() > 0:
            self.velocity = direction.normalize() * self.speed
        else:
            self.velocity = pygame.Vector2(0, 0)
            self.hit_triggered = True
            self._on_hit()

    def update(self, dt):
        if not self.hit_triggered:
            self.pos += self.velocity
            if self.pos.distance_to(self.target_pos) < self.speed:
                self.pos = pygame.Vector2(self.target_pos)
                self.hit_triggered = True
                self._on_hit()
        else:
            for p in self.particles:
                p['pos'] += p['vel']
                p['life'] -= 5
            self.particles = [p for p in self.particles if p['life'] > 0]
            if not self.particles:
                self.finished = True

    def _on_hit(self):
        for _ in range(random.randint(3, 5)):
            self.particles.append({
                'pos': pygame.Vector2(self.pos),
                'vel': pygame.Vector2(random.uniform(-3, 3), random.uniform(-3, 3)),
                'life': 255
            })

    def draw(self, screen):
        if not self.hit_triggered:
            # Scaling radius
            pygame.draw.circle(screen, self.color, (int(self.pos.x), int(self.pos.y)), int(scale_x(6) * self.scale))
        else:
            for p in self.particles:
                s = pygame.Surface((4, 4), pygame.SRCALPHA)
                c = list(self.color)[:3] + [p['life']]
                pygame.draw.circle(s, c, (2, 2), 2)
                screen.blit(s, p['pos'])

class BurstEffect(VisualEffect):
    def __init__(self, vfx_data, start_pos, target_pos, scale_mult=1.0):
        super().__init__(vfx_data, start_pos, target_pos, scale_mult)
        self.radius = 0
        # Scaling max radius
        self.max_radius = scale_x(50) * self.scale
        self.alpha = 255

    def update(self, dt):
        self.radius += 4
        self.alpha -= 10
        if self.alpha <= 0 or self.radius >= self.max_radius:
            self.finished = True

    def draw(self, screen):
        s = pygame.Surface((int(self.max_radius * 2), int(self.max_radius * 2)), pygame.SRCALPHA)
        center = (int(self.max_radius), int(self.max_radius))
        c = list(self.color)[:3] + [self.alpha]
        pygame.draw.circle(s, c, center, int(self.radius), int(max(1, 3 * self.scale)))
        screen.blit(s, (self.target_pos.x - self.max_radius, self.target_pos.y - self.max_radius))

class AuraEffect(VisualEffect):
    def __init__(self, vfx_data, start_pos, target_pos, scale_mult=1.0):
        super().__init__(vfx_data, start_pos, target_pos, scale_mult)
        self.lifetime = 1000 # 1 second in ms
        self.spawn_timer = 0

    def update(self, dt):
        self.timer += dt
        self.spawn_timer += dt
        
        if self.spawn_timer > 100:
            self.spawn_timer = 0
            offset_x = random.uniform(-scale_x(30) * self.scale, scale_x(30) * self.scale)
            self.particles.append({
                'pos': pygame.Vector2(self.target_pos.x + offset_x, self.target_pos.y + scale_y(20)),
                'vel': pygame.Vector2(0, -random.uniform(1, 2)),
                'life': 255
            })
            
        for p in self.particles:
            p['pos'] += p['vel']
            p['life'] -= 4
            
        self.particles = [p for p in self.particles if p['life'] > 0]
        if self.timer >= self.lifetime and not self.particles:
            self.finished = True

    def draw(self, screen):
        for p in self.particles:
            # Scaling particle size
            w, h = int(6 * self.scale), int(8 * self.scale)
            s = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
            c = list(self.color)[:3] + [p['life']]
            pygame.draw.rect(s, c, (0, 0, w, h))
            screen.blit(s, p['pos'])

class SlashEffect(VisualEffect):
    def __init__(self, vfx_data, start_pos, target_pos, scale_mult=1.0):
        super().__init__(vfx_data, start_pos, target_pos, scale_mult)
        self.duration = 10 # frames
        self.frames = 0

    def update(self, dt):
        self.frames += 1
        if self.frames >= self.duration:
            self.finished = True

    def draw(self, screen):
        # Scaling length
        length = scale_x(40) * self.scale
        p1 = (self.target_pos.x - length, self.target_pos.y + length)
        p2 = (self.target_pos.x + length, self.target_pos.y - length)
        # Scaling thickness
        pygame.draw.line(screen, self.color, p1, p2, int(max(1, scale_x(4) * self.scale)))
        pygame.draw.line(screen, (255, 255, 255), p1, p2, int(max(1, scale_x(1) * self.scale)))

class VFXManager:
    def __init__(self):
        self.active_effects = []

    def is_playing(self):
        return len(self.active_effects) > 0

    def is_busy(self):
        return self.is_playing()
    
    def draw_targeting_pulse(self, screen, target_type, col_index=None):
        """
        Draws a pulsing tactical overlay for various AoE types.
        target_type: 'AOE' (single column) or 'SAOE' (all columns)
        col_index: 0, 1, or 2 (required if target_type is 'AOE')
        """
        # Base column X coordinates
        col_x = {0: scale_x(350), 1: scale_x(500), 2: scale_x(650)}

        # Determine which columns to draw over
        columns_to_draw = []
        if target_type == 'SAOE':
            columns_to_draw = [0, 1, 2] # Draw over all three
        elif target_type == 'AOE' and col_index in col_x:
            columns_to_draw = [col_index] # Draw over just the targeted column

        if not columns_to_draw:
            return

        # Calculate the "Breathing" Alpha (Opacity) once per frame
        time_ms = pygame.time.get_ticks()
        # Max opacity 75% = 191. Synced with CombatRenderer pulse (0.008 speed).
        alpha = int(115 + math.sin(time_ms * 0.008) * 76)

        pulse_color = (200, 50, 50, alpha)
        border_color = (255, 100, 100, alpha + 50)

        # Draw the boxes
        for col in columns_to_draw:
            x = col_x[col] - scale_x(20)  # Pad slightly to the left
            y = scale_y(130)              # Start just above the top slot
            width = scale_x(140)          # Wide enough to cover the sprites
            height = scale_y(470)         # Tall enough to cover all 4 slots

            pulse_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            pulse_surf.fill(pulse_color)
            pygame.draw.rect(pulse_surf, border_color, pulse_surf.get_rect(), 2)

            screen.blit(pulse_surf, (x, y))

    def draw_dynamic_aoe(self, screen, affected_targets, action_data):
        """
        Draws tactical indicators under a list of targets.
        Used for highlighting who will be hit by an AoE.
        """
        if not affected_targets:
            return

        # Calculate breathing alpha
        time_ms = pygame.time.get_ticks()
        # Max opacity 75% = 191. Synced with CombatRenderer pulse (0.008 speed).
        alpha = int(115 + math.sin(time_ms * 0.008) * 76)
        
        # Color based on action type (offensive vs defensive)
        color = (200, 50, 50, alpha) # Default red for damage
        if action_data.get('type') == 'heal':
            color = (50, 200, 50, alpha) # Green for heals
            
        for target in affected_targets:
            pos = target.get('screen_pos')
            if not pos:
                # Fallback to _combat_pos if screen_pos is missing
                pos = target.get('_combat_pos')
                if pos:
                    # Adjust to center roughly
                    pos = (pos[0] + scale_x(50), pos[1] + scale_y(80))
            
            if pos:
                # Draw a glow/ellipse under their feet
                # Surface for alpha blending
                width = scale_x(120)
                height = scale_y(40)
                surf = pygame.Surface((width, height), pygame.SRCALPHA)
                
                # Draw outer glow
                pygame.draw.ellipse(surf, color, surf.get_rect())
                # Draw inner highlight
                pygame.draw.ellipse(surf, (255, 255, 255, alpha), surf.get_rect(), 2)
                
                # Blit centered under actor
                screen.blit(surf, (pos[0] - width // 2, pos[1] + scale_y(10)))

    def play_effect(self, ability_data, start_pos, target_pos):
        # 1. Safely extract the nested VFX dictionary
        vfx_data = ability_data.get('vfx', {})
        vfx_type = vfx_data.get('type', 'slash') # Default to slash if missing
        
        # 2. Safely extract Cost or Level for scaling
        raw_cost = ability_data.get('cost', 1)
        raw_level = ability_data.get('level', 1)
        
        # Prevent crashes if the JSON uses a string formula like "{prof}"
        try:
            numeric_val = int(raw_level) if 'level' in ability_data else int(raw_cost)
        except (ValueError, TypeError):
            numeric_val = 1 
            
        # Calculate dynamic scale and clamp it to 3.5 max
        base_scale = vfx_data.get('scale', 1.0)
        final_scale = min(3.5, base_scale * (1.0 + (numeric_val * 0.15)))

        effect = None
        
        # 3. Route to the correct unique tag
        if vfx_type == 'meteor_storm':
            # Uses final_scale for massive screen impact
            effect = MeteorStormEffect(scale=final_scale)
            
        elif vfx_type in ['column_strike', 'lightning_strike']:
            # Passes final_scale to thicken the lightning bolt
            effect = LightningStrikeEffect(vfx_data, start_pos, target_pos, scale_mult=final_scale)
            
        # Standard Primitives
        elif vfx_type == 'projectile':
            effect = ProjectileEffect(vfx_data, start_pos, target_pos, scale_mult=final_scale)
        elif vfx_type == 'burst':
            effect = BurstEffect(vfx_data, start_pos, target_pos, scale_mult=final_scale)
        elif vfx_type == 'aura':
            effect = AuraEffect(vfx_data, start_pos, target_pos, scale_mult=final_scale)
        elif vfx_type == 'slash':
            effect = SlashEffect(vfx_data, start_pos, target_pos, scale_mult=final_scale)
            
        if effect:
            self.active_effects.append(effect)

    def update(self, dt):
        for effect in self.active_effects:
            effect.update(dt)
        # Clean up finished effects (checking both 'finished' and 'is_finished' depending on the class)
        self.active_effects = [e for e in self.active_effects if not getattr(e, 'finished', False) and not getattr(e, 'is_finished', False)]

    def draw(self, screen):
        for effect in self.active_effects:
            effect.draw(screen)