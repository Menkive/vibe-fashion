// static/js/store.js - 양산시민축구단 공식 스토어 클라이언트 장바구니 및 유틸리티

const CartManager = {
    STORAGE_KEY: 'yangsan_fc_cart_v1',

    getItems() {
        try {
            return JSON.parse(localStorage.getItem(this.STORAGE_KEY)) || [];
        } catch (e) {
            console.error('장바구니 로드 실패:', e);
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
        return this.getItems().reduce((total, item) => total + (item.price * item.quantity), 0);
    },

    getTotalCount() {
        return this.getItems().reduce((count, item) => count + item.quantity, 0);
    },

    updateBadge() {
        const count = this.getTotalCount();
        const badges = document.querySelectorAll('.cart-count');
        badges.forEach(b => {
            b.textContent = count;
            b.style.display = count > 0 ? 'inline-block' : 'none';
        });
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
    }
};

// 페이지 로드 시 뱃지 초기화 및 다크모드 설정
document.addEventListener('DOMContentLoaded', () => {
    CartManager.updateBadge();
    initTheme();
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
