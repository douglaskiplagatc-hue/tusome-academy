from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from extensions import db
from models import Event
from datetime import datetime

events_bp = Blueprint("events_bp", __name__, url_prefix="/events")


@events_bp.route("/")
@login_required
def manage_events():
    # show all events
    events = Event.query.order_by(Event.start_time.desc()).all()
    return render_template("events/manage.html", events=events)


@events_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_event():
    # if not current_user.is_admin(): abort(403)
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        start_time_raw = request.form.get("start_time")
        end_time_raw = request.form.get("end_time")
        audience = request.form.get("audience", "all")

        # parse datetimes from form inputs (expects datetime-local format)
        start_time = None
        end_time = None
        try:
            if start_time_raw:
                start_time = datetime.fromisoformat(start_time_raw)
            if end_time_raw:
                end_time = datetime.fromisoformat(end_time_raw)
        except Exception:
            flash("Invalid date/time format", "danger")
            return redirect(url_for("events_bp.add_event"))

        ev = Event(
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            created_by=current_user.id,
        )
        # optional: ev.audience = audience
        db.session.add(ev)
        db.session.commit()
        flash("Event created", "success")
        return redirect(url_for("events_bp.manage_events"))

    return render_template("events/form.html", action="Add", event=None)


@events_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_event(id):
    ev = Event.query.get_or_404(id)
    # if not current_user.is_admin(): abort(403)
    if request.method == "POST":
        ev.title = request.form.get("title")
        ev.description = request.form.get("description")
        start_time_raw = request.form.get("start_time")
        end_time_raw = request.form.get("end_time")
        try:
            if start_time_raw:
                ev.start_time = datetime.fromisoformat(start_time_raw)
            if end_time_raw:
                ev.end_time = datetime.fromisoformat(end_time_raw)
        except Exception:
            flash("Invalid date/time format", "danger")
            return redirect(url_for("events_bp.edit_event", id=id))
        db.session.commit()
        flash("Event updated", "success")
        return redirect(url_for("events_bp.manage_events"))
    return render_template("events/form.html", action="Edit", event=ev)


@events_bp.route("/delete/<int:id>", methods=["POST", "GET"])
@login_required
def delete_event(id):
    ev = Event.query.get_or_404(id)
    db.session.delete(ev)
    db.session.commit()
    flash("Event deleted", "danger")
    return redirect(url_for("events_bp.manage_events"))
@events_bp.route("/view/<int:id>")
@login_required
def view_event(id):
    event = Event.query.get_or_404(id)
    return render_template("events/view.html", event=event)