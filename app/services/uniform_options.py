"""유니폼 커스터마이징 옵션 조회와 서버 측 검증/가격 산정."""
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

CUSTOM_PRODUCT_TYPES = {'jersey', 'kids_jersey'}
DEFAULT_OPTION_CONFIG = [
    {'option_type': 'patch', 'option_value': 'none', 'option_name': '광고패치 없음', 'additional_price': 0, 'active': True, 'sort_order': 1},
    {'option_type': 'patch', 'option_value': 'official', 'option_name': '공식 광고패치 부착', 'additional_price': 5000, 'active': True, 'sort_order': 2},
    {'option_type': 'marking', 'option_value': 'none', 'option_name': '마킹 안 함', 'additional_price': 0, 'active': True, 'sort_order': 1},
    {'option_type': 'marking', 'option_value': 'player', 'option_name': '선수 마킹', 'additional_price': 15000, 'active': True, 'sort_order': 2},
    {'option_type': 'marking', 'option_value': 'custom', 'option_name': '직접 입력 마킹', 'additional_price': 18000, 'active': True, 'sort_order': 3},
    {'option_type': 'embroidery', 'option_value': 'none', 'option_name': '자수 없음', 'additional_price': 0, 'active': True, 'sort_order': 1},
    {'option_type': 'embroidery', 'option_value': 'add', 'option_name': '자수 추가', 'additional_price': 10000, 'active': True, 'sort_order': 2},
]


def parse_custom_options(value: Any) -> dict[str, Any] | None:
    """DB 또는 요청에서 받은 커스터마이징 옵션을 JSON 객체로 변환한다."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    return value if isinstance(value, dict) else None


def is_customizable_product(product: dict[str, Any]) -> bool:
    """명시적으로 지정된 상품 타입만 유니폼 커스터마이징을 허용한다."""
    return product.get('product_type') in CUSTOM_PRODUCT_TYPES


def get_uniform_option_data(db_client: Any) -> dict[str, Any]:
    """DB에 등록된 옵션 가격과 활성 선수 목록을 불러온다."""
    config = DEFAULT_OPTION_CONFIG
    players: list[dict[str, Any]] = []

    try:
        response = db_client.table('product_custom_options').select(
            'option_type, option_value, option_name, additional_price, active, sort_order'
        ).eq('active', True).order('sort_order').execute()
        if response.data:
            config = response.data
    except Exception as exc:
        logger.warning('유니폼 옵션 설정 조회 실패, 기본 가격을 사용합니다: %s', exc)

    try:
        response = db_client.table('players').select(
            'id, name, number, active, additional_price'
        ).eq('active', True).order('number').execute()
        players = response.data or []
    except Exception as exc:
        logger.warning('선수 명단 조회 실패: %s', exc)

    grouped = {'patch': [], 'marking': [], 'embroidery': []}
    for row in config:
        option_type = row.get('option_type')
        if option_type in grouped:
            grouped[option_type].append(row)

    return {'options': grouped, 'players': players}


def build_uniform_custom_options(
    db_client: Any,
    product: dict[str, Any],
    submitted: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """요청값을 DB 설정과 선수 명단으로 검증하고 신뢰 가능한 가격 스냅샷을 만든다."""
    if not is_customizable_product(product):
        return {}, None

    submitted = submitted or {}
    data = get_uniform_option_data(db_client)
    options = data['options']
    players = data['players']

    def choice(option_type: str, value: str) -> dict[str, Any] | None:
        return next((row for row in options[option_type] if row.get('option_value') == value), None)

    patch_value = str(submitted.get('patch', 'none'))
    marking_value = str(submitted.get('marking', 'none'))
    embroidery_value = str(submitted.get('embroidery', 'none'))
    patch = choice('patch', patch_value)
    marking = choice('marking', marking_value)
    embroidery = choice('embroidery', embroidery_value)
    if not patch or not marking or not embroidery:
        return None, '선택한 유니폼 옵션을 확인할 수 없습니다. 페이지를 새로고침해 주세요.'

    result: dict[str, Any] = {
        'patch': {'value': patch_value, 'label': patch['option_name'], 'price': int(patch['additional_price'])},
        'marking': {'type': marking_value, 'label': marking['option_name'], 'price': int(marking['additional_price'])},
        'embroidery': {'value': embroidery_value, 'label': embroidery['option_name'], 'price': int(embroidery['additional_price'])},
    }

    if marking_value == 'player':
        player_id = str(submitted.get('player_id') or '')
        player = next((row for row in players if str(row.get('id')) == player_id), None)
        if not player:
            return None, '마킹할 선수를 선택해주세요.'
        player_name = str(player.get('name') or '').strip()
        player_number = int(player.get('number'))
        player_surcharge = int(player.get('additional_price') or 0)
        result['marking'].update({
            'player_id': str(player['id']),
            'player_name': player_name,
            'player_number': player_number,
            'label': f"{player_number} {player_name}",
            'price': int(marking['additional_price']) + player_surcharge,
        })
    elif marking_value == 'custom':
        name = str(submitted.get('custom_name') or '').strip()
        number_text = str(submitted.get('custom_number') or '').strip()
        if not name or not number_text:
            return None, '마킹 이름과 등번호를 입력해주세요.'
        if not re.fullmatch(r'[A-Za-z가-힣 ]{1,20}', name):
            return None, '마킹 이름은 한글 또는 영문 1~20자로 입력해주세요.'
        if not re.fullmatch(r'\d{1,2}', number_text) or int(number_text) > 99:
            return None, '등번호는 0~99 사이 숫자로 입력해주세요.'
        result['marking'].update({'name': name, 'number': int(number_text), 'label': f'{int(number_text)} {name}'})

    embroidery_text = str(submitted.get('embroidery_text') or '').strip()
    if embroidery_value == 'add':
        if not embroidery_text:
            return None, '자수 문구를 입력해주세요.'
        if not re.fullmatch(r'[A-Za-z가-힣 ]{1,20}', embroidery_text):
            return None, '자수 문구는 한글 또는 영문 1~20자로 입력해주세요.'
        result['embroidery']['text'] = embroidery_text
    else:
        result['embroidery']['text'] = ''

    result['total_additional_price'] = sum(
        int(result[key]['price']) for key in ('patch', 'marking', 'embroidery')
    )
    return result, None


def customization_input_from_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """저장된 옵션 스냅샷에서 가격 재검증에 필요한 선택값만 추출한다."""
    snapshot = snapshot or {}
    marking = snapshot.get('marking') or {}
    embroidery = snapshot.get('embroidery') or {}
    return {
        'patch': (snapshot.get('patch') or {}).get('value', 'none'),
        'marking': marking.get('type', 'none'),
        'player_id': marking.get('player_id'),
        'custom_name': marking.get('name'),
        'custom_number': marking.get('number'),
        'embroidery': embroidery.get('value', 'none'),
        'embroidery_text': embroidery.get('text', ''),
    }


def customization_identity(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """장바구니 중복 판정에 가격/표시명 대신 고객이 선택한 값만 사용한다."""
    snapshot = snapshot or {}
    marking = snapshot.get('marking') or {}
    embroidery = snapshot.get('embroidery') or {}
    return {
        'patch': (snapshot.get('patch') or {}).get('value', 'none'),
        'marking': {
            'type': marking.get('type', 'none'),
            'player_id': marking.get('player_id', ''),
            'name': marking.get('name', ''),
            'number': marking.get('number', ''),
        },
        'embroidery': {
            'value': embroidery.get('value', 'none'),
            'text': embroidery.get('text', ''),
        },
    }


def format_custom_options(snapshot: dict[str, Any] | None) -> str:
    """옵션 스냅샷을 장바구니/주문에 표시할 짧은 설명으로 변환한다."""
    if not snapshot:
        return ''
    parts = []
    for key in ('patch', 'marking', 'embroidery'):
        option = snapshot.get(key) or {}
        label = option.get('label')
        if label and option.get('value', option.get('type')) not in {'none', None}:
            if key == 'embroidery' and option.get('text'):
                label = f"{label}: {option['text']}"
            parts.append(str(label))
    return ' / '.join(parts)