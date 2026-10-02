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
        response = db_client.rpc('restore_order_stock', {
            'p_order_id': order_id,
            'p_target_status': target_status,
            'p_reason': reason,
            'p_is_admin': is_admin
        }).execute()
        result = response.data
        if isinstance(result, list):
            result = result[0] if result else None
        if not isinstance(result, dict):
            logger.error("재고 복구 RPC가 예상하지 못한 응답을 반환했습니다: %r", result)
            return False, "재고 복구 처리 결과를 확인할 수 없습니다.", 0

        return (
            bool(result.get('success')),
            str(result.get('message') or "주문 재고 복구 처리를 완료하지 못했습니다."),
            int(result.get('restored_count') or 0)
        )
    except Exception as e:
        logger.error("주문 취소/환불 RPC 처리 오류: %s", e)
        return False, "주문 취소 처리에 실패했습니다. 데이터베이스 마이그레이션 적용 여부를 확인해 주세요.", 0
