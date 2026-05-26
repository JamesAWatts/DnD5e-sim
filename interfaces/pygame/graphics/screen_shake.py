import random
import math

class ScreenShake:
    """
    Handles screen shake effects by providing X and Y offsets.
    """
    def __init__(self):
        self.intensity = 0
        self.duration = 0
        self.decay = 0.9
        self.offset_x = 0
        self.offset_y = 0

    def trigger(self, intensity=10, duration=20):
        """
        Starts a screen shake.
        intensity: Maximum pixels to shake.
        duration: Number of frames the shake lasts.
        """
        self.intensity = intensity
        self.duration = duration

    def trigger_magnitude(self, magnitude):
        """
        Triggers a shake based on a predefined magnitude (0-5).
        """
        if magnitude == 0:
            return
        elif magnitude == 1:
            self.trigger(intensity=10, duration=10)
        elif magnitude == 2:
            self.trigger(intensity=50, duration=15)
        elif magnitude == 3:
            self.trigger(intensity=100, duration=25)
        elif magnitude == 4:
            self.trigger(intensity=150, duration=35)
        elif magnitude == 5:
            self.trigger(intensity=200, duration=50)

    @staticmethod
    def get_magnitude_for_damage(damage):
        """
        Returns a shake magnitude based on damage dealt.
        """
        if damage < 50:
            return 0
        elif damage < 100:
            return 1
        elif damage < 150:
            return 2
        elif damage < 200:
            return 3
        elif damage < 250:
            return 4
        else:
            return 5

    def update(self):
        """Updates the shake offsets and reduces intensity/duration."""
        if self.duration > 0:
            self.offset_x = random.uniform(-self.intensity, self.intensity)
            self.offset_y = random.uniform(-self.intensity, self.intensity)
            
            self.duration -= 1
            self.intensity *= self.decay
            
            if self.duration <= 0 or self.intensity < 0.1:
                self.stop()
        else:
            self.stop()

    def stop(self):
        self.duration = 0
        self.intensity = 0
        self.offset_x = 0
        self.offset_y = 0

    def get_offsets(self):
        return self.offset_x, self.offset_y
