"""Everything that differs between sports lives in this file.

Each sport says:
  fields      - the result fields to ask for (and show as table columns)
  rank        - a function that turns a result into a sortable value (LOWER = BETTER)
  disciplines - suggestions for the "discipline" box when creating an event

To add a new sport (say archery) add one more entry to SPORTS below. The result
form, the results table and the ranking all pick it up automatically.

Field types: "number", "text", "time" (h:mm:ss) and "choice".
"""
import math

SPORTS = {
    "shooting": {
        "label": "Shooting",
        "fields": [
            {"name": "score", "label": "Score", "type": "number"},
            {"name": "target", "label": "Target", "type": "text",
             "help": "For example 25m precision"},
        ],
        "rank": lambda data: -data["score"],           # higher score is better
        "disciplines": ["25m pistol", "50m rifle", "10m air rifle"],
    },
    "running": {
        "label": "Running",
        "fields": [
            {"name": "finish_time", "label": "Finish time", "type": "time",
             "help": "Like 45:30 (minutes:seconds) or 1:05:30 (hours:minutes:seconds)"},
        ],
        "rank": lambda data: data["finish_time"],      # lower time is better
        "disciplines": ["5K", "10K", "Half marathon"],
    },
    "chess": {
        "label": "Chess",
        "fields": [
            {"name": "outcome", "label": "Result", "type": "choice",
             "choices": [("win", "Win"), ("draw", "Draw"), ("loss", "Loss")]},
        ],
        "rank": lambda data: {"win": 0, "draw": 1, "loss": 2}[data["outcome"]],
        "disciplines": ["Rapid", "Blitz", "Classical"],
    },
}


def sport_choices():
    """[(key, label), ...] for the 'sport' drop-down when creating a club."""
    return [(key, sport["label"]) for key, sport in SPORTS.items()]


def sport_label(key):
    return SPORTS[key]["label"]


# ---------- time helpers ----------

def parse_time(text):
    """'45:30' or '1:05:30' -> seconds. Returns None if the text is not a valid time."""
    parts = text.strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return None
    numbers = [int(p) for p in parts]
    if len(numbers) == 2:
        numbers.insert(0, 0)                  # no hours given
    hours, minutes, seconds = numbers
    if minutes > 59 or seconds > 59:
        return None
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


def format_time(total_seconds):
    hours, rest = divmod(int(total_seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


# ---------- reading and showing results ----------

def parse_result(sport_key, form):
    """Validate the result fields of a submitted form.

    Returns (data, errors): 'data' is a dict ready to store, 'errors' maps a
    field name to a message.
    """
    data, errors = {}, {}
    for field in SPORTS[sport_key]["fields"]:
        name, label, kind = field["name"], field["label"], field["type"]
        raw = (form.get(name) or "").strip()
        if not raw:
            errors[name] = f"{label} is required."
            continue

        if kind == "number":
            try:
                value = float(raw)
            except ValueError:
                errors[name] = "Enter a number."
                continue
            if not math.isfinite(value) or value < 0 or value > 100000:
                errors[name] = "Enter a number between 0 and 100000."
                continue
            data[name] = int(value) if value.is_integer() else value
        elif kind == "time":
            seconds = parse_time(raw)
            if seconds is None:
                errors[name] = "Enter a time like 45:30 or 1:05:30."
                continue
            data[name] = seconds
        elif kind == "choice":
            if raw not in dict(field["choices"]):
                errors[name] = "Choose one of the options."
                continue
            data[name] = raw
        else:  # plain text
            if len(raw) > 100:
                errors[name] = "Please keep this under 100 characters."
                continue
            data[name] = raw
    return data, errors


def rank_key(sport_key, data):
    return SPORTS[sport_key]["rank"](data)


def display_values(sport_key, data):
    """The result as a list of strings, one per column (same order as the fields)."""
    shown = []
    for field in SPORTS[sport_key]["fields"]:
        value = data.get(field["name"])
        if field["type"] == "time":
            shown.append(format_time(value))
        elif field["type"] == "choice":
            shown.append(dict(field["choices"]).get(value, str(value)))
        else:
            shown.append(str(value))
    return shown


def summary(sport_key, data):
    """One-line text such as 'Score 92, Target 25m'."""
    labels = [f["label"] for f in SPORTS[sport_key]["fields"]]
    return ", ".join(f"{label} {value}" for label, value in zip(labels, display_values(sport_key, data)))


def form_values(sport_key, data):
    """Turn stored data back into strings so an edit form can be pre-filled."""
    values = {}
    for field in SPORTS[sport_key]["fields"]:
        value = data.get(field["name"])
        if value is None:
            continue
        values[field["name"]] = format_time(value) if field["type"] == "time" else str(value)
    return values
