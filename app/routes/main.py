# app/routes/main.py - 양산시민축구단 공식 온라인 스토어 라우트
import os
import sys
import logging
from flask import Blueprint, render_template, request, jsonify, abort
from dotenv import load_dotenv
from supabase import create_client, Client
from app.models import INITIAL_PRODUCTS, get_vote_candidates, cast_vote

logger = logging.getLogger(__name__)

# 'main'이라는 이름의 블루프린트 생성
main_bp = Blueprint('main', __name__)

def get_supabase_client() -> Client | None:
    """
    환경 변수(.env)에서 SUPABASE_URL과 SUPABASE_ANON_KEY를 읽어
    Supabase 클라이언트를 초기화하고 반환합니다.
    """
    load_dotenv()
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_ANON_KEY')

    if not url or not key:
        return None

    try:
        return create_client(url, key)
    except Exception as e:
        print(f"[Supabase Client Error] 클라이언트 생성 실패: {e}", file=sys.stderr)
        return None


def fetch_all_products():
    """
    Supabase products 테이블과 연결을 시도하고,
    미연결 시 또는 데이터 보충 시 INITIAL_PRODUCTS(8개 표준 구단 굿즈)를 제공합니다.
    """
    supabase = get_supabase_client()
    if not supabase:
        return INITIAL_PRODUCTS

    try:
        response = supabase.table('products').select('*').eq('is_active', True).execute()
        db_items = response.data
        if db_items and len(db_items) >= 4:
            merged = []
            for item in db_items:
                cat = item.get('category') or '기타'
                if '유니폼' in item.get('name', '') or cat == '유니폼':
                    sizes = ["S", "M", "L", "XL", "XXL"]
                elif cat in ['의류', '트레이닝']:
                    sizes = ["M", "L", "XL"]
                else:
                    sizes = ["Free"]

                try:
                    price = int(float(item.get('price', 0)))
                except (ValueError, TypeError):
                    price = 0

                orig_price = None
                if item.get('original_price'):
                    try:
                        orig_price = int(float(item.get('original_price')))
                    except (ValueError, TypeError):
                        orig_price = None

                merged.append({
                    "id": item.get('id'),
                    "name": item.get('name'),
                    "slug": item.get('slug', f"product-{item.get('id')}"),
                    "category": cat,
                    "price": price,
                    "original_price": orig_price,
                    "description": item.get('description', ''),
                    "image_url": item.get('thumbnail_url') or 'https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=800&q=80',
                    "thumbnail_url": item.get('thumbnail_url') or 'https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=800&q=80',
                    "stock": item.get('stock', 50),
                    "sizes": sizes,
                    "badge": item.get('badge') or 'BEST',
                    "is_featured": item.get('is_featured', True),
                    "is_new": True,
                    "sales_count": 100
                })

            if len(merged) < 8:
                existing_names = {m["name"] for m in merged}
                for init_item in INITIAL_PRODUCTS:
                    if init_item["name"] not in existing_names:
                        merged.append(init_item)
            return merged
        return INITIAL_PRODUCTS
    except Exception as e:
        print(f"[Supabase Query Notice] INITIAL_PRODUCTS 표준 카탈로그로 대체합니다: {e}", file=sys.stderr)
        return INITIAL_PRODUCTS


def get_product_by_id(product_id):
    """상품 ID로 단일 상품 조회"""
    products = fetch_all_products()
    for p in products:
        if str(p["id"]) == str(product_id):
            return p
    return None


def get_featured_products():
    """
    Supabase products 테이블에서 활성 상품을 최대 4개 조회합니다.
    - 실패 시 빈 리스트([])로 대체하여 앱이 중단되지 않도록 합니다.
    - 가격은 {:,}원 형태(예: '19,900원')로 포맷팅합니다.
    """
    supabase = get_supabase_client()
    if not supabase:
        print("[Supabase Warning] Supabase 클라이언트를 초기화할 수 없습니다. .env 설정을 확인하세요.", file=sys.stderr)
        return []

    try:
        # 우선 is_active=True 상품을 최대 4개 조회 (필요 시 is_featured가 있는 레코드 우선 정렬)
        response = (
            supabase.table('products')
            .select('*')
            .eq('is_active', True)
            .limit(4)
            .execute()
        )
        data = response.data

        formatted_products = []
        for item in data or []:
            raw_price = item.get('price')
            if raw_price is not None:
                try:
                    price_str = f"{int(float(raw_price)):,}원"
                except (ValueError, TypeError):
                    price_str = f"{raw_price}원"
            else:
                price_str = "0원"

            raw_orig_price = item.get('original_price')
            if raw_orig_price is not None:
                try:
                    orig_price_str = f"{int(float(raw_orig_price)):,}원"
                except (ValueError, TypeError):
                    orig_price_str = f"{raw_orig_price}원"
            else:
                orig_price_str = None

            thumbnail = item.get('thumbnail_url') or item.get('image_url') or 'https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=800&q=80'

            formatted_products.append({
                "id": item.get('id'),
                "name": item.get('name', '상품명 없음'),
                "price": price_str,
                "original_price": orig_price_str,
                "thumbnail_url": thumbnail,
                "image_url": thumbnail,
                "description": item.get('description', ''),
                "category": item.get('category', '공식 굿즈'),
                "badge": item.get('badge') or 'BEST',
                "stock": item.get('stock', 50)
            })

        return formatted_products

    except Exception as e:
        print(f"[Supabase Error] products 테이블 조회 중 에러 발생: {e}", file=sys.stderr)
        return []


@main_bp.route('/')
def index():
    """
    메인 페이지 라우트:
    Supabase products 테이블에서 is_active=true & is_featured=true 상품 최대 4개를 조회하여
    index.html에 products 변수로 전달합니다.
    """
    products = get_featured_products()
    return render_template('index.html', products=products)


@main_bp.route('/products')
def product_list():
    """전체 상품 목록 화면 (검색, 카테고리 필터, 정렬 기능)"""
    all_products = fetch_all_products()
    return render_template('product_list.html', products=all_products)


@main_bp.route('/products/<product_id>')
def product_detail(product_id):
    """
    상품 상세 페이지:
    대형 이미지, 상품명, 가격, 상세 설명, 사이즈/수량 선택, 장바구니 담기, 바로구매
    """
    product = get_product_by_id(product_id)
    if not product:
        abort(404)

    all_products = fetch_all_products()
    related_products = [p for p in all_products if str(p["id"]) != str(product_id)][:4]

    return render_template('product_detail.html', product=product, related_products=related_products)


@main_bp.route('/cart')
def cart():
    """장바구니 페이지: 상품 수량 변경, 삭제, 총 결제금액, localStorage 연동"""
    return render_template('cart.html')


@main_bp.route('/vote')
def vote_page():
    """2027 시즌 유니폼 디자인 팬 투표 페이지"""
    candidates = get_vote_candidates()
    total_votes = sum(c["votes"] for c in candidates)
    return render_template('vote.html', candidates=candidates, total_votes=total_votes)


@main_bp.route('/api/vote', methods=['POST'])
def api_vote():
    """팬 투표 참여 API (단일 선택, 실시간 결과 계산 반환)"""
    data = request.get_json(silent=True) or {}
    candidate_id = data.get('candidate_id')

    if not candidate_id:
        return jsonify({"success": False, "message": "투표할 디자인을 선택해주세요."}), 400

    result = cast_vote(candidate_id)
    if not result:
        return jsonify({"success": False, "message": "유효하지 않은 디자인 후보입니다."}), 404

    return jsonify(result)


@main_bp.route('/api/products')
def api_products():
    """JSON 상품 목록 API"""
    return jsonify(fetch_all_products())
