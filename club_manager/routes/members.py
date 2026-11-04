"""Club admin pages for managing members (plus the admin dashboard)."""
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

import config
import uploads
from models import events as events_model
from models import results as results_model
from models import users
from routes.helpers import valid_date
from security import generate_password, roles_required

bp = Blueprint("members", __name__)


@bp.route("/dashboard")
@roles_required("admin")
def dashboard():
    club_id = g.user["club_id"]
    users.refresh_club(club_id)
    return render_template(
        "admin/dashboard.html",
        active_members=users.count_members(club_id, "active"),
        upcoming=events_model.next_events(club_id, 4),
        pending=results_model.count_pending(club_id),
    )


@bp.route("/members")
@roles_required("admin")
def index():
    club_id = g.user["club_id"]
    users.refresh_club(club_id)                          # apply yearly renewals first
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    membership_type = request.args.get("type", "")
    return render_template(
        "members/list.html",
        members=users.list_members(club_id, search, status, membership_type),
        q=search, status=status, mtype=membership_type,
        membership_types=config.MEMBERSHIP_TYPES,
    )


def _own_member_or_404(user_id):
    """Look up a member of the admin's own club; any other id is a 404."""
    return users.get_member(g.user["club_id"], user_id) or abort(404)


def read_member_form(form, files, exclude_id=None, editing=False):
    """Check the member form. Returns (values, errors); 'values' are the cleaned-up strings."""
    text_fields = ["full_name", "email", "phone", "date_of_birth", "join_date",
                   "membership_type", "address", "emergency_contact", "notes"]
    values = {name: (form.get(name) or "").strip() for name in text_fields}
    values["status"] = form.get("status", "active")
    errors = {}

    if not values["full_name"]:
        errors["full_name"] = "Enter the member's full name."
    if "@" not in values["email"] or "." not in values["email"]:
        errors["email"] = "Enter a valid email address."
    elif users.email_exists(values["email"], exclude_id):
        errors["email"] = "This email is already used by another account."
    if not valid_date(values["join_date"]):
        errors["join_date"] = "Enter the join date."
    if values["date_of_birth"]:
        if not valid_date(values["date_of_birth"]):
            errors["date_of_birth"] = "Enter a valid date."
        elif values["date_of_birth"] >= date.today().isoformat():
            errors["date_of_birth"] = "The date of birth must be in the past."
    if values["membership_type"] not in config.MEMBERSHIP_TYPES:
        errors["membership_type"] = "Choose a membership type."
    for name in ("phone", "address", "emergency_contact", "notes", "full_name", "email"):
        if len(values[name]) > 500:
            errors[name] = "This is too long."
    if editing and values["status"] not in ("active", "expired", "deactivated"):
        errors["status"] = "Choose a status."

    photo_error = uploads.check_file(files.get("photo"), uploads.PHOTO_EXTENSIONS)
    if photo_error:
        errors["photo"] = photo_error
    document_error = uploads.check_file(files.get("id_document"), uploads.DOCUMENT_EXTENSIONS)
    if document_error:
        errors["id_document"] = document_error
    return values, errors


def _save_uploads(user_id, files, member=None):
    """Store newly chosen files and forget (delete) the ones they replace."""
    for field, column in (("photo", "photo_file"), ("id_document", "id_document_file")):
        chosen = files.get(field)
        if chosen is not None and chosen.filename:
            if member is not None:
                uploads.delete_file(member[column])
            users.set_file(user_id, column, uploads.save_file(chosen))


@bp.route("/members/new", methods=("GET", "POST"))
@roles_required("admin")
def new():
    values = {"join_date": date.today().isoformat(), "membership_type": config.MEMBERSHIP_TYPES[0]}
    errors = {}
    if request.method == "POST":
        values, errors = read_member_form(request.form, request.files)
        if not errors:
            password = generate_password()
            user_id = users.create_member(g.user["club_id"], values, generate_password_hash(password))
            _save_uploads(user_id, request.files)
            flash(f"Member registered. Login: {values['email'].lower()} / temporary password: {password} "
                  "(shown only once, so copy it now).", "success")
            return redirect(url_for("members.detail", user_id=user_id))
    return render_template("members/form.html", member=None, values=values, errors=errors,
                           membership_types=config.MEMBERSHIP_TYPES)


@bp.route("/members/<int:user_id>")
@roles_required("admin")
def detail(user_id):
    users.refresh_club(g.user["club_id"])
    member = _own_member_or_404(user_id)
    return render_template(
        "members/detail.html", member=member,
        upcoming=events_model.upcoming_for_member(user_id),
        history=results_model.history_for_member(user_id, g.club["sport"]),
    )


@bp.route("/members/<int:user_id>/edit", methods=("GET", "POST"))
@roles_required("admin")
def edit(user_id):
    member = _own_member_or_404(user_id)
    values, errors = dict(member), {}
    if request.method == "POST":
        values, errors = read_member_form(request.form, request.files, exclude_id=user_id, editing=True)
        if member["status"] == "deactivated":
            values["status"] = "deactivated"              # changed only with the Reactivate button
        if not errors:
            users.update_member(user_id, values, values["status"])
            _save_uploads(user_id, request.files, member)
            flash("Member details saved.", "success")
            return redirect(url_for("members.detail", user_id=user_id))
    return render_template("members/form.html", member=member, values=values, errors=errors,
                           membership_types=config.MEMBERSHIP_TYPES)


@bp.route("/members/<int:user_id>/deactivate", methods=("POST",))
@roles_required("admin")
def deactivate(user_id):
    member = _own_member_or_404(user_id)
    users.deactivate(user_id)
    flash(f"{member['full_name']} is deactivated. Their history is kept.", "info")
    return redirect(url_for("members.detail", user_id=user_id))


@bp.route("/members/<int:user_id>/reactivate", methods=("POST",))
@roles_required("admin")
def reactivate(user_id):
    member = _own_member_or_404(user_id)
    users.reactivate(user_id)
    flash(f"{member['full_name']} is active again.", "success")
    return redirect(url_for("members.detail", user_id=user_id))


@bp.route("/members/<int:user_id>/reset-password", methods=("POST",))
@roles_required("admin")
def reset_password(user_id):
    member = _own_member_or_404(user_id)
    password = generate_password()
    users.set_password(user_id, generate_password_hash(password))
    flash(f"New temporary password for {member['email']}: {password} (shown only once).", "success")
    return redirect(url_for("members.detail", user_id=user_id))
