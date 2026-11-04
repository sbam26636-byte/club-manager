"""Fill the database with demo data.

Run:   python seed.py

WARNING: this deletes the existing database and uploaded files first, then creates
  * a super-admin,
  * three clubs (shooting, running, chess), each with an admin and 10 members,
  * four events per club, with registrations and results (including one pending result).
"""
import json
import os
import random
import re
import unicodedata
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import config
from app import create_app
from db import get_db
from models import clubs as clubs_model
from models import events as events_model
from models import results as results_model
from models import users

SUPER_EMAIL, SUPER_PASSWORD = "super@clubmanager.example", "SuperAdmin1"
ADMIN_PASSWORD, MEMBER_PASSWORD = "Admin1234", "Member1234"

# One entry per demo club. The "events" tuples are:
# (name, days from today, type, discipline, fee, max participants, description)
DEMO_CLUBS = [
    {
        "name": "Riverside Pistol & Rifle Club", "sport": "shooting", "slug": "shooting",
        "admin": "Alice Murphy", "place": "Riverside Range",
        "members": ["Liam Walsh", "Emma Byrne", "Noah Kelly", "Ava Brennan", "Jack Ryan",
                    "Mia Doyle", "Oisín Hughes", "Sophie Quinn", "Conor Fitzgerald", "Chloe Gallagher"],
        "events": [
            ("Club Championship", -60, "competition", "50m rifle", 15, 12, "The annual club championship over 60 shots."),
            ("Midweek Practice", -14, "training", "25m pistol", 0, None, "Relaxed practice evening with a coach on hand."),
            ("Winter Open", 12, "competition", "25m pistol", 20, 8, "Open competition with limited places."),
            ("Season Social", 30, "social", "", 10, 30, "Food, trophies and a look back at the season."),
        ],
    },
    {
        "name": "Harbour Road Runners", "sport": "running", "slug": "running",
        "admin": "Brian Costello", "place": "Harbour Park",
        "members": ["Hannah Moran", "Ethan Brady", "Lily Nolan", "Dylan Hayes", "Grace Keane",
                    "Ryan Daly", "Ella Burke", "Cian Lynch", "Amelia Hogan", "Luke Farrell"],
        "events": [
            ("Harbour 10K", -60, "competition", "10K", 12, 12, "Flat and fast 10K along the harbour."),
            ("Tuesday Tempo Run", -14, "training", "5K", 0, None, "A steady 5K tempo run, all paces welcome."),
            ("Winter 10K", 12, "competition", "10K", 15, 8, "A cold-weather 10K with hot soup at the finish."),
            ("Season Social", 30, "social", "", 10, 30, "End-of-season get-together."),
        ],
    },
    {
        "name": "Kingside Chess Club", "sport": "chess", "slug": "chess",
        "admin": "Clara Whelan", "place": "Kingside Clubhouse",
        "members": ["Isla Healy", "Adam Sheehan", "Ruby Maguire", "Tom Cassidy", "Zoe Kavanagh",
                    "Daniel Foley", "Freya Mooney", "Sean Regan", "Niamh Dunne", "Patrick Egan"],
        "events": [
            ("Club Championship", -60, "competition", "Classical", 10, 12, "Round-robin club championship."),
            ("Blitz Night", -14, "training", "Blitz", 0, None, "Fast games and friendly rivalry."),
            ("Winter Rapid Open", 12, "competition", "Rapid", 12, 8, "Rapid tournament with limited places."),
            ("Season Social", 30, "social", "", 5, 30, "Pizza and puzzles."),
        ],
    },
]


def plain(text):
    """'Oisín Hughes' -> 'oisin.hughes' (used to build demo email addresses)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z.]", "", text.lower().replace(" ", "."))


CHESS_OUTCOMES = ["win", "draw", "loss", "draw", "win", "loss", "draw", "loss", "draw", "win"]


def make_result(sport, discipline, rng, index):
    """A believable result for the given sport ('index' is the member's position in the club)."""
    if sport == "shooting":
        return {"score": rng.randint(78, 99), "target": discipline}
    if sport == "running":
        low, high = (2300, 3600) if discipline == "10K" else (1100, 1800)
        return {"finish_time": rng.randint(low, high)}
    return {"outcome": CHESS_OUTCOMES[index % len(CHESS_OUTCOMES)]}


def main():
    # Start from a clean slate.
    if os.path.exists(config.Config.DATABASE):
        os.remove(config.Config.DATABASE)
    if os.path.isdir(config.Config.UPLOAD_FOLDER):
        for name in os.listdir(config.Config.UPLOAD_FOLDER):
            os.remove(os.path.join(config.Config.UPLOAD_FOLDER, name))

    app = create_app()
    rng = random.Random(42)                    # same demo data every time
    today = date.today()
    credentials = []

    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO users (role, email, password_hash, full_name) VALUES ('superadmin', ?, ?, 'Super Admin')",
            (SUPER_EMAIL, generate_password_hash(SUPER_PASSWORD)),
        )
        db.commit()

        for demo in DEMO_CLUBS:
            club_id = clubs_model.create_club(demo["name"], demo["sport"])
            admin_email = f"admin@{demo['slug']}.example"
            users.create_admin(club_id, demo["admin"], admin_email, generate_password_hash(ADMIN_PASSWORD))

            # --- members ---
            member_ids = []
            for index, full_name in enumerate(demo["members"]):
                join = today - timedelta(days=rng.randint(60, 1500))
                born = date(rng.randint(1960, 2004), rng.randint(1, 12), rng.randint(1, 28))
                email = f"{plain(full_name)}@{demo['slug']}.example"
                member_id = users.create_member(club_id, {
                    "full_name": full_name, "email": email, "phone": f"555-01{rng.randint(10, 99)}",
                    "date_of_birth": born.isoformat(), "join_date": join.isoformat(),
                    "membership_type": rng.choice(config.MEMBERSHIP_TYPES[:4]),
                    "address": f"{rng.randint(1, 99)} Station Road",
                    "emergency_contact": f"Pat {full_name.split()[-1]}, 555-01{rng.randint(10, 99)}",
                    "notes": "",
                }, generate_password_hash(MEMBER_PASSWORD))
                member_ids.append(member_id)
                if index == 0:
                    credentials.append((demo["name"], "member", email, MEMBER_PASSWORD))
            # The last two members show the other statuses.
            db.execute("UPDATE users SET status = 'expired', expiry_date = ? WHERE id = ?",
                       ((today - timedelta(days=20)).isoformat(), member_ids[8]))
            db.commit()
            users.deactivate(member_ids[9])
            credentials.insert(len(credentials) - 1, (demo["name"], "club admin", admin_email, ADMIN_PASSWORD))

            # --- events, sign-ups and results ---
            event_ids = []
            for name, offset, kind, discipline, fee, maximum, description in demo["events"]:
                event_ids.append(events_model.save_event(club_id, {
                    "name": name, "event_date": (today + timedelta(days=offset)).isoformat(),
                    "location": demo["place"], "discipline": discipline, "description": description,
                    "event_type": kind, "entry_fee": float(fee), "max_participants": maximum,
                }))

            def sign_up(event_id, member_index_list):
                for i in member_index_list:
                    db.execute("INSERT INTO registrations (event_id, user_id, created_at) VALUES (?, ?, ?)",
                               (event_id, member_ids[i], today.isoformat()))
                db.commit()

            sign_up(event_ids[0], range(10))        # championship: everyone, results for all but one
            sign_up(event_ids[1], range(6))         # practice: six members
            sign_up(event_ids[2], range(4))         # upcoming competition
            sign_up(event_ids[3], range(3))         # upcoming social

            def add_results(event_index, member_indexes, status="approved"):
                discipline = demo["events"][event_index][3]
                for i in member_indexes:
                    results_model.create_result(event_ids[event_index], member_ids[i],
                                                make_result(demo["sport"], discipline, rng, i), status)

            add_results(0, [0, 1, 2, 3, 4, 5, 7, 8, 9])      # member 6 has no result yet
            add_results(1, [0, 1, 2, 3])
            add_results(1, [4], status="pending")            # submitted by a member, waiting for approval

    print("\nDemo data created. Log in with:\n")
    print(f"  {'Role':<12}{'Email':<40}Password")
    print(f"  {'super-admin':<12}{SUPER_EMAIL:<40}{SUPER_PASSWORD}")
    for club_name, role, email, password in credentials:
        print(f"  {role:<12}{email:<40}{password}   ({club_name})")
    print(f"\n  All other members use the password {MEMBER_PASSWORD} (emails look like firstname.lastname@<sport>.example).\n")


if __name__ == "__main__":
    main()
