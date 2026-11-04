# Club Membership & Competition Manager (PoC)

A web app for running sports clubs: members, yearly renewals, events, sign-ups and results.
One installation hosts several clubs (the demo has shooting, running and chess), and each
club's data is kept separate.

Built with **Python + Flask**, **SQLite** and server-rendered **Jinja2** pages styled with
**Bootstrap 5**. No JavaScript front end. The only Python package you need to install is Flask.

---

## 1. Set it up and run it

You need Python 3.9 or newer. Open a terminal in the project folder (the one containing `app.py`).

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py          # creates the demo data (and prints the logins)
python app.py           # starts the site
```

**Windows (PowerShell)**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py
python app.py
```

Then open <http://127.0.0.1:5000> in your browser.

> The page layout loads Bootstrap and a font from the internet (CDN links in
> `templates/base.html`), so you need to be online the first time you look at it.

If you skip `python seed.py` the app still starts, with an empty database. The only way to
create the first super-admin is the seed script (or inserting one by hand), so run the seed
for a first try.

### Demo logins

| Role | Email | Password |
|---|---|---|
| Super-admin | `super@clubmanager.example` | `SuperAdmin1` |
| Shooting club admin | `admin@shooting.example` | `Admin1234` |
| Running club admin | `admin@running.example` | `Admin1234` |
| Chess club admin | `admin@chess.example` | `Admin1234` |
| A shooting member | `liam.walsh@shooting.example` | `Member1234` |
| A running member | `hannah.moran@running.example` | `Member1234` |
| A chess member | `isla.healy@chess.example` | `Member1234` |

Every demo member uses `Member1234`; their emails look like `firstname.lastname@shooting.example`
(or `running` / `chess`). `python seed.py` prints this list again, and **resets** all data each time.

### Try the three "week 3" tasks

1. **Register a member:** log in as `admin@shooting.example`, then *Members → Register a member*.
   A temporary password is shown once after saving. Log in as the new member in a private window.
2. **Record a result:** open *Events → Club Championship*. One participant (Oisín Hughes) has no
   result yet, so click *Record result* next to their name.
3. **Show an event's results:** *Events → Club Championship → View results*: ranked table with a podium.

Other things to try: as a member, sign up for the *Winter Open*; submit a result for *Midweek
Practice*; then, as admin, approve it under *Review results*.

### Run the automated tests
```bash
python -m unittest -v
```
They use a temporary database, so your demo data is not touched.

---

## 2. How the code is organised

```
app.py            Creates the app, registers the pages, error pages and template helpers
config.py         Settings (secret key, database path, membership types, currency symbol)
db.py             Opens the SQLite database and creates the tables
schema.sql        The table definitions
security.py       Login checks, role checks and CSRF protection
sports.py         EVERYTHING that differs between sports (fields, ranking, suggestions)
uploads.py        Saving member photos / ID documents
seed.py           Demo data
models/           All database queries: clubs.py, users.py, events.py, results.py
routes/           The pages, one file per subject:
                    auth.py       login, logout, change password
                    superadmin.py clubs and club admins
                    members.py    dashboard + member management (club admin)
                    events.py     events and sign-ups
                    results.py    result entry, member submission, approval, results page
                    me.py         the member's own pages
                    files.py      protected download of uploaded files
templates/        Jinja2 HTML pages (base.html is the shared layout, _macros.html has form helpers)
static/css/       style.css (small layer on top of Bootstrap)
tests/            Automated tests
instance/         Created at run time: the database file and uploads (not for git)
```

How a request flows, using "show an event's results" as the example:
`/events/3/results` → `routes/results.py: event_results()` → asks `models/results.py` for the
approved results → ranks them using the rules in `sports.py` → fills `templates/results/event.html`.

### Adding a new sport

Open `sports.py` and add one entry to `SPORTS` (copy the chess one): its result fields, a
`rank` function (lower value = better place) and some discipline suggestions. The club form,
result form, results table, ranking and member history all pick it up automatically.
Results are stored as JSON in one column, so no database change is needed.

---

## 3. How the spec was applied

| Spec section | Where |
|---|---|
| Roles, role checks on every route | `security.roles_required`, and every query is filtered by the logged-in person's club |
| Hashed passwords, sessions, CSRF | Werkzeug hashing; `SECRET_KEY` in `config.py`; hidden token in every form (`security.py`) |
| Multi-club, sport drives result fields | `clubs.sport` + `sports.py` |
| Members deactivated, never deleted | *Deactivate / Reactivate* buttons; history kept |
| Search and filters | *Members* page (name, email or number; status; type) |
| Sign-ups respect the maximum | `models/events.py: register()` |
| Pending / approved results, no stored ranking | `results.status`; positions computed in `ranked_for_event()` |
| Uploads served only to authorised users | files live in `instance/uploads`, served by `routes/files.py` after a permission check |
| Renewals | `models/users.py: membership_expiry()` and `refresh_club()` |

## 4. Assumptions (the spec left these open)

Each of these is a simple choice that is easy to change:

1. **Renewal.** Renewal is automatic: whenever the member list, dashboard or a profile loads, every
   *active* member whose expiry date has passed gets the next anniversary as the new expiry date and
   stays active. Status *expired* is therefore set by hand by an admin (edit the member); expired
   members are not auto-renewed until an admin sets them back to *active*.
2. **Expired members can still log in** and sign up for events. **Deactivated members cannot log in.**
3. **Membership types** are a fixed list in `config.py` (Standard, Family, Student, Senior, Honorary).
4. **Member numbers** are assigned automatically per club, starting at 1001.
5. **Passwords.** The admin never types a member's password: a random temporary password is shown once
   after registering a member (or resetting the password). Everyone can change their own password.
   *(The temporary password travels in the flash message, which is stored in the signed session cookie
   of the admin's own browser. Fine for a PoC; for production, email it or force a change at first login.)*
6. **One result per member per event.** Rejecting a pending result deletes it so the member can
   submit a corrected one. Result statuses stay `pending` / `approved` as in the spec.
7. **Who may do what with results.** Admins can record a result for any registered participant, at any
   time. Members can submit theirs only for events they signed up for, once the event date is today or past.
8. **Sign-ups** close after the event date. A sign-up with a recorded result cannot be cancelled.
9. **Ties** share a place (1, 1, 3). For chess, a result is win / draw / loss per participant, ranked
   win → draw → loss, so ties are common.
10. **Currency** for entry fees is `€` (`CURRENCY_SYMBOL` in `config.py`). Entry fees are informational:
    there is no payment handling.
11. The **super-admin** only manages clubs and club admins; they cannot see member data.
12. Club admins are accounts but not "members": they do not appear in the member list.
13. Uploads: photos (png, jpg, gif, webp) and ID documents (also pdf), up to 5 MB, checked by file
    extension only.

## 5. Known limits of a PoC

- No password-reset by email, no login rate limiting, no HTTPS handling (put it behind a proper
  web server for real use, and set a strong `SECRET_KEY` environment variable).
- Uploaded files are validated by extension, not by inspecting their content.
- No admin removal, club deletion, event deletion or pagination of long lists.
- SQLite and Flask's built-in server are for development. Use a production server (such as gunicorn)
  and a bigger database if this ever goes live.
