import datetime
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

    def eq(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeDatabase:
    def __init__(self, orders, order_items):
        self.tables = {'profiles': [{'role': 'admin'}], 'orders': orders, 'order_items': order_items}

    def table(self, name):
        return FakeQuery(self.tables[name])


class AdminSalesRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = 'admin-user'
            session['user'] = {'id': 'admin-user', 'role': 'admin'}

    def test_date_range_and_product_metrics_exclude_cancelled_orders(self):
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        start_date = yesterday.isoformat()
        end_date = today.isoformat()
        db = FakeDatabase(
            orders=[
                {'id': 'today', 'created_at': f'{end_date}T09:00:00+00:00', 'status': 'paid', 'final_amount': 12000},
                {'id': 'yesterday', 'created_at': f'{start_date}T09:00:00+00:00', 'status': 'pending', 'final_amount': 8000},
                {'id': 'cancelled', 'created_at': f'{end_date}T10:00:00+00:00', 'status': 'cancelled', 'final_amount': 50000},
                {'id': 'older', 'created_at': f'{start_date[:4]}-01-01T09:00:00+00:00', 'status': 'delivered', 'final_amount': 4000},
            ],
            order_items=[
                {'order_id': 'today', 'product_id': 'a', 'product_name': '홈 유니폼', 'quantity': 2, 'subtotal': 10000},
                {'order_id': 'yesterday', 'product_id': 'a', 'product_name': '홈 유니폼', 'quantity': 1, 'subtotal': 8000},
                {'order_id': 'today', 'product_id': 'b', 'product_name': '머플러', 'quantity': 1, 'subtotal': 2000},
                {'order_id': 'cancelled', 'product_id': 'c', 'product_name': '취소 상품', 'quantity': 8, 'subtotal': 50000},
                {'order_id': 'older', 'product_id': 'd', 'product_name': '이전 상품', 'quantity': 4, 'subtotal': 4000},
            ],
        )

        with patch.object(admin_routes, 'get_db', return_value=db):
            response = self.client.get(f'/admin/sales?start_date={start_date}&end_date={end_date}')

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('선택 기간 주문 건수', html)
        self.assertIn('20,000원', html)
        self.assertIn('홈 유니폼', html)
        self.assertIn('머플러', html)
        self.assertNotIn('취소 상품', html)
        self.assertNotIn('이전 상품', html)
        self.assertIn('4개', html)


if __name__ == '__main__':
    unittest.main()