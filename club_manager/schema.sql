-- Database tables. "IF NOT EXISTS" means this file is safe to run many times.
-- Dates are stored as text in the form YYYY-MM-DD.

CREATE TABLE IF NOT EXISTS clubs (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    sport TEXT NOT NULL              -- a key from sports.py: shooting / running / chess
);

-- One table for every kind of account: super-admin, club admins and members.
CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id          INTEGER REFERENCES clubs(id),   -- empty for the super-admin
    role             TEXT NOT NULL CHECK (role IN ('superadmin', 'admin', 'member')),
    email            TEXT NOT NULL UNIQUE,           -- the login, always lower case
    password_hash    TEXT NOT NULL,
    full_name        TEXT NOT NULL,
    phone            TEXT,
    date_of_birth    TEXT,
    join_date        TEXT,
    member_number    INTEGER,
    membership_type  TEXT,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'expired', 'deactivated')),
    expiry_date      TEXT,
    address          TEXT,
    emergency_contact TEXT,
    notes            TEXT,
    photo_file       TEXT,        -- name of the file inside the uploads folder
    id_document_file TEXT,
    UNIQUE (club_id, member_number)
);

CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id          INTEGER NOT NULL REFERENCES clubs(id),
    name             TEXT NOT NULL,
    event_date       TEXT NOT NULL,
    location         TEXT,
    discipline       TEXT,
    description      TEXT,
    event_type       TEXT NOT NULL DEFAULT 'competition',
    entry_fee        REAL NOT NULL DEFAULT 0,
    max_participants INTEGER            -- empty means "no limit"
);

CREATE TABLE IF NOT EXISTS registrations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   INTEGER NOT NULL REFERENCES events(id),
    user_id    INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE (event_id, user_id)
);

-- "data" holds the sport-specific fields as JSON, e.g. {"score": 92, "target": "25m"}.
-- That is what makes it easy to add a new sport: no new columns are needed.
-- There is no stored ranking: positions are calculated when results are shown.
CREATE TABLE IF NOT EXISTS results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   INTEGER NOT NULL REFERENCES events(id),
    user_id    INTEGER NOT NULL REFERENCES users(id),
    data       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved')),
    created_at TEXT NOT NULL,
    UNIQUE (event_id, user_id)
);
