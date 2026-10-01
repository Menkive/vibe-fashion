# 장바구니 삭제 기능 구현 문서

## 🎯 구현 요약

**DELETE /cart/<cart_id>** API와 프론트엔드 Bootstrap 모달을 통한 장바구니 삭제 기능 완성

---

## 📋 요구사항 체크리스트

| # | 요구사항 | 상태 | 구현 내용 |
|---|---------|------|---------|
| 1️⃣ | DELETE /cart/<cart_id> API | ✅ | Supabase 테이블에서 아이템 삭제 |
| 2️⃣ | 로그인 검증 | ✅ | 비로그인 → 401 Unauthorized |
| 3️⃣ | 소유권 검증 | ✅ | 다른 사용자 cart_id → 403 Forbidden |
| 4️⃣ | Bootstrap 모달 | ✅ | "이 상품을 삭제하시겠습니까?" 확인 |
| 5️⃣ | 페이지 새로고침 없이 삭제 | ✅ | JavaScript fetch + DOM 업데이트 |
| 6️⃣ | 빈 장바구니 UI | ✅ | "장바구니가 비어있습니다" + 쇼핑 계속 버튼 |
| 7️⃣ | 토스트 알림 | ✅ | 삭제 완료 메시지 표시 |

---

## 🔧 백엔드 구현

### 파일: [app/routes/main.py](app/routes/main.py#L615-L680)

#### DELETE /cart/<cart_id> 엔드포인트

```python
@main_bp.route('/cart/<cart_id>', methods=['DELETE'])
def cart_delete(cart_id):
    """
    장바구니 아이템 삭제 API
    1. 로그인 검증
    2. 소유권 검증 (cart.user_id == user_id)
    3. 존재 여부 확인
    4. DELETE 실행
    5. 응답
    """
```

#### 검증 순서
1. **로그인 검증**: user_id 확인 → 없으면 401
2. **아이템 존재 확인**: cart_id 조회 → 없으면 404
3. **소유권 검증**: cart.user_id != user_id → 403
4. **삭제 실행**: DB에서 DELETE
5. **응답**: 200 + 삭제 완료 메시지

#### API 응답

**성공 (200 OK)**:
```json
{
  "success": true,
  "message": "'27시즌 홈 유니폼'이(가) 장바구니에서 삭제되었습니다.",
  "data": {
    "cart_id": "abc123-cart-id",
    "product_name": "27시즌 홈 유니폼"
  }
}
```

**에러 케이스**:
- 401: 로그인 필수
- 403: 접근 권한 없음
- 404: 장바구니 아이템 없음
- 500: 서버 오류

---

## 🎨 프론트엔드 구현

### 1️⃣ Bootstrap 모달 추가

**파일**: [app/templates/cart.html](app/templates/cart.html#L49-L68)

```html
<!-- 삭제 확인 모달 -->
<div class="modal fade" id="deleteConfirmModal" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content border-0 rounded-4">
            <div class="modal-header bg-light border-0">
                <h5 class="modal-title fw-bold">상품 삭제</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body py-4">
                <div class="d-flex align-items-center gap-3 mb-3">
                    <img id="deleteModalProductImage" src="" class="rounded-3" 
                         style="width: 60px; height: 60px; object-fit: cover;">
                    <div>
                        <h6 id="deleteModalProductName" class="fw-bold mb-1">상품명</h6>
                        <small id="deleteModalProductSize" class="text-muted">사이즈</small>
                    </div>
                </div>
                <p class="text-center text-secondary">
                    이 상품을 장바구니에서 삭제하시겠습니까?
                </p>
            </div>
            <div class="modal-footer border-0 gap-2">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
                <button type="button" class="btn btn-danger" id="btn-confirm-delete">삭제</button>
            </div>
        </div>
    </div>
</div>
```

**모달 특징**:
- ✅ 상품 이미지, 이름, 사이즈 표시
- ✅ 중앙 정렬 다이얼로그
- ✅ 취소/삭제 버튼

### 2️⃣ 삭제 버튼 바인딩

**파일**: [app/templates/cart.html](app/templates/cart.html#L128-L150)

```javascript
// 삭제 버튼 클릭
document.querySelectorAll('.btn-remove-item').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const idx = parseInt(btn.getAttribute('data-index'), 10);
        const item = items[idx];
        
        // 모달에 상품 정보 표시
        document.getElementById('deleteModalProductImage').src = item.image_url;
        document.getElementById('deleteModalProductName').textContent = item.name;
        document.getElementById('deleteModalProductSize').textContent = 
            `${item.category} - ${item.size}`;
        
        // 삭제 정보 저장 후 모달 표시
        pendingDeleteIndex = idx;
        pendingDeleteCartId = item.cart_id || null;
        deleteModal.show();
    });
});
```

### 3️⃣ 삭제 API 호출

**파일**: [app/templates/cart.html](app/templates/cart.html#L167-L220)

```javascript
// 삭제 확인 버튼 클릭
deleteConfirmBtn.addEventListener('click', async () => {
    if (pendingDeleteIndex === null) return;

    const items = CartManager.getItems();
    const item = items[pendingDeleteIndex];

    if (pendingDeleteCartId) {
        try {
            // DELETE 요청
            const response = await fetch(`/cart/${pendingDeleteCartId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (response.ok) {
                // 성공: 로컬 스토리지 + DOM 제거
                CartManager.removeItem(pendingDeleteIndex);
                renderCart();
                deleteModal.hide();
                
                // 토스트 알림
                showCartToast(
                    `'${item.name}'이(가) 장바구니에서 삭제되었습니다.`,
                    'success'
                );
            } else {
                // 에러 처리 (401, 403, 404, 500 등)
                handleDeleteError(response.status, data);
            }
        } catch (error) {
            showCartToast('네트워크 오류가 발생했습니다.', 'error');
        }
    } else {
        // cart_id 없으면 로컬만 삭제
        CartManager.removeItem(pendingDeleteIndex);
        renderCart();
        deleteModal.hide();
        showCartToast(`'${item.name}'이(가) 삭제되었습니다.`, 'success');
    }
});
```

### 4️⃣ 에러 처리

```javascript
if (response.status === 401) {
    showCartToast('로그인이 필요합니다.', 'error');
    window.location.href = '/auth/login';
} else if (response.status === 403) {
    showCartToast('접근 권한이 없습니다.', 'error');
} else if (response.status === 404) {
    // 서버에는 없지만 로컬에만 있는 경우 로컬 삭제
    CartManager.removeItem(pendingDeleteIndex);
    renderCart();
    deleteModal.hide();
} else {
    showCartToast(data.message || '삭제 실패', 'error');
}
```

### 5️⃣ 토스트 알림

```javascript
function showCartToast(message, type = 'info') {
    const toastHTML = `
        <div class="toast align-items-center text-white 
                    bg-${type === 'success' ? 'success' : 'danger'} border-0" 
             role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    // DOM에 추가 → Bootstrap Toast 표시 → 3초 후 자동 제거
}
```

### 6️⃣ 빈 장바구니 UI

**자동으로 처리됨** - `renderCart()` 함수에서:

```javascript
if (items.length === 0) {
    container.innerHTML = '';
    emptyView.classList.remove('d-none');  // "장바구니가 비어있습니다" 표시
    subtotalEl.textContent = '0원';
    totalEl.textContent = '0원';
    checkoutBtn.disabled = true;
    return;
}
```

---

## 🔄 데이터 흐름

```
1. 사용자 "삭제" 버튼 클릭
   ↓
2. 상품 정보를 모달에 표시
   ↓
3. 사용자 "삭제" 확인
   ↓
4. DELETE /cart/{cart_id} API 호출
   ↓
5. API 응답 처리
   ├─ 성공 (200) → 로컬 스토리지 제거 + DOM 업데이트
   ├─ 401 → 로그인 페이지 리다이렉트
   ├─ 403 → "접근 권한 없음" 토스트
   ├─ 404 → 로컬만 삭제 (서버 데이터 불일치)
   └─ 500 → 오류 메시지 표시
   ↓
6. 모달 닫기
   ↓
7. 장바구니 다시 렌더링 (즉시, 새로고침 없음)
   ↓
8. 토스트 알림 표시
   ↓
9. 장바구니가 비면 "빈 장바구니" UI 표시
```

---

## 📦 로컬 스토리지 구조 업데이트

### CartManager 변경사항

**파일**: [app/static/js/store.js](app/static/js/store.js#L18-L51)

```javascript
addItem(product, size, quantity = 1, optionId = null, color = null, cartId = null) {
    // ... 로직 ...
    
    // cartId 추가 저장
    items.push({
        id: product.id,
        cart_id: cartId || null,  // ← 새로 추가
        option_id: optionId,
        name: product.name,
        price: Number(product.price),
        image_url: product.image_url || product.thumbnail_url,
        category: product.category,
        color: color || '',
        size: size,
        quantity: Number(quantity)
    });
}
```

### 로컬 스토리지 예시

```json
{
  "yangsan_fc_cart_v1": [
    {
      "id": "prod-001",
      "cart_id": "abc123-def456",  // ← DB에 저장된 cart_id
      "option_id": "opt-blue-m",
      "name": "27시즌 홈 유니폼",
      "price": 109000,
      "image_url": "...",
      "category": "유니폼",
      "color": "양산 블루",
      "size": "M",
      "quantity": 2
    }
  ]
}
```

---

## 🌐 API 호출 예시

```bash
# 삭제 요청
curl -X DELETE http://localhost:5000/cart/abc123-cart-id \
  -H "Content-Type: application/json"

# 응답
{
  "success": true,
  "message": "'27시즌 홈 유니폼'이(가) 장바구니에서 삭제되었습니다.",
  "data": {
    "cart_id": "abc123-cart-id",
    "product_name": "27시즌 홈 유니폼"
  }
}
```

---

## ✅ 완성 체크리스트

### 백엔드
- ✅ DELETE /cart/<cart_id> 구현
- ✅ 로그인 검증 (401)
- ✅ 소유권 검증 (403)
- ✅ 존재 여부 검증 (404)
- ✅ 에러 처리 및 로깅

### 프론트엔드
- ✅ Bootstrap 모달 추가
- ✅ 삭제 버튼 바인딩
- ✅ API 호출 (async/await)
- ✅ 토스트 알림
- ✅ DOM 즉시 업데이트 (새로고침 없음)
- ✅ 빈 장바구니 UI
- ✅ 에러 처리 (401, 403, 404, 500)

### 데이터 동기화
- ✅ CartManager.addItem에 cartId 매개변수 추가
- ✅ product_detail.html에서 cart_id 저장
- ✅ 로컬 스토리지에 cart_id 유지

---

## 🚀 사용자 경험 (UX)

1. **삭제 아이콘** 클릭
   ```
   장바구니 아이템 → [X 삭제] 버튼 클릭
   ```

2. **모달 팝업** 표시
   ```
   ┌─────────────────────────┐
   │      상품 삭제          │
   ├─────────────────────────┤
   │ [이미지] 상품명         │
   │ 이 상품을 삭제합니까?   │
   ├─────────────────────────┤
   │  [취소]  [삭제]        │
   └─────────────────────────┘
   ```

3. **[삭제] 클릭**
   - 백그라운드에서 API 호출 (0.5초)
   - 모달 자동 닫기
   - 장바구니 아이템 즉시 제거
   - 금액 자동 계산
   - 토스트 메시지 표시 (3초)

4. **빈 장바구니**
   ```
   🛒 장바구니가 비어있습니다
   양산시민축구단의 다양한...
   [상품 보러가기] 버튼
   ```

---

## 📝 코드 리뷰 포인트

### 보안
- ✅ 서버에서 user_id 검증 (세션 기반)
- ✅ cart.user_id == user_id 비교
- ✅ CORS 안전성 (Supabase 라우팅)

### 안정성
- ✅ 예외 처리 (try-catch)
- ✅ 에러 응답 코드 구분
- ✅ 로컬-서버 동기화 전략 (404 시 로컬 삭제)

### UX
- ✅ 즉시 반응 (새로고침 없음)
- ✅ 명확한 피드백 (모달, 토스트)
- ✅ 실패 시 사용자 안내

---

## 🎯 다음 단계 (선택사항)

1. **개선 사항**
   - 일괄 삭제 기능 (선택 삭제)
   - 실행 취소 기능 (UNDO)
   - 삭제 애니메이션 (fade-out)

2. **확장 기능**
   - 결제 기능
   - 배송지 관리
   - 주문 이력 추적
