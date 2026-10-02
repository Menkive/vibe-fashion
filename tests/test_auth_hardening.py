import re
import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch

from app import app, create_app
from app.routes import auth as auth_routes
from app.routes import admin as admin_routes
from app.routes import main as main_routes


class FakeQuery:
    def __init__(self, row=None):
        self.row = row
        self.inserted = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def upsert(self, row):
        self.inserted = row
        return self

    def execute(self):
        return SimpleNamespace(data=[self.row] if self.row else [])


class FakeDatabase:
    def __init__(self, role='customer'):
        self.role = role

    def table(self, _name):
        return FakeQuery({'role': self.role})


class FakeAuth:
    def __init__(self, user):
        self.user = user
        self.sign_in_calls = 0

    def sign_in_with_password(self, _credentials):
        self.sign_in_calls += 1
        return SimpleNamespace(
            user=self.user,
            session=SimpleNamespace(access_token='test-access-token', refresh_token='test-refresh-token'),
        )

    def sign_up(self, _credentials):
        return SimpleNamespace(
            user=self.user,
            session=None,
        )

    def sign_out(self):
        return None


class FakeSupabase:
    def __init__(self, user):
        self.auth = FakeAuth(user)


class AuthHardeningTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def csrf_token(self, path='/login'):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(rb"X-CSRF-Token': \"([^\"]+)\"", response.data)
        if not match:
            match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match, 'CSRF 토큰을 렌더링해야 합니다.')
        return match.group(1).decode()

    def test_login_requires_csrf_token(self):
        user = SimpleNamespace(
            id='user-1', email='user@example.com', email_confirmed_at='2026-10-01T00:00:00Z',
            user_metadata={'full_name': '사용자'},
        )
        supabase = FakeSupabase(user)

        with patch.object(main_routes, 'get_supabase_client', return_value=supabase):
            response = self.client.post('/login', json={'email': user.email, 'password': 'password'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(supabase.auth.sign_in_calls, 0)

    def test_unconfirmed_email_cannot_create_login_session(self):
        user = SimpleNamespace(
            id='user-2', email='user@example.com', email_confirmed_at=None, confirmed_at=None,
            user_metadata={'full_name': '사용자'},
        )
        supabase = FakeSupabase(user)
        token = self.csrf_token()

        with patch.object(main_routes, 'get_supabase_client', return_value=supabase):
            response = self.client.post(
                '/login',
                json={'email': user.email, 'password': 'password'},
                headers={'X-CSRF-Token': token},
            )

        self.assertEqual(response.status_code, 403)
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)
            self.assertNotIn('user', session)

    def test_unconfirmed_signup_redirects_to_email_confirmation_instructions(self):
        user = SimpleNamespace(
            id='user-signup', email='new@example.com', email_confirmed_at=None,
            confirmed_at=None, user_metadata={'full_name': '신규 회원'},
        )
        supabase = FakeSupabase(user)
        token = self.csrf_token('/signup')

        with patch.object(main_routes, 'get_supabase_client', return_value=supabase), patch.object(
            main_routes, 'get_supabase_admin_client', return_value=FakeDatabase()
        ):
            response = self.client.post(
                '/signup',
                json={
                    'name': '신규 회원', 'email': user.email, 'password': 'password',
                    'password_confirm': 'password', 'terms': True, 'privacy': True,
                },
                headers={'X-CSRF-Token': token},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('/auth/signup-complete', response.json['redirect_url'])
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)

    def test_auth_login_alias_uses_common_session_shape(self):
        user = SimpleNamespace(
            id='user-auth-alias', email='user@example.com', email_confirmed_at='2026-10-01T00:00:00Z',
            user_metadata={'full_name': '사용자'},
        )
        supabase = FakeSupabase(user)
        token = self.csrf_token('/auth/login')

        with patch.object(auth_routes, 'get_supabase_client', return_value=supabase), patch.object(
            auth_routes, 'get_profile_role', return_value='customer'
        ):
            response = self.client.post(
                '/auth/login',
                data={'email': user.email, 'password': 'password', 'csrf_token': token},
            )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session['user_id'], 'user-auth-alias')
            self.assertEqual(session['user']['role'], 'customer')
            self.assertNotIn('access_token', session)

    def test_logout_requires_csrf_and_clears_session(self):
        token = self.csrf_token()
        with self.client.session_transaction() as session:
            session['user_id'] = 'user-logout'
            session['user'] = {'id': 'user-logout', 'role': 'customer'}

        with patch.object(main_routes, 'get_supabase_client', return_value=None):
            rejected = self.client.post('/logout')
            accepted = self.client.post('/logout', headers={'X-CSRF-Token': token})

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(accepted.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)
            self.assertNotIn('user', session)

    def test_confirmed_login_uses_profiles_role_and_common_session_shape(self):
        user = SimpleNamespace(
            id='user-3', email='user@example.com', email_confirmed_at='2026-10-01T00:00:00Z',
            user_metadata={'full_name': '사용자', 'role': 'admin'},
        )
        supabase = FakeSupabase(user)
        token = self.csrf_token()

        with patch.object(main_routes, 'get_supabase_client', return_value=supabase), patch.object(
            main_routes, 'get_supabase_admin_client', return_value=FakeDatabase('customer')
        ):
            response = self.client.post(
                '/login',
                json={'email': user.email, 'password': 'password', 'remember': True},
                headers={'X-CSRF-Token': token},
            )

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            self.assertEqual(session['user_id'], 'user-3')
            self.assertEqual(session['user']['role'], 'customer')
            self.assertTrue(session.permanent)
            self.assertNotIn('access_token', session)
            self.assertNotIn('refresh_token', session)

    def test_admin_role_in_session_is_not_trusted_after_demotion(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 'admin-user'
            session['user'] = {'id': 'admin-user', 'role': 'admin'}

        with patch.object(admin_routes, 'get_db', return_value=FakeDatabase('customer')):
            response = self.client.get('/admin/sales')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/')
        with self.client.session_transaction() as session:
            self.assertEqual(session['user']['role'], 'customer')

    def test_cookie_security_defaults_are_explicit(self):
        self.assertTrue(app.config['SESSION_COOKIE_HTTPONLY'])
        self.assertEqual(app.config['SESSION_COOKIE_SAMESITE'], 'Lax')

        with patch.dict(os.environ, {'APP_ENV': 'production', 'SECRET_KEY': 'test-production-secret'}):
            production_app = create_app()
        self.assertTrue(production_app.config['SESSION_COOKIE_SECURE'])


if __name__ == '__main__':
    unittest.main()