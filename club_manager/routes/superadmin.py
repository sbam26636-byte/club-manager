"""Super-admin pages: create clubs and assign their admins."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

import sports
from models import clubs as clubs_model
from models import users
from security import generate_password, roles_required

bp = Blueprint("superadmin", __name__, url_prefix="/super")


@bp.route("/clubs")
@roles_required("superadmin")
def clubs():
    return render_template("super/clubs.html", clubs=clubs_model.list_clubs(), sport_label=sports.sport_label)


@bp.route("/clubs/new", methods=("GET", "POST"))
@roles_required("superadmin")
def new_club():
    values, errors = {}, {}
    if request.method == "POST":
        values = {"name": request.form.get("name", "").strip(), "sport": request.form.get("sport", "")}
        if not values["name"]:
            errors["name"] = "Give the club a name."
        elif len(values["name"]) > 100:
            errors["name"] = "Keep the name under 100 characters."
        elif clubs_model.name_exists(values["name"]):
            errors["name"] = "A club with this name already exists."
        if values["sport"] not in sports.SPORTS:
            errors["sport"] = "Choose a sport."
        if not errors:
            club_id = clubs_model.create_club(values["name"], values["sport"])
            flash("Club created. Now add its first admin.", "success")
            return redirect(url_for("superadmin.club_detail", club_id=club_id))
    return render_template("super/club_form.html", values=values, errors=errors,
                           sport_choices=sports.sport_choices())


@bp.route("/clubs/<int:club_id>")
@roles_required("superadmin")
def club_detail(club_id):
    club = clubs_model.get_club(club_id) or abort(404)
    return render_template("super/club_detail.html", club=club, admins=users.list_admins(club_id),
                           sport_label=sports.sport_label, values={}, errors={})


@bp.route("/clubs/<int:club_id>/admins/new", methods=("POST",))
@roles_required("superadmin")
def new_admin(club_id):
    club = clubs_model.get_club(club_id) or abort(404)
    values = {"full_name": request.form.get("full_name", "").strip(),
              "email": request.form.get("email", "").strip().lower()}
    errors = {}
    if not values["full_name"]:
        errors["full_name"] = "Enter the admin's name."
    if "@" not in values["email"] or "." not in values["email"]:
        errors["email"] = "Enter a valid email address."
    elif users.email_exists(values["email"]):
        errors["email"] = "This email is already used by another account."
    if errors:
        return render_template("super/club_detail.html", club=club, admins=users.list_admins(club_id),
                               sport_label=sports.sport_label, values=values, errors=errors)
    password = generate_password()
    users.create_admin(club_id, values["full_name"], values["email"], generate_password_hash(password))
    flash(f"Admin created. Temporary password for {values['email']}: {password} "
          "(shown only once, so copy it now).", "success")
    return redirect(url_for("superadmin.club_detail", club_id=club_id))


@bp.route("/admins/<int:user_id>/reset-password", methods=("POST",))
@roles_required("superadmin")
def reset_admin_password(user_id):
    admin = users.get_by_id(user_id)
    if admin is None or admin["role"] != "admin":
        abort(404)
    password = generate_password()
    users.set_password(user_id, generate_password_hash(password))
    flash(f"New temporary password for {admin['email']}: {password} (shown only once).", "success")
    return redirect(url_for("superadmin.club_detail", club_id=admin["club_id"]))
