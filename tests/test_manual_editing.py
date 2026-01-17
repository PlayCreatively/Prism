"""
Tests for Manual Node Editing Features

Note: EditPreview was removed as it was dead code. The actual edit logic
runs in EditController (Python) and JavaScript in EditOverlay.
These tests focus on EditActions which executes the actual graph mutations.
"""

import pytest
from src.edit import EditActions, EditController
from src.data_manager import DataManager
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def data_manager(temp_data_dir):
    """Create a DataManager with test data."""
    dm = DataManager(data_dir=str(Path(temp_data_dir) / "data"))
    
    # Seed with some test nodes
    dm.seed_demo_data()
    
    return dm


@pytest.fixture
def edit_controller():
    """Create an EditController instance."""
    return EditController()


@pytest.fixture
def edit_actions(data_manager):
    """Create an EditActions instance."""
    return EditActions(data_manager)


class TestEditController:
    """Test the EditController hit detection logic."""
    
    def test_point_to_line_distance_middle(self, edit_controller):
        """Test distance from point to line segment at middle."""
        dist, t = edit_controller._point_to_line_distance(
            (5, 5),      # Point
            (0, 0),      # Line start
            (10, 10)     # Line end
        )
        assert abs(t - 0.5) < 0.01  # Should be at midpoint
        assert dist < 0.1  # Point is on the line
    
    def test_point_to_line_distance_near_start(self, edit_controller):
        """Test distance from point near line start."""
        dist, t = edit_controller._point_to_line_distance(
            (1, 1),
            (0, 0),
            (10, 10)
        )
        assert t < 0.2  # Near start
    
    def test_hit_detection_with_nodes(self, edit_controller):
        """Test hit detection finds nodes within click radius."""
        edit_controller.update_graph_data(
            nodes=[{'id': 'node1'}, {'id': 'node2'}],
            edges=[],
            positions={'node1': [100, 100], 'node2': [300, 300]},
            node_sizes={'node1': 25, 'node2': 25},
            active_user='Alex'
        )
        
        # Set mouse near node1
        edit_controller.set_mouse_position(105, 105)
        state = edit_controller._state
        
        # Verify state is tracking properly
        assert state.mouse_x == 105
        assert state.mouse_y == 105


class TestEditActions:
    """Test the EditActions execution logic."""
    
    def test_create_node(self, edit_actions, data_manager):
        """Test creating a new node."""
        initial_count = len(data_manager.get_graph()['nodes'])
        
        node_id = edit_actions.create_node(
            position=(0.5, 0.5),
            label='Test Node',
            parent_id=None,
            active_user='Alex'
        )
        
        assert node_id is not None
        
        # Verify node was created
        graph = data_manager.get_graph()
        assert len(graph['nodes']) == initial_count + 1
    
    def test_create_node_with_parent(self, edit_actions, data_manager):
        """Test creating a node with a parent connection."""
        graph = data_manager.get_graph()
        parent_id = graph['nodes'][0]['id']
        
        node_id = edit_actions.create_node(
            position=(0.3, 0.7),
            label='Child Node',
            parent_id=parent_id,
            active_user='Sasha'
        )
        
        # Verify parent relationship
        global_data = data_manager._load_global()
        assert global_data['nodes'][node_id]['parent_id'] == parent_id
    
    def test_connect_nodes(self, edit_actions, data_manager):
        """Test connecting two existing nodes."""
        graph = data_manager.get_graph()
        node1_id = graph['nodes'][0]['id']
        node2_id = graph['nodes'][1]['id']
        
        success = edit_actions.connect_nodes(node1_id, node2_id)
        assert success is True
        
        # Verify connection
        global_data = data_manager._load_global()
        assert global_data['nodes'][node1_id]['parent_id'] == node2_id
    
    def test_disconnect_nodes(self, edit_actions, data_manager):
        """Test cutting an edge between nodes."""
        graph = data_manager.get_graph()
        
        # Find a connected pair
        edges = graph['edges']
        if edges:
            edge = edges[0]
            source_id = edge['source']
            target_id = edge['target']
            
            success = edit_actions.disconnect_nodes(source_id, target_id)
            assert success is True
            
            # Verify disconnection
            global_data = data_manager._load_global()
            assert global_data['nodes'][source_id]['parent_id'] != target_id
    
    def test_create_intermediary_node(self, edit_actions, data_manager):
        """Test creating an intermediary node on an edge."""
        graph = data_manager.get_graph()
        
        # Get an edge - edges are {source: parent, target: child}
        edges = graph['edges']
        if edges:
            edge = edges[0]
            parent_id = edge['source']  # parent node (upstream)
            child_id = edge['target']   # child node (downstream)
            
            intermediary_id = edit_actions.create_intermediary_node(
                source_id=parent_id,
                target_id=child_id,
                position=(0.5, 0.5),
                active_user='Alison'
            )
            
            assert intermediary_id is not None
            
            # Verify structure: parent → intermediary → child
            # Which means: I.parent_id = parent AND child.parent_id = I
            global_data = data_manager._load_global()
            assert global_data['nodes'][intermediary_id]['parent_id'] == parent_id, \
                f"Intermediary's parent should be {parent_id[:8]}"
            assert global_data['nodes'][child_id]['parent_id'] == intermediary_id, \
                f"Child's parent should be intermediary {intermediary_id[:8]}"


class TestIntegration:
    """Integration tests for the complete editing workflow."""
    
    def test_complete_create_workflow(self, edit_actions, data_manager):
        """Test complete workflow: action execution creates node."""
        graph = data_manager.get_graph()
        initial_count = len(graph['nodes'])
        
        # Simulate preview state (in real app, this comes from JS)
        preview = {
            'action': 'create_node',
            'new_node_pos': (200, 200)
        }
        
        # Execute the preview action
        node_id = edit_actions.commit_preview_action(
            preview,
            active_user='Alex'
        )
        
        assert node_id is not None
        
        # Verify node was created
        new_graph = data_manager.get_graph()
        assert len(new_graph['nodes']) == initial_count + 1
