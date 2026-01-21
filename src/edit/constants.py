"""
Shared constants for the manual editing system.

These values are used by both Python (edit_controller, edit_actions)
and JavaScript (edit_overlay). Keep them in sync!
"""

# Edge middle detection: 10% tolerance around center (t=0.5 ± 0.10)
# Click in this zone creates an intermediary node
EDGE_MIDDLE_TOLERANCE = 0.10

# Distance in pixels to detect edge hover
EDGE_HOVER_TOLERANCE = 20

# Distance in pixels to detect nearby nodes for connection
CONNECTION_RADIUS = 110

# Radius in pixels for direct node click (delete action)
NODE_CLICK_RADIUS = 25

# Chart scaling for position normalization
CHART_WIDTH = 500.0
CHART_HEIGHT = 350.0
