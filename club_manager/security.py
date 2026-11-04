"""Login, roles and CSRF protection.

  * login_required / roles_required are decorators placed above a route.
  * Every POST form must contain the hidden CSRF token (the templates add it),
    otherwise the request is refused.
"""
import hmac
import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from models import clubs, users


def init_app(app):
    app.before_request(load_user)
    app.before_request(check_csrf)
    app.after_request(add_security_headers)


def load_user():
    """Runs before every request: find out who is logged in (g.user) and their club (g.club)."""
    g.user = None
    g.club = None
    user_id = session.get("user_id")
    if user_id:
        user = users.get_by_id(user_id)
        if user is None or user["status"] == "deactivated":
            session.clear()                       # deleted or deactivated: log them out
        else:
            g.user = user
            if user["club_id"]:
                g.club = clubs.get_club(user["club_id"])


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def check_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not hmac.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "Your session expired or the form was invalid. Go back, reload the page and try again.")


def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


def roles_required(*roles):
    """Only let people with one of these roles in. Everyone else gets an error page."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("auth.login", next=request.path))
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def login_required(view):
    return roles_required("superadmin", "admin", "member")(view)


def safe_next(url):
    """Only follow 'next' addresses that stay on this site."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return None


def generate_password():
    """A random temporary password (no look-alike characters such as 0/O or 1/l)."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))
