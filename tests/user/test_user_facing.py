#!/usr/bin/env python
# -*- coding: utf-8 -*-

from CTFd.models import Teams, Solves, WrongKeys
from CTFd.utils import get_config, set_config
from CTFd import utils
from tests.helpers import *
from freezegun import freeze_time
from mock import patch
import json


def test_index():
    """Does the index page return a 200 by default"""
    app = create_ctfd()
    with app.app_context():
        with app.test_client() as client:
            r = client.get('/')
            assert r.status_code == 200
    destroy_ctfd(app)


def test_not_found():
    """Should return a 404 for pages that are not found"""
    app = create_ctfd()
    with app.app_context():
        with app.test_client() as client:
            r = client.get('/this-should-404')
            assert r.status_code == 404
            r = client.post('/this-should-404')
            assert r.status_code == 404
    destroy_ctfd(app)


def test_page():
    """Test that users can access pages that are created in the database"""
    app = create_ctfd()
    with app.app_context():

        gen_page(app.db, title="Title", route="this-is-a-route", html="This is some HTML")

        with app.test_client() as client:
            r = client.get('/this-is-a-route')
            assert r.status_code == 200
    destroy_ctfd(app)


def test_draft_pages():
    """Test that draft pages can't be seen"""
    app = create_ctfd()
    with app.app_context():
        gen_page(app.db, title="Title", route="this-is-a-route", html="This is some HTML", draft=True)

        with app.test_client() as client:
            r = client.get('/this-is-a-route')
            assert r.status_code == 404

        register_user(app)
        client = login_as_user(app)
        r = client.get('/this-is-a-route')
        assert r.status_code == 404
    destroy_ctfd(app)


def test_page_requiring_auth():
    """Test that pages properly require authentication"""
    app = create_ctfd()
    with app.app_context():
        gen_page(app.db, title="Title", route="this-is-a-route", html="This is some HTML", auth_required=True)

        with app.test_client() as client:
            r = client.get('/this-is-a-route')
            assert r.status_code == 302
            assert r.location == 'http://localhost/login?next=%2Fthis-is-a-route'

        register_user(app)
        client = login_as_user(app)
        r = client.get('/this-is-a-route')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_register_user():
    """Can a user be registered"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        team_count = app.db.session.query(app.db.func.count(Teams.id)).first()[0]
        assert team_count == 2  # There's the admin user and the created user
    destroy_ctfd(app)


def test_register_unicode_user():
    """Can a user with a unicode name be registered"""
    app = create_ctfd()
    with app.app_context():
        register_user(app, name="你好")
        team_count = app.db.session.query(app.db.func.count(Teams.id)).first()[0]
        assert team_count == 2  # There's the admin user and the created user
    destroy_ctfd(app)


def test_register_email_as_team_name():
    """A user shouldn't be able to use an email address as a team name"""
    app = create_ctfd()
    with app.app_context():
        register_user(app, name="user@hanyang.ac.kr", email="user@hanyang.ac.kr", password="password")
        team_count = app.db.session.query(app.db.func.count(Teams.id)).first()[0]
        assert team_count == 1  # There's only the admin user
    destroy_ctfd(app)


def test_register_duplicate_teamname():
    """A user shouldn't be able to use an already registered team name"""
    app = create_ctfd()
    with app.app_context():
        register_user(app, name="user1", email="user1@hanyang.ac.kr", password="password")
        register_user(app, name="user1", email="user2@hanyang.ac.kr", password="password")
        team_count = app.db.session.query(app.db.func.count(Teams.id)).first()[0]
        assert team_count == 2  # There's the admin user and the first created user
    destroy_ctfd(app)


def test_register_duplicate_email():
    """A user shouldn't be able to use an already registered email address"""
    app = create_ctfd()
    with app.app_context():
        register_user(app, name="user1", email="user1@hanyang.ac.kr", password="password")
        register_user(app, name="user2", email="user1@hanyang.ac.kr", password="password")
        team_count = app.db.session.query(app.db.func.count(Teams.id)).first()[0]
        assert team_count == 2  # There's the admin user and the first created user
    destroy_ctfd(app)


def test_user_bad_login():
    """A user should not be able to login with an incorrect password"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app, name="user", password="wrong_password")
        r = client.get('/profile')
        assert r.location.startswith("http://localhost/login")  # We got redirected to login
    destroy_ctfd(app)


def test_user_login():
    """Can a registered user can login"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/profile')
        assert r.location != "http://localhost/login"  # We didn't get redirected to login
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_login_with_email():
    """Can a registered user can login with an email address instead of a team name"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app, name="user@hanyang.ac.kr", password="password")
        r = client.get('/profile')
        assert r.location != "http://localhost/login"  # We didn't get redirected to login
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_isnt_admin():
    """A registered user cannot access admin pages"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        for page in ['pages', 'teams', 'scoreboard', 'chals', 'statistics', 'config']:
            r = client.get('/admin/{}'.format(page))
            assert r.location.startswith("http://localhost/login?next=")
            assert r.status_code == 302
    destroy_ctfd(app)


def test_user_get_teams():
    """Can a registered user load /teams"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/teams')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_scoreboard():
    """Can a registered user load /scoreboard"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/scoreboard')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_scores():
    """Can a registered user load /scores"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/scores')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_topteams():
    """Can a registered user load /top/10"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/top/10')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_solves_per_chal():
    """Can a registered user load /chals/solves"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/chals/solves')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_private_solves():
    """Can a registered user load /solves"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/solves')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_public_solves():
    """Can a registered user load /solves/2"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/solves/2')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_another_public_solves():
    """Can a registered user load public solves page of another user"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/solves/1')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_private_fails():
    """Can a registered user load /fails"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/solves')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_public_fails():
    """Can a registered user load /fails/2"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/fails/2')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_another_public_fails():
    """Can a registered user load public fails page of another user"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/fails/1')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_public_team_page():
    """Can a registered user load their public profile (/team/2)"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/team/2')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_another_public_team_page():
    """Can a registered user load the public profile of another user (/team/1)"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/team/1')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_private_team_page():
    """Can a registered user load their private team page (/team)"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/team')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_get_profile():
    """Can a registered user load their private profile (/profile)"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/profile')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_set_profile():
    """Can a registered user set their private profile (/profile)"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        r = client.get('/profile')
        with client.session_transaction() as sess:
            data = {
                'name': 'user',
                'email': 'user@hanyang.ac.kr',
                'confirm': '',
                'password': '',
                'affiliation': 'affiliation_test',
                'website': 'https://ctfd.io',
                'country': 'United States of America',
                'nonce': sess.get('nonce')
            }

        r = client.post('/profile', data=data)
        assert r.status_code == 302

        user = Teams.query.filter_by(id=2).first()
        assert user.affiliation == 'affiliation_test'
        assert user.website == 'https://ctfd.io'
        assert user.country == 'United States of America'
    destroy_ctfd(app)


def test_user_get_logout():
    """Can a registered user load /logout"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = login_as_user(app)
        client.get('/logout', follow_redirects=True)
        r = client.get('/challenges')
        assert r.location == "http://localhost/login?next=%2Fchallenges"
        assert r.status_code == 302
    destroy_ctfd(app)


def test_user_get_reset_password():
    """Can an unregistered user load /reset_password"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        client = app.test_client()
        r = client.get('/reset_password')
        assert r.status_code == 200
    destroy_ctfd(app)


def test_user_score_is_correct():
    '''Test that a user's score is correct'''
    app = create_ctfd()
    with app.app_context():
        # create user1
        register_user(app, name="user1", email="user1@hanyang.ac.kr")

        # create challenge
        chal = gen_challenge(app.db, value=100)
        flag = gen_flag(app.db, chal=chal.id, flag='flag')
        chal_id = chal.id

        # create a solve for the challenge for user1. (the id is 2 because of the admin)
        gen_solve(app.db, 2, chal_id)
        user1 = Teams.query.filter_by(id=2).first()

        # assert that user1's score is 100
        assert user1.score() == 100
        assert user1.place() == '1st'

        # create user2
        register_user(app, name="user2", email="user2@hanyang.ac.kr")

        # user2 solves the challenge
        gen_solve(app.db, 3, chal_id)

        # assert that user2's score is 100 but is in 2nd place
        user2 = Teams.query.filter_by(id=3).first()
        assert user2.score() == 100
        assert user2.place() == '2nd'

        # create an award for user2
        gen_award(app.db, 3, value=5)

        # assert that user2's score is now 105 and is in 1st place
        assert user2.score() == 105
        assert user2.place() == '1st'
    destroy_ctfd(app)


def test_pages_routing_and_rendering():
    """Test that pages are routing and rendering"""
    app = create_ctfd()
    with app.app_context():
        html = '''##The quick brown fox jumped over the lazy dog'''
        route = 'test'
        title = 'Test'
        page = gen_page(app.db, title, route, html)

        with app.test_client() as client:
            r = client.get('/test')
            output = r.get_data(as_text=True)
            assert "<h2>The quick brown fox jumped over the lazy dog</h2>" in output
    destroy_ctfd(app)


def test_themes_handler():
    """Test that the themes handler is working properly"""
    app = create_ctfd()
    with app.app_context():
        with app.test_client() as client:
            r = client.get('/themes/core/static/css/style.css')
            assert r.status_code == 200
            r = client.get('/themes/core/static/css/404_NOT_FOUND')
            assert r.status_code == 404
            r = client.get('/themes/core/static/%2e%2e/%2e%2e/%2e%2e/utils.py')
            assert r.status_code == 404
            r = client.get('/themes/core/static/%2e%2e%2f%2e%2e%2f%2e%2e%2futils.py')
            assert r.status_code == 404
            r = client.get('/themes/core/static/..%2f..%2f..%2futils.py')
            assert r.status_code == 404
            r = client.get('/themes/core/static/../../../utils.py')
            assert r.status_code == 404
    destroy_ctfd(app)


def test_ctfd_setup_redirect():
    """Test that a fresh CTFd instance redirects to /setup"""
    app = create_ctfd(setup=False)
    with app.app_context():
        with app.test_client() as client:
            r = client.get('/teams')
            assert r.status_code == 302
            assert r.location == "http://localhost/setup"

            # Files in /themes load properly
            r = client.get('/themes/core/static/css/style.css')
            assert r.status_code == 200
    destroy_ctfd(app)


def test_user_cannot_unlock_hint():
    """Test that a user can't unlock a hint if they don't have enough points"""
    app = create_ctfd()
    with app.app_context():
        with app.test_client() as client:
            register_user(app, name="user1", email="user1@hanyang.ac.kr")

            chal = gen_challenge(app.db, value=100)
            chal_id = chal.id

            flag = gen_flag(app.db, chal=chal.id, flag='flag')

            hint = gen_hint(db, chal_id, cost=10)
            hint_id = hint.id

            client = login_as_user(app, name="user1", password="password")

            with client.session_transaction() as sess:
                data = {
                    "nonce": sess.get('nonce')
                }
                r = client.post('/hints/{}'.format(hint_id), data=data)
                resp = json.loads(r.data.decode('utf8'))
                assert resp.get('errors') == 'Not enough points'
    destroy_ctfd(app)


def test_user_can_unlock_hint():
    """Test that a user can unlock a hint if they have enough points"""
    app = create_ctfd()
    with app.app_context():
        with app.test_client() as client:
            register_user(app, name="user1", email="user1@hanyang.ac.kr")

            chal = gen_challenge(app.db, value=100)
            chal_id = chal.id

            flag = gen_flag(app.db, chal=chal.id, flag='flag')

            hint = gen_hint(app.db, chal_id, cost=10)
            hint_id = hint.id

            award = gen_award(app.db, teamid=2, value=15)

            client = login_as_user(app, name="user1", password="password")

            with client.session_transaction() as sess:
                data = {
                    "nonce": sess.get('nonce')
                }
                r = client.post('/hints/{}'.format(hint_id), data=data)
                resp = json.loads(r.data.decode('utf8'))
                assert resp.get('errors') is None
                assert resp.get('hint')
                assert resp.get('chal') == chal_id
    destroy_ctfd(app)


def test_workshop_mode():
    """Test that workshop mode hides the appropriate data"""
    app = create_ctfd()
    with app.app_context():
        # Set CTFd to only allow confirmed users and send emails
        set_config('workshop_mode', True)

        register_user(app)

        chal = gen_challenge(app.db, value=100)
        solve = gen_solve(app.db, teamid=2, chalid=1)

        client = login_as_user(app, name="user", password="password")
        r = client.get('/scoreboard')
        output = r.get_data(as_text=True)
        assert "Scores are currently hidden" in output

        r = client.get('/scoreboard')
        output = r.get_data(as_text=True)
        assert "Scores are currently hidden" in output

        r = client.get('/scores')
        received = r.get_data(as_text=True)
        saved = '''{
          "standings": []
        }
        '''
        assert json.loads(saved) == json.loads(received)

        r = client.get('/teams')
        assert r.status_code == 404

        r = client.get('/teams/1')
        assert r.status_code == 404

        r = client.get('/teams/2')
        assert r.status_code == 404

        r = client.get('/chals/solves')
        output = r.get_data(as_text=True)
        saved = json.loads('''{
          "1": -1
        }
        ''')
        received = json.loads(output)
        assert saved == received

        r = client.get('/team')
        output = r.get_data(as_text=True)
        assert "1st <small>place</small>" not in output

    destroy_ctfd(app)
