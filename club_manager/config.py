"""Settings for the Club Manager app.

Everything you might want to change lives in this one file.
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Flask's "instance" folder holds files that are created at run time
# (the SQLite database and the uploaded photos / documents).
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")


class Config:
    # Used to sign the login session. Set a long random value in the
    # SECRET_KEY environment variable for anything beyond a local demo.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    DATABASE = os.path.join(INSTANCE_DIR, "club_manager.sqlite")
    UPLOAD_FOLDER = os.path.join(INSTANCE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # uploads up to 5 MB

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    CURRENCY_SYMBOL = "€"  # shown next to event entry fees


# Choices offered in the forms (edit freely).
MEMBERSHIP_TYPES = ["Standard", "Family", "Student", "Senior", "Honorary"]
EVENT_TYPES = [
    ("competition", "Competition"),
    ("training", "Training"),
    ("social", "Social"),
]
