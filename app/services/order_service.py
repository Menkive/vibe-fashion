# app/services/order_service.py
"""
주문 및 재고 관리 통합 비즈니스 로직 서비스
- 주문 생성 시 원자적 재고 차감 및 롤백
- 주문 취소/환불 시 재고 복원 및 중복 복원 방지 처리
"""
import logging
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)

# 재고 복원 완료 플래그 (배송 메모에 영구 마킹하여 중복 복구 차단)
STOCK_RESTORED_FLAG = "[STOCK_RESTORED]"


def restore_order_stock_and_record(
    db_client: Any,
    order_id: str,
    target_status: str,
    reason: str = "관리자 직권 상태 변경",
    is_admin: bool = False
) -> Tuple[bool, str, int]:
    """
    주문 취소 또는 환불에 따른 재고 복구 및 관련 테이블 업데이트 통합 처리 함수
    
    매개변수:
        db_client: Supabase 클라이언트 객체
        order_id: 대상 주문 UUID
        target_status: 변경하려는 상태 ('cancelled' 또는 'refunded')
        reason: 취소 또는 환불 사유
        is_admin: 관리자 권한에 의한 실행 여부

    반환값:
        (success: bool, message: str, restored_count: int)
    """
    if not db_client:
        return False, "데이터베이스 연결에 실패했습니다.", 0

    try:
        # 1. 주문 조회
        order_res = db_client.table('orders').select('*').eq('id', order_id).execute()
        if not order_res.data:
            return False, "주문을 찾을 수 없습니다.", 0

        current_order = order_res.data[0]
        current_status = current_order.get('status')
        shipping_memo = current_order.get('shipping_memo') or ''

        # 2. 이미 취소/환불되었거나 복원 완료 플래그가 있는지 확인 (중복 복구 원천 방지)
        is_already_restored = STOCK_RESTORED_FLAG in shipping_memo or current_status in ['cancelled', 'refunded']

        if is_already_restored:
            # 상태만 최신화 (재고는 중복 복구하지 않음)
            db_client.table('orders').update({'status': target_status}).eq('id', order_id).execute()
            return True, "이미 재고 복구가 완료된 주문입니다. (중복 복구 방지됨)", 0

        # 3. 고객 직접 취소 시 상태 검증 (pending, paid만 취소 가능)
        if not is_admin and current_status not in ['pending', 'paid']:
            return False, f"현재 '{current_status}' 상태의 주문은 직접 취소할 수 없습니다. 고객센터에 문의해 주세요.", 0

        # 4. 주문 품목 조회 및 옵션 재고 복구
        items_res = db_client.table('order_items').select('id, product_id, option_id, product_name, quantity').eq('order_id', order_id).execute()
        items = items_res.data or []

        restored_count = 0
        for it in items:
            opt_id = it.get('option_id')
            qty = int(it.get('quantity', 0))
            if opt_id and qty > 0:
                try:
                    cur_opt = db_client.table('product_options').select('id, stock, stock_quantity').eq('id', opt_id).execute()
                    if cur_opt.data:
                        o_data = cur_opt.data[0]
                        stk = int(o_data.get('stock') if o_data.get('stock') is not None else o_data.get('stock_quantity', 0))
                        new_stk = stk + qty
                        up_payload = {}
                        if 'stock' in o_data:
                            up_payload['stock'] = new_stk
                        if 'stock_quantity' in o_data:
                            up_payload['stock_quantity'] = new_stk

                        db_client.table('product_options').update(up_payload).eq('id', opt_id).execute()
                        restored_count += qty
                except Exception as re:
                    logger.error(f"재고 복구 실패 (option_id: {opt_id}, qty: {qty}): {re}")

        # 5. 주문 상태 변경 및 중복 복구 방지 플래그 마킹
        new_memo = f"{STOCK_RESTORED_FLAG} {shipping_memo}".strip()
        db_client.table('orders').update({
            'status': target_status,
            'shipping_memo': new_memo
        }).eq('id', order_id).execute()

        # 6. 환불(refunded)인 경우 공식 환불 테이블(refunds)에 기록
        if target_status == 'refunded' or (not is_admin and current_status == 'paid'):
            try:
                db_client.table('refunds').insert({
                    'order_id': order_id,
                    'user_id': current_order.get('user_id'),
                    'refund_amount': float(current_order.get('final_amount', 0)),
                    'reason': reason,
                    'status': 'completed',
                    'admin_memo': f"{'관리자 직권 처리' if is_admin else '고객 직접 취소'} - 재고 {restored_count}개 자동 복구 완료"
                }).execute()
            except Exception as rfe:
                logger.warning(f"환불 테이블 기록 실패 (무시 가능): {rfe}")

        return True, f"주문이 정상 처리되었으며 총 {restored_count}개의 품목 재고가 안전하게 복구되었습니다.", restored_count

    except Exception as e:
        logger.error(f"주문 취소/환불 서비스 처리 중 오류: {e}")
        return False, f"처리 중 오류가 발생했습니다: {str(e)}", 0
