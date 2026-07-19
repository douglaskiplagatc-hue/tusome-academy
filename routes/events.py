from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from extensions import db
from models import Event
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

events_bp = Blueprint("events_bp", __name__)

# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------
def parse_dt(dt_string: str, field_name: str) -> datetime | None:
    """Parse an ISO datetime string to a timezone‑aware UTC datetime."""
    if not dt_string:
        return None
    try:
        # fromisoformat handles '2025-01-01T10:00' and '+00:00' offsets
        dt = datetime.fromisoformat(dt_string)
        if dt.tzinfo is None:
            # Assume input is in UTC; make it explicit
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except ValueError as e:
        logger.warning(f"Invalid {field_name}: {dt_string} – {e}")
        flash(f"Invalid {field_name} format. Please use YYYY-MM-DDTHH:MM.", "danger")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing {field_name}: {e}")
        flash("An unexpected error occurred while processing the date/time.", "danger")
        return None


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------
@events_bp.route("/")
@login_required
def manage_events():
    """List events with optional search and pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = 20  # adjust as needed
    search = request.args.get("search", "").strip()

    query = Event.query
    if search:
        query = query.filter(Event.title.ilike(f"%{search}%"))
    query = query.order_by(Event.start_time.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    events = pagination.items

    return render_template(
        "events/manage.html",
        events=events,
        pagination=pagination,
        search=search
    )


@events_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_event():
    """Create a new event. Admin only."""
    if not current_user.is_admin():
        abort(403)

    if request.method == "POST":
        # 1. Gather and validate required fields
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
            return render_template("events/form.html", action="Add", event=None), 400

        description = request.form.get("description", "").strip()
        audience = request.form.get("audience", "all").strip()

        start_time = parse_dt(request.form.get("start_time"), "start time")
        end_time = parse_dt(request.form.get("end_time"), "end time")

        if start_time is None:
            return render_template("events/form.html", action="Add", event=None), 400

        # 2. Validate time logic
        if end_time and end_time <= start_time:
            flash("End time must be after start time.", "danger")
            return render_template("events/form.html", action="Add", event=None), 400

        # 3. Create event
        ev = Event(
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            audience=audience,
            created_by=current_user.id,
        )
        db.session.add(ev)
        db.session.commit()
        flash("Event created successfully.", "success")
        return redirect(url_for("events_bp.manage_events"))

    # GET request
    return render_template("events/form.html", action="Add", event=None)


@events_bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_event(id):
    """Edit an existing event. Admin only."""
    ev = Event.query.get_or_404(id)
    if not current_user.is_admin():
        abort(403)

    if request.method == "POST":
        # 1. Validate
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "danger")
            return render_template("events/form.html", action="Edit", event=ev), 400

        audience = request.form.get("audience", "all").strip()

        start_time = parse_dt(request.form.get("start_time"), "start time")
        end_time = parse_dt(request.form.get("end_time"), "end time")

        # If start_time is required for edits as well, enforce it
        if start_time is None:
            flash("A valid start time is required.", "danger")
            return render_template("events/form.html", action="Edit", event=ev), 400

        if end_time and end_time <= start_time:
            flash("End time must be after start time.", "danger")
            return render_template("events/form.html", action="Edit", event=ev), 400

        # 2. Update fields
        ev.title = title
        ev.description = request.form.get("description", "").strip()
        ev.start_time = start_time
        ev.end_time = end_time
        ev.audience = audience

        db.session.commit()
        flash("Event updated successfully.", "success")
        return redirect(url_for("events_bp.manage_events"))

    # GET: pre‑fill the form
    return render_template("events/form.html", action="Edit", event=ev)


@events_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_event(id):
    """Delete an event (POST only, admin only)."""
    if not current_user.is_admin():
        abort(403)

    ev = Event.query.get_or_404(id)
    db.session.delete(ev)
    db.session.commit()
    flash("Event deleted.", "danger")
    return redirect(url_for("events_bp.manage_events"))


@events_bp.route("/view/<int:id>")
@login_required
def view_event(id):
    """View a single event's details."""
    event = Event.query.get_or_404(id)
    return render_template("events/view.html", event=event)
