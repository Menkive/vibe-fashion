// static/js/store.js - 양산시민축구단 공식 스토어 클라이언트 장바구니 및 유틸리티

window.CartManager = {
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

    addItem(product, size, quantity = 1, optionId = null, color = null, cartId = null, customOptions = {}, unitPrice = null) {
        if (!size) {
            alert('사이즈를 선택해주세요.');
            return false;
        }

        const items = this.getItems();
        const identityKey = options => {
            const value = options || {};
            return JSON.stringify({
                patch: value.patch?.value || 'none',
                marking: {
                    type: value.marking?.type || 'none',
                    player_id: value.marking?.player_id || '',
                    name: value.marking?.name || '',
                    number: value.marking?.number ?? ''
                },
                embroidery: {
                    value: value.embroidery?.value || 'none',
                    text: value.embroidery?.text || ''
                }
            });
        };
        const optionsKey = identityKey(customOptions);
        // 같은 상품 옵션과 커스터마이징 선택값이 모두 일치할 때만 수량을 합친다.
        const existingIndex = items.findIndex(item => {
            if (optionId && item.option_id) {
                const itemOptions = item.custom_options || {};
                const itemOptionsKey = identityKey(itemOptions);
                return item.option_id === optionId && itemOptionsKey === optionsKey;
            }
            const itemOptions = item.custom_options || {};
            const itemOptionsKey = identityKey(itemOptions);
            return item.id === product.id && item.size === size && (color ? item.color === color : true)
                && itemOptionsKey === optionsKey;
        });

        if (existingIndex > -1) {
            items[existingIndex].quantity += Number(quantity);
            if (optionId) items[existingIndex].option_id = optionId;
            if (color) items[existingIndex].color = color;
            if (cartId) items[existingIndex].cart_id = cartId;
            if (unitPrice !== null) {
                items[existingIndex].price = Number(unitPrice);
                items[existingIndex].unit_price = Number(unitPrice);
            }
        } else {
            items.push({
                id: product.id,
                cart_id: cartId || null,
                option_id: optionId,
                name: product.name,
                price: Number(unitPrice !== null ? unitPrice : product.price),
                unit_price: Number(unitPrice !== null ? unitPrice : product.price),
                custom_options: customOptions || {},
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

    async updateBadge() {
        try {
            const badges = document.querySelectorAll('.cart-count');
            if (badges.length === 0) {
                return;
            }

            let count = 0;

            // 1) 로그인 상태인 경우 DB API에서 최신 장바구니 수량 조회
            if (window.isLoggedIn) {
                try {
                    const res = await fetch('/api/cart/count');
                    if (res.ok) {
                        const data = await res.json();
                        if (data && typeof data.count === 'number') {
                            count = data.count;
                        }
                    }
                } catch (apiErr) {
                    // API 실패 시 localStorage 폴백
                    count = this.getTotalCount();
                }
            } else {
                // 2) 비로그인 상태인 경우 localStorage 수량 반영
                count = this.getTotalCount();
            }

            badges.forEach(b => {
                b.textContent = Math.max(0, count);
                if (count > 0) {
                    b.style.display = 'inline-block';
                } else {
                    b.style.display = 'none';
                    b.textContent = '';
                }
            });
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
