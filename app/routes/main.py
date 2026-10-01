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


def get_supabase_admin_client() -> Client | None:
    """
    환경 변수에서 SUPABASE_SERVICE_ROLE_KEY(또는 SUPABASE_SERVICE_KEY)를 읽어
    관리자 권한의 Supabase 클라이언트를 초기화하고 반환합니다.
    (회원 탈퇴 등 Admin API 작업에 사용)
    """
    load_dotenv()
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')

    if not url or not service_key:
        return None

    try:
        return create_client(url, service_key)
    except Exception as e:
        print(f"[Supabase Admin Client Error] 관리자 클라이언트 생성 실패: {e}", file=sys.stderr)
        return None


def fetch_all_products():
    """
    Supabase products 테이블과 연결을 시도하고,
    양산시민축구단 공식 카탈로그를 안전하게 제공합니다.
    임시 샘플 상품(Unsplash 데모 등)은 필터링하고 공식 상품 중심으로 구성합니다.
    """
    supabase = get_supabase_client()
    if not supabase:
        return INITIAL_PRODUCTS

    try:
        response = supabase.table('products').select('*').eq('is_active', True).execute()
        db_items = response.data
        if db_items and len(db_items) >= 4:
            merged = []
            # 제외할 키워드 및 이미지 필터링
            excluded_names = ['크롭 티셔츠', '데님 팬츠', '코튼 자켓', '원피스', '스마트폰', '커피']
            for item in db_items:
                item_name = item.get('name', '')
                thumb = item.get('thumbnail_url', '') or ''
                # 샘플 의류나 picsum/unsplash 임시 샘플 상품 제외
                if any(ex in item_name for ex in excluded_names) or 'picsum.photos' in thumb:
                    continue

                cat = item.get('category') or '기타'
                if '유니폼' in item_name or cat == '유니폼':
                    sizes = ["S", "M", "L", "XL", "XXL"]
                elif cat in ['의류', '패션/잡화']:
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
                    "name": item_name,
                    "slug": item.get('slug', f"product-{item.get('id')}"),
                    "category": cat,
                    "price": price,
                    "original_price": orig_price,
                    "description": item.get('description', ''),
                    "image_url": thumb or '/static/images/home-uniform.png',
                    "thumbnail_url": thumb or '/static/images/home-uniform.png',
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
    """상품 ID로 단일 상품 조회"""
    products = fetch_all_products()
    for p in products:
        if str(p["id"]) == str(product_id):
            return p
    return None


def get_featured_products():
    """
    메인 페이지 인기상품(BEST SELLERS) 목록을 반환합니다.
    - 양산시민축구단 공식 카탈로그 중 is_featured=True인 상품 6종 구성
    """
    products = fetch_all_products()
    featured = [p for p in products if p.get('is_featured')]
    return featured[:6] if featured else products[:6]


@main_bp.route('/')
def index():
    """
    메인 페이지 라우트:
    공식 카탈로그에서 is_featured=true 인기 상품 6개를 조회하여
    index.html에 products 변수로 전달합니다.
    """
    products = get_featured_products()
    return render_template('index.html', products=products)


@main_bp.route('/about')
def about():
    """양산시민축구단 및 공식 스토어 브랜드 소개 페이지"""
    return render_template('about.html')


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
    """팬 투표 참여 API (단일 선택, 회원/세션 기반 중복 투표 방지, 실시간 결과 계산 반환)"""
    data = request.get_json(silent=True) or {}
    candidate_id = data.get('candidate_id')

    if not candidate_id:
        return jsonify({"success": False, "message": "투표할 디자인을 선택해주세요."}), 400

    # 로그인 회원 또는 세션 기준 중복 투표 검증
    user = session.get('user')
    user_key = user.get('id') if isinstance(user, dict) and user.get('id') else session.get('user_id')
    
    # 세션 내 투표 기록 확인
    voted_candidates = session.get('voted_candidates', {})
    if user_key and user_key in voted_candidates:
        return jsonify({"success": False, "message": "이미 2027 시즌 유니폼 투표에 참여하셨습니다. (1인 1회 참여)"}), 400
    if session.get('has_voted'):
        return jsonify({"success": False, "message": "이미 투표에 참여하셨습니다. (1인 1회 참여)"}), 400

    result = cast_vote(candidate_id)
    if not result:
        return jsonify({"success": False, "message": "유효하지 않은 유니폼 후보입니다."}), 404

    # 투표 완료 상태 저장
    session['has_voted'] = True
    session['voted_candidate_id'] = candidate_id
    if user_key:
        if 'voted_candidates' not in session:
            session['voted_candidates'] = {}
        session['voted_candidates'][user_key] = candidate_id

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


@main_bp.route('/mypage', methods=['GET', 'POST'])
def mypage():
    """
    마이페이지 라우트 (로그인 필요):
    - profiles 테이블에서 로그인 사용자 정보 조회하여 내 정보 탭에 표시
    - POST 요청 시 내 정보(이름, 배송지, 전화번호) 수정 처리
    - Bootstrap 5 탭 구조 (내 정보 / 주문 내역 / 환불 내역)
    """
    user_info = session.get('user') or {}
    user_id = user_info.get('id') or session.get('user_id')
    user_email = user_info.get('email') or session.get('email')

    if not user_id:
        return redirect(url_for('main.login', error='login_required'))

    admin_client = get_supabase_admin_client()
    anon_client = get_supabase_client()
    db_client = admin_client or anon_client

    # POST: 내 정보 수정 처리
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        shipping_address = request.form.get('shipping_address', '').strip()

        update_data = {
            "updated_at": "now()"
        }
        if full_name:
            update_data["full_name"] = full_name
        if phone_number is not None:
            update_data["phone_number"] = phone_number
        if shipping_address is not None:
            update_data["shipping_address"] = shipping_address

        if db_client:
            try:
                db_client.table('profiles').update(update_data).eq('id', user_id).execute()
                # 세션 내 사용자 정보도 동기화
                if 'user' in session:
                    if full_name:
                        session['user']['name'] = full_name
                    if phone_number is not None:
                        session['user']['phone'] = phone_number
                    session.modified = True
            except Exception as e:
                logger.error(f"프로필 업데이트 오류: {e}")
                return redirect(url_for('main.mypage', error='update_failed'))

        return redirect(url_for('main.mypage', success='profile_updated'))

    # GET: profiles 테이블에서 사용자 최신 프로필 정보 조회
    profile_data = {}
    if db_client:
        try:
            res = db_client.table('profiles').select('*').eq('id', user_id).execute()
            if res.data and len(res.data) > 0:
                profile_data = res.data[0]
        except Exception as e:
            logger.warning(f"마이페이지 프로필 조회 오류: {e}")

    # DB에 아직 프로필이 없거나 일부 누락된 경우 세션 기본값으로 보완
    if not profile_data:
        profile_data = {
            "id": user_id,
            "email": user_email,
            "full_name": user_info.get('name') or (user_email.split('@')[0] if user_email else '회원'),
            "phone_number": user_info.get('phone') or '',
            "shipping_address": '',
            "avatar_url": user_info.get('avatar_url')
        }
    else:
        # 이메일 또는 이름이 비어있으면 세션 정보로 보완
        if not profile_data.get('email'):
            profile_data['email'] = user_email
        if not profile_data.get('full_name'):
            profile_data['full_name'] = user_info.get('name') or '회원'

    # 소셜 로그인 여부 확인 (이메일/비밀번호 가입 회원만 비밀번호 변경 가능)
    is_password_user = True
    provider = user_info.get('provider')
    if provider in ['kakao', 'naver', 'google', 'microsoft', 'oauth']:
        is_password_user = False
    elif isinstance(user_id, str) and (user_id.startswith('naver-') or user_id.startswith('kakao-')):
        is_password_user = False
    elif admin_client and user_id:
        try:
            auth_user_res = admin_client.auth.admin.get_user_by_id(user_id)
            if auth_user_res and auth_user_res.user:
                app_meta = getattr(auth_user_res.user, 'app_metadata', {}) or {}
                user_provider = app_meta.get('provider')
                providers = app_meta.get('providers') or []
                if user_provider and user_provider != 'email':
                    is_password_user = False
                elif providers and 'email' not in providers:
                    is_password_user = False
        except Exception as ue:
            logger.debug(f"사용자 인증 제공자 조회 알림: {ue}")

    return render_template('mypage.html', profile=profile_data, is_password_user=is_password_user)


@main_bp.route('/mypage/change-password', methods=['POST'])
def change_password():
    """
    마이페이지 비밀번호 변경 라우트 (POST /mypage/change-password):
    - 로그인 필수
    - 기존 비밀번호 검증 (재로그인 방식)
    - 새 비밀번호 검증 (6자 이상, 확인 일치, 기존 비밀번호와 동일 여부)
    - Supabase admin update_user_by_id()를 통한 비밀번호 변경
    """
    user_info = session.get('user') or {}
    user_id = user_info.get('id') or session.get('user_id')
    user_email = user_info.get('email') or session.get('email')

    if not user_id or not user_email:
        return redirect(url_for('main.login', error='login_required'))

    current_password = request.form.get('current_password') or ''
    new_password = request.form.get('new_password') or ''
    new_password_confirm = request.form.get('new_password_confirm') or ''

    # 1. 입력값 누락 검사
    if not current_password or not new_password or not new_password_confirm:
        return redirect(url_for('main.mypage', pw_error='모든 비밀번호 항목을 입력해 주세요.'))

    # 2. 새 비밀번호 유효성 검사 (Day 4 회원가입 조건과 동일: 최소 6자 이상)
    if len(new_password) < 6:
        return redirect(url_for('main.mypage', pw_error='새 비밀번호는 최소 6자 이상이어야 합니다.'))

    # 3. 새 비밀번호 확인 일치 검사
    if new_password != new_password_confirm:
        return redirect(url_for('main.mypage', pw_error='새 비밀번호와 비밀번호 확인이 일치하지 않습니다.'))

    # 4. 기존 비밀번호와 새 비밀번호 동일 여부 검사
    if current_password == new_password:
        return redirect(url_for('main.mypage', pw_error='새로운 비밀번호가 현재 비밀번호와 동일합니다.'))

    # 5. 기존 비밀번호 검증 (Supabase sign_in_with_password 시도)
    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for('main.mypage', pw_error='인증 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'))

    try:
        auth_check = supabase.auth.sign_in_with_password({
            "email": user_email,
            "password": current_password
        })
        if not auth_check or not auth_check.user:
            return redirect(url_for('main.mypage', pw_error='현재 비밀번호가 일치하지 않습니다.'))
    except Exception as e:
        logger.warning(f"현재 비밀번호 검증 실패: {e}")
        return redirect(url_for('main.mypage', pw_error='현재 비밀번호가 일치하지 않습니다.'))

    # 6. Supabase Admin API로 비밀번호 변경
    admin_client = get_supabase_admin_client()
    if not admin_client:
        return redirect(url_for('main.mypage', pw_error='관리자 인증 서버에 연결할 수 없습니다.'))

    try:
        admin_client.auth.admin.update_user_by_id(user_id, {
            "password": new_password
        })
        logger.info(f"사용자 비밀번호 변경 완료: {user_email} ({user_id})")
        return redirect(url_for('main.mypage', pw_success='비밀번호가 변경되었습니다.'))
    except Exception as e:
        logger.error(f"비밀번호 변경 처리 중 오류 발생: {e}")
        return redirect(url_for('main.mypage', pw_error=f'비밀번호 변경 처리 중 오류가 발생했습니다: {str(e)}'))


@main_bp.route('/withdraw', methods=['POST'])
def withdraw():
    """
    회원 탈퇴 처리 라우트:
    현재 로그인된 사용자의 세션 및 데이터베이스 계정을 안전하게 삭제하고 탈퇴 완료 처리합니다.
    (카카오 연동 회원인 경우 카카오 연결 끊기 API 호출 포함)
    """
    user_info = session.get('user') or {}
    user_id = user_info.get('id') or session.get('user_id')
    user_email = user_info.get('email') or session.get('email')
    provider = user_info.get('provider')
    kakao_access_token = session.get('kakao_access_token')

    if not user_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    admin_client = get_supabase_admin_client()
    anon_client = get_supabase_client()

    # 1. 소셜 로그인(네이버/카카오 등 가상 UUID 포함)인 경우와 Supabase Auth 가입 회원 구분
    is_social_custom = (provider in ['naver', 'kakao']) or (isinstance(user_id, str) and (user_id.startswith('naver-') or user_id.startswith('kakao-')))
    is_kakao = (provider == 'kakao') or (isinstance(user_id, str) and user_id.startswith('kakao-'))

    try:
        # 1-1. 카카오 로그인 회원인 경우 카카오 계정 연결 끊기(탈퇴) API 호출
        if is_kakao:
            try:
                import httpx
                # 1순위: 세션에 저장된 kakao_access_token으로 연결 끊기
                if kakao_access_token:
                    unlink_res = httpx.post(
                        "https://kapi.kakao.com/v1/user/unlink",
                        headers={"Authorization": f"Bearer {kakao_access_token}"},
                        timeout=5.0
                    )
                    logger.info(f"카카오 unlink(토큰) 응답: {unlink_res.status_code}")
                else:
                    # 2순위: Admin Key가 환경변수에 설정되어 있다면 Target ID로 연결 끊기
                    kakao_admin_key = os.getenv("KAKAO_ADMIN_KEY")
                    raw_target_id = user_id.replace('kakao-', '') if isinstance(user_id, str) else ''
                    if kakao_admin_key and raw_target_id.isdigit():
                        unlink_res = httpx.post(
                            "https://kapi.kakao.com/v1/user/unlink",
                            headers={"Authorization": f"KakaoAK {kakao_admin_key}"},
                            data={"target_id_type": "user_id", "target_id": int(raw_target_id)},
                            timeout=5.0
                        )
                        logger.info(f"카카오 unlink(어드민키) 응답: {unlink_res.status_code}")
            except Exception as ke:
                logger.warning(f"카카오 연결 끊기 API 호출 중 예외: {ke}")

        # 2. DB에서 프로필 및 관련 데이터 삭제
        if admin_client:
            try:
                # profiles 테이블에서 삭제 시도
                admin_client.table('profiles').delete().eq('id', user_id).execute()
            except Exception as pe:
                logger.warning(f"프로필 삭제 시도 중 알림: {pe}")

            # Supabase Auth 회원이면 Auth 계정 삭제 (admin API)
            if not is_social_custom:
                try:
                    admin_client.auth.admin.delete_user(user_id)
                except Exception as ae:
                    logger.warning(f"Supabase auth admin delete_user 실패: {ae}")
        elif anon_client:
            # 관리자 클라이언트가 없을 경우 anon 클라이언트로 시도
            try:
                anon_client.table('profiles').delete().eq('id', user_id).execute()
            except Exception as pe:
                logger.warning(f"프로필 삭제 시도 중 알림: {pe}")

        # Supabase 세션 로그아웃 처리
        if anon_client:
            try:
                anon_client.auth.sign_out()
            except Exception:
                pass

        # Flask 세션 전체 초기화
        session.clear()

        return jsonify({
            "success": True,
            "message": "회원 탈퇴 및 카카오 연동 해제가 안전하게 완료되었습니다. 그동안 양산시민축구단을 응원해 주셔서 감사합니다."
        })

    except Exception as e:
        logger.error(f"회원 탈퇴 처리 중 오류 발생: {e}")
        return jsonify({
            "success": False,
            "message": "회원 탈퇴 처리 중 오류가 발생했습니다. 고객센터로 문의해 주세요."
        }), 500

