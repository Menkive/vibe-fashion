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
    """관리자 메인 대시보드 - 핵심 KPI 및 최근 주문 현황"""
    db = get_db()
    
    total_sales = 0
    total_orders_count = 0
    total_products_count = 0
    total_users_count = 0
    recent_orders = []
    
    if db:
        try:
            # 1) 전체 주문 조회 및 매출 합계 계산
            orders_res = db.table('orders').select('*').order('created_at', desc=True).execute()
            if orders_res.data:
                total_orders_count = len(orders_res.data)
                recent_orders = orders_res.data[:7]
                for o in orders_res.data:
                    # 취소/환불 제외한 유효 주문 금액 합산
                    if o.get('status') not in ['cancelled', 'refunded']:
                        try:
                            total_sales += int(float(o.get('final_amount', 0)))
                        except (ValueError, TypeError):
                            pass

            # 2) 등록 상품 수
            products_res = db.table('products').select('id', count='exact').execute()
            total_products_count = products_res.count if products_res.count is not None else len(products_res.data or [])

            # 3) 회원 수
            users_res = db.table('profiles').select('id', count='exact').execute()
            total_users_count = users_res.count if users_res.count is not None else len(users_res.data or [])

        except Exception as e:
            logger.error(f"관리자 대시보드 통계 조회 오류: {e}")
    else:
        # DB 연결 실패 시 기본 폴백
        total_products_count = len(INITIAL_PRODUCTS)
        total_sales = 1358000
        total_orders_count = 5
        total_users_count = 3

    return render_template(
        'admin/dashboard.html',
        total_sales=total_sales,
        total_orders_count=total_orders_count,
        total_products_count=total_products_count,
        total_users_count=total_users_count,
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

            update_data = {
                'name': name,
                'price': price,
                'original_price': orig_price,
                'badge': badge,
                'description': description,
                'is_active': is_active
            }

            db.table('products').update(update_data).eq('id', product_id).execute()
            flash(f"상품 [{name}] 정보가 성공적으로 수정되었습니다.", 'success')
            return redirect(url_for('admin.products'))
        except Exception as e:
            logger.error(f"상품 정보 수정 오류: {e}")
            flash(f"수정 중 오류가 발생했습니다: {e}", 'danger')

    # GET 요청: 상품 상세 데이터 로드
    product_res = db.table('products').select('*, categories(name)').eq('id', product_id).execute()
    if not product_res.data:
        flash('존재하지 않는 상품입니다.', 'danger')
        return redirect(url_for('admin.products'))

    product = product_res.data[0]
    options_res = db.table('product_options').select('*').eq('product_id', product_id).execute()
    options = options_res.data or []

    return render_template('admin/product_edit.html', product=product, options=options)


# ==============================================================================
# 3. 주문 관리 (Orders)
# ==============================================================================
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
        'paid': 0,
        'preparing': 0,
        'shipping': 0,
        'delivered': 0,
        'cancelled': 0
    }

    if db:
        try:
            # 전체 주문 조회
            res = db.table('orders').select('*').order('created_at', desc=True).execute()
            all_orders = res.data or []

            # 상태별 카운트 계산
            status_counts['all'] = len(all_orders)
            for o in all_orders:
                st = o.get('status', '')
                if st in status_counts:
                    status_counts[st] += 1

            # 필터링 적용
            for o in all_orders:
                if status_filter and o.get('status') != status_filter:
                    continue
                if search_keyword:
                    ord_num = str(o.get('order_number', ''))
                    recip = str(o.get('recipient_name', ''))
                    if search_keyword.lower() not in ord_num.lower() and search_keyword.lower() not in recip.lower():
                        continue
                orders_list.append(o)

        except Exception as e:
            logger.error(f"관리자 주문 목록 조회 오류: {e}")

    return render_template(
        'admin/orders.html',
        orders=orders_list,
        current_status=status_filter,
        search_keyword=search_keyword,
        status_counts=status_counts
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
            user_profile=user_profile
        )
    except Exception as e:
        logger.error(f"주문 상세 조회 오류: {e}")
        flash(f"주문 상세 조회 중 오류 발생: {e}", 'danger')
        return redirect(url_for('admin.orders'))


@admin_bp.route('/orders/<order_id>/status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    """주문 상태 업데이트 (결제완료, 배송준비, 배송중, 배송완료, 취소)"""
    new_status = request.form.get('status', '').strip()
    valid_statuses = ['pending', 'paid', 'preparing', 'shipping', 'delivered', 'cancelled', 'refunded']

    if new_status not in valid_statuses:
        flash('올바르지 않은 주문 상태입니다.', 'danger')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    db = get_db()
    if db:
        try:
            db.table('orders').update({'status': new_status}).eq('id', order_id).execute()
            status_labels = {
                'pending': '결제대기',
                'paid': '결제완료',
                'preparing': '배송준비중',
                'shipping': '배송중',
                'delivered': '배송완료',
                'cancelled': '주문취소',
                'refunded': '환불완료'
            }
            flash(f"주문 상태가 '{status_labels.get(new_status, new_status)}'(으)로 변경되었습니다.", 'success')
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
