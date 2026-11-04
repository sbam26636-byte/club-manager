"""Automated checks. Run them with:   python -m unittest -v

They use a throw-away database, so your real data is never touched.
"""
import os
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from db import get_db  # noqa: E402
from models import clubs, events, results, users  # noqa: E402


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE": os.path.join(self.folder.name, "test.sqlite"),
            "UPLOAD_FOLDER": os.path.join(self.folder.name, "uploads"),
            "SECRET_KEY": "test",
        })
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO users (role, email, password_hash, full_name) VALUES ('superadmin', 'super@x.test', ?, 'Super')",
                       (generate_password_hash("SuperAdmin1"),))
            db.commit()
            self.shooting = clubs.create_club("Shooters", "shooting")
            self.running = clubs.create_club("Runners", "running")
            self.admin = users.create_admin(self.shooting, "Alice", "alice@x.test", generate_password_hash("Admin1234"))
            self.other_admin = users.create_admin(self.running, "Bob", "bob@x.test", generate_password_hash("Admin1234"))
            self.member = self._member(self.shooting, "Mary Member", "mary@x.test")
            self.member2 = self._member(self.shooting, "Mick Member", "mick@x.test")
            self.runner = self._member(self.running, "Rita Runner", "rita@x.test")
            self.event = events.save_event(self.shooting, self._event("Shoot A", -3))
            self.future_event = events.save_event(self.shooting, self._event("Shoot B", 10, maximum=1))
            self.running_event = events.save_event(self.running, self._event("Run A", -3))
        self.client = self.app.test_client()

    def tearDown(self):
        self.folder.cleanup()

    # ----- helpers -----
    def _member(self, club_id, name, email):
        return users.create_member(club_id, {
            "full_name": name, "email": email, "phone": "", "date_of_birth": "", "join_date": "2024-03-10",
            "membership_type": "Standard", "address": "", "emergency_contact": "", "notes": "",
        }, generate_password_hash("Member1234"))

    def _event(self, name, offset, maximum=None):
        return {"name": name, "event_date": (date.today() + timedelta(days=offset)).isoformat(),
                "location": "", "discipline": "25m pistol", "description": "", "event_type": "competition",
                "entry_fee": 0.0, "max_participants": maximum}

    def token(self, client=None):
        """Load a page to get a session, then read the CSRF token out of its form."""
        client = client or self.client
        page = client.get("/login").get_data(as_text=True)
        return re.search(r'name="_csrf" value="([^"]+)"', page).group(1)

    def login(self, email, password):
        client = self.app.test_client()
        client.post("/login", data={"email": email, "password": password, "_csrf": self.token(client)})
        return client

    def post(self, client, url, data=None, **kwargs):
        """POST with a fresh CSRF token taken from the session."""
        with client.session_transaction() as session:
            session.setdefault("_csrf", "token-for-tests")
            token = session["_csrf"]
        return client.post(url, data=dict(data or {}, _csrf=token), **kwargs)


class LoginAndAccessTests(AppTestCase):
    def test_every_page_needs_login(self):
        for url in ("/", "/members", "/events", "/me", "/super/clubs", "/dashboard"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("/login", response.headers["Location"])

    def test_login_with_wrong_password_fails(self):
        client = self.login("alice@x.test", "wrong")
        self.assertEqual(client.get("/members").status_code, 302)

    def test_post_without_csrf_token_is_refused(self):
        response = self.client.post("/login", data={"email": "alice@x.test", "password": "Admin1234"})
        self.assertEqual(response.status_code, 400)

    def test_roles_see_different_homes(self):
        self.assertIn("/super/clubs", self.login("super@x.test", "SuperAdmin1").get("/").headers["Location"])
        self.assertIn("/dashboard", self.login("alice@x.test", "Admin1234").get("/").headers["Location"])
        self.assertIn("/me", self.login("mary@x.test", "Member1234").get("/").headers["Location"])

    def test_member_cannot_open_admin_pages(self):
        client = self.login("mary@x.test", "Member1234")
        for url in ("/members", "/members/new", "/events/new", "/results/pending", "/dashboard", "/super/clubs"):
            self.assertEqual(client.get(url).status_code, 403, url)

    def test_member_cannot_see_other_members(self):
        client = self.login("mary@x.test", "Member1234")
        self.assertEqual(client.get(f"/members/{self.member2}").status_code, 403)

    def test_admin_cannot_reach_another_clubs_data(self):
        client = self.login("alice@x.test", "Admin1234")
        self.assertEqual(client.get(f"/members/{self.runner}").status_code, 404)
        self.assertEqual(client.get(f"/members/{self.runner}/edit").status_code, 404)
        self.assertEqual(client.get(f"/events/{self.running_event}").status_code, 404)
        self.assertEqual(client.get(f"/events/{self.running_event}/results").status_code, 404)

    def test_member_cannot_reach_another_clubs_event(self):
        client = self.login("mary@x.test", "Member1234")
        self.assertEqual(client.get(f"/events/{self.running_event}").status_code, 404)

    def test_super_admin_cannot_open_member_data(self):
        client = self.login("super@x.test", "SuperAdmin1")
        self.assertEqual(client.get("/members").status_code, 403)

    def test_deactivated_member_cannot_log_in(self):
        with self.app.app_context():
            users.deactivate(self.member)
        client = self.login("mary@x.test", "Member1234")
        self.assertEqual(client.get("/me").status_code, 302)


class WeekThreeTasks(AppTestCase):
    """The three tasks the spec says must work end to end."""

    def test_register_a_member_then_log_in_as_them(self):
        admin = self.login("alice@x.test", "Admin1234")
        response = self.post(admin, "/members/new", {
            "full_name": "Nora New", "email": "nora@x.test", "join_date": "2025-01-15",
            "membership_type": "Student", "phone": "", "date_of_birth": "", "address": "",
            "emergency_contact": "", "notes": ""}, follow_redirects=True)
        page = response.get_data(as_text=True)
        self.assertIn("Nora New", page)
        password = re.search(r"temporary password: (\w+)", page).group(1)
        member = self.login("nora@x.test", password)
        self.assertEqual(member.get("/me").status_code, 200)

    def test_duplicate_email_is_rejected(self):
        admin = self.login("alice@x.test", "Admin1234")
        response = self.post(admin, "/members/new", {
            "full_name": "Copy", "email": "MARY@x.test", "join_date": "2025-01-15", "membership_type": "Standard"})
        self.assertIn("already used", response.get_data(as_text=True))

    def test_record_a_result_and_show_event_results(self):
        admin = self.login("alice@x.test", "Admin1234")
        with self.app.app_context():
            for member in (self.member, self.member2):
                events.register({"id": self.event, "event_date": "2999-01-01", "max_participants": None,
                                 "reg_count": 0}, {"id": member, "status": "active"})
        for member_id, score in ((self.member, "88"), (self.member2, "95")):
            response = self.post(admin, f"/events/{self.event}/results/new",
                                 {"member_id": member_id, "score": score, "target": "25m"})
            self.assertEqual(response.status_code, 302)
        page = admin.get(f"/events/{self.event}/results").get_data(as_text=True)
        self.assertLess(page.index("Mick Member"), page.rindex("Mary Member"))   # 95 ranks above 88
        self.assertIn("1st place", page)

    def test_result_for_unregistered_member_is_refused(self):
        admin = self.login("alice@x.test", "Admin1234")
        response = self.post(admin, f"/events/{self.event}/results/new",
                             {"member_id": self.member, "score": "90", "target": "25m"})
        self.assertEqual(response.status_code, 200)                  # no redirect: nothing was saved
        self.assertIn("nobody has signed up yet", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(results.ranked_for_event(self.event, "shooting"), [])


class SignUpAndApprovalTests(AppTestCase):
    def test_member_signs_up_and_event_capacity_is_respected(self):
        first = self.login("mary@x.test", "Member1234")
        second = self.login("mick@x.test", "Member1234")
        self.post(first, f"/events/{self.future_event}/register")
        response = self.post(second, f"/events/{self.future_event}/register", follow_redirects=True)
        self.assertIn("This event is full", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(events.get_event(self.shooting, self.future_event)["reg_count"], 1)

    def test_member_result_stays_pending_until_approved(self):
        with self.app.app_context():
            get_db().execute("INSERT INTO registrations (event_id, user_id, created_at) VALUES (?, ?, 'x')",
                             (self.event, self.member))
            get_db().commit()
        member = self.login("mary@x.test", "Member1234")
        self.post(member, f"/events/{self.event}/results/submit", {"score": "91", "target": "25m"})

        # Pending results are not shown on the results page.
        self.assertIn("No results to show yet", member.get(f"/events/{self.event}/results").get_data(as_text=True))
        with self.app.app_context():
            pending = results.list_pending(self.shooting)
            self.assertEqual(len(pending), 1)
            result_id = pending[0]["id"]

        admin = self.login("alice@x.test", "Admin1234")
        self.post(admin, f"/results/{result_id}/approve")
        page = admin.get(f"/events/{self.event}/results").get_data(as_text=True)
        self.assertIn("Mary Member", page)
        self.assertIn("91", page)

    def test_other_clubs_admin_cannot_approve(self):
        with self.app.app_context():
            results.create_result(self.event, self.member, {"score": 80, "target": "x"}, "pending")
            result_id = results.list_pending(self.shooting)[0]["id"]
        other = self.login("bob@x.test", "Admin1234")
        self.assertEqual(self.post(other, f"/results/{result_id}/approve").status_code, 404)


class UploadTests(AppTestCase):
    def _upload(self, name="photo.png", content=b"\x89PNG fake image"):
        import io
        admin = self.login("alice@x.test", "Admin1234")
        data = {"full_name": "Mary Member", "email": "mary@x.test", "join_date": "2024-03-10",
                "membership_type": "Standard", "status": "active",
                "photo": (io.BytesIO(content), name)}
        response = self.post(admin, f"/members/{self.member}/edit", data, content_type="multipart/form-data")
        return admin, response

    def test_photo_is_stored_and_served_only_to_authorised_people(self):
        admin, response = self._upload()
        self.assertEqual(response.status_code, 302)
        url = f"/files/{self.member}/photo"
        self.assertEqual(admin.get(url).status_code, 200)                                    # the club admin
        self.assertEqual(self.login("mary@x.test", "Member1234").get(url).status_code, 200)  # the member
        self.assertEqual(self.login("mick@x.test", "Member1234").get(url).status_code, 403)  # another member
        self.assertEqual(self.login("bob@x.test", "Admin1234").get(url).status_code, 404)    # another club
        self.assertEqual(self.client.get(url).status_code, 302)                              # not logged in

    def test_wrong_file_type_is_refused(self):
        _, response = self._upload("virus.exe")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Allowed file types", response.get_data(as_text=True))


class RenewalTests(unittest.TestCase):
    def test_expiry_is_next_anniversary(self):
        join = date(2024, 3, 10)
        self.assertEqual(users.membership_expiry(join, date(2024, 3, 10)), date(2025, 3, 10))
        self.assertEqual(users.membership_expiry(join, date(2025, 3, 10)), date(2025, 3, 10))
        self.assertEqual(users.membership_expiry(join, date(2025, 3, 11)), date(2026, 3, 10))
        self.assertEqual(users.membership_expiry(date(2020, 2, 29), date(2023, 1, 1)), date(2023, 2, 28))


if __name__ == "__main__":
    unittest.main()
