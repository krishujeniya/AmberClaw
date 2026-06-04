# ruff: noqa: E501
"""Unit tests for the TemporalGraphMemory system."""

from amberclaw.memory.graph_memory import TemporalGraphMemory


def test_add_entity_and_history(tmp_path):
    db_file = tmp_path / "graph.json"
    tgm = TemporalGraphMemory(db_path=db_file)

    # Add entity
    node_id = tgm.add_entity("Alice", "Person", {"location": "New York", "role": "Engineer"})
    assert node_id == "alice"

    entity = tgm.get_entity("Alice")
    assert entity["name"] == "Alice"
    assert entity["type"] == "Person"
    assert entity["properties"]["location"] == "New York"
    assert len(entity["history"]) == 0

    # Update entity property (change location)
    tgm.add_entity("Alice", "Person", {"location": "London"})

    entity_updated = tgm.get_entity("Alice")
    assert entity_updated["properties"]["location"] == "London"
    assert entity_updated["properties"]["role"] == "Engineer"  # Role should be preserved (merged)
    assert len(entity_updated["history"]) == 1
    assert "location" in entity_updated["history"][0]["changes"]
    assert entity_updated["history"][0]["changes"]["location"]["old"] == "New York"
    assert entity_updated["history"][0]["changes"]["location"]["new"] == "London"


def test_add_relationships(tmp_path):
    db_file = tmp_path / "graph.json"
    tgm = TemporalGraphMemory(db_path=db_file)

    tgm.add_entity("Alice", "Person")
    tgm.add_entity("Google", "Organization")

    tgm.add_relationship("Alice", "Google", "works_at", {"since": "2020"})

    entity = tgm.get_entity("Alice")
    rels = entity["relationships"]
    assert len(rels) == 1
    assert rels[0]["type"] == "outgoing"
    assert rels[0]["relation"] == "works_at"
    assert rels[0]["target"] == "google"
    assert rels[0]["properties"]["since"] == "2020"


def test_query_path_multihop(tmp_path):
    db_file = tmp_path / "graph.json"
    tgm = TemporalGraphMemory(db_path=db_file)

    tgm.add_relationship("Alice", "Bob", "knows")
    tgm.add_relationship("Bob", "Charlie", "knows")

    path = tgm.query_path("Alice", "Charlie")
    assert path == ["Alice", "Bob", "Charlie"]

    # Verify no path behavior
    no_path = tgm.query_path("Alice", "David")
    assert no_path is None


def test_graph_persistence(tmp_path):
    db_file = tmp_path / "graph.json"
    tgm1 = TemporalGraphMemory(db_path=db_file)
    tgm1.add_relationship("Alice", "Bob", "knows")

    # Load again from same path
    tgm2 = TemporalGraphMemory(db_path=db_file)
    entity = tgm2.get_entity("Alice")
    assert entity is not None
    assert len(entity["relationships"]) == 1
    assert entity["relationships"][0]["target"] == "bob"
