"""Saving and deleting uploaded files (member photos and ID documents).

Files are stored in instance/uploads under a random name. They are NOT inside the
static folder, so nobody can open them without logging in: they are served by the
route in routes/files.py, which checks permissions first.
"""
import os
import uuid

from flask import current_app

PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
DOCUMENT_EXTENSIONS = PHOTO_EXTENSIONS | {"pdf"}


def _extension(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def check_file(file_storage, allowed):
    """Return an error message if the chosen file is not allowed, otherwise None."""
    if file_storage is None or not file_storage.filename:
        return None                                  # nothing chosen: fine
    if _extension(file_storage.filename) not in allowed:
        return "Allowed file types: " + ", ".join(sorted(allowed)) + "."
    return None


def save_file(file_storage):
    """Store the file under a random name and return that name."""
    name = uuid.uuid4().hex + "." + _extension(file_storage.filename)
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], name))
    return name


def delete_file(name):
    if name:
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], name)
        if os.path.exists(path):
            os.remove(path)
