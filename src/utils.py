from typing import List

def color_from_users(users: List[str]) -> str:
    """
    Map user presence to RGB-ish colors per project documentation.
    Alex -> Red, Sasha -> Green, Alison -> Blue
    """
    r = 255 if 'Alex' in users else 0
    g = 255 if 'Sasha' in users else 0
    b = 255 if 'Alison' in users else 0
    # If none selected, return light gray
    if r == g == b == 0:
        return '#d0d0d0'
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

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

def hex_to_rgba(hex_color: str, opacity: float) -> str:
    """Converts hex color and opacity to rgba string."""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f'rgba({r}, {g}, {b}, {opacity})'
