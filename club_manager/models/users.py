"""Accounts: super-admin, club admins and members, plus the renewal logic."""
from datetime import date

from db import get_db


# ---------- looking people up ----------

def get_by_id(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_by_email(email):
    return get_db().execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()


def email_exists(email, exclude_id=None):
    row = get_db().execute(
        "SELECT id FROM users WHERE email = ? AND id != ?", (email.lower(), exclude_id or 0)
    ).fetchone()
    return row is not None


def get_member(club_id, user_id):
    """A member of THIS club only (returns None for other clubs, admins, etc.)."""
    return get_db().execute(
        "SELECT * FROM users WHERE id = ? AND club_id = ? AND role = 'member'", (user_id, club_id)
    ).fetchone()


def list_members(club_id, search="", status="", membership_type=""):
    sql = "SELECT * FROM users WHERE club_id = ? AND role = 'member'"
    params = [club_id]
    if search:
        sql += " AND (full_name LIKE ? OR email LIKE ? OR CAST(member_number AS TEXT) LIKE ?)"
        params += [f"%{search}%"] * 3
    if status:
        sql += " AND status = ?"
        params.append(status)
    if membership_type:
        sql += " AND membership_type = ?"
        params.append(membership_type)
    sql += " ORDER BY full_name COLLATE NOCASE"
    return get_db().execute(sql, params).fetchall()


def list_admins(club_id):
    return get_db().execute(
        "SELECT * FROM users WHERE club_id = ? AND role = 'admin' ORDER BY full_name COLLATE NOCASE",
        (club_id,),
    ).fetchall()


def count_members(club_id, status="active"):
    return get_db().execute(
        "SELECT COUNT(*) FROM users WHERE club_id = ? AND role = 'member' AND status = ?",
        (club_id, status),
    ).fetchone()[0]


# ---------- membership renewal (section 8 of the spec) ----------

def add_years(day, years):
    """The same calendar day some years later (29 Feb becomes 28 Feb in a non-leap year)."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def membership_expiry(join_date, today=None):
    """The next anniversary of the join date that is today or later.

    A member who joined on 10 March 2024 is paid up until 10 March 2025; after that
    the expiry moves on to 10 March 2026, and so on.
    """
    today = today or date.today()
    years = max(1, today.year - join_date.year - 1)
    while add_years(join_date, years) < today:
        years += 1
    return add_years(join_date, years)


def refresh_club(club_id):
    """Automatic yearly renewal.

    Every ACTIVE member whose expiry date has passed is renewed: the expiry date moves
    to the next anniversary and the member stays active. This runs whenever the member
    list, dashboard or a profile is loaded. (Members an admin has marked 'expired' or
    'deactivated' are left alone.)
    """
    db = get_db()
    today = date.today().isoformat()
    rows = db.execute(
        """SELECT id, join_date FROM users
           WHERE club_id = ? AND role = 'member' AND status = 'active' AND expiry_date < ?""",
        (club_id, today),
    ).fetchall()
    for row in rows:
        new_expiry = membership_expiry(date.fromisoformat(row["join_date"]))
        db.execute("UPDATE users SET expiry_date = ? WHERE id = ?", (new_expiry.isoformat(), row["id"]))
    db.commit()


# ---------- creating and changing accounts ----------

def next_member_number(club_id):
    row = get_db().execute(
        "SELECT MAX(member_number) FROM users WHERE club_id = ?", (club_id,)
    ).fetchone()
    return (row[0] or 1000) + 1               # numbers start at 1001


def create_member(club_id, values, password_hash):
    db = get_db()
    expiry = membership_expiry(date.fromisoformat(values["join_date"]))
    cursor = db.execute(
        """INSERT INTO users (club_id, role, email, password_hash, full_name, phone, date_of_birth,
                              join_date, member_number, membership_type, status, expiry_date,
                              address, emergency_contact, notes)
           VALUES (?, 'member', ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
        (club_id, values["email"].lower(), password_hash, values["full_name"], values["phone"],
         values["date_of_birth"] or None, values["join_date"], next_member_number(club_id),
         values["membership_type"], expiry.isoformat(), values["address"],
         values["emergency_contact"], values["notes"]),
    )
    db.commit()
    return cursor.lastrowid


def update_member(user_id, values, status):
    """Save edited details. 'status' is 'active' or 'expired'."""
    db = get_db()
    if status == "active":
        expiry = membership_expiry(date.fromisoformat(values["join_date"])).isoformat()
        db.execute("UPDATE users SET expiry_date = ? WHERE id = ?", (expiry, user_id))
    db.execute(
        """UPDATE users SET email = ?, full_name = ?, phone = ?, date_of_birth = ?, join_date = ?,
                            membership_type = ?, status = ?, address = ?, emergency_contact = ?, notes = ?
           WHERE id = ?""",
        (values["email"].lower(), values["full_name"], values["phone"], values["date_of_birth"] or None,
         values["join_date"], values["membership_type"], status, values["address"],
         values["emergency_contact"], values["notes"], user_id),
    )
    db.commit()


def deactivate(user_id):
    """Members are never deleted, so their history is kept."""
    db = get_db()
    db.execute("UPDATE users SET status = 'deactivated' WHERE id = ?", (user_id,))
    db.commit()


def reactivate(user_id):
    db = get_db()
    member = get_by_id(user_id)
    expiry = membership_expiry(date.fromisoformat(member["join_date"])).isoformat()
    db.execute("UPDATE users SET status = 'active', expiry_date = ? WHERE id = ?", (expiry, user_id))
    db.commit()


def create_admin(club_id, full_name, email, password_hash):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO users (club_id, role, email, password_hash, full_name) VALUES (?, 'admin', ?, ?, ?)",
        (club_id, email.lower(), password_hash, full_name),
    )
    db.commit()
    return cursor.lastrowid


def set_password(user_id, password_hash):
    db = get_db()
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    db.commit()


def set_file(user_id, column, filename):
    """column is 'photo_file' or 'id_document_file' (only ever set by our own code)."""
    assert column in ("photo_file", "id_document_file")
    db = get_db()
    db.execute(f"UPDATE users SET {column} = ? WHERE id = ?", (filename, user_id))
    db.commit()
