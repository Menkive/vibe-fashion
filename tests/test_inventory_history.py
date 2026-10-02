import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from app.routes import admin as admin_routes


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeDatabase:
    def __init__(self, tables=None, rpc_result=None):
        self.tables = tables or {}
        self.rpc_result = rpc_result or {}
        self.rpc_calls = []

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=self.rpc_result))


class InventoryHistoryTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['_csrf_token'] = 'test-csrf-token'
            session['user_id'] = 'admin-user'
            session['user'] = {'id': 'admin-user', 'role': 'admin'}

    def test_inventory_adjustment_requires_csrf(self):
        with patch.object(admin_routes, 'is_admin_user', return_value=True):
            response = self.client.post('/admin/inventory/adjust', data={
                'option_id': 'option-1',
                'mode': 'delta',
                'stock_value': '20',
            })

        self.assertEqual(response.status_code, 400)
        self.assertIn('보안 토큰', response.get_data(as_text=True))

    def test_manual_receipt_is_recorded_with_reason(self):
        db = FakeDatabase(rpc_result={
            'success': True,
            'previous_quantity': 8,
            'changed_quantity': 20,
            'new_quantity': 28,
            'product_name': '홈 유니폼',
            'color': 'BLUE',
            'size': 'L',
        })
        with patch.object(admin_routes, 'is_admin_user', return_value=True), patch.object(
            admin_routes, 'get_supabase_admin_client', return_value=db
        ):
            response = self.client.post('/admin/inventory/adjust', data={
                'csrf_token': 'test-csrf-token',
                'option_id': 'option-1',
                'mode': 'delta',
                'stock_value': '20',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(db.rpc_calls), 1)
        rpc_name, params = db.rpc_calls[0]
        self.assertEqual(rpc_name, 'adjust_product_option_stock')
        self.assertEqual(params['p_reason'], '관리자 입고')
        self.assertEqual(params['p_value'], 20)

    def test_inventory_page_renders_recent_stock_history(self):
        db = FakeDatabase(tables={
            'product_options': [{
                'id': 'option-1',
                'product_id': 'product-1',
                'color': 'BLUE',
                'size': 'L',
                'stock_quantity': 28,
                'products': {'name': '홈 유니폼', 'categories': {'name': '유니폼'}},
            }],
            'inventory_stock_history': [{
                'product_name': '홈 유니폼',
                'color': 'BLUE',
                'size': 'L',
                'previous_quantity': 8,
                'changed_quantity': 20,
                'new_quantity': 28,
                'reason': '관리자 입고',
                'order_number': None,
                'changed_at': '2026-10-02T10:00:00+00:00',
            }],
        })
        with patch.object(admin_routes, 'is_admin_user', return_value=True), patch.object(
            admin_routes, 'get_db', return_value=db
        ), patch.object(admin_routes, 'get_supabase_admin_client', return_value=db):
            response = self.client.get('/admin/inventory')

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('최근 재고 변경 이력', page)
        self.assertIn('관리자 입고', page)
        self.assertIn('홈 유니폼', page)
        self.assertIn('+20', page)


if __name__ == '__main__':
    unittest.main()