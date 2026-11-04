# Week 03 — Independent AI Code Review

## Project
Club Membership & Competition Manager

## Review approach
The application scaffold was generated using Claude. ChatGPT was used as a second AI to review selected parts of the code. Findings were checked against the source code and automated tests before corrections were made.

## Finding 1 — Flask debug mode enabled

- File: `club_manager/app.py`
- Original code: `create_app().run(debug=True)`
- Status: Confirmed
- Risk: Flask's interactive debugger is unsafe if exposed in a production deployment.
- Fix: Changed `debug=True` to `debug=False`.
- Commit: `398ac66`
- Verification: All 20 automated tests passed. The server subsequently displayed `Debug mode: off`.

## Finding 2 — Predictable default secret key

- File: `club_manager/config.py`
- Original code: `SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")`
- Status: Confirmed
- Risk: If the environment variable was missing, Flask would use a publicly known key for signing sessions.
- Fix: Removed the predictable fallback so the key must be supplied through the environment.
- Commit: `b80641e`
- Verification: All 20 automated tests passed. The application was started with a randomly generated environment key, and login was tested successfully.
- Remaining limitation: Production startup should explicitly reject a missing secret key.

## Finding 3 — ResourceWarning during upload test

- File: `club_manager/tests/test_app.py`
- Status: Warning observed; root cause not yet confirmed.
- Evidence: `ResourceWarning: unclosed file` appeared during the photo upload test.
- Decision: Record for further investigation rather than claim a confirmed application vulnerability.

## Automated testing

Command:

`python -m unittest discover -s tests -v`

Results:
- Original scaffold: 20 tests passed.
- After fix 1: 20 tests passed.
- After fix 2: 20 tests passed.

## Manual verification

- Super administrator login and club listing worked.
- Club administrator dashboard and member listing worked.
- A test member was registered and found again through the member search.
- The corrected application started with debug mode disabled.
- Login continued to work after the security changes.

## Conclusion

Two confirmed configuration issues were corrected in separate Git commits. Automated tests and manual checks found no regressions in the scenarios tested. This does not establish that the application is free from all security or functional defects.
