// static/js/store.js - 양산시민축구단 공식 스토어 클라이언트 장바구니 및 유틸리티

const CartManager = {
    STORAGE_KEY: 'yangsan_fc_cart_v1',

    getItems() {
        try {
            const data = JSON.parse(localStorage.getItem(this.STORAGE_KEY)) || [];
            
            // 데이터 유효성 검사 및 정리
            if (!Array.isArray(data)) {
                console.warn('[CartManager] 장바구니 데이터가 배열이 아닙니다. 초기화합니다.');
                localStorage.removeItem(this.STORAGE_KEY);
                return [];
            }
            
            // 각 항목의 필수 필드 검증
            const validItems = data.filter(item => {
                return item && 
                       typeof item === 'object' &&
                       item.id && 
                       item.name && 
                       typeof item.quantity === 'number' && 
                       item.quantity > 0;
            });
            
            // corrupted 항목이 있었으면 정리된 데이터 저장
            if (validItems.length !== data.length) {
                console.warn(`[CartManager] 손상된 항목 ${data.length - validItems.length}개 제거됨`);
                if (validItems.length > 0) {
                    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(validItems));
                } else {
                    localStorage.removeItem(this.STORAGE_KEY);
                }
            }
            
            return validItems;
        } catch (e) {
            console.error('장바구니 로드 실패:', e);
            // corrupted 데이터 제거
            localStorage.removeItem(this.STORAGE_KEY);
            return [];
        }
    },

    saveItems(items) {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
        this.updateBadge();
    },

    addItem(product, size, quantity = 1, optionId = null, color = null, cartId = null) {
        if (!size) {
            alert('사이즈를 선택해주세요.');
            return false;
        }

        const items = this.getItems();
        // optionId가 있는 경우 optionId 기준, 없으면 id + size 기준 식별
        const existingIndex = items.findIndex(item => {
            if (optionId && item.option_id) {
                return item.option_id === optionId;
            }
            return item.id === product.id && item.size === size && (color ? item.color === color : true);
        });

        if (existingIndex > -1) {
            items[existingIndex].quantity += Number(quantity);
            if (optionId) items[existingIndex].option_id = optionId;
            if (color) items[existingIndex].color = color;
            if (cartId) items[existingIndex].cart_id = cartId;
        } else {
            items.push({
                id: product.id,
                cart_id: cartId || null,
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

        this.saveItems(items);
        const optLabel = color ? `${color} / ${size}` : size;
        this.showToast(`${product.name} (${optLabel}) ${quantity}개가 장바구니에 담겼습니다.`);
        return true;
    },

    updateQuantity(index, quantity) {
        const items = this.getItems();
        if (items[index]) {
            const newQty = parseInt(quantity, 10);
            if (newQty <= 0) {
                return this.removeItem(index);
            }
            items[index].quantity = newQty;
            this.saveItems(items);
        }
    },

    removeItem(index) {
        const items = this.getItems();
        items.splice(index, 1);
        this.saveItems(items);
    },

    clearCart() {
        localStorage.removeItem(this.STORAGE_KEY);
        this.updateBadge();
    },

    getTotalPrice() {
        try {
            const items = this.getItems();
            return items.reduce((total, item) => {
                const price = parseInt(item.price, 10) || 0;
                const qty = parseInt(item.quantity, 10) || 0;
                return total + (Math.max(0, price) * Math.max(0, qty));  // 음수 방지
            }, 0);
        } catch (e) {
            console.error('총 가격 계산 오류:', e);
            return 0;
        }
    },

    getTotalCount() {
        try {
            const items = this.getItems();
            return items.reduce((count, item) => {
                const qty = parseInt(item.quantity, 10) || 0;
                return count + Math.max(0, qty);  // 음수 방지
            }, 0);
        } catch (e) {
            console.error('총 수량 계산 오류:', e);
            return 0;
        }
    },

    updateBadge() {
        try {
            const count = this.getTotalCount();
            const badges = document.querySelectorAll('.cart-count');
            
            if (badges.length === 0) {
                console.warn('[CartManager] 장바구니 뱃지를 찾을 수 없습니다.');
                return;
            }
            
            badges.forEach(b => {
                // 뱃지 숫자 업데이트
                b.textContent = Math.max(0, count);  // 음수 방지
                
                // 뱃지 표시/숨김 처리
                if (count > 0) {
                    b.style.display = 'inline-block';
                } else {
                    b.style.display = 'none';
                    b.textContent = '';  // count = 0일 때 텍스트도 비우기
                }
            });
            
            console.log(`[CartManager] 뱃지 업데이트: ${count}개`);
        } catch (e) {
            console.error('뱃지 업데이트 오류:', e);
        }
    },

    showToast(message) {
        // 기존 토스트 제거
        const existingToast = document.getElementById('store-toast');
        if (existingToast) existingToast.remove();

        const toastEl = document.createElement('div');
        toastEl.id = 'store-toast';
        toastEl.className = 'store-floating-toast';
        toastEl.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <i class="bi bi-check-circle-fill text-warning fs-5"></i>
                <div class="small fw-semibold text-white">${message}</div>
            </div>
            <a href="/cart" class="btn btn-sm btn-outline-warning ms-3 py-0 px-2 small">장바구니 이동</a>
        `;
        document.body.appendChild(toastEl);

        setTimeout(() => {
            toastEl.classList.add('show');
        }, 10);

        setTimeout(() => {
            toastEl.classList.remove('show');
            setTimeout(() => toastEl.remove(), 300);
        }, 3500);
    },

    // 로그아웃 시 호출: localStorage 정리
    logout() {
        this.clearCart();
        console.log('[CartManager] 로그아웃: 장바구니 데이터 정리 완료');
    }
};

// 페이지 로드 시 뱃지 초기화 및 다크모드 설정
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Store] 페이지 초기화 시작');
    
    // 장바구니 뱃지 초기화
    setTimeout(() => {
        CartManager.updateBadge();
    }, 100);  // 약간의 지연으로 DOM 안정화 보장
    
    // 다크모드 초기화
    initTheme();
    
    console.log('[Store] 페이지 초기화 완료');
});

// 다크모드 토글 기능
function initTheme() {
    const savedTheme = localStorage.getItem('yangsan_theme') || 'light';
    setTheme(savedTheme);

    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
            localStorage.setItem('yangsan_theme', newTheme);
        });
    }
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('theme-toggle-icon');
    if (icon) {
        if (theme === 'dark') {
            icon.className = 'bi bi-sun-fill text-warning';
        } else {
            icon.className = 'bi bi-moon-stars-fill text-white-50';
        }
    }
}
