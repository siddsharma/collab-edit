import json
from datetime import datetime, timedelta

def _seed_note_with_versions(session_factory):
    from db import Note, NoteVersion  # pylint: disable=import-error,import-outside-toplevel

    session = session_factory()
    try:
        note = Note(
            title="Test Note",
            content="",
            created_at=datetime(2026, 1, 1, 10, 0, 0),
            updated_at=datetime(2026, 1, 1, 10, 0, 0),
        )
        session.add(note)
        session.flush()

        base = datetime(2026, 1, 1, 10, 0, 0)
        v1 = NoteVersion(
            note_id=note.id,
            user_id="u1",
            delta=json.dumps({"kind": "yjs_update", "update": "AAA", "user_name": "Alice"}),
            timestamp=base,
        )
        v2 = NoteVersion(
            note_id=note.id,
            user_id="u2",
            delta=json.dumps({"kind": "presence", "cursor": 1}),
            timestamp=base + timedelta(seconds=1),
        )
        v3 = NoteVersion(
            note_id=note.id,
            user_id="u3",
            delta=json.dumps({"kind": "yjs_update", "update": "BBB"}),
            timestamp=base + timedelta(seconds=2),
        )
        session.add_all([v1, v2, v3])
        session.commit()
        return note.id, v1.id, v2.id, v3.id
    finally:
        session.close()


def test_list_versions_returns_descending_and_kinds(client_and_db):
    client, session_factory = client_and_db
    note_id, _, _, _ = _seed_note_with_versions(session_factory)

    response = client.get(f"/notes/{note_id}/versions", params={"limit": 3})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 3
    assert payload[0]["kind"] == "yjs_update"
    assert payload[1]["kind"] == "presence"
    assert payload[2]["kind"] == "yjs_update"
    assert payload[0]["user_name"] == "u3"
    assert payload[1]["user_name"] == "u2"
    assert payload[2]["user_name"] == "Alice"
    assert payload[0]["timestamp"] >= payload[1]["timestamp"]


def test_snapshot_returns_only_yjs_updates_up_to_target_version(client_and_db):
    client, session_factory = client_and_db
    note_id, _, v2_id, _ = _seed_note_with_versions(session_factory)

    response = client.get(f"/notes/{note_id}/versions/{v2_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["note_id"] == note_id
    assert payload["version_id"] == v2_id
    assert payload["yjs_updates"] == ["AAA"]


def test_restore_creates_restore_version_event(client_and_db):
    from db import NoteVersion  # pylint: disable=import-error,import-outside-toplevel

    client, session_factory = client_and_db
    note_id, _, _, v3_id = _seed_note_with_versions(session_factory)

    restore_response = client.post(
        f"/notes/{note_id}/versions/{v3_id}/restore",
        json={"user_id": "u9", "user_name": "Bob"},
    )
    assert restore_response.status_code == 200
    restore_payload = restore_response.json()
    assert restore_payload["note_id"] == note_id
    assert restore_payload["restored_from_version_id"] == v3_id

    session = session_factory()
    try:
        restore_events = (
            session.query(NoteVersion)
            .filter(NoteVersion.note_id == note_id)
            .order_by(NoteVersion.timestamp.desc())
            .all()
        )
        latest_delta = json.loads(restore_events[0].delta)
        assert restore_events[0].user_id == "u9"
        assert latest_delta["kind"] == "restore"
        assert latest_delta["target_version_id"] == v3_id
        assert latest_delta["user_name"] == "Bob"
    finally:
        session.close()
