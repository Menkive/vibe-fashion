-- ==============================================================================
-- VIBE-FASHION 쇼핑몰 데이터베이스 스키마 (Supabase SQL Editor 실행용)
-- 테이블: profiles, categories, products, product_options, product_images,
--         carts, orders, order_items, refunds, notifications, reviews
-- 포함: auth.users 신규 유저 자동 프로필 생성 트리거(handle_new_user)
--       고객 등급 자동 업데이트 함수(update_customer_grade) 및 관련 트리거
-- ==============================================================================

-- 1. UUID 확장 모듈 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- 2. ENUM 타입 정의
-- ==============================================================================
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('customer', 'admin', 'seller');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE customer_grade AS ENUM ('BRONZE', 'SILVER', 'GOLD', 'VIP', 'VVIP');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE order_status AS ENUM ('pending', 'paid', 'preparing', 'shipping', 'delivered', 'cancelled', 'refunded');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE refund_status AS ENUM ('requested', 'approved', 'rejected', 'completed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE notification_type AS ENUM ('order', 'delivery', 'refund', 'promotion', 'system');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ==============================================================================
-- 3. 테이블 생성
-- ==============================================================================

-- (1) 프로필 테이블 (Supabase auth.users 1:1 연동)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE,
    full_name TEXT,
    avatar_url TEXT,
    phone_number TEXT,
    role user_role DEFAULT 'customer' NOT NULL,
    grade customer_grade DEFAULT 'BRONZE' NOT NULL,
    total_spent NUMERIC(12, 2) DEFAULT 0.00 NOT NULL,
    shipping_address TEXT,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (2) 카테고리 테이블 (계층 구조 지원)
CREATE TABLE IF NOT EXISTS public.categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    parent_id UUID REFERENCES public.categories(id) ON DELETE SET NULL,
    sort_order INT DEFAULT 0 NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (3) 상품 테이블
CREATE TABLE IF NOT EXISTS public.products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES public.categories(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    original_price NUMERIC(10, 2) CHECK (original_price >= price),
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    badge TEXT, -- 'BEST', 'NEW', 'HOT', 'MD 추천' 등
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (4) 상품 옵션 테이블 (사이즈, 색상 및 재고 관리)
CREATE TABLE IF NOT EXISTS public.product_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE NOT NULL,
    color TEXT,
    size TEXT,
    additional_price NUMERIC(10, 2) DEFAULT 0.00 NOT NULL,
    stock_quantity INT DEFAULT 0 NOT NULL CHECK (stock_quantity >= 0),
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (5) 상품 이미지 테이블
CREATE TABLE IF NOT EXISTS public.product_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE NOT NULL,
    image_url TEXT NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE NOT NULL,
    sort_order INT DEFAULT 0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (6) 장바구니 테이블
CREATE TABLE IF NOT EXISTS public.carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE NOT NULL,
    option_id UUID REFERENCES public.product_options(id) ON DELETE SET NULL,
    quantity INT DEFAULT 1 NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    UNIQUE (user_id, product_id, option_id)
);

-- (7) 주문 테이블
CREATE TABLE IF NOT EXISTS public.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number TEXT UNIQUE NOT NULL,
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
    discount_amount NUMERIC(10, 2) DEFAULT 0.00 NOT NULL,
    shipping_fee NUMERIC(10, 2) DEFAULT 0.00 NOT NULL,
    final_amount NUMERIC(12, 2) NOT NULL CHECK (final_amount >= 0),
    status order_status DEFAULT 'pending' NOT NULL,
    recipient_name TEXT NOT NULL,
    recipient_phone TEXT NOT NULL,
    shipping_address TEXT NOT NULL,
    shipping_memo TEXT,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (8) 주문 상세 아이템 테이블
CREATE TABLE IF NOT EXISTS public.order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES public.orders(id) ON DELETE CASCADE NOT NULL,
    product_id UUID REFERENCES public.products(id) ON DELETE SET NULL,
    option_id UUID REFERENCES public.product_options(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    option_info TEXT, -- 예: "블랙 / L"
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    quantity INT NOT NULL CHECK (quantity > 0),
    subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (9) 환불/반품 테이블
CREATE TABLE IF NOT EXISTS public.refunds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES public.orders(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    refund_amount NUMERIC(12, 2) NOT NULL CHECK (refund_amount >= 0),
    reason TEXT NOT NULL,
    status refund_status DEFAULT 'requested' NOT NULL,
    admin_memo TEXT,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (10) 알림 테이블
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type notification_type DEFAULT 'system' NOT NULL,
    is_read BOOLEAN DEFAULT FALSE NOT NULL,
    link_url TEXT,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- (11) 상품 리뷰 테이블
CREATE TABLE IF NOT EXISTS public.reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES public.products(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    order_item_id UUID REFERENCES public.order_items(id) ON DELETE SET NULL,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    content TEXT,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT TIMEZONE('utc', NOW()) NOT NULL
);

-- ==============================================================================
-- 4. 인덱스 생성 (조회 성능 최적화)
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_products_category ON public.products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON public.products(is_active);
CREATE INDEX IF NOT EXISTS idx_product_options_product ON public.product_options(product_id);
CREATE INDEX IF NOT EXISTS idx_product_images_product ON public.product_images(product_id);
CREATE INDEX IF NOT EXISTS idx_carts_user ON public.carts(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_user ON public.orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON public.orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON public.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON public.notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_reviews_product ON public.reviews(product_id);

-- ==============================================================================
-- 5. 함수 및 트리거 1: 소셜/일반 회원가입 시 public.profiles 자동 생성
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (
        id,
        email,
        full_name,
        avatar_url,
        role,
        grade,
        total_spent
    )
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(
            NEW.raw_user_meta_data->>'full_name',
            NEW.raw_user_meta_data->>'name',
            NEW.raw_user_meta_data->>'user_name',
            split_part(NEW.email, '@', 1)
        ),
        COALESCE(
            NEW.raw_user_meta_data->>'avatar_url',
            NEW.raw_user_meta_data->>'picture'
        ),
        'customer',
        'BRONZE',
        0.00
    )
    ON CONFLICT (id) DO UPDATE SET
        email = EXCLUDED.email,
        full_name = COALESCE(EXCLUDED.full_name, public.profiles.full_name),
        avatar_url = COALESCE(EXCLUDED.avatar_url, public.profiles.avatar_url),
        updated_at = TIMEZONE('utc', NOW());

    RETURN NEW;
END;
$$;

-- auth.users 트리거 연결
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- ==============================================================================
-- 6. 함수 및 트리거 2: 고객 누적 결제액 기준 등급 자동 업데이트
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.update_customer_grade(target_user_id UUID)
RETURNS customer_grade
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    calculated_total NUMERIC(12, 2) := 0.00;
    new_grade customer_grade := 'BRONZE';
BEGIN
    -- 결제 완료(paid), 배송 준비/중/완료(preparing, shipping, delivered) 상태의 실 결제 금액 합산
    SELECT COALESCE(SUM(final_amount), 0.00)
    INTO calculated_total
    FROM public.orders
    WHERE user_id = target_user_id
      AND status IN ('paid', 'preparing', 'shipping', 'delivered');

    -- 등급 기준 산정 (BRONZE, SILVER, GOLD, VIP, VVIP)
    IF calculated_total >= 2000000 THEN
        new_grade := 'VVIP';
    ELSIF calculated_total >= 1000000 THEN
        new_grade := 'VIP';
    ELSIF calculated_total >= 500000 THEN
        new_grade := 'GOLD';
    ELSIF calculated_total >= 200000 THEN
        new_grade := 'SILVER';
    ELSE
        new_grade := 'BRONZE';
    END IF;

    -- profiles 테이블 갱신
    UPDATE public.profiles
    SET total_spent = calculated_total,
        grade = new_grade,
        updated_at = TIMEZONE('utc', NOW())
    WHERE id = target_user_id;

    RETURN new_grade;
END;
$$;

-- 주문 상태 변경 시 등급 업데이트 자동 트리거 함수
CREATE OR REPLACE FUNCTION public.trigger_update_customer_grade_on_order()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- 주문자 ID가 존재하는 경우 등급 재계산
    IF NEW.user_id IS NOT NULL THEN
        PERFORM public.update_customer_grade(NEW.user_id);
    END IF;

    -- 이전 주문자가 달라진 경우 이전 유저도 재계산
    IF TG_OP = 'UPDATE' AND OLD.user_id IS NOT NULL AND OLD.user_id <> NEW.user_id THEN
        PERFORM public.update_customer_grade(OLD.user_id);
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_order_status_grade_update ON public.orders;
CREATE TRIGGER on_order_status_grade_update
    AFTER INSERT OR UPDATE OF status, final_amount, user_id ON public.orders
    FOR EACH ROW
    EXECUTE FUNCTION public.trigger_update_customer_grade_on_order();

-- ==============================================================================
-- 7. Row Level Security (RLS) 활성화 및 기본 정책 설정 (재실행 에러 방지)
-- ==============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_options ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.carts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

-- (1) profiles: 본인 프로필 조회 및 수정 가능
DROP POLICY IF EXISTS "Users can view their own profile" ON public.profiles;
CREATE POLICY "Users can view their own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- (2) categories & products & options & images: 누구나 읽기 가능
DROP POLICY IF EXISTS "Public read for categories" ON public.categories;
CREATE POLICY "Public read for categories"
    ON public.categories FOR SELECT
    USING (is_active = TRUE);

DROP POLICY IF EXISTS "Public read for products" ON public.products;
CREATE POLICY "Public read for products"
    ON public.products FOR SELECT
    USING (is_active = TRUE);

DROP POLICY IF EXISTS "Public read for product options" ON public.product_options;
CREATE POLICY "Public read for product options"
    ON public.product_options FOR SELECT
    USING (TRUE);

DROP POLICY IF EXISTS "Public read for product images" ON public.product_images;
CREATE POLICY "Public read for product images"
    ON public.product_images FOR SELECT
    USING (TRUE);

-- (3) carts: 본인 장바구니만 관리
DROP POLICY IF EXISTS "Users can manage their own cart" ON public.carts;
CREATE POLICY "Users can manage their own cart"
    ON public.carts FOR ALL
    USING (auth.uid() = user_id);

-- (4) orders & order_items: 본인 주문만 조회/생성
DROP POLICY IF EXISTS "Users can view their own orders" ON public.orders;
CREATE POLICY "Users can view their own orders"
    ON public.orders FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own orders" ON public.orders;
CREATE POLICY "Users can insert their own orders"
    ON public.orders FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view their own order items" ON public.order_items;
CREATE POLICY "Users can view their own order items"
    ON public.order_items FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM public.orders
        WHERE orders.id = order_items.order_id
          AND orders.user_id = auth.uid()
    ));

-- (5) refunds: 본인 환불 요청 조회 및 등록
DROP POLICY IF EXISTS "Users can view their own refunds" ON public.refunds;
CREATE POLICY "Users can view their own refunds"
    ON public.refunds FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create their own refunds" ON public.refunds;
CREATE POLICY "Users can create their own refunds"
    ON public.refunds FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- (6) notifications: 본인 알림만 조회 및 읽음 처리
DROP POLICY IF EXISTS "Users can manage their own notifications" ON public.notifications;
CREATE POLICY "Users can manage their own notifications"
    ON public.notifications FOR ALL
    USING (auth.uid() = user_id);

-- (7) reviews: 누구나 조회 가능, 작성은 본인만
DROP POLICY IF EXISTS "Public read for reviews" ON public.reviews;
CREATE POLICY "Public read for reviews"
    ON public.reviews FOR SELECT
    USING (TRUE);

DROP POLICY IF EXISTS "Authenticated users can create reviews" ON public.reviews;
CREATE POLICY "Authenticated users can create reviews"
    ON public.reviews FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own reviews" ON public.reviews;
CREATE POLICY "Users can update their own reviews"
    ON public.reviews FOR UPDATE
    USING (auth.uid() = user_id);
