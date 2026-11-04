"""Login, logout and changing your own password."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import security
from models import users

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = users.get_by_email(email)
        # One vague message for every failure, so nobody can find out which emails exist.
        if user and user["status"] != "deactivated" and check_password_hash(user["password_hash"], password):
            session.clear()                        # start a fresh session
            session["user_id"] = user["id"]
            return redirect(security.safe_next(request.args.get("next")) or url_for("index"))
        flash("Wrong email or password, or the account is deactivated.", "danger")
    return render_template("login.html")


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/account/password", methods=("GET", "POST"))
@security.login_required
def change_password():
    errors = {}
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not check_password_hash(g.user["password_hash"], current):
            errors["current_password"] = "That is not your current password."
        if len(new) < 8:
            errors["new_password"] = "Use at least 8 characters."
        elif new != confirm:
            errors["confirm_password"] = "The two new passwords do not match."
        if not errors:
            users.set_password(g.user["id"], generate_password_hash(new))
            flash("Your password has been changed.", "success")
            return redirect(url_for("index"))
    return render_template("account_password.html", errors=errors, values={})
