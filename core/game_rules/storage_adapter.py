import json
import os
import sys
import asyncio
from core.game_rules.path_utils import get_writeable_path

class StorageBackend:
    """Base interface for storage operations."""
    def save(self, path, data):
        raise NotImplementedError

    def load(self, path):
        raise NotImplementedError

    def exists(self, path):
        raise NotImplementedError

    def delete(self, path):
        raise NotImplementedError

class DesktopStorage(StorageBackend):
    """Standard file I/O for desktop environments."""
    def save(self, path, data):
        temp_path = path + ".tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            if os.path.exists(path):
                os.remove(path)
            os.rename(temp_path, path)
            return True
        except Exception as e:
            print(f"[STORAGE] Desktop Save Error: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    def load(self, path):
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[STORAGE] Desktop Load Error: {e}")
            return None

    def exists(self, path):
        return os.path.exists(path)

    def delete(self, path):
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

class WebStorage(StorageBackend):
    """Bypasses Emscripten MEMFS to use browser localStorage directly."""
    def save(self, path, data):
        try:
            import platform
            platform.window.localStorage.setItem(path, json.dumps(data))
            return True
        except Exception as e:
            print(f"[STORAGE] Web Save Error (localStorage): {e}")
            return False

    def load(self, path):
        try:
            import platform
            saved_str = platform.window.localStorage.getItem(path)
            if saved_str is not None:
                return json.loads(saved_str)
            return None
        except Exception as e:
            print(f"[STORAGE] Web Load Error (localStorage): {e}")
            return None

    def exists(self, path):
        try:
            import platform
            return platform.window.localStorage.getItem(path) is not None
        except:
            return False

    def delete(self, path):
        try:
            import platform
            platform.window.localStorage.removeItem(path)
            return True
        except:
            return False

class StorageManager:
    """Adapter that selects the appropriate backend based on platform."""
    def __init__(self):
        self.is_web = (sys.platform == "emscripten")
        if self.is_web:
            self.backend = WebStorage()
        else:
            self.backend = DesktopStorage()
        
        self.save_dir = get_writeable_path("saves")
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def get_path(self, slot):
        # We keep the path format as the key for localStorage
        return os.path.join(self.save_dir, f"save_slot_{slot}.json")

    def serialize(self, data):
        """
        Strictly extracts primitive types (str, int, float, bool, list, dict).
        Filters out Pygame Surfaces, Rects, and internal '_' keys.
        """
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                # Skip keys starting with _ (internal runtime state)
                if isinstance(k, str) and k.startswith('_'):
                    continue
                # Skip non-serializable objects (Pygame specific check)
                if self._is_serializable(v):
                    cleaned[k] = self.serialize(v)
            return cleaned
        elif isinstance(data, list):
            return [self.serialize(item) for item in data if self._is_serializable(item)]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        return None

    def _is_serializable(self, obj):
        """Quick check for common non-serializable types in this engine."""
        # Check for Pygame types without importing pygame if possible, 
        # but usually it's better to just check the type name.
        t_name = type(obj).__name__
        if t_name in ['Surface', 'Rect', 'Font', 'Sound']:
            return False
        # Function/Lambda check
        if callable(obj):
            return False
        return True

    async def save_async(self, slot, data):
        """Asynchronous save wrapper to support Web sync."""
        path = self.get_path(slot)
        serialized = self.serialize(data)
        success = self.backend.save(path, serialized)
        
        if self.is_web:
            # localStorage is synchronous, but we yield to the browser loop anyway
            await asyncio.sleep(0)
            
        return success

    def save(self, slot, data):
        """Synchronous save (Desktop-friendly)."""
        path = self.get_path(slot)
        serialized = self.serialize(data)
        return self.backend.save(path, serialized)

    def load(self, slot):
        path = self.get_path(slot)
        return self.backend.load(path)

    def exists(self, slot):
        path = self.get_path(slot)
        return self.backend.exists(path)

    def delete(self, slot):
        path = self.get_path(slot)
        return self.backend.delete(path)
