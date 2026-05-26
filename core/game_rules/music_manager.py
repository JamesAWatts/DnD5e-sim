import pygame
import os
import random
from core.game_rules.path_utils import get_resource_path

class MusicManager:
    def __init__(self):
        # 1. Get the dynamic path to assets/bgm
        self.music_dir = get_resource_path(os.path.join('assets', 'bgm'))
        
        self.current_track = None
        self.last_combat_index = -1
        self.last_boss_index = -1
        
        # Settings
        self.volume = 0.15
        self.is_muted = False
        
        # Fading Logic
        self.fade_state = 'IDLE' # 'IDLE', 'FADING_OUT', 'FADING_IN'
        self.fade_timer = 0.0
        self.FADE_DURATION = 0.75 # Seconds per phase (total 1.5s transition)
        self.target_track = None
        self.target_loops = -1

        # 2. Force a clean mixer initialization
        if not pygame.mixer.get_init():
            pygame.mixer.pre_init(44100, -16, 2, 2048)
            pygame.mixer.init()
            
        # 3. Set an initial volume
        pygame.mixer.music.set_volume(self.volume)
        print(f"MusicManager: Mixer initialized. Music Dir: {self.music_dir}")

    def update(self, dt_ms):
        """Processes music volume fades."""
        if self.is_muted:
            return

        if self.fade_state == 'FADING_OUT':
            self.fade_timer += dt_ms / 1000.0
            progress = min(1.0, self.fade_timer / self.FADE_DURATION)
            
            # Reduce volume
            current_vol = self.volume * (1.0 - progress)
            pygame.mixer.music.set_volume(current_vol)

            if progress >= 1.0:
                # Switch tracks
                self._execute_play(self.target_track, self.target_loops)
                self.fade_state = 'FADING_IN'
                self.fade_timer = 0.0
                pygame.mixer.music.set_volume(0.0)

        elif self.fade_state == 'FADING_IN':
            self.fade_timer += dt_ms / 1000.0
            progress = min(1.0, self.fade_timer / self.FADE_DURATION)
            
            # Increase volume
            current_vol = self.volume * progress
            pygame.mixer.music.set_volume(current_vol)

            if progress >= 1.0:
                pygame.mixer.music.set_volume(self.volume)
                self.fade_state = 'IDLE'
                self.target_track = None

    def set_volume(self, value):
        """Sets the target volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, value))
        if not self.is_muted and self.fade_state == 'IDLE':
            pygame.mixer.music.set_volume(self.volume)

    def toggle_mute(self):
        """Toggles between muted and unmuted."""
        self.is_muted = not self.is_muted
        if self.is_muted:
            pygame.mixer.music.set_volume(0.0)
        else:
            if self.fade_state == 'IDLE':
                pygame.mixer.music.set_volume(self.volume)
        return self.is_muted

    def play_state_music(self, state_name, is_boss=False):
        """
        Initiates a faded transition to the music defined for the state.
        """
        new_path = None
        # Handle variants of state names (e.g. CombatStateNew -> combat)
        s_name = state_name.lower()

        # 1. Map states to their music files/folders
        if 'title' in s_name:
            new_path = os.path.join(self.music_dir, 'title', 'theme - into the throne v3.mid')
        elif 'hub' in s_name:
            new_path = os.path.join(self.music_dir, 'hub', 'scene - prepare for tomorrow.mid')
        elif any(x in s_name for x in ['level_up', 'levelup', 'victory']):
            new_path = os.path.join(self.music_dir, 'level_up', 'jingle - win.mid')
        elif 'combat' in s_name:
            if is_boss:
                new_path = self._get_random_track('boss')
            else:
                new_path = self._get_random_track('combat')

        # 2. Check if we actually have music for this state
        if new_path is None or not os.path.exists(new_path):
            return

        # 3. Check if we're already playing or transitioning to this exact track
        if new_path == self.current_track or new_path == self.target_track:
            return

        # 4. Initiate Fade Transition
        loops = 0 if any(x in s_name for x in ['level_up', 'levelup', 'victory']) else -1
        
        if self.current_track is None or not pygame.mixer.music.get_busy():
            # Quick start if nothing is playing
            self._execute_play(new_path, loops)
            self.fade_state = 'FADING_IN'
            self.fade_timer = 0.0
            pygame.mixer.music.set_volume(0.0)
        else:
            # Fade out current, then fade in new
            self.target_track = new_path
            self.target_loops = loops
            self.fade_state = 'FADING_OUT'
            self.fade_timer = 0.0

    def _execute_play(self, path, loops):
        """Immediate track execution (stops current)."""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(loops)
            self.current_track = path
            print(f"MusicManager: Transitioned to {os.path.basename(path)}")
        except Exception as e:
            print(f"MusicManager Error: Could not play {path}: {e}")

    def _get_random_track(self, folder_name):
        """Picks a random track from the specified bgm subfolder."""
        folder_path = os.path.join(self.music_dir, folder_name)
        if not os.path.exists(folder_path):
            return None
            
        tracks = [f for f in os.listdir(folder_path) if f.endswith('.mid')]
        if not tracks: return None
        if len(tracks) == 1: return os.path.join(folder_path, tracks[0])

        # Avoid repeat
        last_idx_attr = f"last_{folder_name}_index"
        last_idx = getattr(self, last_idx_attr, -1)
        
        new_index = last_idx
        while new_index == last_idx:
            new_index = random.randint(0, len(tracks) - 1)
        
        setattr(self, last_idx_attr, new_index)
        return os.path.join(folder_path, tracks[new_index])
