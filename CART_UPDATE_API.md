# 장바구니 수량 변경 API 문서

## 엔드포인트

```
PATCH /cart/<cart_id>
```

---

## 요청 (Request)

### Method
`PATCH`

### URL 파라미터
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| `cart_id` | string (UUID) | ✅ | 변경할 장바구니 아이템의 ID |

### Request Body (JSON)
```json
{
  "quantity": 2
}
```

| 파라미터 | 타입 | 필수 | 설명 | 제약 조건 |
|---------|------|-----|------|---------|
| `quantity` | integer | ✅ | 변경할 수량 | >= 1, <= 상품 재고 |

### 예시 cURL 요청

```bash
# 성공 케이스
curl -X PATCH http://localhost:5000/cart/12345abc-1234-1234-1234-123456789012 \
  -H "Content-Type: application/json" \
  -d '{"quantity": 2}'

# 수량 증가
curl -X PATCH http://localhost:5000/cart/cart-id-here \
  -H "Content-Type: application/json" \
  -d '{"quantity": 5}'

# 수량 감소
curl -X PATCH http://localhost:5000/cart/cart-id-here \
  -H "Content-Type: application/json" \
  -d '{"quantity": 1}'
```

---

## 응답 (Response)

### ✅ 성공 응답 (200 OK)

```json
{
  "success": true,
  "message": "장바구니 수량이 변경되었습니다.",
  "data": {
    "cart_id": "12345abc-1234-1234-1234-123456789012",
    "product_id": "prod-id-123",
    "product_name": "27시즌 홈 유니폼",
    "price": 109000,
    "quantity": 2,
    "subtotal": 218000
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `success` | boolean | 요청 성공 여부 |
| `message` | string | 성공 메시지 |
| `data.cart_id` | string | 장바구니 아이템 ID |
| `data.product_id` | string | 상품 ID |
| `data.product_name` | string | 상품명 |
| `data.price` | integer | 단가 (원) |
| `data.quantity` | integer | 변경된 수량 |
| `data.subtotal` | integer | 소계 (price × quantity) |

---

## ❌ 에러 응답

### 1️⃣ 로그인 필수 (401 Unauthorized)
```json
{
  "success": false,
  "message": "로그인이 필요한 서비스입니다."
}
```
**원인**: 세션에 user_id가 없을 때
**해결**: `/auth/login` 또는 OAuth 로그인 페이지로 리다이렉트

---

### 2️⃣ 잘못된 quantity 입력 (400 Bad Request)

#### A. quantity 누락
```json
{
  "success": false,
  "message": "수량(quantity)은 필수입니다."
}
```

#### B. quantity가 숫자가 아님
```json
{
  "success": false,
  "message": "올바른 수량을 입력해 주세요."
}
```

#### C. quantity < 1
```json
{
  "success": false,
  "message": "수량은 1개 이상이어야 합니다."
}
```

**테스트**:
```bash
# quantity 필수
curl -X PATCH http://localhost:5000/cart/cart-id-here \
  -H "Content-Type: application/json" \
  -d '{}'

# quantity가 문자열
curl -X PATCH http://localhost:5000/cart/cart-id-here \
  -H "Content-Type: application/json" \
  -d '{"quantity": "abc"}'

# quantity가 0 이하
curl -X PATCH http://localhost:5000/cart/cart-id-here \
  -H "Content-Type: application/json" \
  -d '{"quantity": 0}'
```

---

### 3️⃣ 장바구니 아이템 없음 (404 Not Found)
```json
{
  "success": false,
  "message": "존재하지 않는 장바구니 아이템입니다."
}
```
**원인**: 해당 cart_id가 데이터베이스에 없을 때
**테스트**:
```bash
curl -X PATCH http://localhost:5000/cart/nonexistent-id \
  -H "Content-Type: application/json" \
  -d '{"quantity": 2}'
```

---

### 4️⃣ 접근 권한 없음 (403 Forbidden)
```json
{
  "success": false,
  "message": "접근 권한이 없습니다."
}
```
**원인**: cart_id가 다른 사용자의 장바구니 아이템일 때
**설명**: 
- user_id1이 로그인한 상태에서 user_id2의 cart_id를 수정하려고 시도하면 거절됨
- 장바구니의 소유권을 엄격히 검증하여 보안 유지

---

### 5️⃣ 재고 부족 (400 Bad Request)
```json
{
  "success": false,
  "message": "재고가 부족합니다 (현재 5개)"
}
```
**원인**: 요청 수량 > 상품 옵션의 재고
**동작**: DB UPDATE를 수행하지 않음 (원자성 보장)

**테스트 시나리오**:
```bash
# 상품의 현재 재고가 3개인데 5개를 요청
curl -X PATCH http://localhost:5000/cart/cart-id-here \
  -H "Content-Type: application/json" \
  -d '{"quantity": 5}'

# 응답: {"success": false, "message": "재고가 부족합니다 (현재 3개)"}
```

---

### 6️⃣ 데이터베이스 연결 실패 (500 Internal Server Error)
```json
{
  "success": false,
  "message": "데이터베이스 연결에 실패했습니다."
}
```
**원인**: Supabase 클라이언트 초기화 실패
**해결**: 환경 변수 (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) 확인

---

### 7️⃣ 서버 예외 (500 Internal Server Error)
```json
{
  "success": false,
  "message": "장바구니 수량 변경 중 오류가 발생했습니다: [상세 오류]"
}
```
**원인**: 예기치 않은 서버 오류
**해결**: 서버 로그 확인 (`logger.error`)

---

## 📋 API 검증 체크리스트

### 1️⃣ 로그인 검증 (401)
- ✅ 세션에 user_id 없음 → 401 반환
- ✅ Naver OAuth 로그인 후 → 정상 작동

### 2️⃣ Quantity 검증 (400)
- ✅ quantity 필수 입력
- ✅ quantity >= 1
- ✅ quantity는 정수 타입

### 3️⃣ Cart 소유권 검증 (403, 404)
- ✅ 존재하지 않는 cart_id → 404
- ✅ 다른 사용자의 cart_id → 403

### 4️⃣ 재고 검증 (400)
- ✅ 요청 수량 > 재고 → 에러 반환
- ✅ UPDATE 미수행 (원자성 보장)

### 5️⃣ DB 업데이트 (200)
- ✅ carts 테이블의 quantity UPDATE
- ✅ updated_at을 now()로 설정

### 6️⃣ Subtotal 계산 (200)
- ✅ products 테이블에서 price 조회
- ✅ subtotal = price × quantity 계산
- ✅ 응답에 포함

---

## 🔄 통합 동작 흐름

```
1. 클라이언트 요청 → PATCH /cart/<cart_id> + {quantity: N}
   ↓
2. 로그인 검증 → user_id 확인 (없으면 401)
   ↓
3. Quantity 검증 → >= 1 && 정수 (아니면 400)
   ↓
4. Cart 소유권 검증 → cart.user_id == user_id? (아니면 403, 없으면 404)
   ↓
5. 재고 검증 → quantity <= product_options.stock? (아니면 400 에러 반환)
   ↓
6. DB UPDATE → carts.quantity = N, updated_at = now()
   ↓
7. Subtotal 계산 → products.price × quantity
   ↓
8. 응답 반환 → 200 + 모든 데이터
```

---

## 💡 프론트엔드 통합 예시 (JavaScript)

```javascript
// 장바구니 수량 변경 함수
async function updateCartQuantity(cartId, newQuantity) {
  try {
    const response = await fetch(`/cart/${cartId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        quantity: newQuantity
      })
    });

    const data = await response.json();

    if (response.ok) {
      // 성공
      console.log('✅ 수량 변경 완료:', data.data);
      console.log(`₩${data.data.price} × ${data.data.quantity} = ₩${data.data.subtotal}`);
      
      // UI 업데이트
      updateCartItemUI(cartId, data.data);
      
      // Toast 메시지
      showToast('장바구니 수량이 변경되었습니다');
    } else {
      // 에러 처리
      if (response.status === 401) {
        // 로그인 페이지로 리다이렉트
        window.location.href = '/auth/login';
      } else if (response.status === 403) {
        showError('접근 권한이 없습니다');
      } else if (response.status === 404) {
        showError('존재하지 않는 상품입니다');
      } else {
        showError(data.message || '수량 변경 실패');
      }
    }
  } catch (error) {
    console.error('❌ 오류:', error);
    showError('네트워크 오류가 발생했습니다');
  }
}

// 사용 예시
document.getElementById('quantity-input').addEventListener('change', (e) => {
  const newQty = parseInt(e.target.value);
  const cartId = e.target.dataset.cartId;
  
  if (newQty >= 1) {
    updateCartQuantity(cartId, newQty);
  }
});
```

---

## 🧪 테스트 데이터

### 성공 케이스
```json
{
  "cart_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "auth_user_123",
  "product_id": "prod_uniform_01",
  "option_id": "opt_blue_m",
  "quantity_before": 1,
  "quantity_after": 3,
  "price": 109000,
  "expected_subtotal": 327000,
  "stock": 50
}
```

### 실패 케이스 (재고 부족)
```json
{
  "cart_id": "550e8400-e29b-41d4-a716-446655440000",
  "quantity_request": 10,
  "available_stock": 3,
  "expected_error": "재고가 부족합니다 (현재 3개)"
}
```

### 권한 없음 케이스
```json
{
  "cart_id": "550e8400-e29b-41d4-a716-446655440000",
  "cart_owner_user_id": "other_user_456",
  "request_user_id": "my_user_123",
  "expected_error": "접근 권한이 없습니다"
}
```
