# app/routes/main.py - 양산시민축구단 공식 온라인 스토어 라우트
import os
import re
import sys
import logging
from flask import Blueprint, render_template, request, jsonify, abort, session, redirect, url_for
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
    """상품 ID로 단일 상품 조회 (인기상품 6종 및 전체 상품 지원)"""
    featured = get_featured_products()
    for fp in featured:
        if str(fp["id"]) == str(product_id):
            return {
                "id": fp["id"],
                "name": fp["name"],
                "slug": f"yangsan-uniform-{fp['id']}",
                "category": fp["category"],
                "price": fp["price_num"],
                "original_price": None,
                "description": fp["description"],
                "image_url": fp["image_url"],
                "thumbnail_url": fp["thumbnail_url"],
                "stock": fp["stock"],
                "sizes": ["S", "M", "L", "XL", "XXL"],
                "badge": fp["badge"],
                "is_featured": True
            }
    products = fetch_all_products()
    for p in products:
        if str(p["id"]) == str(product_id):
            return p
    return None


def get_featured_products():
    """
    메인 페이지 인기상품(BEST SELLERS) 6개 상품 목록을 반환합니다.
    - 양산FC 유니폼 컬렉션 6종 구성
    - 이미지: static/images/...png
    """
    uniform_products = [
        {
            "id": 1,
            "name": "양산FC 홈 유니폼",
            "category": "푸른색",
            "price": "129,000원",
            "price_num": 129000,
            "original_price": None,
            "image_url": "/static/images/home-uniform.png",
            "thumbnail_url": "/static/images/home-uniform.png",
            "description": "양산의 푸른 투혼을 담은 시그니처 로열 블루 홈 경기용 유니폼입니다.",
            "badge": "BEST",
            "stock": 50
        },
        {
            "id": 2,
            "name": "양산FC 어웨이 유니폼",
            "category": "흰색",
            "price": "119,000원",
            "price_num": 119000,
            "original_price": None,
            "image_url": "/static/images/away-uniform.png",
            "thumbnail_url": "/static/images/away-uniform.png",
            "description": "세련된 화이트 톤과 깔끔한 배색이 돋보이는 원정 경기용 공식 저지입니다.",
            "badge": "NEW",
            "stock": 50
        },
        {
            "id": 3,
            "name": "양산FC 브라운 스페셜 유니폼",
            "category": "갈색",
            "price": "139,000원",
            "price_num": 139000,
            "original_price": None,
            "image_url": "/static/images/brown-uniform.png",
            "thumbnail_url": "/static/images/brown-uniform.png",
            "description": "고급스러운 브라운 컬러웨이에 정밀 그래픽 패턴을 더한 한정판 스페셜 에디션입니다.",
            "badge": "LIMITED",
            "stock": 30
        },
        {
            "id": 4,
            "name": "양산FC 블루 스트라이프 유니폼",
            "category": "푸른색 세로 줄무늬",
            "price": "135,000원",
            "price_num": 135000,
            "original_price": None,
            "image_url": "/static/images/stripe-uniform.png",
            "thumbnail_url": "/static/images/stripe-uniform.png",
            "description": "클래식한 버티컬 골드 & 블루 스트라이프로 전통과 자부심을 표현한 저지입니다.",
            "badge": "MD 추천",
            "stock": 45
        },
        {
            "id": 5,
            "name": "양산FC GK 레드 유니폼",
            "category": "붉은색",
            "price": "125,000원",
            "price_num": 125000,
            "original_price": None,
            "image_url": "/static/images/gk-red-uniform.png",
            "thumbnail_url": "/static/images/gk-red-uniform.png",
            "description": "강렬한 레드 컬러로 골문을 든든하게 지켜내는 수문장을 위한 골키퍼 유니폼입니다.",
            "badge": "GK",
            "stock": 35
        },
        {
            "id": 6,
            "name": "양산FC GK 그린 유니폼",
            "category": "녹색",
            "price": "125,000원",
            "price_num": 125000,
            "original_price": None,
            "image_url": "/static/images/gk-green-uniform.png",
            "thumbnail_url": "/static/images/gk-green-uniform.png",
            "description": "역동적인 그린 브러시 패턴과 최적의 활동성을 제공하는 골키퍼 유니폼입니다.",
            "badge": "GK",
            "stock": 35
        }
    ]
    return uniform_products


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


# ==============================================================================
# 회원 인증 라우트 (Supabase Auth 연동)
# ==============================================================================

@main_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """회원가입 페이지 및 회원가입 처리"""
    if request.method == 'GET':
        if session.get('user'):
            return redirect(url_for('main.index'))
        return render_template('signup.html')

    # POST 처리
    data = request.get_json(silent=True) or request.form
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or ''
    phone = (data.get('phone') or '').strip()
    terms = data.get('terms')
    privacy = data.get('privacy')

    # 유효성 검사
    if not name:
        return jsonify({"success": False, "message": "이름을 입력해 주세요."}), 400

    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not email or not re.match(email_regex, email):
        return jsonify({"success": False, "message": "올바른 이메일 주소를 입력해 주세요."}), 400

    if not password or len(password) < 6:
        return jsonify({"success": False, "message": "비밀번호는 최소 6자 이상이어야 합니다."}), 400

    if password != password_confirm:
        return jsonify({"success": False, "message": "비밀번호가 일치하지 않습니다."}), 400

    if not terms or not privacy:
        return jsonify({"success": False, "message": "이용약관 및 개인정보 처리방침에 모두 동의해야 합니다."}), 400

    supabase = get_supabase_client()
    if not supabase:
        return jsonify({"success": False, "message": "인증 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."}), 503

    try:
        # Supabase Auth signUp 호출
        auth_res = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": name,
                    "phone": phone
                }
            }
        })

        user = auth_res.user
        if not user:
            return jsonify({"success": False, "message": "회원가입에 실패했습니다. 다시 시도해 주세요."}), 400

        # 세션 정보 저장 (로그인 처리)
        session['user'] = {
            "id": str(user.id),
            "email": user.email,
            "name": name,
            "phone": phone
        }
        if auth_res.session:
            session['access_token'] = auth_res.session.access_token

        return jsonify({
            "success": True,
            "message": f"{name}님, 양산시민축구단 공식 스토어 회원이 되신 것을 환영합니다!"
        })

    except Exception as e:
        logger.error(f"회원가입 오류: {e}")
        err_msg = str(e)
        if "User already registered" in err_msg or "already exists" in err_msg:
            return jsonify({"success": False, "message": "이미 가입된 이메일 주소입니다. 로그인해 주세요."}), 400
        return jsonify({"success": False, "message": f"회원가입 처리 중 오류가 발생했습니다: {err_msg}"}), 400


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인 페이지 및 로그인 처리"""
    if request.method == 'GET':
        if session.get('user'):
            return redirect(url_for('main.index'))
        return render_template('login.html')

    # POST 처리
    data = request.get_json(silent=True) or request.form
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    remember = data.get('remember')

    if not email or not password:
        return jsonify({"success": False, "message": "이메일과 비밀번호를 모두 입력해 주세요."}), 400

    supabase = get_supabase_client()
    if not supabase:
        return jsonify({"success": False, "message": "인증 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."}), 503

    try:
        auth_res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        user = auth_res.user
        if not user:
            return jsonify({"success": False, "message": "이메일 또는 비밀번호가 일치하지 않습니다."}), 400

        user_metadata = user.user_metadata or {}
        user_name = user_metadata.get('full_name') or user_metadata.get('name') or email.split('@')[0]

        session['user'] = {
            "id": str(user.id),
            "email": user.email,
            "name": user_name,
            "phone": user_metadata.get('phone', '')
        }
        if auth_res.session:
            session['access_token'] = auth_res.session.access_token

        if remember:
            session.permanent = True

        return jsonify({
            "success": True,
            "message": f"{user_name}님, 환영합니다!"
        })

    except Exception as e:
        logger.error(f"로그인 오류: {e}")
        err_msg = str(e)
        if "Invalid login credentials" in err_msg:
            return jsonify({"success": False, "message": "이메일 또는 비밀번호가 올바르지 않습니다."}), 401
        return jsonify({"success": False, "message": "로그인에 실패했습니다. 입력 정보를 확인해 주세요."}), 400


@main_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """로그아웃 처리 (Supabase signOut 및 세션 삭제)"""
    try:
        supabase = get_supabase_client()
        if supabase:
            supabase.auth.sign_out()
    except Exception as e:
        logger.warning(f"Supabase signOut 예외: {e}")

    session.clear()
    return redirect(url_for('main.index'))


@main_bp.route('/mypage')
def mypage():
    """마이페이지 라우트 (로그인 필요)"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login', error='login_required'))
    return render_template('mypage.html')


