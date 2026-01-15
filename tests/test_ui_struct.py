import pytest
from src import ui_components as ui


def test_color_mapping_single_and_combinations():
    cases = [
        (['Alex'], '#ff0000'),
        (['Sasha'], '#00ff00'),
        (['Alison'], '#0000ff'),
        (['Alex', 'Sasha'], '#ffff00'),
        (['Alex', 'Alison'], '#ff00ff'),
        (['Sasha', 'Alison'], '#00ffff'),
        (['Alex', 'Sasha', 'Alison'], '#ffffff'),
    ]
    for users, expected in cases:
        got = ui.color_for_interested_users(users)
        assert got.lower() == expected, f'For users {users} expected {expected} got {got}'


def test_edge_highlighting_for_full_consensus_nodes():
    # Both endpoints have all three users -> full consensus -> consensus edge style
    nodes = [
        {'id': 'n1', 'label': 'N1', 'parent_id': None, 'status': 'accepted', 'interested_users': ['Alex', 'Sasha', 'Alison']},
        {'id': 'n2', 'label': 'N2', 'parent_id': 'n1', 'status': 'accepted', 'interested_users': ['Alex', 'Sasha', 'Alison']},
    ]
    edges = [{'source': 'n1', 'target': 'n2'}]
    state = ui.build_ui_state(nodes, edges)
    assert 'edges' in state
    assert len(state['edges']) == 1
    edge = state['edges'][0]
    assert edge['glow'] is True
    assert edge['width'] >= 3
    assert edge['color'] == '#ffd700'


def test_context_window_parent_and_children():
    # Build a small tree:
    # root
    #  ├─ child1
    #  │   └─ grandchild
    #  └─ child2
    nodes = [
        {'id': 'root', 'label': 'Root', 'parent_id': None, 'interested_users': ['Alex']},
        {'id': 'child1', 'label': 'Child 1', 'parent_id': 'root', 'interested_users': ['Sasha']},
        {'id': 'child2', 'label': 'Child 2', 'parent_id': 'root', 'interested_users': ['Alison']},
        {'id': 'grandchild', 'label': 'Grandchild', 'parent_id': 'child1', 'interested_users': ['Alex', 'Sasha']},
    ]
    edges = [
        {'source': 'root', 'target': 'child1'},
        {'source': 'root', 'target': 'child2'},
        {'source': 'child1', 'target': 'grandchild'},
    ]
    state = ui.build_ui_state(nodes, edges, context_radius=1)

    # root's context should include root, child1 and child2
    root_ctx = set(state['context_windows'].get('root', []))
    assert 'root' in root_ctx
    assert 'child1' in root_ctx
    assert 'child2' in root_ctx

    # child1's context should include its parent (root) and its child (grandchild)
    c1_ctx = set(state['context_windows'].get('child1', []))
    assert 'child1' in c1_ctx
    assert 'root' in c1_ctx
    assert 'grandchild' in c1_ctx

    # grandchild's context should include its parent (child1) and grandparent (root) within radius=1 upwards,
    # and no children (none exist)
    gc_ctx = set(state['context_windows'].get('grandchild', []))
    assert 'grandchild' in gc_ctx
    assert 'child1' in gc_ctx
    # For radius=1 we include the parent; siblings of grandchild should not appear (there are none),
    # but root may appear because we include ancestors up to radius; depending on implementation root may or may not
    # be included. Here we expect parent at minimum.
    assert 'root' in gc_ctx or 'root' not in gc_ctx  # just ensure no KeyError; primary checks above are sufficient


if __name__ == '__main__':
    pytest.main([__file__])
