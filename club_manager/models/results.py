"""Results, and the ranking that is calculated whenever results are shown."""
import json
from datetime import datetime

import sports
from db import get_db


def _with_data(row):
    item = dict(row)
    item["data"] = json.loads(item["data"])
    return item


def get_result(club_id, result_id):
    """A result belonging to this club (joined with event and member details)."""
    row = get_db().execute(
        """SELECT r.*, e.name AS event_name, e.event_date, u.full_name
           FROM results r
           JOIN events e ON e.id = r.event_id
           JOIN users u ON u.id = r.user_id
           WHERE r.id = ? AND e.club_id = ?""",
        (result_id, club_id),
    ).fetchone()
    return _with_data(row) if row else None


def result_for(event_id, user_id):
    row = get_db().execute(
        "SELECT * FROM results WHERE event_id = ? AND user_id = ?", (event_id, user_id)
    ).fetchone()
    return _with_data(row) if row else None


def create_result(event_id, user_id, data, status):
    db = get_db()
    db.execute(
        "INSERT INTO results (event_id, user_id, data, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (event_id, user_id, json.dumps(data), status, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()


def update_result(result_id, data):
    db = get_db()
    db.execute("UPDATE results SET data = ? WHERE id = ?", (json.dumps(data), result_id))
    db.commit()


def approve(result_id):
    db = get_db()
    db.execute("UPDATE results SET status = 'approved' WHERE id = ?", (result_id,))
    db.commit()


def delete(result_id):
    """Used both to delete a result and to reject a pending one."""
    db = get_db()
    db.execute("DELETE FROM results WHERE id = ?", (result_id,))
    db.commit()


def list_pending(club_id):
    rows = get_db().execute(
        """SELECT r.*, e.name AS event_name, e.event_date, u.full_name, u.member_number
           FROM results r
           JOIN events e ON e.id = r.event_id
           JOIN users u ON u.id = r.user_id
           WHERE e.club_id = ? AND r.status = 'pending'
           ORDER BY r.created_at""",
        (club_id,),
    ).fetchall()
    return [_with_data(r) for r in rows]


def count_pending(club_id):
    return get_db().execute(
        """SELECT COUNT(*) FROM results r JOIN events e ON e.id = r.event_id
           WHERE e.club_id = ? AND r.status = 'pending'""",
        (club_id,),
    ).fetchone()[0]


def ranked_for_event(event_id, sport_key):
    """Approved results, best first, each with a 'position' (equal results share a position)."""
    rows = get_db().execute(
        """SELECT r.id, r.user_id, r.data, u.full_name, u.member_number
           FROM results r JOIN users u ON u.id = r.user_id
           WHERE r.event_id = ? AND r.status = 'approved'""",
        (event_id,),
    ).fetchall()
    items = [_with_data(r) for r in rows]
    items.sort(key=lambda i: (sports.rank_key(sport_key, i["data"]), i["full_name"].lower()))

    previous_key, position = None, 0
    for index, item in enumerate(items, start=1):
        key = sports.rank_key(sport_key, item["data"])
        if key != previous_key:            # a new, different result: position = place in the list
            position, previous_key = index, key
        item["position"] = position
        item["cells"] = sports.display_values(sport_key, item["data"])
    return items


def history_for_member(user_id, sport_key):
    """A member's results across all events (pending ones included), newest first."""
    rows = get_db().execute(
        """SELECT r.id, r.event_id, r.data, r.status, e.name AS event_name, e.event_date, e.discipline
           FROM results r JOIN events e ON e.id = r.event_id
           WHERE r.user_id = ? ORDER BY e.event_date DESC""",
        (user_id,),
    ).fetchall()
    history, ranked_cache = [], {}
    for row in rows:
        item = _with_data(row)
        item["summary"] = sports.summary(sport_key, item["data"])
        item["position"] = None
        if item["status"] == "approved":
            if item["event_id"] not in ranked_cache:
                ranked_cache[item["event_id"]] = ranked_for_event(item["event_id"], sport_key)
            for ranked in ranked_cache[item["event_id"]]:
                if ranked["user_id"] == user_id:
                    item["position"] = ranked["position"]
        history.append(item)
    return history
