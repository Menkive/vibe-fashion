# app/routes/main.py - 양산시민축구단 공식 온라인 스토어 라우트
import os
import sys
import logging
from flask import Blueprint, render_template, request, jsonify, abort, session, url_for
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


@main_bp.route('/attractions')
def attractions():
    """양산 8경 소개 페이지"""
    attractions_data = [
        {
            'id': '01',
            'name': '통도사',
            'ko_name': 'TONGDOSA TEMPLE',
            'image': url_for('static', filename='images/attractions/tongdosa.jpg'),
            'description': '한국 불교의 성지'
        },
        {
            'id': '02',
            'name': '홍룡폭포',
            'ko_name': 'HONGRYONG WATERFALL',
            'image': url_for('static', filename='images/attractions/hongryong-waterfall.jpg'),
            'description': '천연 비경'
        },
        {
            'id': '03',
            'name': '내원사계곡',
            'ko_name': 'NAEWONSA VALLEY',
            'image': url_for('static', filename='images/attractions/naewonsa-valley.jpg'),
            'description': '자연 속 휴식처'
        },
        {
            'id': '04',
            'name': '배내골',
            'ko_name': 'BAENAEGOL',
            'image': url_for('static', filename='images/attractions/baenaegol.jpg'),
            'description': '휴양림'
        },
        {
            'id': '05',
            'name': '오봉산 임경대',
            'ko_name': 'IMGYEONGDAE OBSERVATORY',
            'image': url_for('static', filename='images/attractions/imgyeongdae.jpg'),
            'description': '전망대'
        },
        {
            'id': '06',
            'name': '천태산',
            'ko_name': 'CHEONTAESAN MOUNTAIN',
            'image': url_for('static', filename='images/attractions/cheontaesan.jpg'),
            'description': '산악 명소'
        },
        {
            'id': '07',
            'name': '천성산',
            'ko_name': 'CHEONSONGSAN MOUNTAIN',
            'image': url_for('static', filename='images/attractions/cheonsongsan.jpg'),
            'description': '산악 코스'
        },
        {
            'id': '08',
            'name': '대운산자연휴양림',
            'ko_name': 'DAEUNSAN RECREATION FOREST',
            'image': url_for('static', filename='images/attractions/daeunsan.jpg'),
            'description': '숲 속 휴양'
        }
    ]
    return render_template('attractions.html', attractions=attractions_data)


@main_bp.route('/products')
def product_list():
    """전체 상품 목록 화면 (검색, 카테고리 필터, 정렬 기능)"""
    all_products = fetch_all_products()
    return render_template('product_list.html', products=all_products)


@main_bp.route('/products/<product_id>')
def product_detail(product_id):
    """
    상품 상세 페이지 (GET /products/<product_id>):
    1. Supabase products 테이블에서 product_id로 상품 상세 정보 조회
    2. product_options 테이블에서 해당 상품의 색상(color) 목록 DISTINCT 조회
    3. 상품 이미지, 상품명, 정가, 할인가, 설명 및 연관 상품 전달
    """
    admin_client = get_supabase_admin_client()
    anon_client = get_supabase_client()
    db_client = admin_client or anon_client

    product = None
    colors = []

    if db_client:
        try:
            # 1. Supabase products 테이블에서 상품 조회 (카테고리 및 이미지 조인)
            p_res = db_client.table('products') \
                .select('*, categories(name), product_images(image_url, is_primary)') \
                .eq('id', product_id) \
                .execute()
            
            if p_res.data and len(p_res.data) > 0:
                p_item = p_res.data[0]
                category_name = (p_item.get('categories') or {}).get('name') if isinstance(p_item.get('categories'), dict) else (p_item.get('category') or '기타')
                
                # 이미지 추출 (is_primary 우선)
                imgs = p_item.get('product_images') or []
                primary_imgs = [img.get('image_url') for img in imgs if img.get('is_primary') and img.get('image_url')]
                other_imgs = [img.get('image_url') for img in imgs if img.get('image_url')]
                img_url = primary_imgs[0] if primary_imgs else (other_imgs[0] if other_imgs else '/static/images/home-uniform.png')

                # 가격 정보 파싱
                try:
                    price = int(float(p_item.get('price', 0)))
                except (ValueError, TypeError):
                    price = 0

                orig_price = None
                if p_item.get('original_price'):
                    try:
                        orig_price = int(float(p_item.get('original_price')))
                    except (ValueError, TypeError):
                        orig_price = None

                product = {
                    "id": p_item.get('id'),
                    "name": p_item.get('name'),
                    "slug": p_item.get('slug'),
                    "category": category_name,
                    "price": price,
                    "original_price": orig_price,
                    "description": p_item.get('description', ''),
                    "image_url": img_url,
                    "thumbnail_url": img_url,
                    "badge": p_item.get('badge') or 'BEST',
                    "is_featured": p_item.get('is_featured', True)
                }

                # 2. product_options 테이블에서 색상(color) 목록 DISTINCT 조회
                opts_res = db_client.table('product_options') \
                    .select('color') \
                    .eq('product_id', product_id) \
                    .execute()
                
                if opts_res.data:
                    raw_colors = [o.get('color') for o in opts_res.data if o.get('color')]
                    # 순서 보존 및 중복 제거
                    seen = set()
                    for c in raw_colors:
                        if c not in seen:
                            seen.add(c)
                            colors.append(c)
        except Exception as e:
            logger.error(f"Supabase 상품 상세 조회 오류: {e}")

    # DB 조회가 실패하거나 로컬 기본 상품일 경우 폴백
    if not product:
        product = get_product_by_id(product_id)
        if not product:
            abort(404)
        if not colors:
            colors = ["기본 컬러"]

    all_products = fetch_all_products()
    related_products = [p for p in all_products if str(p["id"]) != str(product_id)][:4]

    return render_template(
        'product_detail.html',
        product=product,
        colors=colors,
        related_products=related_products
    )


@main_bp.route('/api/products/<product_id>/sizes')
def api_product_sizes(product_id):
    """
    상품 상세 페이지에서 색상 선택 시 호출하는 사이즈 & 재고 API:
    GET /api/products/<product_id>/sizes?color=<선택한 색상>
    - product_options 테이블 조회
    - product_id와 color 조건으로 필터링
    - 해당 색상의 사이즈 및 재고 목록 반환
      응답 예시: [{"size": "S", "stock": 3, "id": "..."}, {"size": "M", "stock": 0, "id": "..."}]
    """
    color = request.args.get('color', '').strip()
    if not color:
        return jsonify({"success": False, "message": "색상을 지정해주세요."}), 400

    admin_client = get_supabase_admin_client()
    anon_client = get_supabase_client()
    db_client = admin_client or anon_client

    sizes_list = []
    if db_client:
        try:
            # product_options에서 product_id + color로 필터링
            res = db_client.table('product_options') \
                .select('id, size, stock, stock_quantity') \
                .eq('product_id', product_id) \
                .eq('color', color) \
                .execute()
            
            if res.data:
                for row in res.data:
                    # stock 컬럼 우선, 없으면 stock_quantity 사용
                    stock_val = row.get('stock')
                    if stock_val is None:
                        stock_val = row.get('stock_quantity', 0)
                    try:
                        stock_num = max(0, int(stock_val))
                    except (ValueError, TypeError):
                        stock_num = 0

                    sizes_list.append({
                        "size": row.get('size'),
                        "stock": stock_num,
                        "id": str(row.get('id'))
                    })

                # 사이즈 순서 정렬 (XS, S, M, L, XL, XXL 등 표준 순서)
                size_order = {"XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6, "2XL": 6, "3XL": 7, "Free": 8}
                sizes_list.sort(key=lambda x: size_order.get(x['size'], 99))
        except Exception as e:
            logger.error(f"사이즈 옵션 API 조회 오류: {e}")

    # DB에 옵션이 없는 레거시 또는 폴백 상품인 경우 기본값 제공
    if not sizes_list:
        sizes_list = [
            {"size": "Free", "stock": 10, "id": f"opt-{product_id}-free"}
        ]

    return jsonify(sizes_list)


@main_bp.route('/cart')
def cart():
    """
    장바구니 페이지 (GET /cart):
    1. 로그인한 사용자의 장바구니 조회
    2. carts, products, product_options 테이블 JOIN
    3. 각 상품의 색상, 사이즈, 수량, 단가, 소계 표시
    4. 품절 상품 처리 (stock=0)
    5. 금액 계산 (소계, 배송비, 총액)
    """
    # 1. 로그인 확인
    user_info = session.get('user') or {}
    user_id = user_info.get('id') or session.get('user_id')
    
    # 비로그인이면 빈 장바구니 페이지 표시 (로컬스토리지 사용)
    if not user_id:
        return render_template('cart.html', cart_items=[], user_logged_in=False)

    admin_client = get_supabase_admin_client()
    anon_client = get_supabase_client()
    db_client = admin_client or anon_client

    if not db_client:
        return render_template('cart.html', cart_items=[], user_logged_in=True, error="데이터베이스 연결 실패")

    try:
        # 2. 사용자의 장바구니 항목 조회 (JOIN: carts → products, product_options)
        cart_response = db_client.table('carts') \
            .select('id, product_id, option_id, quantity, created_at, updated_at') \
            .eq('user_id', user_id) \
            .order('updated_at', desc=True) \
            .execute()

        cart_items = []
        has_sold_out = False
        
        if cart_response.data:
            for cart_item in cart_response.data:
                cart_id = cart_item['id']
                product_id = cart_item['product_id']
                option_id = cart_item['option_id']
                quantity = cart_item['quantity']

                # 상품 정보 조회 (image_url은 product_images 테이블에서 따로 조회)
                prod_response = db_client.table('products') \
                    .select('id, name, price') \
                    .eq('id', product_id) \
                    .execute()

                if not prod_response.data:
                    continue

                product = prod_response.data[0]
                
                # 상품 이미지 조회 (product_images 테이블에서 primary 이미지 가져오기)
                image_url = ''
                img_response = db_client.table('product_images') \
                    .select('image_url') \
                    .eq('product_id', product_id) \
                    .eq('is_primary', True) \
                    .limit(1) \
                    .execute()
                
                if img_response.data:
                    image_url = img_response.data[0].get('image_url', '')
                else:
                    # primary 이미지가 없으면 첫 번째 이미지 사용
                    img_response = db_client.table('product_images') \
                        .select('image_url') \
                        .eq('product_id', product_id) \
                        .order('sort_order', desc=False) \
                        .limit(1) \
                        .execute()
                    if img_response.data:
                        image_url = img_response.data[0].get('image_url', '')
                
                # 상품 옵션 정보 조회 (색상, 사이즈, 재고)
                opt_response = db_client.table('product_options') \
                    .select('id, color, size, stock_quantity') \
                    .eq('id', option_id) \
                    .execute()

                if not opt_response.data:
                    continue

                option = opt_response.data[0]

                # 재고 계산 (stock_quantity 사용)
                try:
                    available_stock = int(option.get('stock_quantity', 0))
                except (ValueError, TypeError):
                    available_stock = 0

                # 가격 계산
                try:
                    price = int(float(product.get('price', 0)))
                except (ValueError, TypeError):
                    price = 0

                subtotal = price * quantity
                
                # 품절 여부
                is_sold_out = available_stock <= 0
                if is_sold_out:
                    has_sold_out = True

                cart_items.append({
                    'cart_id': cart_id,
                    'product_id': product_id,
                    'product_name': product.get('name', '상품'),
                    'color': option.get('color', 'N/A'),
                    'size': option.get('size', 'N/A'),
                    'quantity': quantity,
                    'price': price,
                    'subtotal': subtotal,
                    'image_url': image_url,
                    'available_stock': available_stock,
                    'is_sold_out': is_sold_out
                })

        # 3. 금액 계산
        subtotal = sum(item['subtotal'] for item in cart_items)
        shipping = 0 if (subtotal >= 50000 or subtotal == 0) else 3000
        total = subtotal + shipping

        return render_template(
            'cart.html',
            cart_items=cart_items,
            subtotal=subtotal,
            shipping=shipping,
            total=total,
            has_sold_out=has_sold_out,
            user_logged_in=True
        )

    except Exception as e:
        logger.error(f"장바구니 페이지 로드 오류: {e}")
        return render_template('cart.html', cart_items=[], user_logged_in=True, error=f"오류 발생: {str(e)}")


@main_bp.route('/cart/add', methods=['POST'])
def cart_add():
    """
    장바구니 담기 API (POST /cart/add):
    1. 로그인 검증: 비로그인 사용자는 /auth/login (또는 /login) 리다이렉트 (JSON 요청 시 401 및 redirect_url 반환)
    2. 요청 데이터: product_option_id, quantity
    3. 재고 검증:
       - product_options 테이블에서 선택한 옵션 조회
       - 요청 수량이 현재 재고(stock)보다 많으면 오류 반환
    4. 장바구니 저장 (carts 테이블):
       - 동일 사용자 + 동일 product_option_id가 이미 존재하면 수량 누적
       - 누적 수량이 stock을 초과하면 에러 반환 (DB 변경 금지)
       - 존재하지 않으면 신규 생성
    5. 성공 시 JSON 응답 반환 및 추후 바로구매 확장이 용이하도록 처리
    """
    is_json = request.is_json or bool(request.get_json(silent=True))

    # 1. 로그인 검증
    user_info = session.get('user') or {}
    user_id = user_info.get('id') or session.get('user_id')
    if not user_id:
        login_url = url_for('auth.login', error='login_required') if 'auth.login' in current_app.view_functions else url_for('main.login', error='login_required')
        if is_json:
            return jsonify({
                "success": False,
                "message": "로그인이 필요한 서비스입니다.",
                "redirect_url": login_url
            }), 401
        return redirect(login_url)

    # 2. 요청 데이터 파싱
    data = request.get_json(silent=True) or request.form
    product_option_id = data.get('product_option_id')
    raw_quantity = data.get('quantity', 1)

    if not product_option_id:
        return jsonify({"success": False, "message": "상품 옵션(사이즈/색상)을 선택해 주세요."}), 400

    try:
        quantity = int(raw_quantity)
        if quantity <= 0:
            return jsonify({"success": False, "message": "수량은 1개 이상이어야 합니다."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "올바른 수량을 입력해 주세요."}), 400

    admin_client = get_supabase_admin_client()
    anon_client = get_supabase_client()
    db_client = admin_client or anon_client

    if not db_client:
        return jsonify({"success": False, "message": "데이터베이스 연결에 실패했습니다."}), 500

    try:
        # 3. 재고 검증: product_options 테이블에서 옵션 및 상품 정보 조회
        opt_res = db_client.table('product_options') \
            .select('id, product_id, size, color, stock, stock_quantity') \
            .eq('id', product_option_id) \
            .execute()

        if not opt_res.data or len(opt_res.data) == 0:
            return jsonify({"success": False, "message": "존재하지 않는 상품 옵션입니다."}), 404

        option_row = opt_res.data[0]
        product_id = option_row.get('product_id')

        # stock 컬럼 우선, 없으면 stock_quantity 사용
        stock_val = option_row.get('stock')
        if stock_val is None:
            stock_val = option_row.get('stock_quantity', 0)
        try:
            available_stock = max(0, int(stock_val))
        except (ValueError, TypeError):
            available_stock = 0

        # 요청 수량 단독 재고 초과 검증
        if quantity > available_stock:
            return jsonify({
                "success": False,
                "message": f"재고가 부족합니다. (현재 {available_stock}개)"
            }), 400

        # 4. carts 테이블에서 동일 사용자 + 동일 option_id 항목 조회
        cart_item_res = db_client.table('carts') \
            .select('id, quantity') \
            .eq('user_id', user_id) \
            .eq('option_id', product_option_id) \
            .execute()

        existing_cart = cart_item_res.data[0] if cart_item_res.data else None

        if existing_cart:
            existing_qty = int(existing_cart.get('quantity', 0))
            new_total_qty = existing_qty + quantity

            # 5. 누적 재고 검증: 기존 수량 + 추가 수량이 재고를 초과하면 저장하지 않고 에러 반환
            if new_total_qty > available_stock:
                return jsonify({
                    "success": False,
                    "message": f"장바구니 담기 가능한 재고를 초과했습니다. (장바구니 담긴 수량: {existing_qty}개, 현재 재고: {available_stock}개)"
                }), 400

            # 수량 누적 업데이트 (검증 통과 후에만 반영)
            update_res = db_client.table('carts') \
                .update({
                    "quantity": new_total_qty,
                    "updated_at": "now()"
                }) \
                .eq('id', existing_cart['id']) \
                .execute()

            cart_id = existing_cart['id']
            final_qty = new_total_qty
        else:
            # 신규 생성
            insert_data = {
                "user_id": user_id,
                "product_id": product_id,
                "option_id": product_option_id,
                "quantity": quantity
            }
            insert_res = db_client.table('carts') \
                .insert(insert_data) \
                .execute()

            cart_id = insert_res.data[0]['id'] if insert_res.data else None
            final_qty = quantity

        # 6. 성공 응답
        return jsonify({
            "success": True,
            "message": "장바구니에 담겼습니다.",
            "data": {
                "cart_id": cart_id,
                "product_id": product_id,
                "product_option_id": product_option_id,
                "quantity": final_qty
            }
        })

    except Exception as e:
        logger.error(f"장바구니 담기 처리 오류: {e}")
        return jsonify({"success": False, "message": f"장바구니 담기 처리 중 오류가 발생했습니다: {str(e)}"}), 500


@main_bp.route('/cart/<cart_id>', methods=['PATCH'])
def cart_update(cart_id):
    """
    장바구니 수량 변경 API (PATCH /cart/<cart_id>):
    1. 로그인 검증: 비로그인 사용자는 401 반환
    2. 요청 body: quantity (변경할 수량)
    3. quantity < 1이면 오류 반환
    4. 해당 cart_id가 로그인한 사용자의 것인지 검증 (다른 사용자면 403 반환)
    5. 상품 옵션의 재고 확인
    6. 변경 수량이 재고를 초과하면 오류 반환 (수정하지 않음)
    7. UPDATE 후 subtotal 계산하여 응답
    """
    # 1. 로그인 검증
    user_info = session.get('user') or {}
    user_id = user_info.get('id') or session.get('user_id')
    if not user_id:
        return jsonify({
            "success": False,
            "message": "로그인이 필요한 서비스입니다."
        }), 401

    # 2. 요청 데이터 파싱
    data = request.get_json(silent=True) or request.form
    raw_quantity = data.get('quantity')

    if raw_quantity is None:
        return jsonify({"success": False, "message": "수량(quantity)은 필수입니다."}), 400

    try:
        quantity = int(raw_quantity)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "올바른 수량을 입력해 주세요."}), 400

    # 3. quantity >= 1 검증
    if quantity < 1:
        return jsonify({"success": False, "message": "수량은 1개 이상이어야 합니다."}), 400

    admin_client = get_supabase_admin_client()
    anon_client = get_supabase_client()
    db_client = admin_client or anon_client

    if not db_client:
        return jsonify({"success": False, "message": "데이터베이스 연결에 실패했습니다."}), 500

    try:
        # 4. cart_id가 해당 사용자의 것인지 검증
        cart_res = db_client.table('carts') \
            .select('id, user_id, product_id, option_id, quantity') \
            .eq('id', cart_id) \
            .execute()

        if not cart_res.data or len(cart_res.data) == 0:
            return jsonify({"success": False, "message": "존재하지 않는 장바구니 아이템입니다."}), 404

        cart_item = cart_res.data[0]
        cart_user_id = cart_item.get('user_id')

        # 다른 사용자의 cart_id 접근 차단
        if cart_user_id != user_id:
            return jsonify({"success": False, "message": "접근 권한이 없습니다."}), 403

        option_id = cart_item.get('option_id')
        product_id = cart_item.get('product_id')

        # 5. 상품 옵션의 재고 확인
        opt_res = db_client.table('product_options') \
            .select('id, stock_quantity') \
            .eq('id', option_id) \
            .execute()

        if not opt_res.data or len(opt_res.data) == 0:
            return jsonify({"success": False, "message": "상품 옵션을 찾을 수 없습니다."}), 404

        option_row = opt_res.data[0]
        stock_val = option_row.get('stock_quantity', 0)

        try:
            available_stock = max(0, int(stock_val))
        except (ValueError, TypeError):
            available_stock = 0

        # 6. 변경 수량이 재고를 초과하면 오류 반환
        if quantity > available_stock:
            return jsonify({
                "success": False,
                "message": f"재고가 부족합니다 (현재 {available_stock}개)"
            }), 400

        # 7. quantity UPDATE
        update_res = db_client.table('carts') \
            .update({
                "quantity": quantity,
                "updated_at": "now()"
            }) \
            .eq('id', cart_id) \
            .execute()

        if not update_res.data:
            return jsonify({"success": False, "message": "장바구니 수량 변경에 실패했습니다."}), 500

        # 8. 상품 가격 조회하여 subtotal 계산
        prod_res = db_client.table('products') \
            .select('id, name, price') \
            .eq('id', product_id) \
            .execute()

        if not prod_res.data or len(prod_res.data) == 0:
            return jsonify({"success": False, "message": "상품을 찾을 수 없습니다."}), 404

        product = prod_res.data[0]
        try:
            price = int(float(product.get('price', 0)))
        except (ValueError, TypeError):
            price = 0

        subtotal = price * quantity

        # 9. 응답 반환
        return jsonify({
            "success": True,
            "message": "장바구니 수량이 변경되었습니다.",
            "data": {
                "cart_id": cart_id,
                "product_id": product_id,
                "product_name": product.get('name'),
                "price": price,
                "quantity": quantity,
                "subtotal": subtotal
            }
        }), 200

    except Exception as e:
        logger.error(f"장바구니 수량 변경 처리 오류: {e}")
        return jsonify({"success": False, "message": f"장바구니 수량 변경 중 오류가 발생했습니다: {str(e)}"}), 500


@main_bp.route('/cart/<cart_id>', methods=['DELETE'])
def cart_delete(cart_id):
    """
    장바구니 아이템 삭제 API (DELETE /cart/<cart_id>):
    1. 로그인 검증: 비로그인 사용자는 401 반환
    2. cart_id가 로그인한 사용자의 것인지 검증 (다른 사용자면 403 반환)
    3. 존재하지 않는 cart_id면 404 반환
    4. 데이터베이스에서 해당 항목 DELETE
    5. 삭제 완료 응답 반환
    """
    # 1. 로그인 검증
    user_info = session.get('user') or {}
    user_id = user_info.get('id') or session.get('user_id')
    if not user_id:
        return jsonify({
            "success": False,
            "message": "로그인이 필요한 서비스입니다."
        }), 401

    admin_client = get_supabase_admin_client()
    anon_client = get_supabase_client()
    db_client = admin_client or anon_client

    if not db_client:
        return jsonify({"success": False, "message": "데이터베이스 연결에 실패했습니다."}), 500

    try:
        # 2. cart_id 존재 및 소유권 검증
        cart_res = db_client.table('carts') \
            .select('id, user_id, product_id, option_id') \
            .eq('id', cart_id) \
            .execute()

        if not cart_res.data or len(cart_res.data) == 0:
            return jsonify({"success": False, "message": "존재하지 않는 장바구니 아이템입니다."}), 404

        cart_item = cart_res.data[0]
        cart_user_id = cart_item.get('user_id')

        # 다른 사용자의 cart_id 삭제 시도 차단
        if cart_user_id != user_id:
            return jsonify({"success": False, "message": "접근 권한이 없습니다."}), 403

        # 상품명 조회 (products 테이블에서)
        product_id = cart_item.get('product_id')
        prod_res = db_client.table('products') \
            .select('id, name') \
            .eq('id', product_id) \
            .execute()
        
        product_name = '상품'
        if prod_res.data and len(prod_res.data) > 0:
            product_name = prod_res.data[0].get('name', '상품')

        # 3. 장바구니 항목 삭제
        delete_res = db_client.table('carts') \
            .delete() \
            .eq('id', cart_id) \
            .execute()

        # 4. 삭제 완료 응답
        return jsonify({
            "success": True,
            "message": f"'{product_name}'이(가) 장바구니에서 삭제되었습니다.",
            "data": {
                "cart_id": cart_id,
                "product_name": product_name
            }
        }), 200

    except Exception as e:
        logger.error(f"장바구니 삭제 처리 오류: {e}")
        return jsonify({"success": False, "message": f"장바구니 삭제 중 오류가 발생했습니다: {str(e)}"}), 500


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

