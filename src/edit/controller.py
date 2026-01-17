"""
Edit Controller - Single source of truth for manual editing state.

This controller manages all edit mode state and coordinates between:
- Mouse/keyboard events from the UI
- Preview overlay rendering
- Action execution via EditActions

The key insight is that we NEVER update ECharts during preview.
We only update ECharts when an edit is committed.
"""

import math
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass

from src.edit.constants import (
    EDGE_MIDDLE_TOLERANCE,
    EDGE_HOVER_TOLERANCE,
    CONNECTION_RADIUS,
)


@dataclass
class EditState:
    """Immutable snapshot of current edit state."""
    is_active: bool = False
    mouse_x: float = 0
    mouse_y: float = 0
    dragging_node_id: Optional[str] = None
    action: Optional[str] = None
    target_edge: Optional[Tuple[str, str]] = None
    target_node_id: Optional[str] = None
    preview_position: Optional[Tuple[float, float]] = None
    is_edge_middle: bool = False


class EditController:
    """Manages edit mode state and calculates what action would occur."""
    
    def __init__(self):
        self._state = EditState()
        self._nodes: List[Dict[str, Any]] = []
        self._edges: List[Dict[str, Any]] = []
        self._node_positions: Dict[str, Tuple[float, float]] = {}
        self._node_sizes: Dict[str, float] = {}
        self._active_user: str = 'Alex'
        self._on_state_change: Optional[Callable[[EditState], None]] = None
    
    @property
    def state(self) -> EditState:
        return self._state
    
    def set_on_state_change(self, callback: Callable[[EditState], None]):
        self._on_state_change = callback
    
    def update_graph_data(self, nodes: List[Dict], edges: List[Dict], 
                          positions: Dict[str, Tuple[float, float]],
                          node_sizes: Dict[str, float],
                          active_user: str):
        self._nodes = nodes
        self._edges = edges
        self._node_positions = positions
        self._node_sizes = node_sizes
        self._active_user = active_user
    
    def set_ctrl_pressed(self, pressed: bool) -> EditState:
        if pressed == self._state.is_active:
            return self._state
        
        if pressed:
            self._state = EditState(is_active=True, mouse_x=self._state.mouse_x, mouse_y=self._state.mouse_y)
            self._recalculate_action()
        else:
            self._state = EditState(is_active=False, mouse_x=self._state.mouse_x, mouse_y=self._state.mouse_y)
        
        self._notify_change()
        return self._state
    
    def set_mouse_position(self, x: float, y: float) -> EditState:
        self._state = EditState(
            is_active=self._state.is_active, mouse_x=x, mouse_y=y,
            dragging_node_id=self._state.dragging_node_id
        )
        if self._state.is_active:
            self._recalculate_action()
            self._notify_change()
        return self._state
    
    def start_drag(self, node_id: str) -> EditState:
        self._state = EditState(
            is_active=self._state.is_active, mouse_x=self._state.mouse_x,
            mouse_y=self._state.mouse_y, dragging_node_id=node_id
        )
        self._recalculate_action()
        self._notify_change()
        return self._state
    
    def end_drag(self) -> EditState:
        self._state = EditState(
            is_active=self._state.is_active, mouse_x=self._state.mouse_x,
            mouse_y=self._state.mouse_y, dragging_node_id=None
        )
        self._recalculate_action()
        self._notify_change()
        return self._state
    
    def get_commit_data(self) -> Optional[Dict[str, Any]]:
        if not self._state.action:
            return None
        return {
            'action': self._state.action,
            'mouse_x': self._state.mouse_x,
            'mouse_y': self._state.mouse_y,
            'target_edge': self._state.target_edge,
            'target_node_id': self._state.target_node_id,
            'dragging_node_id': self._state.dragging_node_id,
            'preview_position': self._state.preview_position,
            'active_user': self._active_user
        }
    
    def _notify_change(self):
        if self._on_state_change:
            self._on_state_change(self._state)
    
    def _recalculate_action(self):
        if not self._state.is_active:
            return
        
        mouse = (self._state.mouse_x, self._state.mouse_y)
        
        # Priority 1: Dragging node over edge
        if self._state.dragging_node_id:
            edge_hit = self._find_edge_at(mouse)
            if edge_hit and edge_hit['is_middle']:
                self._state = EditState(
                    is_active=True, mouse_x=mouse[0], mouse_y=mouse[1],
                    dragging_node_id=self._state.dragging_node_id,
                    action='make_intermediary',
                    target_edge=(edge_hit['source'], edge_hit['target']),
                    is_edge_middle=True
                )
                return
            
            nearby = self._find_nearby_node(mouse, exclude=self._state.dragging_node_id)
            if nearby:
                self._state = EditState(
                    is_active=True, mouse_x=mouse[0], mouse_y=mouse[1],
                    dragging_node_id=self._state.dragging_node_id,
                    action='connect', target_node_id=nearby['id']
                )
                return
            
            self._state = EditState(
                is_active=True, mouse_x=mouse[0], mouse_y=mouse[1],
                dragging_node_id=self._state.dragging_node_id, action=None
            )
            return
        
        # Priority 2: Click on edge
        edge_hit = self._find_edge_at(mouse)
        if edge_hit:
            if edge_hit['is_middle']:
                self._state = EditState(
                    is_active=True, mouse_x=mouse[0], mouse_y=mouse[1],
                    action='create_intermediary',
                    target_edge=(edge_hit['source'], edge_hit['target']),
                    preview_position=edge_hit['midpoint'], is_edge_middle=True
                )
            else:
                self._state = EditState(
                    is_active=True, mouse_x=mouse[0], mouse_y=mouse[1],
                    action='cut_edge',
                    target_edge=(edge_hit['source'], edge_hit['target']),
                    is_edge_middle=False
                )
            return
        
        # Priority 3: Click near node
        nearby = self._find_nearby_node(mouse)
        if nearby:
            self._state = EditState(
                is_active=True, mouse_x=mouse[0], mouse_y=mouse[1],
                action='create_and_connect', target_node_id=nearby['id'],
                preview_position=mouse
            )
            return
        
        # Priority 4: Empty space
        self._state = EditState(
            is_active=True, mouse_x=mouse[0], mouse_y=mouse[1],
            action='create_node', preview_position=mouse
        )
    
    def _find_edge_at(self, mouse: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        closest = None
        closest_dist = float('inf')
        
        for edge in self._edges:
            src_id, tgt_id = edge.get('source'), edge.get('target')
            if src_id not in self._node_positions or tgt_id not in self._node_positions:
                continue
            
            src_pos, tgt_pos = self._node_positions[src_id], self._node_positions[tgt_id]
            dist, t = self._point_to_line_distance(mouse, src_pos, tgt_pos)
            
            if dist < EDGE_HOVER_TOLERANCE and dist < closest_dist:
                closest_dist = dist
                is_middle = abs(t - 0.5) <= EDGE_MIDDLE_TOLERANCE
                mid_x = (src_pos[0] + tgt_pos[0]) / 2
                mid_y = (src_pos[1] + tgt_pos[1]) / 2
                closest = {
                    'source': src_id, 'target': tgt_id, 'is_middle': is_middle,
                    't': t, 'distance': dist, 'midpoint': (mid_x, mid_y)
                }
        return closest
    
    def _find_nearby_node(self, mouse: Tuple[float, float], exclude: str = None) -> Optional[Dict[str, Any]]:
        closest = None
        closest_dist = float('inf')
        
        for node in self._nodes:
            node_id = node.get('id')
            if node_id == exclude or node_id not in self._node_positions:
                continue
            
            pos = self._node_positions[node_id]
            dist = math.sqrt((mouse[0] - pos[0])**2 + (mouse[1] - pos[1])**2)
            radius = self._node_sizes.get(node_id, 25) + CONNECTION_RADIUS
            
            if dist < radius and dist < closest_dist:
                closest_dist = dist
                closest = {'id': node_id, 'position': pos, 'distance': dist}
        return closest
    
    def _point_to_line_distance(self, point: Tuple[float, float],
                                 line_start: Tuple[float, float],
                                 line_end: Tuple[float, float]) -> Tuple[float, float]:
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end
        dx, dy = x2 - x1, y2 - y1
        
        if dx == 0 and dy == 0:
            return math.sqrt((px - x1)**2 + (py - y1)**2), 0.0
        
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        closest_x, closest_y = x1 + t * dx, y1 + t * dy
        return math.sqrt((px - closest_x)**2 + (py - closest_y)**2), t
