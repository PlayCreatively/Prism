from typing import List, Optional
from pathlib import Path
import json
import colorsys

# Module-level cache for user settings
_user_settings_cache = {
    'hidden_users': set(),
    'all_users': [],
}

# RGB Spectrum offset: shifts the starting position of the color window
# 0.0 = start at Red, 0.33 = start at Green, 0.67 = start at Blue, 1.0 = wraps back to Red
# Range: 0.0 to 1.0 (values wrap around)
RGB_SPECTRUM_OFFSET = {
    3 : 0.2,
    4 : 0.2
}


def get_all_users(data_dir: str = "db/data") -> List[str]:
    """
    Discover all users by scanning JSON files in the data directory.
    Returns a sorted list of user IDs (filenames without .json extension).
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        return []
    users = sorted([f.stem for f in data_path.glob("*.json")])
    _user_settings_cache['all_users'] = users
    return users


def get_hidden_users(global_path: str = "db/global.json") -> set:
    """
    Load the set of hidden users from global settings.
    """
    path = Path(global_path)
    if not path.exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            hidden = data.get("hidden_users", [])
            _user_settings_cache['hidden_users'] = set(hidden)
            return set(hidden)
    except Exception:
        return set()


def set_hidden_users(hidden_users: set, global_path: str = "db/global.json") -> None:
    """
    Save the set of hidden users to global settings.
    """
    path = Path(global_path)
    data = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    
    data["hidden_users"] = list(hidden_users)
    _user_settings_cache['hidden_users'] = hidden_users
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_visible_users(data_dir: str = "db/data", global_path: str = "db/global.json") -> List[str]:
    """
    Return list of users that are not hidden.
    """
    all_users = get_all_users(data_dir)
    hidden = get_hidden_users(global_path)
    return [u for u in all_users if u not in hidden]


def toggle_user_visibility(user_id: str, global_path: str = "db/global.json") -> bool:
    """
    Toggle a user's visibility. Returns True if user is now visible, False if hidden.
    """
    hidden = get_hidden_users(global_path)
    if user_id in hidden:
        hidden.discard(user_id)
        is_visible = True
    else:
        hidden.add(user_id)
        is_visible = False
    set_hidden_users(hidden, global_path)
    return is_visible


def get_user_color(user_id: str, visible_users: Optional[List[str]] = None, data_dir: str = "db/data", global_path: str = "db/global.json") -> str:
    """
    Get the assigned color for a specific user based on their position in the visible users list.
    
    Color is determined by linear RGB splitting:
    - The RGB spectrum (R→G→B) is divided into N segments for N users
    - Each user gets one segment
    - When all users combine, their colors sum to white (255,255,255)
    - RGB_SPECTRUM_OFFSET shifts the starting position (0=R, 0.33=G, 0.67=B)
    
    Examples (with offset=0):
    - 3 users: (1,0,0), (0,1,0), (0,0,1) - pure RGB
    - 2 users: (1,0.5,0), (0,0.5,1) - orange and cyan
    - 4 users: (0.75,0,0), (0.25,0.5,0), (0,0.5,0.25), (0,0,0.75)
    
    Returns hex color string.
    """
    if visible_users is None:
        visible_users = get_visible_users(data_dir, global_path)
    
    if not visible_users or user_id not in visible_users:
        return '#808080'  # Gray for hidden/unknown users
    
    index = visible_users.index(user_id)
    count = len(visible_users)
    
    # Each user gets a segment of width 3/count along the R-G-B spectrum
    # Spectrum: R covers [0,1], G covers [1,2], B covers [2,3]
    # Apply offset (scaled to 0-3 range) and wrap around
    offset = (RGB_SPECTRUM_OFFSET.get(count, 0.0) % 1.0) * 3.0
    segment_width = 3.0 / count
    start = (index * segment_width + offset) % 3.0
    end = start + segment_width
    
    # Calculate overlap with each color channel (handling wrap-around)
    def channel_overlap(ch_start, ch_end, seg_start, seg_end):
        """Calculate overlap between a segment and a channel, handling wrap-around."""
        # Direct overlap
        overlap = max(0, min(ch_end, seg_end) - max(ch_start, seg_start))
        # Wrapped overlap (segment extends past 3.0 and wraps to 0)
        if seg_end > 3.0:
            wrapped_end = seg_end - 3.0
            overlap += max(0, min(ch_end, wrapped_end) - max(ch_start, 0))
        return overlap
    
    r = channel_overlap(0, 1, start, end)  # R channel [0,1]
    g = channel_overlap(1, 2, start, end)  # G channel [1,2]
    b = channel_overlap(2, 3, start, end)  # B channel [2,3]
    
    return '#{:02x}{:02x}{:02x}'.format(int(r * 255), int(g * 255), int(b * 255))


def color_from_users(users: List[str], visible_users: Optional[List[str]] = None, data_dir: str = "db/data", global_path: str = "db/global.json") -> str:
    """
    Calculate the combined color for a set of interested users.
    
    Uses linear RGB splitting where each user contributes their segment of the R→G→B spectrum.
    When all visible users are interested, the result is white (255,255,255).
    RGB_SPECTRUM_OFFSET shifts the starting position of the color window.
    
    Examples with 3 users (offset=0):
    - User 1 only: Red (255,0,0)
    - User 2 only: Green (0,255,0)
    - User 3 only: Blue (0,0,255)
    - All 3: White (255,255,255)
    
    Args:
        users: List of user IDs who are interested in this node
        visible_users: Optional pre-computed list of visible users
        data_dir: Path to user data directory
        global_path: Path to global settings file
    
    Returns:
        Hex color string
    """
    if visible_users is None:
        visible_users = get_visible_users(data_dir, global_path)
    
    if not visible_users:
        return '#d0d0d0'  # Light gray if no visible users
    
    # Filter to only visible users who are interested
    interested_visible = [u for u in users if u in visible_users]
    
    if not interested_visible:
        return '#d0d0d0'  # Light gray if no interested visible users
    
    count = len(visible_users)
    segment_width = 3.0 / count
    offset = (RGB_SPECTRUM_OFFSET.get(count, 0.0) % 1.0) * 3.0
    
    # Helper for wrap-around channel overlap
    def channel_overlap(ch_start, ch_end, seg_start, seg_end):
        overlap = max(0, min(ch_end, seg_end) - max(ch_start, seg_start))
        if seg_end > 3.0:
            wrapped_end = seg_end - 3.0
            overlap += max(0, min(ch_end, wrapped_end) - max(ch_start, 0))
        return overlap
    
    # Sum up RGB contributions from all interested users
    r_sum, g_sum, b_sum = 0.0, 0.0, 0.0
    
    for user_id in interested_visible:
        index = visible_users.index(user_id)
        start = (index * segment_width + offset) % 3.0
        end = start + segment_width
        
        # Calculate this user's RGB contribution with wrap-around
        r = channel_overlap(0, 1, start, end)
        g = channel_overlap(1, 2, start, end)
        b = channel_overlap(2, 3, start, end)
        
        r_sum += r
        g_sum += g
        b_sum += b
    
    # Clamp to 1.0 (255) - shouldn't exceed since segments don't overlap
    r_final = min(255, int(r_sum * 255))
    g_final = min(255, int(g_sum * 255))
    b_final = min(255, int(b_sum * 255))
    
    return '#{:02x}{:02x}{:02x}'.format(r_final, g_final, b_final)

def lighten_hex(hex_color: str, amount: float = 0.5) -> str:
    """Lightens a hex color by mixing it with white."""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

def darken_hex(hex_color: str, amount: float) -> str:
    """Darkens a hex color by mixing it with black. amount=0 is no change, amount=1 is black."""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    r = int(r * (1 - amount))
    g = int(g * (1 - amount))
    b = int(b * (1 - amount))
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

def lerp_hex(hex_a: str, hex_b: str, t: float) -> str:
    """Linearly interpolates between two hex colors by t (0.0 to 1.0)."""
    hex_a = hex_a.lstrip('#')
    hex_b = hex_b.lstrip('#')
    r1, g1, b1 = tuple(int(hex_a[i:i+2], 16) for i in (0, 2, 4))
    r2, g2, b2 = tuple(int(hex_b[i:i+2], 16) for i in (0, 2, 4))
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

def hex_to_rgba(hex_color: str, opacity: float) -> str:
    """Converts hex color and opacity to rgba string."""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r}, {g}, {b}, {opacity})'