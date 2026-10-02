-- Record every product option stock change with its source and related order.

CREATE TABLE IF NOT EXISTS public.inventory_stock_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_option_id UUID NOT NULL,
    product_id UUID,
    product_name TEXT NOT NULL DEFAULT '삭제된 상품',
    color TEXT,
    size TEXT,
    previous_quantity INTEGER NOT NULL,
    changed_quantity INTEGER NOT NULL,
    new_quantity INTEGER NOT NULL,
    reason TEXT NOT NULL,
    order_id UUID,
    order_number TEXT,
    changed_by UUID,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX IF NOT EXISTS idx_inventory_stock_history_changed_at
    ON public.inventory_stock_history (changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_stock_history_option
    ON public.inventory_stock_history (product_option_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_stock_history_order
    ON public.inventory_stock_history (order_id)
    WHERE order_id IS NOT NULL;

ALTER TABLE public.inventory_stock_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.inventory_stock_history FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.inventory_stock_history TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.inventory_stock_history_id_seq TO service_role;

CREATE OR REPLACE FUNCTION public.record_inventory_stock_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    old_quantity INTEGER := 0;
    new_quantity INTEGER := 0;
    change_reason TEXT;
    related_order_id UUID;
    related_order_number TEXT;
    actor_id UUID;
    product_name_snapshot TEXT;
BEGIN
    new_quantity := COALESCE(
        NULLIF(to_jsonb(NEW)->>'stock', '')::INTEGER,
        NULLIF(to_jsonb(NEW)->>'stock_quantity', '')::INTEGER,
        0
    );

    IF TG_OP = 'UPDATE' THEN
        old_quantity := COALESCE(
            NULLIF(to_jsonb(OLD)->>'stock', '')::INTEGER,
            NULLIF(to_jsonb(OLD)->>'stock_quantity', '')::INTEGER,
            0
        );
    END IF;

    IF old_quantity = new_quantity THEN
        RETURN NEW;
    END IF;

    change_reason := NULLIF(current_setting('app.inventory_change_reason', TRUE), '');
    IF change_reason IS NULL THEN
        change_reason := CASE
            WHEN TG_OP = 'INSERT' THEN '초기 재고 등록'
            ELSE '분류되지 않은 재고 변경'
        END;
    END IF;

    related_order_id := NULLIF(current_setting('app.inventory_order_id', TRUE), '')::UUID;
    actor_id := NULLIF(current_setting('app.inventory_changed_by', TRUE), '')::UUID;

    SELECT name INTO product_name_snapshot
    FROM public.products
    WHERE id = NEW.product_id;

    IF related_order_id IS NOT NULL THEN
        SELECT order_number INTO related_order_number
        FROM public.orders
        WHERE id = related_order_id;
    END IF;

    INSERT INTO public.inventory_stock_history (
        product_option_id, product_id, product_name, color, size,
        previous_quantity, changed_quantity, new_quantity,
        reason, order_id, order_number, changed_by
    ) VALUES (
        NEW.id, NEW.product_id, COALESCE(product_name_snapshot, '삭제된 상품'),
        NEW.color, NEW.size, old_quantity, new_quantity - old_quantity,
        new_quantity, change_reason, related_order_id, related_order_number, actor_id
    );

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS product_options_inventory_history ON public.product_options;
CREATE TRIGGER product_options_inventory_history
AFTER INSERT OR UPDATE ON public.product_options
FOR EACH ROW
EXECUTE FUNCTION public.record_inventory_stock_change();

CREATE OR REPLACE FUNCTION public.adjust_product_option_stock(
    p_option_id UUID,
    p_mode TEXT,
    p_value INTEGER,
    p_reason TEXT DEFAULT NULL,
    p_order_id UUID DEFAULT NULL,
    p_changed_by UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    option_row JSONB;
    previous_quantity INTEGER;
    new_quantity INTEGER;
    product_name_snapshot TEXT;
BEGIN
    IF p_mode NOT IN ('set', 'delta') THEN
        RETURN jsonb_build_object('success', FALSE, 'message', '재고 변경 방식이 올바르지 않습니다.');
    END IF;
    IF p_mode = 'set' AND p_value < 0 THEN
        RETURN jsonb_build_object('success', FALSE, 'message', '재고는 0개 미만으로 설정할 수 없습니다.');
    END IF;

    SELECT to_jsonb(po) INTO option_row
    FROM public.product_options AS po
    WHERE po.id = p_option_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', FALSE, 'message', '상품 옵션을 찾을 수 없습니다.');
    END IF;

    previous_quantity := COALESCE(
        NULLIF(option_row->>'stock', '')::INTEGER,
        NULLIF(option_row->>'stock_quantity', '')::INTEGER,
        0
    );
    new_quantity := CASE
        WHEN p_mode = 'set' THEN p_value
        ELSE previous_quantity + p_value
    END;

    IF new_quantity < 0 THEN
        RETURN jsonb_build_object('success', FALSE, 'message', '재고가 부족하여 변경할 수 없습니다.');
    END IF;

    IF new_quantity = previous_quantity THEN
        SELECT name INTO product_name_snapshot FROM public.products WHERE id = (option_row->>'product_id')::UUID;
        RETURN jsonb_build_object(
            'success', TRUE,
            'previous_quantity', previous_quantity,
            'changed_quantity', 0,
            'new_quantity', new_quantity,
            'product_name', COALESCE(product_name_snapshot, '삭제된 상품'),
            'color', option_row->>'color',
            'size', option_row->>'size'
        );
    END IF;

    PERFORM set_config('app.inventory_change_reason', COALESCE(NULLIF(p_reason, ''), '분류되지 않은 재고 변경'), TRUE);
    PERFORM set_config('app.inventory_order_id', COALESCE(p_order_id::TEXT, ''), TRUE);
    PERFORM set_config('app.inventory_changed_by', COALESCE(p_changed_by::TEXT, ''), TRUE);

    IF option_row ? 'stock' THEN
        UPDATE public.product_options
        SET stock = new_quantity,
            stock_quantity = new_quantity,
            updated_at = TIMEZONE('utc', NOW())
        WHERE id = p_option_id;
    ELSE
        UPDATE public.product_options
        SET stock_quantity = new_quantity,
            updated_at = TIMEZONE('utc', NOW())
        WHERE id = p_option_id;
    END IF;

    SELECT name INTO product_name_snapshot FROM public.products WHERE id = (option_row->>'product_id')::UUID;
    RETURN jsonb_build_object(
        'success', TRUE,
        'previous_quantity', previous_quantity,
        'changed_quantity', new_quantity - previous_quantity,
        'new_quantity', new_quantity,
        'product_name', COALESCE(product_name_snapshot, '삭제된 상품'),
        'color', option_row->>'color',
        'size', option_row->>'size'
    );
END;
$$;

REVOKE ALL ON FUNCTION public.adjust_product_option_stock(UUID, TEXT, INTEGER, TEXT, UUID, UUID) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.adjust_product_option_stock(UUID, TEXT, INTEGER, TEXT, UUID, UUID) TO service_role;

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

    PERFORM set_config(
        'app.inventory_change_reason',
        CASE WHEN p_target_status = 'cancelled' THEN '주문 취소' ELSE '주문 환불' END,
        TRUE
    );
    PERFORM set_config('app.inventory_order_id', p_order_id::TEXT, TRUE);
    PERFORM set_config(
        'app.inventory_changed_by',
        CASE WHEN p_is_admin THEN '' ELSE COALESCE(target_order.user_id::TEXT, '') END,
        TRUE
    );

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