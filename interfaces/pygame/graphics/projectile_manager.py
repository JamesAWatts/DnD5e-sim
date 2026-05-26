import pygame
import math
import random
from core.game_rules.constants import scale_x, scale_y

class Projectile:
    def __init__(self, start_pos, target_pos, effect_type, is_hit):
        self.start_pos = pygame.Vector2(start_pos)
        self.target_pos = pygame.Vector2(target_pos)
        self.pos = pygame.Vector2(start_pos)
        self.effect_type = effect_type.lower()
        self.is_hit = is_hit
        
        self.speed = scale_x(12)
        direction = (self.target_pos - self.start_pos)
        if direction.length() == 0:
            self.velocity = pygame.Vector2(self.speed, 0)
        else:
            self.velocity = direction.normalize() * self.speed
            
        self.finished = False
        self.hit_triggered = False
        self.particles = []
        self.trail = []
        self.max_trail = 5
        self.timer = 0
        self.alpha = 255
        self.ring_radius = 0
        self.ring_max_radius = scale_x(60)

    def update(self):
        if not self.hit_triggered:
            self.trail.append(pygame.Vector2(self.pos))
            if len(self.trail) > self.max_trail:
                self.trail.pop(0)
                
            self.pos += self.velocity
            
            # Check if reached target
            dist_to_target = self.pos.distance_to(self.target_pos)
            if dist_to_target < self.speed and self.is_hit:
                self.hit_triggered = True
                self.pos = pygame.Vector2(self.target_pos)
                self._on_hit()
            
            # If missed or hit was triggered and finished, or just passed through, check off screen
            if (self.pos.x < -200 or self.pos.x > 2000 or 
                self.pos.y < -200 or self.pos.y > 1200):
                self.finished = True
        else:
            self._update_hit_effect()

    def _on_hit(self):
        if self.effect_type == 'sorcerer':
            for _ in range(random.randint(3, 5)):
                self.particles.append({
                    'pos': pygame.Vector2(self.pos),
                    'vel': pygame.Vector2(random.uniform(-3, 3), random.uniform(-3, 3)),
                    'life': 255
                })
        elif self.effect_type == 'wizard':
            for _ in range(random.randint(5, 8)):
                self.particles.append({
                    'pos': pygame.Vector2(self.pos),
                    'vel': pygame.Vector2(random.uniform(-2, 2), random.uniform(-4, 0)),
                    'life': 255
                })
        elif self.effect_type == 'cleric':
            self.ring_radius = 0
            self.alpha = 255

    def _update_hit_effect(self):
        if self.effect_type == 'ranger':
            self.alpha -= 20
            if self.alpha <= 0:
                self.finished = True
        elif self.effect_type == 'sorcerer':
            for p in self.particles:
                p['pos'] += p['vel']
                p['life'] -= 10
            self.particles = [p for p in self.particles if p['life'] > 0]
            if not self.particles:
                self.finished = True
        elif self.effect_type == 'wizard':
            gravity = 0.2
            for p in self.particles:
                p['vel'].y += gravity
                p['pos'] += p['vel']
                p['life'] -= 8
            self.particles = [p for p in self.particles if p['life'] > 0]
            if not self.particles:
                self.finished = True
        elif self.effect_type == 'cleric':
            self.ring_radius += 3
            self.alpha -= 10
            if self.alpha <= 0:
                self.finished = True

    def draw(self, surface):
        if self.finished:
            return

        if not self.hit_triggered:
            self._draw_projectile(surface)
        else:
            self._draw_hit(surface)

    def _draw_projectile(self, surface):
        if self.effect_type == 'ranger':
            # Trail
            for i, p in enumerate(self.trail):
                alpha = int((i / len(self.trail)) * 150)
                s = pygame.Surface((4, 4), pygame.SRCALPHA)
                pygame.draw.circle(s, (0, 0, 0, alpha), (2, 2), 2)
                surface.blit(s, p)
            
            # Triangle
            angle = math.atan2(self.velocity.y, self.velocity.x)
            size = scale_x(10)
            p1 = self.pos + pygame.Vector2(size, 0).rotate_rad(angle)
            p2 = self.pos + pygame.Vector2(-size, -size/2).rotate_rad(angle)
            p3 = self.pos + pygame.Vector2(-size, size/2).rotate_rad(angle)
            pygame.draw.polygon(surface, (255, 255, 255), [p1, p2, p3])
            pygame.draw.polygon(surface, (0, 0, 0), [p1, p2, p3], 1)

        elif self.effect_type == 'sorcerer':
            pygame.draw.circle(surface, (255, 140, 0), self.pos, scale_x(6))
            pygame.draw.circle(surface, (255, 255, 0), self.pos, scale_x(3))

        elif self.effect_type == 'wizard':
            angle = math.atan2(self.velocity.y, self.velocity.x)
            size_l = scale_x(12)
            size_w = scale_x(4)
            p1 = self.pos + pygame.Vector2(size_l, 0).rotate_rad(angle)
            p2 = self.pos + pygame.Vector2(-size_l, -size_w).rotate_rad(angle)
            p3 = self.pos + pygame.Vector2(-size_l, size_w).rotate_rad(angle)
            pygame.draw.polygon(surface, (173, 216, 230), [p1, p2, p3])
            pygame.draw.polygon(surface, (255, 255, 255), [p1, p2, p3], 1)

        elif self.effect_type == 'cleric':
            pygame.draw.circle(surface, (255, 215, 0), self.pos, scale_x(8))
            pygame.draw.circle(surface, (255, 255, 255), self.pos, scale_x(4))

    def _draw_hit(self, surface):
        if self.effect_type == 'ranger':
            # Fade out the triangle at hit position
            angle = math.atan2(self.velocity.y, self.velocity.x)
            size = scale_x(10)
            p1 = self.pos + pygame.Vector2(size, 0).rotate_rad(angle)
            p2 = self.pos + pygame.Vector2(-size, -size/2).rotate_rad(angle)
            p3 = self.pos + pygame.Vector2(-size, size/2).rotate_rad(angle)
            
            pts = [p1, p2, p3]
            min_x = min(p.x for p in pts)
            min_y = min(p.y for p in pts)
            max_x = max(p.x for p in pts)
            max_y = max(p.y for p in pts)
            
            s = pygame.Surface((max_x - min_x + 2, max_y - min_y + 2), pygame.SRCALPHA)
            local_pts = [(p.x - min_x, p.y - min_y) for p in pts]
            pygame.draw.polygon(s, (255, 255, 255, self.alpha), local_pts)
            surface.blit(s, (min_x, min_y))

        elif self.effect_type == 'sorcerer':
            for p in self.particles:
                s = pygame.Surface((6, 6), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 140, 0, p['life']), (3, 3), 3)
                surface.blit(s, p['pos'])

        elif self.effect_type == 'wizard':
            for p in self.particles:
                s = pygame.Surface((4, 4), pygame.SRCALPHA)
                pygame.draw.rect(s, (173, 216, 230, p['life']), (0, 0, 4, 4))
                surface.blit(s, p['pos'])

        elif self.effect_type == 'cleric':
            s = pygame.Surface((self.ring_max_radius * 2, self.ring_max_radius * 2), pygame.SRCALPHA)
            center = (self.ring_max_radius, self.ring_max_radius)
            pygame.draw.circle(s, (255, 215, 0, self.alpha), center, int(self.ring_radius), 2)
            surface.blit(s, (self.pos.x - self.ring_max_radius, self.pos.y - self.ring_max_radius))

class ProjectileManager:
    def __init__(self):
        self.projectiles = []

    def spawn(self, start_pos, target_pos, effect_type, is_hit):
        new_proj = Projectile(start_pos, target_pos, effect_type, is_hit)
        self.projectiles.append(new_proj)

    def update(self):
        for proj in self.projectiles:
            proj.update()
        self.projectiles = [p for p in self.projectiles if not p.finished]

    def draw(self, surface):
        for proj in self.projectiles:
            proj.draw(surface)

    def is_finished(self):
        return len(self.projectiles) == 0
