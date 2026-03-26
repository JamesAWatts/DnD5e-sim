import pygame
import os

class SpriteManager:
    """
    Manages static combat sprites for both players and enemies.
    """
    _cache = {}
    
    # Mapping of enemy keys (from enemies.json) to list of potential image filenames
    _enemy_mapping = {
        "kobold": ["kobold.png"],
        "kobold_slinger": ["kobold.png"],
        "skeleton": ["skeleton1.png", "skeleton2.png", "skeleton3.png"],
        "kobold_sorcerer": ["kobold sorc.png"],
        "goblin": ["goblin.png"],
        "goblin_archer": ["goblin archer.png"],
        "cultist": ["cultist.png"],
        "harpy": ["harpy1.png", "harpy2.png"],
        "thief": ["thief.png"],
        "goblin_chieften": ["goblin chief.png"],
        "assassin": ["assassin1.png", "assassin2.png"],
        "guard": ["guard.png"],
        "orc_warrior": ["orc.png", "orc2.png"],
        "guard_captain": ["guard_cpt.png"],
        "minotaur": ["minotaur1.png", "minotaur2.png"],
        "medusa": ["medusa1.png", "medusa2.png"],
        "dark_knight": ["dark_knight.png", "dark_knight2.png"],
        "chimera": ["chimera1.png", "chimera2.png"],
        "ancient_dragon": ["dragon attack.png"]
    }

    @staticmethod
    def get_enemy_sprite(enemy_key, size=(192, 192)):
        """Loads and returns a sprite for the given enemy key."""
        enemy_key = enemy_key.lower().replace(" ", "_")
        
        # Determine which file to use
        filenames = SpriteManager._enemy_mapping.get(enemy_key, [])
        if not filenames:
            filenames = [f"{enemy_key}.png"]
            
        filename = filenames[0]
        cache_key = ("enemy", filename, size)
        
        if cache_key in SpriteManager._cache:
            return SpriteManager._cache[cache_key]

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        sprite_path = os.path.join(base_dir, "assets", "sprites", "enemy_images", filename)

        try:
            if not os.path.exists(sprite_path):
                # Try variations
                images_dir = os.path.join(base_dir, "assets", "sprites", "enemy_images")
                all_files = os.listdir(images_dir)
                matches = [f for f in all_files if f.lower().startswith(enemy_key)]
                if matches:
                    sprite_path = os.path.join(images_dir, matches[0])
                else:
                    raise FileNotFoundError(f"No sprite found for {enemy_key}")

            sprite = pygame.image.load(sprite_path).convert_alpha()
            if size:
                sprite = pygame.transform.scale(sprite, size)
            
            SpriteManager._cache[cache_key] = sprite
            return sprite
        except Exception:
            placeholder = pygame.Surface(size if size else (192, 192), pygame.SRCALPHA)
            pygame.draw.rect(placeholder, (200, 0, 0), placeholder.get_rect(), 2)
            return placeholder

    @staticmethod
    def get_player_sprite(class_name, size=(192, 192)):
        """Loads and returns a sprite for the given player class."""
        class_name = class_name.lower()
        filename = f"{class_name}.png"
        
        cache_key = ("player", filename, size)
        if cache_key in SpriteManager._cache:
            return SpriteManager._cache[cache_key]

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        sprite_path = os.path.join(base_dir, "assets", "sprites", "player_sprites", filename)

        try:
            if not os.path.exists(sprite_path):
                # Try webp fallback for special cases like kobold sorc if any
                if class_name == "kobold_sorcerer":
                     sprite_path = os.path.join(base_dir, "assets", "sprites", "player_sprites", "Kobald_sorc.webp")
                else:
                     raise FileNotFoundError(f"No player sprite found for {class_name}")

            sprite = pygame.image.load(sprite_path).convert_alpha()
            if size:
                sprite = pygame.transform.scale(sprite, size)
            
            SpriteManager._cache[cache_key] = sprite
            return sprite
        except Exception:
            placeholder = pygame.Surface(size if size else (192, 192), pygame.SRCALPHA)
            pygame.draw.rect(placeholder, (0, 0, 200), placeholder.get_rect(), 2)
            return placeholder
