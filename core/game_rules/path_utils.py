import os
import sys

def get_resource_path(relative_path):
    """
    Get the absolute path to a resource.
    Supports Development, PyInstaller, and WebAssembly (Pygbag).
    """
    if sys.platform == "emscripten":
        # Pygbag VFS is usually rooted at /
        base_path = ""
    else:
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            # Development: This file is in core/game_rules/, so root is ../../
            base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    return os.path.normpath(os.path.join(base_path, relative_path))

def get_writeable_path(relative_path):
    """
    Get the absolute path to a writable file/folder.
    WebAssembly uses /home/webuser/ for persistent data.
    """
    if sys.platform == "emscripten":
        base_path = "/home/webuser"
    elif getattr(sys, 'frozen', False):
        # Running as a bundled executable
        base_path = os.path.dirname(sys.executable)
    else:
        # Not running as a bundled executable, use the project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    return os.path.normpath(os.path.join(base_path, relative_path))
