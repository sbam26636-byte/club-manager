"""Club Manager: the starting point of the application.

Run it with:   python app.py      (or)      flask --app app run --debug
"""
from datetime import date

from flask import Flask, g, redirect, render_template, url_for

import config
import db
import security
from models import results as results_model


def nice_date(value):
    """'2026-03-10' -> '10 Mar 2026' (used in the templates as {{ value|nice_date }})."""
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return "-"


def create_app(test_config=None):
    app = Flask(__name__, instance_path=config.INSTANCE_DIR)
    app.config.from_object(config.Config)
    if test_config:                          # the automated tests pass their own settings
        app.config.update(test_config)

    db.init_app(app)
    security.init_app(app)

    # Each blueprint is a group of related pages (see the routes/ folder).
    from routes import auth, events, files, me, members, results, superadmin
    for module in (auth, superadmin, members, events, results, me, files):
        app.register_blueprint(module.bp)

    app.jinja_env.filters["nice_date"] = nice_date

    @app.route("/")
    def index():
        """Send each kind of user to their own home page."""
        if g.user is None:
            return redirect(url_for("auth.login"))
        role = g.user["role"]
        if role == "superadmin":
            return redirect(url_for("superadmin.clubs"))
        if role == "admin":
            return redirect(url_for("members.dashboard"))
        return redirect(url_for("me.profile"))

    @app.context_processor
    def template_globals():
        """Values every template can use."""
        pending = 0
        if g.user is not None and g.user["role"] == "admin":
            pending = results_model.count_pending(g.user["club_id"])
        return {
            "current_user": g.user,
            "current_club": g.club,
            "csrf_token": security.csrf_token,
            "today": date.today().isoformat(),
            "pending_count": pending,
            "currency": app.config["CURRENCY_SYMBOL"],
        }

    messages = {
        400: ("Request not accepted", None),
        403: ("You do not have access to this page", "Your account is not allowed to see this."),
        404: ("Page not found", "The page does not exist, or it belongs to another club."),
        413: ("File too large", "Uploaded files can be up to 5 MB."),
    }

    def show_error(error):
        title, default_text = messages.get(error.code, ("Something went wrong", None))
        text = default_text or getattr(error, "description", "")
        return render_template("errors/error.html", code=error.code, title=title, text=text), error.code

    for code in messages:
        app.register_error_handler(code, show_error)

    return app


if __name__ == "__main__":
    create_app().run(debug=False)
