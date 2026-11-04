"""Serving uploaded files, but only to people who are allowed to see them."""
from flask import Blueprint, abort, current_app, g, send_from_directory

from models import users
from security import roles_required

bp = Blueprint("files", __name__)


@bp.route("/files/<int:user_id>/<kind>")
@roles_required("admin", "member")
def member_file(user_id, kind):
    """Allowed: the member themselves, and the admins of that member's club."""
    column = {"photo": "photo_file", "id": "id_document_file"}.get(kind) or abort(404)
    owner = users.get_member(g.user["club_id"], user_id) or abort(404)    # also blocks other clubs
    if g.user["role"] == "member" and g.user["id"] != user_id:
        abort(403)
    filename = owner[column] or abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
