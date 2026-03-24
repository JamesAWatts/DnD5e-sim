# =========================
# SCREEN / RESOLUTION
# =========================
BASE_WIDTH = 800
BASE_HEIGHT = 600

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# Scale factors (used for UI scaling)
SCALE_X = SCREEN_WIDTH / BASE_WIDTH
SCALE_Y = SCREEN_HEIGHT / BASE_HEIGHT


# =========================
# FPS / TIMING
# =========================
FPS = 60


# =========================
# COLORS
# =========================
COLOR_BG = (30, 30, 30)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_RED = (200, 50, 50)
COLOR_GREEN = (50, 200, 50)
COLOR_BLUE = (50, 100, 200)
COLOR_GRAY = (100, 100, 100)
COLOR_LIGHT_GRAY = (200, 200, 200)
COLOR_ROYAL_BLUE = (65, 105, 225)
COLOR_MIDNIGHT_BLUE = (25, 25, 112)
COLOR_GOLD = (255, 215, 0)


# =========================
# FONT
# =========================
DEFAULT_FONT_SIZE = 32


# =========================
# UI HELPERS (SCALING)
# =========================
def scale_x(value):
    return int(value * SCALE_X)

def scale_y(value):
    return int(value * SCALE_Y)

def scale_pos(x, y):
    return int(x * SCALE_X), int(y * SCALE_Y)

def scale_size(w, h):
    return int(w * SCALE_X), int(h * SCALE_Y)

def scale_font(size):
    return int(size * SCALE_Y)


# =========================
# UI LAYOUT (OPTIONAL BUT USEFUL)
# =========================
PADDING_SMALL = scale_y(5)
PADDING_MEDIUM = scale_y(10)
PADDING_LARGE = scale_y(20)

# Example panel heights (like Pokémon UI)
BOTTOM_PANEL_HEIGHT = scale_y(150)
TOP_BAR_HEIGHT = scale_y(50)