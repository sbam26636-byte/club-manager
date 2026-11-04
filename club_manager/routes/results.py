"""Results: admin entry, member submission, approval, and the event results page."""
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

import sports
from models import events as events_model
from models import results as results_model
from routes.helpers import to_int
from security import roles_required

bp = Blueprint("results", __name__)


def _event_or_404(event_id):
    return events_model.get_event(g.user["club_id"], event_id) or abort(404)


def _sport():
    return sports.SPORTS[g.club["sport"]]


@bp.route("/events/<int:event_id>/results")
@roles_required("admin", "member")
def event_results(event_id):
    """The results table of an event: approved results only, best first."""
    event = _event_or_404(event_id)
    ranked = results_model.ranked_for_event(event_id, g.club["sport"])

    # The top three places (equal results share a place, so one place can hold several people).
    podium = {}
    for item in ranked:
        if item["position"] <= 3:
            podium.setdefault(item["position"], []).append(item)

    return render_template("results/event.html", event=event, ranked=ranked,
                           podium=sorted(podium.items()), columns=[f["label"] for f in _sport()["fields"]])


@bp.route("/events/<int:event_id>/results/new", methods=("GET", "POST"))
@roles_required("admin")
def record(event_id):
    """An admin records a result for a registered participant (approved straight away)."""
    event = _event_or_404(event_id)
    candidates = events_model.participants_without_result(event_id)
    values, errors = {"member_id": request.args.get("member_id", "")}, {}

    if request.method == "POST":
        member_id = to_int(request.form.get("member_id"))
        data, errors = sports.parse_result(g.club["sport"], request.form)
        values = request.form.to_dict()
        if member_id not in [c["id"] for c in candidates]:
            errors["member_id"] = "Choose one of the registered participants."
        if not errors:
            results_model.create_result(event_id, member_id, data, "approved")
            flash("Result recorded.", "success")
            return redirect(url_for("results.event_results", event_id=event_id))
    return render_template("results/form.html", mode="record", event=event, sport=_sport(),
                           candidates=candidates, values=values, errors=errors, result=None)


@bp.route("/events/<int:event_id>/results/submit", methods=("GET", "POST"))
@roles_required("member")
def submit(event_id):
    """A member submits their own result; it waits for admin approval."""
    event = _event_or_404(event_id)
    if not events_model.is_registered(event_id, g.user["id"]):
        flash("You can only submit a result for an event you signed up for.", "warning")
        return redirect(url_for("events.detail", event_id=event_id))
    if event["event_date"] > date.today().isoformat():
        flash("You can submit your result once the event has taken place.", "warning")
        return redirect(url_for("events.detail", event_id=event_id))
    if results_model.result_for(event_id, g.user["id"]):
        flash("There is already a result for you on this event.", "info")
        return redirect(url_for("events.detail", event_id=event_id))

    values, errors = {}, {}
    if request.method == "POST":
        data, errors = sports.parse_result(g.club["sport"], request.form)
        values = request.form.to_dict()
        if not errors:
            results_model.create_result(event_id, g.user["id"], data, "pending")
            flash("Result submitted. A club admin will review it.", "success")
            return redirect(url_for("events.detail", event_id=event_id))
    return render_template("results/form.html", mode="submit", event=event, sport=_sport(),
                           candidates=[], values=values, errors=errors, result=None)


@bp.route("/results/<int:result_id>/edit", methods=("GET", "POST"))
@roles_required("admin")
def edit(result_id):
    result = results_model.get_result(g.user["club_id"], result_id) or abort(404)
    event = _event_or_404(result["event_id"])
    values, errors = sports.form_values(g.club["sport"], result["data"]), {}
    if request.method == "POST":
        data, errors = sports.parse_result(g.club["sport"], request.form)
        values = request.form.to_dict()
        if not errors:
            results_model.update_result(result_id, data)
            flash("Result updated.", "success")
            return redirect(url_for("results.event_results", event_id=event["id"]))
    return render_template("results/form.html", mode="edit", event=event, sport=_sport(),
                           candidates=[], values=values, errors=errors, result=result)


@bp.route("/results/<int:result_id>/delete", methods=("POST",))
@roles_required("admin")
def delete(result_id):
    result = results_model.get_result(g.user["club_id"], result_id) or abort(404)
    results_model.delete(result_id)
    flash(f"Result for {result['full_name']} deleted.", "info")
    return redirect(url_for("events.detail", event_id=result["event_id"]))


@bp.route("/results/pending")
@roles_required("admin")
def pending():
    rows = results_model.list_pending(g.user["club_id"])
    for row in rows:
        row["summary"] = sports.summary(g.club["sport"], row["data"])
    return render_template("results/pending.html", rows=rows)


@bp.route("/results/<int:result_id>/approve", methods=("POST",))
@roles_required("admin")
def approve(result_id):
    result = results_model.get_result(g.user["club_id"], result_id) or abort(404)
    results_model.approve(result_id)
    flash(f"Result for {result['full_name']} approved.", "success")
    return redirect(url_for("results.pending"))


@bp.route("/results/<int:result_id>/reject", methods=("POST",))
@roles_required("admin")
def reject(result_id):
    result = results_model.get_result(g.user["club_id"], result_id) or abort(404)
    if result["status"] != "pending":
        abort(400, "Only pending results can be rejected.")
    results_model.delete(result_id)          # the member can submit a corrected result
    flash(f"Result for {result['full_name']} rejected.", "info")
    return redirect(url_for("results.pending"))
