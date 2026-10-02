"""
양산시민축구단 공식 팀스토어 - 관리자(Admin) 라우트 모듈
- 대시보드: 핵심 지표(총 매출, 주문 수, 상품 수, 회원 수) 및 최근 주문/인기 상품 목록
- 상품 관리: 상품 목록 조회, 재고/상태(판매중/품절) 토글, 상품 가격 및 정보 수정
- 주문 관리: 전체 주문 내역 조회, 주문 상태(결제완료, 배송준비, 배송중, 배송완료, 주문취소) 변경, 주문 상세
- 회원 관리: 가입 회원 목록 조회, 등급 및 누적 구매액 확인
- 권한 체크: @admin_required 데코레이터 (개발/테스트 모드 및 admin role 지원)
"""

import logging
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort
from app.routes.main import get_supabase_admin_client, get_supabase_client, fetch_all_products
from app.models import INITIAL_PRODUCTS
from app.services.order_service import restore_order_stock_and_record, STOCK_RESTORED_FLAG

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def get_db():
    """관리자 권한의 Supabase 클라이언트 반환 (없으면 anon 클라이언트)"""
    return get_supabase_admin_client() or get_supabase_client()


def is_admin_user():
    """
    현재 로그인된 사용자가 관리자인지 확인:
    1. session에 로그인 정보가 없으면 False
    2. session['user']['role']이 'admin'이면 True
    3. 세션 정보에 role이 불확실한 경우, Supabase profiles 테이블에서 실제 'role' 조회
    4. role == 'admin'인 경우에만 True 반환 (그 외 customer 등 일반 회원은 절대 접근 불가)
    """
    user_id = session.get('user_id') or session.get('user', {}).get('id')
    if not user_id:
        return False
    
    # 세션 캐시 확인
    user_data = session.get('user', {})
    if isinstance(user_data, dict) and user_data.get('role') == 'admin':
        return True

    # DB profiles 테이블에서 실시간 role 검증
    db = get_db()
    if db and user_id:
        try:
            res = db.table('profiles').select('role').eq('id', user_id).execute()
            if res.data and res.data[0].get('role') == 'admin':
                # 세션에도 role 동기화
                if isinstance(session.get('user'), dict):
                    session['user']['role'] = 'admin'
                    session.modified = True
                return True
        except Exception as e:
            logger.warning(f"관리자 권한 확인 중 오류: {e}")

    return False


def admin_required(f):
    """
    관리자 접근 제한 데코레이터:
    - 로그인하지 않은 사용자가 /admin 직접 입력 시 -> 로그인 페이지로 리다이렉트
    - 로그인했으나 관리자 권한(role != 'admin')이 없는 일반 사용자가 /admin 직접 입력 시 -> 접근 거부 플래시 메시지와 함께 메인 페이지로 차단
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id') or session.get('user', {}).get('id')
        if not user_id:
            flash('관리자 페이지는 로그인이 필요합니다.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        if not is_admin_user():
            flash('관리자 권한이 없습니다. 접근이 거부되었습니다.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# 1. 대시보드 (Dashboard)
# ==============================================================================
@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """
    관리자 메인 대시보드:
    요구사항 반영 5대 상단 요약 카드:
    - 오늘 매출 (today_sales)
    - 오늘 주문 건수 (today_orders_count)
    - 전체 상품 수 (total_products_count)
    - 재고 부족 상품 수 (low_stock_products_count)
    - 품절 상품 수 (out_of_stock_products_count)
    하단:
    - 최근 주문 목록 (최근 5~10건)
    """
    import datetime
    from collections import defaultdict
    
    db = get_db()
    today_str = datetime.date.today().isoformat()
    
    today_sales = 0
    today_orders_count = 0
    total_sales = 0
    total_orders_count = 0
    total_products_count = 0
    low_stock_products_count = 0
    out_of_stock_products_count = 0
    recent_orders = []
    
    if db:
        try:
            # 1) 전체 주문 조회 및 오늘 주문/매출 집계
            orders_res = db.table('orders').select('*').order('created_at', desc=True).execute()
            if orders_res.data:
                all_orders = orders_res.data
                total_orders_count = len(all_orders)
                recent_orders = all_orders[:8]  # 최근 8건

                for o in all_orders:
                    c_date = str(o.get('created_at', ''))[:10]
                    is_valid = o.get('status') not in ['cancelled', 'refunded']
                    try:
                        amt = int(float(o.get('final_amount', 0)))
                    except (ValueError, TypeError):
                        amt = 0

                    if is_valid:
                        total_sales += amt

                    if c_date == today_str:
                        today_orders_count += 1
                        if is_valid:
                            today_sales += amt

            # 2) 전체 상품 및 옵션별 재고 집계
            prods_res = db.table('products').select('id, name, is_active').execute()
            prods = prods_res.data or []
            total_products_count = len(prods)

            opts_res = db.table('product_options').select('product_id, stock, stock_quantity').execute()
            opts = opts_res.data or []

            p_stock_map = defaultdict(int)
            p_zero_opts = defaultdict(int)
            p_low_opts = defaultdict(int)

            for o in opts:
                pid = o.get('product_id')
                stk = o.get('stock')
                if stk is None:
                    stk = o.get('stock_quantity', 0)
                try:
                    stk_val = max(0, int(stk))
                except (ValueError, TypeError):
                    stk_val = 0

                p_stock_map[pid] += stk_val
                if stk_val == 0:
                    p_zero_opts[pid] += 1
                elif stk_val <= 5:
                    p_low_opts[pid] += 1

            for p in prods:
                pid = p.get('id')
                tot_stk = p_stock_map.get(pid, 0)
                zero_cnt = p_zero_opts.get(pid, 0)
                low_cnt = p_low_opts.get(pid, 0)
                is_active = p.get('is_active', True)

                # 품절 판정: 총 재고가 0이거나, 판매중지(비활성)이거나, 품절된 옵션(재고 0)이 1개 이상 존재하는 상품
                if tot_stk == 0 or not is_active or zero_cnt > 0:
                    out_of_stock_products_count += 1
                # 재고 부족 판정: 품절은 아니지만 총 재고 30개 이하이거나 재고 5개 이하인 임박 옵션을 가진 상품
                elif tot_stk <= 30 or low_cnt > 0:
                    low_stock_products_count += 1

        except Exception as e:
            logger.error(f"관리자 대시보드 통계 조회 오류: {e}")
    else:
        # DB 연결 실패 시 기본 폴백
        total_products_count = len(INITIAL_PRODUCTS)
        today_sales = 1090000
        today_orders_count = 5
        total_sales = 1308000
        total_orders_count = 5
        low_stock_products_count = 4
        out_of_stock_products_count = 1

    return render_template(
        'admin/dashboard.html',
        today_sales=today_sales,
        today_orders_count=today_orders_count,
        total_sales=total_sales,
        total_orders_count=total_orders_count,
        total_products_count=total_products_count,
        low_stock_products_count=low_stock_products_count,
        out_of_stock_products_count=out_of_stock_products_count,
        recent_orders=recent_orders
    )


# ==============================================================================
# 2. 상품 관리 (Products)
# ==============================================================================
@admin_bp.route('/products')
@admin_required
def products():
    """관리자 상품 목록 및 재고 현황"""
    db = get_db()
    category_filter = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()
    search_keyword = request.args.get('search', '').strip()

    products_list = []
    categories = []

    if db:
        try:
            # 카테고리 목록
            cat_res = db.table('categories').select('id, name, slug').execute()
            categories = cat_res.data or []

            # 상품 목록 (카테고리 및 대표 이미지 JOIN)
            query = db.table('products').select('id, name, slug, price, original_price, is_active, badge, category_id, created_at, categories(name, slug), product_images(image_url, is_primary)')
            
            if category_filter:
                query = query.eq('category_id', category_filter)
            if status_filter == 'active':
                query = query.eq('is_active', True)
            elif status_filter == 'inactive':
                query = query.eq('is_active', False)

            res = query.order('created_at', desc=True).execute()
            raw_products = res.data or []

            for p in raw_products:
                cat_name = p.get('categories', {}).get('name') if isinstance(p.get('categories'), dict) else '기타'
                
                # 이미지 추출
                imgs = p.get('product_images', [])
                img_url = '/static/images/uniforms/01-home-jersey.png'
                if isinstance(imgs, list) and imgs:
                    primary = next((i.get('image_url') for i in imgs if i.get('is_primary')), imgs[0].get('image_url'))
                    if primary:
                        img_url = primary

                # 옵션별 재고 합계 확인
                opts_res = db.table('product_options').select('stock, stock_quantity').eq('product_id', p.get('id')).execute()
                total_stock = 0
                if opts_res.data:
                    for o in opts_res.data:
                        stk = o.get('stock')
                        if stk is None:
                            stk = o.get('stock_quantity', 0)
                        try:
                            total_stock += int(stk)
                        except (ValueError, TypeError):
                            pass
                else:
                    total_stock = 50

                if search_keyword and search_keyword.lower() not in p.get('name', '').lower():
                    continue

                products_list.append({
                    "id": p.get('id'),
                    "name": p.get('name'),
                    "slug": p.get('slug'),
                    "category": cat_name,
                    "category_id": p.get('category_id'),
                    "price": int(float(p.get('price', 0))),
                    "original_price": int(float(p.get('original_price', 0))) if p.get('original_price') else None,
                    "is_active": p.get('is_active', True),
                    "badge": p.get('badge', ''),
                    "image_url": img_url,
                    "total_stock": total_stock
                })
        except Exception as e:
            logger.error(f"관리자 상품 목록 조회 오류: {e}")

    # 폴백
    if not products_list and not search_keyword and not category_filter:
        for ip in INITIAL_PRODUCTS:
            products_list.append({
                "id": str(ip.get('id')),
                "name": ip.get('name'),
                "slug": ip.get('slug'),
                "category": ip.get('category'),
                "category_id": "",
                "price": ip.get('price'),
                "original_price": ip.get('original_price'),
                "is_active": True,
                "badge": ip.get('badge', ''),
                "image_url": ip.get('image_url'),
                "total_stock": ip.get('stock', 50)
            })

    return render_template(
        'admin/products.html',
        products=products_list,
        categories=categories,
        current_category=category_filter,
        current_status=status_filter,
        search_keyword=search_keyword
    )


@admin_bp.route('/products/<product_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_product_status(product_id):
    """상품 판매 상태(판매중/품절·미노출) 토글"""
    db = get_db()
    if not db:
        flash('데이터베이스 연결에 실패했습니다.', 'danger')
        return redirect(url_for('admin.products'))

    try:
        # 현재 상태 조회
        cur = db.table('products').select('is_active, name').eq('id', product_id).execute()
        if not cur.data:
            flash('해당 상품을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin.products'))

        current_active = cur.data[0].get('is_active', True)
        new_active = not current_active
        p_name = cur.data[0].get('name')

        db.table('products').update({'is_active': new_active}).eq('id', product_id).execute()
        state_str = '판매중' if new_active else '판매중지(미노출)'
        flash(f"[{p_name}] 상태가 '{state_str}'(으)로 변경되었습니다.", 'success')
    except Exception as e:
        logger.error(f"상품 상태 토글 오류: {e}")
        flash(f"상태 변경 중 오류가 발생했습니다: {e}", 'danger')

    return redirect(url_for('admin.products'))


@admin_bp.route('/products/<product_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    """상품 기본 정보 수정 (가격, 정가, 뱃지, 설명)"""
    db = get_db()
    if not db:
        flash('데이터베이스에 연결할 수 없습니다.', 'danger')
        return redirect(url_for('admin.products'))

    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            price = int(request.form.get('price', 0))
            orig_price_str = request.form.get('original_price', '').strip()
            orig_price = int(orig_price_str) if orig_price_str else None
            badge = request.form.get('badge', '').strip()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'true'
            category_id = request.form.get('category_id', '').strip() or None
            image_url = request.form.get('image_url', '').strip()

            update_data = {
                'name': name,
                'price': price,
                'original_price': orig_price,
                'badge': badge,
                'description': description,
                'is_active': is_active
            }
            if category_id:
                update_data['category_id'] = category_id

            db.table('products').update(update_data).eq('id', product_id).execute()

            # 대표 이미지 처리 (product_images)
            if image_url:
                try:
                    # 기존 대표 이미지 확인
                    img_check = db.table('product_images').select('id').eq('product_id', product_id).eq('is_primary', True).execute()
                    if img_check.data:
                        db.table('product_images').update({'image_url': image_url}).eq('id', img_check.data[0]['id']).execute()
                    else:
                        db.table('product_images').insert({
                            'product_id': product_id,
                            'image_url': image_url,
                            'is_primary': True,
                            'sort_order': 0
                        }).execute()
                except Exception as img_err:
                    logger.warning(f"상품 이미지 업데이트 오류: {img_err}")

            flash(f"상품 [{name}] 정보가 성공적으로 수정되었습니다.", 'success')
            return redirect(url_for('admin.edit_product', product_id=product_id))
        except Exception as e:
            logger.error(f"상품 정보 수정 오류: {e}")
            flash(f"수정 중 오류가 발생했습니다: {e}", 'danger')

    # GET 요청: 상품 상세 데이터 로드
    product_res = db.table('products').select('*, categories(name)').eq('id', product_id).execute()
    if not product_res.data:
        flash('존재하지 않는 상품입니다.', 'danger')
        return redirect(url_for('admin.products'))

    product = product_res.data[0]
    
    # 대표 이미지 조회
    primary_img_url = ''
    try:
        img_res = db.table('product_images').select('image_url, is_primary').eq('product_id', product_id).execute()
        if img_res.data:
            primary_img = next((i.get('image_url') for i in img_res.data if i.get('is_primary')), img_res.data[0].get('image_url'))
            primary_img_url = primary_img or ''
    except Exception as e:
        logger.warning(f"대표 이미지 조회 오류: {e}")

    # 카테고리 목록
    categories = []
    try:
        cat_res = db.table('categories').select('id, name').execute()
        categories = cat_res.data or []
    except Exception as e:
        logger.warning(f"카테고리 목록 조회 오류: {e}")

    # 옵션 목록
    options_res = db.table('product_options').select('*').eq('product_id', product_id).order('created_at').execute()
    options = options_res.data or []

    return render_template('admin/product_edit.html', product=product, options=options, categories=categories, primary_img_url=primary_img_url)


@admin_bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def create_product():
    """신규 상품 등록 및 기본 옵션 생성"""
    db = get_db()
    if not db:
        flash('데이터베이스에 연결할 수 없습니다.', 'danger')
        return redirect(url_for('admin.products'))

    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            slug = request.form.get('slug', '').strip()
            price = int(request.form.get('price', 0))
            orig_price_str = request.form.get('original_price', '').strip()
            orig_price = int(orig_price_str) if orig_price_str else None
            category_id = request.form.get('category_id', '').strip() or None
            badge = request.form.get('badge', '').strip()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'true'
            image_url = request.form.get('image_url', '').strip()

            if not name:
                flash('상품명을 입력해주세요.', 'warning')
                return redirect(url_for('admin.create_product'))

            # 슬러그 자동 생성
            if not slug:
                import re, time
                slug_base = re.sub(r'[^a-zA-Z0-9가-힣]+', '-', name).strip('-').lower()
                slug = f"{slug_base}-{int(time.time())}" if slug_base else f"product-{int(time.time())}"

            # 1. products 테이블에 신규 등록
            insert_data = {
                'name': name,
                'slug': slug,
                'price': price,
                'original_price': orig_price,
                'badge': badge,
                'description': description,
                'is_active': is_active
            }
            if category_id:
                insert_data['category_id'] = category_id

            p_res = db.table('products').insert(insert_data).execute()
            if not p_res.data:
                flash('상품 등록에 실패했습니다.', 'danger')
                return redirect(url_for('admin.create_product'))

            new_product = p_res.data[0]
            product_id = new_product['id']

            # 2. 대표 이미지 등록 (product_images)
            if image_url:
                try:
                    db.table('product_images').insert({
                        'product_id': product_id,
                        'image_url': image_url,
                        'is_primary': True,
                        'sort_order': 0
                    }).execute()
                except Exception as img_err:
                    logger.warning(f"상품 이미지 등록 오류: {img_err}")

            # 3. 기본 옵션(색상/사이즈/재고) 입력 처리
            opt_color = request.form.get('opt_color', '').strip() or '기본'
            opt_size = request.form.get('opt_size', '').strip() or 'Free'
            opt_stock = int(request.form.get('opt_stock', 50))

            try:
                db.table('product_options').insert({
                    'product_id': product_id,
                    'color': opt_color,
                    'size': opt_size,
                    'stock_quantity': opt_stock,
                    'stock': opt_stock,
                    'additional_price': 0
                }).execute()
            except Exception as opt_err:
                logger.warning(f"초기 옵션 등록 오류: {opt_err}")

            flash(f"신규 상품 [{name}]이(가) 성공적으로 등록되었습니다.", 'success')
            return redirect(url_for('admin.edit_product', product_id=product_id))

        except Exception as e:
            logger.error(f"신규 상품 등록 오류: {e}")
            flash(f"상품 등록 중 오류가 발생했습니다: {e}", 'danger')

    # GET 요청: 카테고리 목록 로드
    categories = []
    try:
        cat_res = db.table('categories').select('id, name').execute()
        categories = cat_res.data or []
    except Exception as e:
        logger.warning(f"카테고리 로드 오류: {e}")

    return render_template('admin/product_create.html', categories=categories)


@admin_bp.route('/products/<product_id>/options', methods=['POST'])
@admin_required
def add_product_option(product_id):
    """상품 옵션(색상, 사이즈, 재고) 신규 추가"""
    db = get_db()
    if not db:
        flash('데이터베이스에 연결할 수 없습니다.', 'danger')
        return redirect(url_for('admin.edit_product', product_id=product_id))

    try:
        color = request.form.get('color', '').strip()
        size = request.form.get('size', '').strip()
        stock = int(request.form.get('stock', 0))
        add_price = int(request.form.get('additional_price', 0))

        if not color or not size:
            flash('옵션의 색상(Color)과 사이즈(Size)를 모두 입력해주세요.', 'warning')
            return redirect(url_for('admin.edit_product', product_id=product_id))

        db.table('product_options').insert({
            'product_id': product_id,
            'color': color,
            'size': size,
            'stock': stock,
            'stock_quantity': stock,
            'additional_price': add_price
        }).execute()

        flash(f"옵션 [{color} / {size} (재고 {stock}개)]이(가) 추가되었습니다.", 'success')
    except Exception as e:
        logger.error(f"상품 옵션 추가 오류: {e}")
        flash(f"옵션 추가 중 오류가 발생했습니다: {e}", 'danger')

    return redirect(url_for('admin.edit_product', product_id=product_id))


@admin_bp.route('/products/<product_id>/options/<option_id>/update', methods=['POST'])
@admin_required
def update_product_option(product_id, option_id):
    """상품 특정 옵션의 색상, 사이즈, 재고 수정"""
    db = get_db()
    if not db:
        flash('데이터베이스에 연결할 수 없습니다.', 'danger')
        return redirect(url_for('admin.edit_product', product_id=product_id))

    try:
        color = request.form.get('color', '').strip()
        size = request.form.get('size', '').strip()
        stock = int(request.form.get('stock', 0))
        add_price = int(request.form.get('additional_price', 0))

        update_payload = {
            'stock': stock,
            'stock_quantity': stock,
            'additional_price': add_price
        }
        if color:
            update_payload['color'] = color
        if size:
            update_payload['size'] = size

        db.table('product_options').update(update_payload).eq('id', option_id).execute()
        flash('옵션 정보가 수정되었습니다.', 'success')
    except Exception as e:
        logger.error(f"상품 옵션 수정 오류: {e}")
        flash(f"옵션 수정 중 오류가 발생했습니다: {e}", 'danger')

    return redirect(url_for('admin.edit_product', product_id=product_id))


@admin_bp.route('/products/<product_id>/options/<option_id>/delete', methods=['POST'])
@admin_required
def delete_product_option(product_id, option_id):
    """상품 특정 옵션 삭제"""
    db = get_db()
    if not db:
        flash('데이터베이스에 연결할 수 없습니다.', 'danger')
        return redirect(url_for('admin.edit_product', product_id=product_id))

    try:
        db.table('product_options').delete().eq('id', option_id).execute()
        flash('해당 옵션이 삭제되었습니다.', 'info')
    except Exception as e:
        logger.error(f"상품 옵션 삭제 오류: {e}")
        flash(f"옵션 삭제 중 오류가 발생했습니다: {e}", 'danger')

    return redirect(url_for('admin.edit_product', product_id=product_id))


# ==============================================================================
# 3. 주문 관리 (Orders)
# ==============================================================================
ORDER_STATUS_MAP = {
    'pending': {'label': '주문 접수', 'badge': 'bg-warning-subtle text-warning border border-warning-subtle'},
    'paid': {'label': '결제 완료', 'badge': 'bg-success-subtle text-success border border-success-subtle'},
    'preparing': {'label': '상품 준비중', 'badge': 'bg-info-subtle text-info border border-info-subtle'},
    'shipping': {'label': '배송중', 'badge': 'bg-primary-subtle text-primary border border-primary-subtle'},
    'delivered': {'label': '배송 완료', 'badge': 'bg-secondary-subtle text-secondary border border-secondary-subtle'},
    'cancelled': {'label': '주문 취소', 'badge': 'bg-danger-subtle text-danger border border-danger-subtle'},
    'refunded': {'label': '환불', 'badge': 'bg-dark-subtle text-dark border border-dark-subtle'}
}


@admin_bp.route('/orders')
@admin_required
def orders():
    """관리자 주문 목록 조회 및 상태 필터링"""
    db = get_db()
    status_filter = request.args.get('status', '').strip()
    search_keyword = request.args.get('search', '').strip()

    orders_list = []
    status_counts = {
        'all': 0,
        'pending': 0,
        'paid': 0,
        'preparing': 0,
        'shipping': 0,
        'delivered': 0,
        'cancelled': 0,
        'refunded': 0
    }

    if db:
        try:
            # 1. 전체 주문 조회 (최신순)
            res = db.table('orders').select('*').order('created_at', desc=True).execute()
            all_orders = res.data or []

            # 상태별 카운트 계산
            status_counts['all'] = len(all_orders)
            for o in all_orders:
                st = o.get('status', '')
                if st in status_counts:
                    status_counts[st] += 1

            # 주문 번호 및 고객명, 사용자 ID 목록 수집
            order_ids = [o['id'] for o in all_orders if 'id' in o]
            user_ids = list({o['user_id'] for o in all_orders if o.get('user_id')})

            # 2. 관련 order_items 한 번에 일괄 조회하여 주문별 상품 정보 요약 매핑
            order_items_map = {}
            if order_ids:
                try:
                    items_res = db.table('order_items').select('order_id, product_name, quantity, option_info, subtotal').in_('order_id', order_ids).execute()
                    for it in (items_res.data or []):
                        oid = it.get('order_id')
                        if oid not in order_items_map:
                            order_items_map[oid] = []
                        order_items_map[oid].append(it)
                except Exception as ie:
                    logger.warning(f"주문 상품 일괄 조회 중 경고: {ie}")

            # 3. 관련 회원 정보(profiles) 일괄 조회
            user_profiles_map = {}
            if user_ids:
                try:
                    prof_res = db.table('profiles').select('id, email, full_name, role, grade').in_('id', user_ids).execute()
                    for p in (prof_res.data or []):
                        user_profiles_map[p['id']] = p
                except Exception as pe:
                    logger.warning(f"회원 프로필 일괄 조회 중 경고: {pe}")

            # 4. 각 주문별 상품 요약 및 주문 수량, 고객 정보 보강
            for o in all_orders:
                items = order_items_map.get(o['id'], [])
                total_qty = sum(int(it.get('quantity', 0)) for it in items)
                
                if items:
                    first_prod = items[0].get('product_name', '양산FC 상품')
                    if len(items) > 1:
                        product_summary = f"{first_prod} 외 {len(items) - 1}건"
                    else:
                        product_summary = first_prod
                else:
                    product_summary = "주문 상품 없음"

                u_prof = user_profiles_map.get(o.get('user_id'))
                user_display = (u_prof.get('full_name') if u_prof and u_prof.get('full_name') else '') or o.get('recipient_name') or '고객'
                user_email = u_prof.get('email') if u_prof else ''

                o['product_summary'] = product_summary
                o['total_quantity'] = total_qty
                o['user_display'] = user_display
                o['user_email'] = user_email
                o['user_grade'] = u_prof.get('grade', 'BRONZE') if u_prof else ''
                o['status_info'] = ORDER_STATUS_MAP.get(o.get('status'), {'label': o.get('status'), 'badge': 'bg-light text-dark'})

                # 필터링 적용
                if status_filter and o.get('status') != status_filter:
                    continue
                if search_keyword:
                    ord_num = str(o.get('order_number', ''))
                    recip = str(o.get('recipient_name', ''))
                    prod = str(o.get('product_summary', ''))
                    u_name = str(o.get('user_display', ''))
                    kw = search_keyword.lower()
                    if kw not in ord_num.lower() and kw not in recip.lower() and kw not in prod.lower() and kw not in u_name.lower():
                        continue

                orders_list.append(o)

        except Exception as e:
            logger.error(f"관리자 주문 목록 조회 오류: {e}")

    return render_template(
        'admin/orders.html',
        orders=orders_list,
        current_status=status_filter,
        search_keyword=search_keyword,
        status_counts=status_counts,
        status_map=ORDER_STATUS_MAP
    )


@admin_bp.route('/orders/<order_id>')
@admin_required
def order_detail(order_id):
    """관리자 주문 상세 내역 및 주문 상품 목록"""
    db = get_db()
    if not db:
        flash('데이터베이스에 연결할 수 없습니다.', 'danger')
        return redirect(url_for('admin.orders'))

    try:
        order_res = db.table('orders').select('*').eq('id', order_id).execute()
        if not order_res.data:
            flash('주문을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin.orders'))

        order = order_res.data[0]
        items_res = db.table('order_items').select('*').eq('order_id', order_id).execute()
        items = items_res.data or []

        # 주문 상품 총 수량 계산
        total_items_quantity = sum(int(it.get('quantity', 0)) for it in items)
        order['total_quantity'] = total_items_quantity
        order['status_info'] = ORDER_STATUS_MAP.get(order.get('status'), {'label': order.get('status'), 'badge': 'bg-light text-dark'})

        # 주문 고객의 프로필 확인
        user_profile = None
        if order.get('user_id'):
            p_res = db.table('profiles').select('*').eq('id', order.get('user_id')).execute()
            if p_res.data:
                user_profile = p_res.data[0]

        return render_template(
            'admin/order_detail.html',
            order=order,
            items=items,
            user_profile=user_profile,
            status_map=ORDER_STATUS_MAP
        )
    except Exception as e:
        logger.error(f"주문 상세 조회 오류: {e}")
        flash(f"주문 상세 조회 중 오류 발생: {e}", 'danger')
        return redirect(url_for('admin.orders'))


@admin_bp.route('/orders/<order_id>/status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    """
    주문 상태 업데이트 (주문 접수, 결제 완료, 상품 준비중, 배송중, 배송 완료, 주문 취소, 환불)
    - 취소(cancelled) 또는 환불(refunded) 상태로 변경 시 주문 상품의 옵션 재고를 자동으로 복구합니다.
    - 중복 복구 방지 로직은 order_service 모듈을 통해 통합 처리됩니다.
    """
    new_status = request.form.get('status', '').strip()
    refund_reason = request.form.get('reason', '').strip() or '관리자 직권 상태 변경'
    valid_statuses = list(ORDER_STATUS_MAP.keys())

    if new_status not in valid_statuses:
        flash('올바르지 않은 주문 상태입니다.', 'danger')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    db = get_db()
    if not db:
        flash('데이터베이스에 연결할 수 없습니다.', 'danger')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    try:
        # 취소 또는 환불 상태로 변경하는 경우 전용 서비스 함수 호출
        if new_status in ['cancelled', 'refunded']:
            success, msg, restored_cnt = restore_order_stock_and_record(
                db_client=db,
                order_id=order_id,
                target_status=new_status,
                reason=refund_reason,
                is_admin=True
            )
            flash(msg, 'success' if success else 'danger')
        else:
            # 기타 일반 배송/결제 상태 변경
            db.table('orders').update({'status': new_status}).eq('id', order_id).execute()
            label = ORDER_STATUS_MAP.get(new_status, {}).get('label', new_status)
            flash(f"주문 상태가 '{label}'(으)로 변경되었습니다.", 'success')

    except Exception as e:
        logger.error(f"주문 상태 변경 오류: {e}")
        flash(f"상태 변경 실패: {e}", 'danger')

    return redirect(url_for('admin.order_detail', order_id=order_id))


# ==============================================================================
# 4. 회원 관리 (Users / Customers)
# ==============================================================================
@admin_bp.route('/users')
@admin_required
def users():
    """가입 회원 목록 및 주문/구매 실적 현황"""
    db = get_db()
    users_list = []
    search_keyword = request.args.get('search', '').strip()

    if db:
        try:
            res = db.table('profiles').select('*').order('created_at', desc=True).execute()
            all_users = res.data or []

            for u in all_users:
                # 검색 필터
                if search_keyword:
                    email_str = u.get('email', '') or ''
                    name_str = u.get('full_name', '') or ''
                    if search_keyword.lower() not in email_str.lower() and search_keyword.lower() not in name_str.lower():
                        continue

                # 각 회원별 주문 수 및 누적 결제금액 계산
                order_cnt = 0
                calc_spent = 0
                try:
                    user_orders = db.table('orders').select('final_amount, status').eq('user_id', u.get('id')).execute()
                    if user_orders.data:
                        order_cnt = len(user_orders.data)
                        for uo in user_orders.data:
                            if uo.get('status') not in ['cancelled', 'refunded']:
                                calc_spent += int(float(uo.get('final_amount', 0)))
                except Exception:
                    pass

                users_list.append({
                    "id": u.get('id'),
                    "email": u.get('email'),
                    "name": u.get('full_name') or '고객',
                    "phone": u.get('phone_number') or '-',
                    "role": u.get('role', 'customer'),
                    "grade": u.get('grade', 'BRONZE'),
                    "order_count": order_cnt,
                    "total_spent": calc_spent or int(float(u.get('total_spent', 0) or 0)),
                    "created_at": u.get('created_at', '')
                })
        except Exception as e:
            logger.error(f"관리자 회원 목록 조회 오류: {e}")

    return render_template(
        'admin/users.html',
        users=users_list,
        search_keyword=search_keyword
    )


# ==============================================================================
# 5. 재고 관리 (Inventory)
# ==============================================================================
@admin_bp.route('/inventory')
@admin_required
def inventory():
    """관리자 재고 관리 (전체 옵션별 실시간 잔여 재고 현황)"""
    db = get_db()
    inventory_items = []
    status_filter = request.args.get('status', '').strip()
    search_keyword = request.args.get('search', '').strip()

    total_count = 0
    soldout_count = 0
    low_count = 0
    normal_count = 0

    if db:
        try:
            # product_options와 products JOIN 조회
            opts_res = db.table('product_options').select('id, product_id, color, size, stock, stock_quantity, additional_price, products(name, slug, is_active, category_id, categories(name))').order('product_id').execute()
            if opts_res.data:
                for row in opts_res.data:
                    p_info = row.get('products') or {}
                    cat_info = p_info.get('categories') or {}
                    p_name = p_info.get('name', '미확인 상품')
                    stk = row.get('stock')
                    if stk is None:
                        stk = row.get('stock_quantity', 0)
                    try:
                        stk_num = max(0, int(stk))
                    except:
                        stk_num = 0

                    total_count += 1
                    if stk_num == 0:
                        soldout_count += 1
                    elif stk_num <= 5:
                        low_count += 1
                    else:
                        normal_count += 1

                    if search_keyword and search_keyword.lower() not in p_name.lower():
                        continue

                    # 상태 필터 (품절, 부족, 정상)
                    if status_filter == 'soldout' and stk_num > 0:
                        continue
                    elif status_filter == 'low' and (stk_num == 0 or stk_num > 5):
                        continue
                    elif status_filter == 'normal' and stk_num <= 5:
                        continue

                    # 재고 상태 라벨 및 배지 스타일
                    if stk_num == 0:
                        status_label = "품절"
                        badge_class = "bg-danger text-white"
                    elif stk_num <= 5:
                        status_label = "재고 부족"
                        badge_class = "bg-warning-subtle text-warning-emphasis border border-warning-subtle"
                    else:
                        status_label = "정상"
                        badge_class = "bg-success-subtle text-success border border-success-subtle"

                    inventory_items.append({
                        "id": row.get('id'),
                        "product_id": row.get('product_id'),
                        "product_name": p_name,
                        "category": cat_info.get('name', '기타'),
                        "color": row.get('color'),
                        "size": row.get('size'),
                        "stock": stk_num,
                        "status_label": status_label,
                        "badge_class": badge_class,
                        "is_active": p_info.get('is_active', True)
                    })
        except Exception as e:
            logger.error(f"재고 관리 조회 오류: {e}")

    return render_template(
        'admin/inventory.html',
        inventory_items=inventory_items,
        current_status=status_filter,
        search_keyword=search_keyword,
        total_count=total_count,
        soldout_count=soldout_count,
        low_count=low_count,
        normal_count=normal_count
    )


@admin_bp.route('/inventory/adjust', methods=['POST'])
@admin_required
def adjust_inventory():
    """
    관리자 옵션별 재고 직접 수정 / 입고(+) / 출고(-)
    - mode: 'set' (직접 입력값으로 설정) 또는 'delta' (현재 재고에 delta 더하기)
    - stock_value: 변경할 수량 또는 가감할 수량 (+20, -5 등)
    """
    db = get_db()
    if not db:
        flash('데이터베이스에 연결할 수 없습니다.', 'danger')
        return redirect(url_for('admin.inventory'))

    option_id = request.form.get('option_id', '').strip()
    mode = request.form.get('mode', 'set').strip()
    val_str = request.form.get('stock_value', '').strip()

    if not option_id or not val_str:
        flash('옵션 및 재고 수량을 정확히 입력해주세요.', 'warning')
        return redirect(url_for('admin.inventory'))

    try:
        val = int(val_str)
        # 현재 옵션 정보 조회
        cur_res = db.table('product_options').select('id, product_id, color, size, stock, stock_quantity, products(name)').eq('id', option_id).execute()
        if not cur_res.data:
            flash('해당 옵션을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('admin.inventory'))

        cur_opt = cur_res.data[0]
        cur_stock = cur_opt.get('stock')
        if cur_stock is None:
            cur_stock = cur_opt.get('stock_quantity', 0)
        cur_stock = max(0, int(cur_stock))

        if mode == 'delta':
            # 입고(+) 또는 차감(-)
            new_stock = max(0, cur_stock + val)
            action_desc = f"입고 (+{val})" if val > 0 else f"조정 ({val})"
        else:
            # 직접 수량 지정
            new_stock = max(0, val)
            action_desc = "수동 지정"

        # stock 및 stock_quantity 동시 갱신
        import datetime
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        db.table('product_options').update({
            'stock': new_stock,
            'stock_quantity': new_stock,
            'updated_at': now_iso
        }).eq('id', option_id).execute()

        prod_name = cur_opt.get('products', {}).get('name', '')
        color = cur_opt.get('color', '')
        size = cur_opt.get('size', '')

        flash(f"[{prod_name} - {color}/{size}] 재고가 {cur_stock}개에서 {new_stock}개로 {action_desc} 완료되었습니다.", 'success')

    except ValueError:
        flash('수량은 숫자(정수)로 입력해주세요.', 'warning')
    except Exception as e:
        logger.error(f"재고 조정 오류: {e}")
        flash(f"재고 수정 중 오류가 발생했습니다: {e}", 'danger')

    # 이전 페이지 필터 유지
    status = request.form.get('status', '')
    search = request.form.get('search', '')
    return redirect(url_for('admin.inventory', status=status, search=search))


# ==============================================================================
# 6. 매출 관리 (Sales)
# ==============================================================================
@admin_bp.route('/sales')
@admin_required
def sales():
    """관리자 매출 분석 및 주문 정산 현황"""
    import datetime
    from collections import defaultdict
    db = get_db()

    sales_by_date = defaultdict(int)
    sales_by_status = defaultdict(int)
    total_revenue = 0
    total_valid_orders = 0
    today_revenue = 0
    today_str = datetime.date.today().isoformat()

    orders_list = []
    if db:
        try:
            res = db.table('orders').select('*').order('created_at', desc=True).execute()
            orders_list = res.data or []
            for o in orders_list:
                amt = int(float(o.get('final_amount', 0)))
                st = o.get('status', '')
                dt = str(o.get('created_at', ''))[:10]

                if st not in ['cancelled', 'refunded']:
                    total_revenue += amt
                    total_valid_orders += 1
                    sales_by_date[dt] += amt
                    if dt == today_str:
                        today_revenue += amt
                sales_by_status[st] += amt
        except Exception as e:
            logger.error(f"매출 통계 조회 오류: {e}")

    return render_template(
        'admin/sales.html',
        total_revenue=total_revenue,
        total_valid_orders=total_valid_orders,
        today_revenue=today_revenue,
        sales_by_date=sorted(sales_by_date.items(), reverse=True),
        orders_list=orders_list[:15]
    )
