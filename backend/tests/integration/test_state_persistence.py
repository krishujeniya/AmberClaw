from pathlib import Path

from amberclaw.governance.tickets import TicketStatus, TicketSystem
from amberclaw.schemas.agent import AgentProfile
from amberclaw.storage.persistence import JSONStateStore


def test_json_state_store_persistence(tmp_path: Path):
    store_file = tmp_path / "agents.json"
    store1 = JSONStateStore(store_file, AgentProfile)

    profile = AgentProfile(
        agent_id="agent_persist_1",
        name="PersistAgent",
        role="Tester",
        model_name="gpt-4o",
    )
    store1.set(profile.agent_id, profile)

    assert store_file.exists()

    # Create new instance pointing to same file (simulating server restart)
    store2 = JSONStateStore(store_file, AgentProfile)
    assert store2.contains("agent_persist_1")
    reloaded = store2.get("agent_persist_1")
    assert reloaded is not None
    assert reloaded.name == "PersistAgent"


def test_ticket_system_state_persistence(tmp_path: Path):
    ticket_sys1 = TicketSystem(data_dir=tmp_path)

    # Save a ticket to store
    ticket_sys1._store.set(
        "tix_101",
        ticket_sys1._store.model_cls(
            id="tix_101",
            requester_id="req1",
            description="Deploy production patch",
            status=TicketStatus.PENDING,
        ),
    )

    ticket_sys1.resolve_ticket("tix_101", TicketStatus.APPROVED, reviewer_id="admin")

    # Re-initialize ticket system (simulating server restart)
    ticket_sys2 = TicketSystem(data_dir=tmp_path)
    loaded_ticket = ticket_sys2._store.get("tix_101")
    assert loaded_ticket is not None
    assert loaded_ticket.status == TicketStatus.APPROVED
    assert loaded_ticket.reviewer_id == "admin"
