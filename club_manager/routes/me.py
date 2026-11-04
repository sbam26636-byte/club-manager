"""Pages a member sees about themselves."""
from flask import Blueprint, g, render_template

from models import events as events_model
from models import results as results_model
from models import users
from security import roles_required

bp = Blueprint("me", __name__, url_prefix="/me")


@bp.route("")
@roles_required("member")
def profile():
    users.refresh_club(g.user["club_id"])
    member = users.get_by_id(g.user["id"])                 # re-read after a possible renewal
    return render_template("me/profile.html", member=member,
                           upcoming=events_model.upcoming_for_member(member["id"]))


@bp.route("/results")
@roles_required("member")
def my_results():
    history = results_model.history_for_member(g.user["id"], g.club["sport"])
    return render_template("me/results.html", history=history)
