-- ==============================================================================
-- VIBE-FASHION 쇼핑몰 초기 시드 데이터 (Seed SQL)
-- 1. 카테고리 7개 (top, bottom, outer, dress, acc, bag, shoes)
-- 2. 샘플 상품 4개 (베이직 크롭 티셔츠, 와이드 데님 팬츠, 오버핏 코튼 자켓, 플로럴 미디 원피스)
-- 3. 첫 번째 상품(베이직 크롭 티셔츠) 옵션 9개 (블랙/화이트/베이지 × S/M/L)
-- 4. 상품별 대표 및 갤러리 썸네일 이미지 (picsum.photos 무료 이미지)
-- ==============================================================================

-- 1. 카테고리 7개 등록 (중복 방지 ON CONFLICT DO UPDATE)
INSERT INTO public.categories (name, slug, sort_order, is_active)
VALUES
    ('상의', 'top', 1, TRUE),
    ('하의', 'bottom', 2, TRUE),
    ('아우터', 'outer', 3, TRUE),
    ('원피스/세트', 'dress', 4, TRUE),
    ('액세서리', 'acc', 5, TRUE),
    ('가방', 'bag', 6, TRUE),
    ('신발', 'shoes', 7, TRUE)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    sort_order = EXCLUDED.sort_order,
    is_active = EXCLUDED.is_active;

-- ==============================================================================
-- 2. 샘플 상품 4개 등록
-- ==============================================================================
-- (1) 베이직 크롭 티셔츠 (상의, 판매가 19,900원, 원래가격/할인전 29,900원)
INSERT INTO public.products (category_id, name, slug, description, price, original_price, is_active, badge)
VALUES (
    (SELECT id FROM public.categories WHERE slug = 'top'),
    '베이직 크롭 티셔츠',
    'basic-crop-tshirt',
    '부드러운 코튼 소재로 편안한 착용감을 선사하는 데일리 크롭 티셔츠입니다. 다양한 하의와 매치하기 좋습니다.',
    19900.00,
    29900.00,
    TRUE,
    'BEST'
)
ON CONFLICT (slug) DO UPDATE SET
    category_id = EXCLUDED.category_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    original_price = EXCLUDED.original_price,
    is_active = EXCLUDED.is_active,
    badge = EXCLUDED.badge;

-- (2) 와이드 데님 팬츠 (하의, 판매가 39,900원, 정가 49,900원)
INSERT INTO public.products (category_id, name, slug, description, price, original_price, is_active, badge)
VALUES (
    (SELECT id FROM public.categories WHERE slug = 'bottom'),
    '와이드 데님 팬츠',
    'wide-denim-pants',
    '자연스러운 워싱감과 체형을 커버해주는 트렌디한 와이드 핏 데님 팬츠입니다.',
    39900.00,
    49900.00,
    TRUE,
    'NEW'
)
ON CONFLICT (slug) DO UPDATE SET
    category_id = EXCLUDED.category_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    original_price = EXCLUDED.original_price,
    is_active = EXCLUDED.is_active,
    badge = EXCLUDED.badge;

-- (3) 오버핏 코튼 자켓 (아우터, 판매가 59,900원, 정가 69,900원)
INSERT INTO public.products (category_id, name, slug, description, price, original_price, is_active, badge)
VALUES (
    (SELECT id FROM public.categories WHERE slug = 'outer'),
    '오버핏 코튼 자켓',
    'overfit-cotton-jacket',
    '탄탄한 고밀도 코튼 원단으로 제작되어 간절기 시즌 가볍게 걸치기 좋은 오버핏 자켓입니다.',
    59900.00,
    69900.00,
    TRUE,
    'HOT'
)
ON CONFLICT (slug) DO UPDATE SET
    category_id = EXCLUDED.category_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    original_price = EXCLUDED.original_price,
    is_active = EXCLUDED.is_active,
    badge = EXCLUDED.badge;

-- (4) 플로럴 미디 원피스 (원피스, 판매가 45,900원, 정가 55,900원)
INSERT INTO public.products (category_id, name, slug, description, price, original_price, is_active, badge)
VALUES (
    (SELECT id FROM public.categories WHERE slug = 'dress'),
    '플로럴 미디 원피스',
    'floral-midi-dress',
    '은은한 플라워 패턴과 살랑이는 실루엣이 로맨틱한 무드를 연출해주는 미디 기장 원피스입니다.',
    45900.00,
    55900.00,
    TRUE,
    'MD 추천'
)
ON CONFLICT (slug) DO UPDATE SET
    category_id = EXCLUDED.category_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    original_price = EXCLUDED.original_price,
    is_active = EXCLUDED.is_active,
    badge = EXCLUDED.badge;

-- ==============================================================================
-- 3. 첫 번째 상품(베이직 크롭 티셔츠) 옵션 9개 등록 (블랙/화이트/베이지 × S/M/L)
-- ==============================================================================
-- 기존 옵션 초기화 후 재등록 (재실행 시 멱등성 보장)
DELETE FROM public.product_options 
WHERE product_id = (SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt');

INSERT INTO public.product_options (product_id, color, size, additional_price, stock_quantity)
VALUES
    -- 블랙 옵션
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '블랙', 'S', 0.00, 50),
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '블랙', 'M', 0.00, 100),
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '블랙', 'L', 0.00, 30),
    -- 화이트 옵션
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '화이트', 'S', 0.00, 60),
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '화이트', 'M', 0.00, 120),
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '화이트', 'L', 0.00, 40),
    -- 베이지 옵션
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '베이지', 'S', 0.00, 30),
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '베이지', 'M', 0.00, 80),
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), '베이지', 'L', 0.00, 25);

-- 나머지 상품 기본 옵션 등록 (선택적)
DELETE FROM public.product_options WHERE product_id IN (
    SELECT id FROM public.products WHERE slug IN ('wide-denim-pants', 'overfit-cotton-jacket', 'floral-midi-dress')
);

INSERT INTO public.product_options (product_id, color, size, additional_price, stock_quantity)
VALUES
    ((SELECT id FROM public.products WHERE slug = 'wide-denim-pants'), '중청', 'M', 0.00, 80),
    ((SELECT id FROM public.products WHERE slug = 'wide-denim-pants'), '중청', 'L', 0.00, 60),
    ((SELECT id FROM public.products WHERE slug = 'overfit-cotton-jacket'), '카키', 'FREE', 0.00, 50),
    ((SELECT id FROM public.products WHERE slug = 'floral-midi-dress'), '네이비', 'FREE', 0.00, 40);

-- ==============================================================================
-- 4. 상품별 이미지 등록 (picsum.photos 고화질 무료 썸네일)
-- ==============================================================================
DELETE FROM public.product_images WHERE product_id IN (
    SELECT id FROM public.products WHERE slug IN (
        'basic-crop-tshirt', 'wide-denim-pants', 'overfit-cotton-jacket', 'floral-midi-dress'
    )
);

INSERT INTO public.product_images (product_id, image_url, is_primary, sort_order)
VALUES
    -- 1. 베이직 크롭 티셔츠 (대표 썸네일 + 서브 이미지)
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), 'https://picsum.photos/id/1059/800/800', TRUE, 1),
    ((SELECT id FROM public.products WHERE slug = 'basic-crop-tshirt'), 'https://picsum.photos/id/1062/800/800', FALSE, 2),
    
    -- 2. 와이드 데님 팬츠 (대표 썸네일)
    ((SELECT id FROM public.products WHERE slug = 'wide-denim-pants'), 'https://picsum.photos/id/1025/800/800', TRUE, 1),
    
    -- 3. 오버핏 코튼 자켓 (대표 썸네일)
    ((SELECT id FROM public.products WHERE slug = 'overfit-cotton-jacket'), 'https://picsum.photos/id/103/800/800', TRUE, 1),
    
    -- 4. 플로럴 미디 원피스 (대표 썸네일)
    ((SELECT id FROM public.products WHERE slug = 'floral-midi-dress'), 'https://picsum.photos/id/64/800/800', TRUE, 1);
