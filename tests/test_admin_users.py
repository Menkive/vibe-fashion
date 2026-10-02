import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from app.routes import admin as admin_routes


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.filters.append((column, set(values)))
        return self

    def execute(self):
        rows = self.rows
        for column, value in self.filters:
            if isinstance(value, set):
                rows = [row for row in rows if row.get(column) in value]
            else:
                rows = [row for row in rows if row.get(column) == value]
        return SimpleNamespace(data=rows)


class FakeDatabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


class AdminUsersTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = 'admin-user'
            session['user'] = {'id': 'admin-user', 'role': 'admin'}

    def _admin_request(self, database, path):
        with patch.object(admin_routes, 'is_admin_user', return_value=True), patch.object(
            admin_routes, 'get_db', return_value=database
        ):
            return self.client.get(path)

    def test_member_list_shows_required_fields_without_phone(self):
        db = FakeDatabase({
            'profiles': [{
                'id': 'member-1',
                'email': 'fan@example.com',
                'full_name': '양산 팬',
                'created_at': '2026-01-05T00:00:00+00:00',
                'phone_number': '010-1111-2222',
                'total_spent': 12000,
            }],
            'orders': [{
                'user_id': 'member-1',
                'final_amount': 12000,
                'status': 'paid',
            }],
        })

        response = self._admin_request(db, '/admin/users')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('fan@example.com', page)
        self.assertIn('양산 팬', page)
        self.assertIn('2026-01-05', page)
        self.assertIn('주문 보기', page)
        self.assertNotIn('010-1111-2222', page)

    def test_member_detail_shows_only_selected_member_orders(self):
        db = FakeDatabase({
            'profiles': [{
                'id': 'member-1',
                'email': 'fan@example.com',
                'full_name': '양산 팬',
                'created_at': '2026-01-05T00:00:00+00:00',
                'phone_number': '010-1111-2222',
                'shipping_address': 'private address',
            }],
            'orders': [{
                'id': 'order-1',
                'user_id': 'member-1',
                'order_number': 'VF-20260105-1234',
                'created_at': '2026-01-05T10:00:00+00:00',
                'status': 'paid',
                'final_amount': 12000,
            }],
            'order_items': [{
                'order_id': 'order-1',
                'product_name': '홈 유니폼',
                'option_info': 'BLUE / L',
                'quantity': 1,
                'subtotal': 12000,
            }],
        })

        response = self._admin_request(db, '/admin/users/member-1')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('VF-20260105-1234', page)
        self.assertIn('홈 유니폼', page)
        self.assertIn('BLUE / L', page)
        self.assertNotIn('010-1111-2222', page)
        self.assertNotIn('private address', page)

    def test_dashboard_popular_products_exclude_cancelled_orders(self):
        db = FakeDatabase({
            'orders': [
                {'id': 'order-1', 'status': 'paid', 'created_at': '2026-10-02T10:00:00+00:00', 'final_amount': 10000},
                {'id': 'order-2', 'status': 'cancelled', 'created_at': '2026-10-02T09:00:00+00:00', 'final_amount': 50000},
            ],
            'order_items': [
                {'order_id': 'order-1', 'product_name': '홈 유니폼', 'quantity': 2},
                {'order_id': 'order-2', 'product_name': '취소 상품', 'quantity': 9},
            ],
            'products': [],
            'product_options': [],
        })

        response = self._admin_request(db, '/admin/')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('판매 인기 상품', page)
        self.assertIn('홈 유니폼', page)
        self.assertNotIn('취소 상품', page)


if __name__ == '__main__':
    unittest.main()