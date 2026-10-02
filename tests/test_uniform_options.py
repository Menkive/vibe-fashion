import unittest

from app.services.uniform_options import (
    DEFAULT_OPTION_CONFIG,
    build_uniform_custom_options,
    customization_identity,
    is_customizable_product,
    parse_custom_options,
)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def order(self, *_args):
        return self

    def execute(self):
        rows = [row for row in self.rows if all(row.get(key) == value for key, value in self.filters.items())]
        return FakeResponse(rows)


class FakeDatabase:
    def __init__(self, players=None):
        self.tables = {
            'product_custom_options': DEFAULT_OPTION_CONFIG,
            'players': players or [],
        }

    def table(self, name):
        return FakeQuery(self.tables[name])


class UniformOptionsTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDatabase([
            {'id': 'player-1', 'name': '선수', 'number': 7, 'active': True, 'additional_price': 0},
        ])

    def test_only_explicit_jersey_types_are_customizable(self):
        self.assertTrue(is_customizable_product({'product_type': 'jersey'}))
        self.assertTrue(is_customizable_product({'product_type': 'kids_jersey'}))
        self.assertFalse(is_customizable_product({'product_type': 'standard'}))
        self.assertFalse(is_customizable_product({'category': 'authentic', 'name': '트레이닝 탑'}))

    def test_custom_options_parser_accepts_objects_and_rejects_invalid_values(self):
        self.assertEqual(parse_custom_options('{"patch": "official"}'), {'patch': 'official'})
        self.assertEqual(parse_custom_options({'patch': 'official'}), {'patch': 'official'})
        self.assertIsNone(parse_custom_options('{invalid json'))
        self.assertIsNone(parse_custom_options('[]'))

    def test_adult_player_options_use_server_configured_prices(self):
        snapshot, error = build_uniform_custom_options(
            self.db,
            {'product_type': 'jersey'},
            {
                'patch': 'official',
                'patch_price': 0,
                'marking': 'player',
                'player_id': 'player-1',
                'marking_price': 0,
                'embroidery': 'add',
                'embroidery_text': 'SEUNGHUN',
                'total_additional_price': 0,
            },
        )

        self.assertIsNone(error)
        self.assertEqual(snapshot['total_additional_price'], 30000)
        self.assertEqual(snapshot['marking']['player_number'], 7)

    def test_custom_name_number_and_embroidery_are_bounded(self):
        snapshot, error = build_uniform_custom_options(
            self.db,
            {'product_type': 'kids_jersey'},
            {'patch': 'none', 'marking': 'custom', 'custom_name': 'KIM', 'custom_number': '99', 'embroidery': 'add', 'embroidery_text': 'KIDS'},
        )

        self.assertIsNone(error)
        self.assertEqual(snapshot['total_additional_price'], 28000)
        invalid_snapshot, invalid_error = build_uniform_custom_options(
            self.db,
            {'product_type': 'kids_jersey'},
            {'marking': 'custom', 'custom_name': 'KIM', 'custom_number': '100'},
        )
        self.assertIsNone(invalid_snapshot)
        self.assertIsNotNone(invalid_error)

    def test_unknown_player_is_rejected(self):
        snapshot, error = build_uniform_custom_options(
            self.db,
            {'product_type': 'jersey'},
            {'marking': 'player', 'player_id': 'not-on-roster'},
        )

        self.assertIsNone(snapshot)
        self.assertIsNotNone(error)

    def test_cart_identity_ignores_price_and_display_label(self):
        first = {
            'patch': {'value': 'official', 'label': 'Official patch', 'price': 5000},
            'marking': {'type': 'player', 'player_id': 'player-1', 'label': '7 선수', 'price': 15000},
            'embroidery': {'value': 'none', 'label': 'No embroidery', 'price': 0},
        }
        repriced = {
            'patch': {'value': 'official', 'label': '공식 패치', 'price': 6000},
            'marking': {'type': 'player', 'player_id': 'player-1', 'label': '7 선수', 'price': 18000},
            'embroidery': {'value': 'none', 'label': '자수 없음', 'price': 0},
        }
        another_player = {
            **repriced,
            'marking': {'type': 'player', 'player_id': 'player-2', 'label': '8 선수', 'price': 18000},
        }

        self.assertEqual(customization_identity(first), customization_identity(repriced))
        self.assertNotEqual(customization_identity(first), customization_identity(another_player))


if __name__ == '__main__':
    unittest.main()