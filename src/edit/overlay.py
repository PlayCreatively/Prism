"""
Edit Overlay - Lightweight HTML/CSS layer for edit previews.

This overlay sits on top of the ECharts canvas and renders preview
elements using simple HTML/CSS. This is MUCH faster than updating ECharts.

IMPORTANT: This overlay queries ECharts directly for node positions to
account for zoom, pan, and viewport transformations.
"""

from nicegui import ui
from typing import Dict, Tuple

from src.edit.controller import EditState
from src.edit.constants import (
    EDGE_MIDDLE_TOLERANCE,
    EDGE_HOVER_TOLERANCE,
    CONNECTION_RADIUS,
    NODE_CLICK_RADIUS,
)
from src.utils import color_from_users


class EditOverlay:
    """
    Renders edit preview elements as an HTML overlay.
    
    Uses absolute-positioned divs for preview nodes and SVG for edges.
    Updates are nearly instantaneous since we're just moving DOM elements.
    Queries ECharts for actual screen positions of nodes.
    """
    
    def __init__(self):
        """Initialize overlay - call setup() after chart is created."""
        self._overlay_id = 'edit-overlay-container'
        self._active_user = None  # Set dynamically
        self._node_positions: Dict[str, Tuple[float, float]] = {}
        self._is_setup = False
        self._chart_element_id = None
    
    def setup(self, chart_element_id: str = None):
        """Create the overlay DOM elements. Call once after chart exists."""
        if self._is_setup:
            return
        
        self._chart_element_id = chart_element_id
        
        # Pass constants to JavaScript
        js_constants = f'''
            NODE_CLICK_RADIUS: {NODE_CLICK_RADIUS},
            CONNECTION_RADIUS: {CONNECTION_RADIUS},
            EDGE_HOVER_TOLERANCE: {EDGE_HOVER_TOLERANCE},
            EDGE_MIDDLE_TOLERANCE: {EDGE_MIDDLE_TOLERANCE}
        '''
        
        # Inject the overlay HTML and helper JavaScript
        ui.add_body_html(f'''
            <div id="{self._overlay_id}" style="
                position: absolute;
                top: 0; left: 0;
                width: 100%; height: 100%;
                pointer-events: none;
                z-index: 100;
            ">
                <!-- SVG layer for edge previews -->
                <svg id="edit-overlay-svg" style="
                    position: absolute;
                    top: 0; left: 0;
                    width: 100%; height: 100%;
                ">
                    <line id="preview-edge" 
                        x1="0" y1="0" x2="0" y2="0"
                        stroke="#ffffff" stroke-width="3" stroke-dasharray="8,4"
                        opacity="0" />
                </svg>
                
                <!-- Preview node (ghost circle) -->
                <div id="preview-node" style="
                    position: absolute;
                    width: 30px; height: 30px;
                    border-radius: 50%;
                    border: 3px dashed white;
                    opacity: 0;
                    transform: translate(-50%, -50%);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 10px;
                    color: white;
                    text-shadow: 0 0 3px black;
                "></div>
                
                <!-- Status indicator -->
                <div id="edit-status" style="
                    position: fixed;
                    bottom: 20px; left: 50%;
                    transform: translateX(-50%);
                    background: rgba(0,0,0,0.8);
                    color: white;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 500;
                    opacity: 0;
                    transition: opacity 0.15s;
                    font-family: system-ui, sans-serif;
                "></div>
                
                <!-- Debug panel (hidden by default) -->
                <div id="edit-debug" style="
                    position: fixed;
                    top: 10px; right: 10px;
                    background: rgba(0,0,0,0.9);
                    color: #0f0;
                    padding: 10px;
                    border-radius: 6px;
                    font-size: 11px;
                    font-family: monospace;
                    max-width: 300px;
                    max-height: 400px;
                    overflow: auto;
                    opacity: 0;
                    z-index: 9999;
                "></div>
            </div>
            
            <script>
                // Edit overlay state and helper functions
                // Constants are injected from Python to ensure consistency
                window.editOverlayState = {{
                    nodePositions: {{}},
                    nodeDataCoords: {{}},
                    nodeSizes: {{}},
                    nodeData: [],
                    edgeData: [],
                    chartRect: null,
                    debugLog: [],
                    // Hit detection config - synced with Python constants
                    {js_constants}
                }};
                
                window.updateEditOverlayPositions = function() {{
                    const log = [];
                    const st = window.editOverlayState;
                    
                    let chart = window.prismChart;
                    
                    if (!chart && window.prismChartId && typeof getElement === 'function') {{
                        try {{
                            const vueComponent = getElement(window.prismChartId);
                            if (vueComponent && vueComponent.chart) {{
                                chart = vueComponent.chart;
                                window.prismChart = chart;
                            }}
                        }} catch(e) {{}}
                    }}
                    
                    if (!chart) return;
                    
                    const chartEl = chart.getDom();
                    if (!chartEl) return;
                    
                    const rect = chartEl.getBoundingClientRect();
                    st.chartRect = rect;
                    
                    const overlay = document.getElementById('{self._overlay_id}');
                    if (overlay) {{
                        overlay.style.position = 'fixed';
                        overlay.style.left = rect.left + 'px';
                        overlay.style.top = rect.top + 'px';
                        overlay.style.width = rect.width + 'px';
                        overlay.style.height = rect.height + 'px';
                    }}
                    
                    const option = chart.getOption();
                    if (!option || !option.series || !option.series[0]) return;
                    
                    const positions = {{}};
                    const dataCoords = {{}};
                    const nodeSizes = {{}};
                    let successCount = 0;
                    
                    try {{
                        const model = chart.getModel();
                        const seriesModel = model.getSeriesByIndex(0);
                        if (seriesModel) {{
                            const graph = seriesModel.getGraph();
                            if (graph) {{
                                graph.eachNode(function(node) {{
                                    const layout = node.getLayout();
                                    const dataItem = node.getModel();
                                    const id = node.id;
                                    if (layout && id) {{
                                        const screenPos = chart.convertToPixel({{seriesIndex: 0}}, [layout[0], layout[1]]);
                                        if (screenPos && !isNaN(screenPos[0]) && !isNaN(screenPos[1])) {{
                                            positions[id] = [screenPos[0], screenPos[1]];
                                            dataCoords[id] = [layout[0], layout[1]];
                                            nodeSizes[id] = dataItem.get('symbolSize') || 25;
                                            successCount++;
                                        }}
                                    }}
                                }});
                            }}
                        }}
                    }} catch(e) {{}}
                    
                    if (successCount === 0) {{
                        const nodeData = option.series[0].data || [];
                        nodeData.forEach((node) => {{
                            if (node && node.id) {{
                                try {{
                                    const pos = chart.convertToPixel({{seriesIndex: 0}}, [node.x || 0, node.y || 0]);
                                    if (pos && !isNaN(pos[0]) && !isNaN(pos[1])) {{
                                        positions[node.id] = [pos[0], pos[1]];
                                        dataCoords[node.id] = [node.x || 0, node.y || 0];
                                        nodeSizes[node.id] = node.symbolSize || 25;
                                    }}
                                }} catch(e) {{}}
                            }}
                        }});
                    }}
                    
                    const edgeData = option.series[0].links || option.series[0].edges || [];
                    
                    st.nodePositions = positions;
                    st.nodeDataCoords = dataCoords;
                    st.nodeSizes = nodeSizes;
                    st.edgeData = edgeData;
                }};
                
                window.getNodeScreenPosition = function(nodeId) {{
                    return window.editOverlayState.nodePositions[nodeId] || null;
                }};
                
                window.detectEditAction = function(mouseX, mouseY, draggingNodeId) {{
                    const st = window.editOverlayState;
                    const positions = st.nodePositions;
                    const nodeSizes = st.nodeSizes || {{}};
                    const edges = st.edgeData;
                    const chart = window.prismChart;
                    
                    function screenToData(screenX, screenY) {{
                        if (chart) {{
                            try {{
                                const dataPos = chart.convertFromPixel({{seriesIndex: 0}}, [screenX, screenY]);
                                if (dataPos && !isNaN(dataPos[0]) && !isNaN(dataPos[1])) {{
                                    return dataPos;
                                }}
                            }} catch(e) {{}}
                        }}
                        return [screenX, screenY];
                    }}
                    
                    if (Object.keys(positions).length === 0) {{
                        const dataPos = screenToData(mouseX, mouseY);
                        return {{ action: 'create_node', preview_position: [mouseX, mouseY], data_position: dataPos }};
                    }}
                    
                    function pointToLine(px, py, x1, y1, x2, y2) {{
                        const dx = x2 - x1, dy = y2 - y1;
                        if (dx === 0 && dy === 0) {{
                            return [Math.sqrt((px-x1)**2 + (py-y1)**2), 0];
                        }}
                        let t = Math.max(0, Math.min(1, ((px-x1)*dx + (py-y1)*dy) / (dx*dx + dy*dy)));
                        const cx = x1 + t*dx, cy = y1 + t*dy;
                        return [Math.sqrt((px-cx)**2 + (py-cy)**2), t];
                    }}
                    
                    // If dragging a node...
                    if (draggingNodeId) {{
                        let closestEdge = null, closestEdgeDist = Infinity;
                        for (const edge of edges) {{
                            const srcId = edge.source, tgtId = edge.target;
                            const srcPos = positions[srcId], tgtPos = positions[tgtId];
                            if (!srcPos || !tgtPos) continue;
                            const [dist, t] = pointToLine(mouseX, mouseY, srcPos[0], srcPos[1], tgtPos[0], tgtPos[1]);
                            if (dist < st.EDGE_HOVER_TOLERANCE && dist < closestEdgeDist) {{
                                closestEdgeDist = dist;
                                const isMiddle = Math.abs(t - 0.5) <= st.EDGE_MIDDLE_TOLERANCE;
                                if (isMiddle) {{
                                    closestEdge = {{ source: srcId, target: tgtId, midpoint: [(srcPos[0]+tgtPos[0])/2, (srcPos[1]+tgtPos[1])/2] }};
                                }}
                            }}
                        }}
                        if (closestEdge) {{
                            return {{ action: 'make_intermediary', target_edge: [closestEdge.source, closestEdge.target], preview_position: closestEdge.midpoint }};
                        }}
                        
                        let closestNode = null, closestNodeDist = Infinity;
                        for (const [nodeId, pos] of Object.entries(positions)) {{
                            if (nodeId === draggingNodeId) continue;
                            const dist = Math.sqrt((mouseX - pos[0])**2 + (mouseY - pos[1])**2);
                            if (dist < st.CONNECTION_RADIUS && dist < closestNodeDist) {{
                                closestNodeDist = dist;
                                closestNode = {{ id: nodeId, position: pos }};
                            }}
                        }}
                        if (closestNode) {{
                            return {{ action: 'connect', target_node_id: closestNode.id, target_position: closestNode.position }};
                        }}
                        
                        return {{ action: null }};
                    }}
                    
                    // Check if directly ON a node (for delete)
                    let nodeUnderMouse = null;
                    let nodeUnderMouseDist = Infinity;
                    for (const [nodeId, pos] of Object.entries(positions)) {{
                        const dist = Math.sqrt((mouseX - pos[0])**2 + (mouseY - pos[1])**2);
                        const nodeRadius = (nodeSizes[nodeId] || 25) / 2 + 5;
                        if (dist < nodeRadius && dist < nodeUnderMouseDist) {{
                            nodeUnderMouseDist = dist;
                            nodeUnderMouse = {{ id: nodeId, position: pos }};
                        }}
                    }}
                    if (nodeUnderMouse) {{
                        return {{ action: 'delete_node', target_node_id: nodeUnderMouse.id, target_position: nodeUnderMouse.position }};
                    }}
                    
                    // Check for edge hit
                    let closestEdge = null, closestEdgeDist = Infinity, closestEdgeT = 0;
                    for (const edge of edges) {{
                        const srcId = edge.source, tgtId = edge.target;
                        const srcPos = positions[srcId], tgtPos = positions[tgtId];
                        if (!srcPos || !tgtPos) continue;
                        const [dist, t] = pointToLine(mouseX, mouseY, srcPos[0], srcPos[1], tgtPos[0], tgtPos[1]);
                        if (dist < st.EDGE_HOVER_TOLERANCE && dist < closestEdgeDist) {{
                            closestEdgeDist = dist;
                            closestEdgeT = t;
                            closestEdge = {{ source: srcId, target: tgtId, srcPos: srcPos, tgtPos: tgtPos }};
                        }}
                    }}
                    if (closestEdge) {{
                        const isMiddle = Math.abs(closestEdgeT - 0.5) <= st.EDGE_MIDDLE_TOLERANCE;
                        const midpoint = [(closestEdge.srcPos[0]+closestEdge.tgtPos[0])/2, (closestEdge.srcPos[1]+closestEdge.tgtPos[1])/2];
                        const dataMid = screenToData(midpoint[0], midpoint[1]);
                        if (isMiddle) {{
                            return {{ action: 'create_intermediary', target_edge: [closestEdge.source, closestEdge.target], preview_position: midpoint, data_position: dataMid }};
                        }} else {{
                            return {{ action: 'cut_edge', target_edge: [closestEdge.source, closestEdge.target] }};
                        }}
                    }}
                    
                    // Check for nearby node
                    let closestNode = null, closestNodeDist = Infinity;
                    for (const [nodeId, pos] of Object.entries(positions)) {{
                        const dist = Math.sqrt((mouseX - pos[0])**2 + (mouseY - pos[1])**2);
                        if (dist < st.CONNECTION_RADIUS && dist < closestNodeDist) {{
                            closestNodeDist = dist;
                            closestNode = {{ id: nodeId, position: pos }};
                        }}
                    }}
                    if (closestNode) {{
                        const dataPos = screenToData(mouseX, mouseY);
                        return {{ action: 'create_and_connect', target_node_id: closestNode.id, target_position: closestNode.position, preview_position: [mouseX, mouseY], data_position: dataPos }};
                    }}
                    
                    // Empty space
                    const dataPos = screenToData(mouseX, mouseY);
                    return {{ action: 'create_node', preview_position: [mouseX, mouseY], data_position: dataPos }};
                }};
            </script>
        ''')
        
        self._is_setup = True
    
    def set_active_user(self, user: str):
        """Set active user for color calculations."""
        self._active_user = user
    
    def set_node_positions(self, positions: Dict[str, Tuple[float, float]]):
        """Update cached node positions for edge drawing."""
        self._node_positions = positions
    
    def update(self, state: EditState):
        """
        Update overlay based on current edit state.
        This is called on every mouse move - must be fast!
        """
        if not state.is_active:
            self._hide_all()
            return
        
        color = color_from_users([self._active_user])
        dragging_js = f"'{state.dragging_node_id}'" if state.dragging_node_id else 'null'
        
        js_code = f'''
            (function() {{
                if (window.updateEditOverlayPositions) window.updateEditOverlayPositions();
                
                const mouseX = {state.mouse_x};
                const mouseY = {state.mouse_y};
                const draggingNodeId = {dragging_js};
                const userColor = '{color}';
                
                const detected = window.detectEditAction ? window.detectEditAction(mouseX, mouseY, draggingNodeId) : null;
                const action = detected?.action || 'create_node';
                const previewPos = detected?.preview_position || [mouseX, mouseY];
                const targetEdge = detected?.target_edge;
                const targetNodeId = detected?.target_node_id;
                const targetNodePos = detected?.target_position;
                
                const actionTexts = {{
                    'create_node': '➕ Click to create new node',
                    'create_and_connect': '➕🔗 Click to create and connect',
                    'create_intermediary': '➕ Click to insert node on edge',
                    'cut_edge': '✂️ Click to cut edge',
                    'connect': '🔗 Release to connect nodes',
                    'make_intermediary': '📍 Release to insert as intermediary',
                    'delete_node': '🗑️ Click to delete node'
                }};
                
                const status = document.getElementById('edit-status');
                if (status) {{
                    status.textContent = actionTexts[action] || 'Manual edit mode active';
                    status.style.opacity = '1';
                }}
                
                const previewNode = document.getElementById('preview-node');
                if (previewNode) {{
                    if (action === 'create_node' || action === 'create_and_connect' || action === 'create_intermediary') {{
                        previewNode.style.left = previewPos[0] + 'px';
                        previewNode.style.top = previewPos[1] + 'px';
                        previewNode.style.background = userColor;
                        previewNode.style.opacity = '0.6';
                    }} else {{
                        previewNode.style.opacity = '0';
                    }}
                }}
                
                const line = document.getElementById('preview-edge');
                if (line) {{
                    if (action === 'create_and_connect' && targetNodePos) {{
                        line.setAttribute('x1', previewPos[0]);
                        line.setAttribute('y1', previewPos[1]);
                        line.setAttribute('x2', targetNodePos[0]);
                        line.setAttribute('y2', targetNodePos[1]);
                        line.setAttribute('stroke', '#ffffff');
                        line.setAttribute('stroke-dasharray', '8,4');
                        line.setAttribute('opacity', '0.7');
                    }} else if (action === 'cut_edge' && targetEdge) {{
                        const srcPos = window.getNodeScreenPosition(targetEdge[0]);
                        const tgtPos = window.getNodeScreenPosition(targetEdge[1]);
                        if (srcPos && tgtPos) {{
                            line.setAttribute('x1', srcPos[0]);
                            line.setAttribute('y1', srcPos[1]);
                            line.setAttribute('x2', tgtPos[0]);
                            line.setAttribute('y2', tgtPos[1]);
                            line.setAttribute('stroke', '#ff4444');
                            line.setAttribute('stroke-dasharray', '4,4');
                            line.setAttribute('opacity', '0.8');
                        }}
                    }} else if ((action === 'create_intermediary' || action === 'make_intermediary') && targetEdge) {{
                        const srcPos = window.getNodeScreenPosition(targetEdge[0]);
                        const tgtPos = window.getNodeScreenPosition(targetEdge[1]);
                        if (srcPos && tgtPos) {{
                            line.setAttribute('x1', srcPos[0]);
                            line.setAttribute('y1', srcPos[1]);
                            line.setAttribute('x2', tgtPos[0]);
                            line.setAttribute('y2', tgtPos[1]);
                            line.setAttribute('stroke', '#00ff00');
                            line.setAttribute('stroke-dasharray', '8,4');
                            line.setAttribute('opacity', '0.6');
                        }}
                    }} else if (action === 'connect' && draggingNodeId && targetNodePos) {{
                        const srcPos = window.getNodeScreenPosition(draggingNodeId);
                        if (srcPos) {{
                            line.setAttribute('x1', srcPos[0]);
                            line.setAttribute('y1', srcPos[1]);
                            line.setAttribute('x2', targetNodePos[0]);
                            line.setAttribute('y2', targetNodePos[1]);
                            line.setAttribute('stroke', '#00ffff');
                            line.setAttribute('stroke-dasharray', '8,4');
                            line.setAttribute('opacity', '0.7');
                        }}
                    }} else {{
                        line.setAttribute('opacity', '0');
                    }}
                }}
                
                window.editOverlayState.lastAction = detected;
            }})();
        '''
        
        ui.run_javascript(js_code)
    
    def _hide_all(self):
        """Hide all preview elements."""
        ui.run_javascript('''
            const node = document.getElementById('preview-node');
            if (node) node.style.opacity = '0';
            
            const status = document.getElementById('edit-status');
            if (status) status.style.opacity = '0';
            
            const line = document.getElementById('preview-edge');
            if (line) line.setAttribute('opacity', '0');
            
            const debug = document.getElementById('edit-debug');
            if (debug) debug.style.opacity = '0';
        ''')
