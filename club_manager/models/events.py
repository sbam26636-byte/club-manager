"""Events and event registrations."""
from datetime import date, datetime

from db import get_db


def list_events(club_id, user_id=None):
    """All events of a club. If user_id is given, 'registered' says whether that user signed up."""
    return get_db().execute(
        """SELECT e.*,
                  (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count,
                  EXISTS (SELECT 1 FROM registrations r
                          WHERE r.event_id = e.id AND r.user_id = ?) AS registered
           FROM events e WHERE e.club_id = ? ORDER BY e.event_date""",
        (user_id or 0, club_id),
    ).fetchall()


def get_event(club_id, event_id):
    """An event of THIS club only."""
    return get_db().execute(
        """SELECT e.*, (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count
           FROM events e WHERE e.id = ? AND e.club_id = ?""",
        (event_id, club_id),
    ).fetchone()


def save_event(club_id, values, event_id=None):
    """Insert a new event, or update an existing one when event_id is given."""
    db = get_db()
    fields = (values["name"], values["event_date"], values["location"], values["discipline"],
              values["description"], values["event_type"], values["entry_fee"],
              values["max_participants"])
    if event_id is None:
        cursor = db.execute(
            """INSERT INTO events (name, event_date, location, discipline, description, event_type,
                                   entry_fee, max_participants, club_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            fields + (club_id,),
        )
        event_id = cursor.lastrowid
    else:
        db.execute(
            """UPDATE events SET name = ?, event_date = ?, location = ?, discipline = ?, description = ?,
                                 event_type = ?, entry_fee = ?, max_participants = ?
               WHERE id = ? AND club_id = ?""",
            fields + (event_id, club_id),
        )
    db.commit()
    return event_id


def participants(event_id):
    """Registered members of an event, with the state of their result (if any)."""
    return get_db().execute(
        """SELECT u.id, u.full_name, u.member_number, u.status,
                  res.id AS result_id, res.status AS result_status
           FROM registrations reg
           JOIN users u ON u.id = reg.user_id
           LEFT JOIN results res ON res.event_id = reg.event_id AND res.user_id = reg.user_id
           WHERE reg.event_id = ? ORDER BY u.full_name COLLATE NOCASE""",
        (event_id,),
    ).fetchall()


def participants_without_result(event_id):
    return get_db().execute(
        """SELECT u.id, u.full_name, u.member_number
           FROM registrations reg JOIN users u ON u.id = reg.user_id
           WHERE reg.event_id = ?
             AND NOT EXISTS (SELECT 1 FROM results r WHERE r.event_id = reg.event_id AND r.user_id = reg.user_id)
           ORDER BY u.full_name COLLATE NOCASE""",
        (event_id,),
    ).fetchall()


def members_not_registered(club_id, event_id):
    """Members an admin could still sign up (deactivated members are left out)."""
    return get_db().execute(
        """SELECT id, full_name, member_number FROM users
           WHERE club_id = ? AND role = 'member' AND status != 'deactivated'
             AND id NOT IN (SELECT user_id FROM registrations WHERE event_id = ?)
           ORDER BY full_name COLLATE NOCASE""",
        (club_id, event_id),
    ).fetchall()


def is_registered(event_id, user_id):
    row = get_db().execute(
        "SELECT 1 FROM registrations WHERE event_id = ? AND user_id = ?", (event_id, user_id)
    ).fetchone()
    return row is not None


def register(event, member):
    """Sign a member up. Returns an error message, or None when it worked."""
    if member["status"] == "deactivated":
        return "Deactivated members cannot sign up for events."
    if event["event_date"] < date.today().isoformat():
        return "This event has already taken place."
    if is_registered(event["id"], member["id"]):
        return "Already registered for this event."
    if event["max_participants"] is not None and event["reg_count"] >= event["max_participants"]:
        return "This event is full."
    db = get_db()
    db.execute(
        "INSERT INTO registrations (event_id, user_id, created_at) VALUES (?, ?, ?)",
        (event["id"], member["id"], datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    return None


def unregister(event, member):
    """Cancel a sign-up. Returns an error message, or None when it worked."""
    if event["event_date"] < date.today().isoformat():
        return "This event has already taken place."
    db = get_db()
    has_result = db.execute(
        "SELECT 1 FROM results WHERE event_id = ? AND user_id = ?", (event["id"], member["id"])
    ).fetchone()
    if has_result:
        return "A result is already recorded, so the sign-up cannot be cancelled."
    db.execute("DELETE FROM registrations WHERE event_id = ? AND user_id = ?", (event["id"], member["id"]))
    db.commit()
    return None


def upcoming_for_member(user_id):
    return get_db().execute(
        """SELECT e.* FROM events e JOIN registrations r ON r.event_id = e.id
           WHERE r.user_id = ? AND e.event_date >= ? ORDER BY e.event_date""",
        (user_id, date.today().isoformat()),
    ).fetchall()


def next_events(club_id, limit=5):
    return get_db().execute(
        """SELECT e.*, (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS reg_count
           FROM events e WHERE e.club_id = ? AND e.event_date >= ? ORDER BY e.event_date LIMIT ?""",
        (club_id, date.today().isoformat(), limit),
    ).fetchall()
