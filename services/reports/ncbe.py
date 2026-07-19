"""CBC / NCBE level helpers — delegates to Grade model."""

from models import Grade


def marks_to_ncbe(marks):
    if marks is None:
        return "—"
    level, _ = Grade.get_ncbe_level_and_points(float(marks))
    return level or "—"


def marks_to_remarks(marks):
    if marks is None:
        return "Not graded"
    m = float(marks)
    if m >= 80:
        return "Excellent"
    if m >= 60:
        return "Good"
    if m >= 40:
        return "Satisfactory"
    return "Intervention Needed"


def average_marks(values):
    nums = [float(v) for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None
