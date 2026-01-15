import pytest

from app import normalize_click_payload, resolve_node_id_from_payload


class DummyDataManager:
    def __init__(self, nodes):
        self._nodes = nodes

    def get_graph(self):
        return {'nodes': self._nodes, 'edges': []}


def test_normalize_click_payload_handles_dict():
    payload = {'componentType': 'series', 'name': 'node-1'}
    assert normalize_click_payload(payload) is payload


def test_normalize_click_payload_handles_list():
    payload = normalize_click_payload(['series', 'node-2', 'graph', {'foo': 'bar'}])
    assert payload == {
        'componentType': 'series',
        'name': 'node-2',
        'seriesType': 'graph',
        'value': {'foo': 'bar'},
    }


def test_normalize_click_payload_handles_string():
    payload = normalize_click_payload('node-3')
    assert payload == {'name': 'node-3'}


def test_resolve_node_id_prefers_exact_id():
    nodes = [{'id': 'abc', 'label': 'Some Label'}]
    dm = DummyDataManager(nodes)
    payload = {'componentType': 'series', 'name': 'abc'}
    assert resolve_node_id_from_payload(payload, dm) == 'abc'


def test_resolve_node_id_falls_back_to_label_match():
    nodes = [{'id': 'xyz', 'label': 'Serious Games'}]
    dm = DummyDataManager(nodes)
    payload = {'componentType': 'series', 'name': 'Serious Games'}
    assert resolve_node_id_from_payload(payload, dm) == 'xyz'


def test_resolve_node_id_returns_none_for_non_series():
    nodes = [{'id': 'node', 'label': 'Node'}]
    dm = DummyDataManager(nodes)
    payload = {'componentType': 'tooltip', 'name': 'node'}
    assert resolve_node_id_from_payload(payload, dm) is None
