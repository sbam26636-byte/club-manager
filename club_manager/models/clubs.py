from db import get_db


def list_clubs():
    return get_db().execute(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM users u WHERE u.club_id = c.id AND u.role = 'admin')  AS admin_count,
                  (SELECT COUNT(*) FROM users u WHERE u.club_id = c.id AND u.role = 'member') AS member_count
           FROM clubs c ORDER BY c.name COLLATE NOCASE"""
    ).fetchall()


def get_club(club_id):
    return get_db().execute("SELECT * FROM clubs WHERE id = ?", (club_id,)).fetchone()


def name_exists(name):
    row = get_db().execute("SELECT 1 FROM clubs WHERE lower(name) = lower(?)", (name,)).fetchone()
    return row is not None


def create_club(name, sport):
    db = get_db()
    cursor = db.execute("INSERT INTO clubs (name, sport) VALUES (?, ?)", (name, sport))
    db.commit()
    return cursor.lastrowid
