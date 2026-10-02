-- Uniform customization data model migration.
-- Apply through the Supabase SQL editor before deploying the application code.

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS product_type TEXT NOT NULL DEFAULT 'standard';

ALTER TABLE public.products
    DROP CONSTRAINT IF EXISTS products_product_type_check;
ALTER TABLE public.products
    ADD CONSTRAINT products_product_type_check
    CHECK (product_type IN ('standard', 'jersey', 'kids_jersey'));

-- Explicitly tag only the known adult and kids uniform products.
UPDATE public.products
SET product_type = 'jersey'
WHERE slug IN (
    '27-season-home-jersey',
    '27-season-away-jersey',
    '27-season-third-jersey',
    '27-season-special-jersey',
    '27-season-gk-home-jersey',
    '27-season-gk-away-jersey'
);

UPDATE public.products
SET product_type = 'kids_jersey'
WHERE slug IN ('kids-home-uniform-set', 'kids-away-uniform-set');

CREATE TABLE IF NOT EXISTS public.product_custom_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    option_type TEXT NOT NULL CHECK (option_type IN ('patch', 'marking', 'embroidery')),
    option_value TEXT NOT NULL,
    option_name TEXT NOT NULL,
    additional_price NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (additional_price >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW()),
    UNIQUE (option_type, option_value)
);

CREATE TABLE IF NOT EXISTS public.players (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 20),
    number INT NOT NULL CHECK (number BETWEEN 0 AND 99),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    additional_price NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (additional_price >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW()),
    UNIQUE (number, name)
);

INSERT INTO public.product_custom_options
    (option_type, option_value, option_name, additional_price, active, sort_order)
VALUES
    ('patch', 'none', '광고패치 없음', 0, TRUE, 1),
    ('patch', 'official', '공식 광고패치 부착', 5000, TRUE, 2),
    ('marking', 'none', '마킹 안 함', 0, TRUE, 1),
    ('marking', 'player', '선수 마킹', 15000, TRUE, 2),
    ('marking', 'custom', '직접 입력 마킹', 18000, TRUE, 3),
    ('embroidery', 'none', '자수 없음', 0, TRUE, 1),
    ('embroidery', 'add', '자수 추가', 10000, TRUE, 2)
ON CONFLICT (option_type, option_value) DO UPDATE SET
    option_name = EXCLUDED.option_name,
    additional_price = EXCLUDED.additional_price,
    active = EXCLUDED.active,
    sort_order = EXCLUDED.sort_order,
    updated_at = TIMEZONE('utc', NOW());

ALTER TABLE public.carts
    ADD COLUMN IF NOT EXISTS custom_options JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS custom_options_key TEXT NOT NULL DEFAULT '';

ALTER TABLE public.carts
    DROP CONSTRAINT IF EXISTS carts_user_id_product_id_option_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_carts_custom_option_identity
    ON public.carts (
        user_id,
        product_id,
        COALESCE(option_id, '00000000-0000-0000-0000-000000000000'::uuid),
        custom_options_key
    );

ALTER TABLE public.order_items
    ADD COLUMN IF NOT EXISTS custom_options JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.product_custom_options ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.players ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Active customization options are readable" ON public.product_custom_options;
CREATE POLICY "Active customization options are readable"
    ON public.product_custom_options FOR SELECT TO anon, authenticated
    USING (active = TRUE);
DROP POLICY IF EXISTS "Active players are readable" ON public.players;
CREATE POLICY "Active players are readable"
    ON public.players FOR SELECT TO anon, authenticated
    USING (active = TRUE);

CREATE INDEX IF NOT EXISTS idx_products_product_type ON public.products(product_type);
CREATE INDEX IF NOT EXISTS idx_players_active_number ON public.players(active, number);

CREATE OR REPLACE FUNCTION public.restore_order_stock(
    p_order_id UUID,
    p_target_status order_status,
    p_reason TEXT DEFAULT '관리자 직권 상태 변경',
    p_is_admin BOOLEAN DEFAULT FALSE
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    target_order public.orders%ROWTYPE;
    order_line RECORD;
    restored_quantity INT := 0;
    affected_rows INT := 0;
    has_legacy_stock BOOLEAN;
    stock_restored_flag TEXT := '[STOCK_RESTORED]';
BEGIN
    IF p_target_status NOT IN ('cancelled', 'refunded') THEN
        RETURN jsonb_build_object('success', FALSE, 'message', '취소 또는 환불 상태만 재고 복구할 수 있습니다.', 'restored_count', 0);
    END IF;

    SELECT * INTO target_order
    FROM public.orders
    WHERE id = p_order_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', FALSE, 'message', '주문을 찾을 수 없습니다.', 'restored_count', 0);
    END IF;

    IF NOT p_is_admin AND target_order.status NOT IN ('pending', 'paid') THEN
        RETURN jsonb_build_object('success', FALSE, 'message', '현재 주문 상태에서는 직접 취소할 수 없습니다.', 'restored_count', 0);
    END IF;

    IF target_order.status IN ('cancelled', 'refunded')
       OR COALESCE(target_order.shipping_memo, '') LIKE '%' || stock_restored_flag || '%' THEN
        UPDATE public.orders SET status = p_target_status WHERE id = p_order_id;
        IF p_target_status = 'refunded' AND NOT EXISTS (
            SELECT 1 FROM public.refunds WHERE order_id = p_order_id AND status = 'completed'
        ) THEN
            INSERT INTO public.refunds (order_id, user_id, refund_amount, reason, status, admin_memo)
            VALUES (p_order_id, target_order.user_id, target_order.final_amount, COALESCE(NULLIF(p_reason, ''), '관리자 직권 상태 변경'), 'completed', '재고는 이전에 복구되어 중복 처리하지 않았습니다.');
        END IF;
        RETURN jsonb_build_object('success', TRUE, 'message', '이미 재고 복구가 완료된 주문입니다. 중복 복구를 차단했습니다.', 'restored_count', 0);
    END IF;

    FOR order_line IN
        SELECT option_id, SUM(quantity)::INT AS quantity
        FROM public.order_items
        WHERE order_id = p_order_id AND option_id IS NOT NULL
        GROUP BY option_id
    LOOP
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_options'
              AND column_name = 'stock'
        ) INTO has_legacy_stock;

        IF has_legacy_stock THEN
            EXECUTE 'UPDATE public.product_options
                     SET stock = COALESCE(stock, 0) + $1,
                         stock_quantity = stock_quantity + $1,
                         updated_at = TIMEZONE(''utc'', NOW())
                     WHERE id = $2'
            USING order_line.quantity, order_line.option_id;
        ELSE
            UPDATE public.product_options
            SET stock_quantity = stock_quantity + order_line.quantity,
                updated_at = TIMEZONE('utc', NOW())
            WHERE id = order_line.option_id;
        END IF;

        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        IF affected_rows = 0 THEN
            RAISE EXCEPTION '주문 옵션 %을 찾을 수 없어 재고 복구를 취소했습니다.', order_line.option_id;
        END IF;
        restored_quantity := restored_quantity + order_line.quantity;
    END LOOP;

    UPDATE public.orders
    SET status = p_target_status,
        shipping_memo = CASE
            WHEN COALESCE(shipping_memo, '') LIKE '%' || stock_restored_flag || '%' THEN shipping_memo
            ELSE stock_restored_flag || ' ' || COALESCE(shipping_memo, '')
        END
    WHERE id = p_order_id;

    IF p_target_status = 'refunded' OR (NOT p_is_admin AND target_order.status = 'paid') THEN
        INSERT INTO public.refunds (order_id, user_id, refund_amount, reason, status, admin_memo)
        VALUES (
            p_order_id,
            target_order.user_id,
            target_order.final_amount,
            COALESCE(NULLIF(p_reason, ''), '관리자 직권 상태 변경'),
            'completed',
            format('재고 %s개 자동 복구 완료', restored_quantity)
        );
    END IF;

    RETURN jsonb_build_object(
        'success', TRUE,
        'message', format('주문이 처리되었으며 재고 %s개를 복구했습니다.', restored_quantity),
        'restored_count', restored_quantity
    );
END;
$$;

REVOKE ALL ON FUNCTION public.restore_order_stock(UUID, order_status, TEXT, BOOLEAN) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.restore_order_stock(UUID, order_status, TEXT, BOOLEAN) TO service_role;
