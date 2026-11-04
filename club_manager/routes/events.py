"""Events and event sign-ups (admins manage events; members sign themselves up)."""
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

import config
import sports
from models import events as events_model
from models import results as results_model
from models import users
from routes.helpers import to_int, valid_date
from security import roles_required

bp = Blueprint("events", __name__)


def _event_or_404(event_id):
    """An event of the logged-in person's own club; other clubs' events are a 404."""
    return events_model.get_event(g.user["club_id"], event_id) or abort(404)


@bp.route("/events")
@roles_required("admin", "member")
def index():
    everything = events_model.list_events(g.user["club_id"], g.user["id"])
    today = date.today().isoformat()
    upcoming = [e for e in everything if e["event_date"] >= today]
    past = [e for e in everything if e["event_date"] < today][::-1]     # newest first
    return render_template("events/list.html", upcoming=upcoming, past=past)


def _read_event_form(form):
    values = {name: (form.get(name) or "").strip() for name in
              ("name", "event_date", "location", "discipline", "description",
               "event_type", "entry_fee", "max_participants")}
    errors = {}
    if not values["name"]:
        errors["name"] = "Give the event a name."
    if not valid_date(values["event_date"]):
        errors["event_date"] = "Enter the event date."
    if values["event_type"] not in dict(config.EVENT_TYPES):
        errors["event_type"] = "Choose an event type."

    clean_fee = 0.0
    if values["entry_fee"]:
        try:
            clean_fee = round(float(values["entry_fee"]), 2)
            if clean_fee < 0 or clean_fee > 100000:
                raise ValueError
        except ValueError:
            errors["entry_fee"] = "Enter an amount such as 10 or 7.50."
    maximum = None
    if values["max_participants"]:
        maximum = to_int(values["max_participants"])
        if maximum is None or maximum < 1:
            errors["max_participants"] = "Enter a whole number of 1 or more, or leave blank for no limit."

    cleaned = dict(values, entry_fee=clean_fee, max_participants=maximum)
    return values, cleaned, errors


@bp.route("/events/new", methods=("GET", "POST"))
@roles_required("admin")
def new():
    values, errors = {"event_type": "competition", "entry_fee": "0"}, {}
    if request.method == "POST":
        values, cleaned, errors = _read_event_form(request.form)
        if not errors:
            event_id = events_model.save_event(g.user["club_id"], cleaned)
            flash("Event created.", "success")
            return redirect(url_for("events.detail", event_id=event_id))
    return render_template("events/form.html", event=None, values=values, errors=errors,
                           event_types=config.EVENT_TYPES,
                           disciplines=sports.SPORTS[g.club["sport"]]["disciplines"])


@bp.route("/events/<int:event_id>/edit", methods=("GET", "POST"))
@roles_required("admin")
def edit(event_id):
    event = _event_or_404(event_id)
    values, errors = dict(event), {}
    values["entry_fee"] = f"{event['entry_fee']:g}"                       # 15.0 -> "15"
    values["max_participants"] = event["max_participants"] or ""
    if request.method == "POST":
        values, cleaned, errors = _read_event_form(request.form)
        if (not errors and cleaned["max_participants"] is not None
                and cleaned["max_participants"] < event["reg_count"]):
            errors["max_participants"] = (f"{event['reg_count']} members are already registered, "
                                          "so the limit cannot be lower than that.")
        if not errors:
            events_model.save_event(g.user["club_id"], cleaned, event_id)
            flash("Event saved.", "success")
            return redirect(url_for("events.detail", event_id=event_id))
    return render_template("events/form.html", event=event, values=values, errors=errors,
                           event_types=config.EVENT_TYPES,
                           disciplines=sports.SPORTS[g.club["sport"]]["disciplines"])


@bp.route("/events/<int:event_id>")
@roles_required("admin", "member")
def detail(event_id):
    event = _event_or_404(event_id)
    participants = events_model.participants(event_id)
    is_admin = g.user["role"] == "admin"
    my_result = None
    if not is_admin:
        my_result = results_model.result_for(event_id, g.user["id"])
    return render_template(
        "events/detail.html", event=event, participants=participants,
        i_am_registered=any(p["id"] == g.user["id"] for p in participants),
        is_full=event["max_participants"] is not None and event["reg_count"] >= event["max_participants"],
        is_past=event["event_date"] < date.today().isoformat(),
        can_add=events_model.members_not_registered(g.user["club_id"], event_id) if is_admin else [],
        my_result=my_result,
    )


def _target_member():
    """Who is being signed up or cancelled: a member acts for themselves, an admin picks someone."""
    if g.user["role"] == "admin":
        return users.get_member(g.user["club_id"], to_int(request.form.get("member_id"))) or abort(404)
    return g.user


@bp.route("/events/<int:event_id>/register", methods=("POST",))
@roles_required("admin", "member")
def register(event_id):
    event = _event_or_404(event_id)
    member = _target_member()
    error = events_model.register(event, member)
    if error:
        flash(error, "warning")
    else:
        flash(f"{member['full_name']} is registered for {event['name']}.", "success")
    return redirect(url_for("events.detail", event_id=event_id))


@bp.route("/events/<int:event_id>/unregister", methods=("POST",))
@roles_required("admin", "member")
def unregister(event_id):
    event = _event_or_404(event_id)
    member = _target_member()
    error = events_model.unregister(event, member)
    if error:
        flash(error, "warning")
    else:
        flash(f"{member['full_name']} is no longer registered for {event['name']}.", "info")
    return redirect(url_for("events.detail", event_id=event_id))
