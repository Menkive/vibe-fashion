# app/models.py - 양산시민축구단 공식 스토어 상품 및 투표 데이터 모델
from typing import List, Dict, Any, Optional

# 양산시민축구단 공식 유니폼 및 2028 시즌 공식 굿즈 카탈로그
INITIAL_PRODUCTS: List[Dict[str, Any]] = [
    # [유니폼 - 27시즌 컬렉션]
    {
        "id": 1,
        "name": "27시즌 홈 유니폼",
        "slug": "27-season-home-jersey",
        "category": "유니폼",
        "price": 109000,
        "original_price": 129000,
        "description": "양산시민축구단을 대표하는 27시즌 1st 유니폼입니다. 구단의 메인 컬러인 푸른색을 중심으로 구성하여 양산시민축구단의 정체성과 상징성을 가장 직접적으로 표현한 디자인입니다. 스포티하고 현대적인 축구 유니폼 디자인과 간결한 실루엣을 바탕으로, 경기장에서 선수들이 착용하는 홈 유니폼의 이미지를 살리면서도 팬들이 일상에서도 부담 없이 착용할 수 있는 깔끔하고 스포티한 스타일을 콘셉트로 합니다. 가슴에 새겨진 스우시 로고와 엠블럼이 조화를 이루며 실제 프로 축구 클럽의 경기용 킷을 연상시키는 스타일을 완성합니다.",
        "image_url": "/static/images/uniforms/01-home-jersey.png",
        "thumbnail_url": "/static/images/uniforms/01-home-jersey.png",
        "stock": 50,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "badge": "27 SEASON SALE",
        "is_featured": True,
        "is_new": True,
        "sales_count": 1820
    },
    {
        "id": 2,
        "name": "27시즌 어웨이 유니폼",
        "slug": "27-season-away-jersey",
        "category": "유니폼",
        "price": 109000,
        "original_price": 129000,
        "description": "원정 경기를 콘셉트로 제작된 양산시민축구단의 27시즌 2nd 유니폼입니다. 깨끗한 흰색을 기본으로 사용하고 푸른색 포인트를 더해 홈 유니폼과 뚜렷하게 대비되는 디자인을 완성했습니다. 밝고 산뜻한 인상을 강조하면서 구단의 대표 컬러를 자연스럽게 유지한 것이 특징입니다. 간결한 실루엣과 감각적인 배색으로 실제 프로 축구 클럽의 원정 킷을 연상시키는 스타일을 선사하며, 팬들이 경기장 응원은 물론 일상에서도 스타일리시하게 활용할 수 있습니다.",
        "image_url": "/static/images/uniforms/02-away-jersey.png",
        "thumbnail_url": "/static/images/uniforms/02-away-jersey.png",
        "stock": 42,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "badge": "27 SEASON SALE",
        "is_featured": True,
        "is_new": True,
        "sales_count": 1410
    },
    {
        "id": 3,
        "name": "27시즌 서드 유니폼",
        "slug": "27-season-third-jersey",
        "category": "유니폼",
        "price": 119000,
        "original_price": 139000,
        "description": "홈과 어웨이 유니폼에서 한 단계 벗어난 개성 있는 27시즌 3rd 유니폼입니다. 갈색과 브론즈 계열을 중심으로 차분하면서도 고급스러운 분위기를 표현했습니다. 일반적인 축구 유니폼에서는 보기 드문 색상 조합을 활용해 팬 컬렉션이나 특별한 경기에서 더욱 돋보일 수 있는 디자인을 콘셉트로 합니다. 현대적인 스포츠웨어 감성의 정밀 그래픽 패턴과 스포티한 실루엣이 더해져 실제 프로 축구 클럽의 한정판 킷을 연상시키는 스타일을 자랑합니다.",
        "image_url": "/static/images/uniforms/03-third-jersey.png",
        "thumbnail_url": "/static/images/uniforms/03-third-jersey.png",
        "stock": 30,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "badge": "27 SEASON SALE",
        "is_featured": True,
        "is_new": True,
        "sales_count": 980
    },
    {
        "id": 4,
        "name": "27시즌 스페셜 유니폼",
        "slug": "27-season-special-jersey",
        "category": "유니폼",
        "price": 129000,
        "original_price": 149000,
        "description": "양산시민축구단의 대표 컬러인 푸른색을 활용한 특별판 유니폼입니다. 푸른색 계열의 세로 스트라이프 패턴을 강조하여 기존 홈 유니폼과는 또 다른 클래식하고 역동적인 분위기를 표현했습니다. 기념 경기, 특별 이벤트, 구단 창단 기념전 등 특별한 순간에 착용하는 한정판 유니폼을 연상시키는 디자인입니다. 역동적인 컬러 구성과 세련된 스포츠웨어 라인으로 경기장과 일상에서 모두 높은 소장 가치와 착용 만족감을 선사합니다.",
        "image_url": "/static/images/uniforms/06-special-jersey.png",
        "thumbnail_url": "/static/images/uniforms/06-special-jersey.png",
        "stock": 45,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "badge": "27 SEASON SALE",
        "is_featured": True,
        "is_new": False,
        "sales_count": 1120
    },
    {
        "id": 5,
        "name": "27시즌 골키퍼 홈 유니폼",
        "slug": "27-season-gk-home-jersey",
        "category": "유니폼",
        "price": 119000,
        "original_price": 139000,
        "description": "강렬한 레드 컬러를 중심으로 디자인한 27시즌 골키퍼 홈 유니폼입니다. 선명한 붉은색을 기본으로 검정색과 짙은 적색 계열의 거친 브러시 패턴을 곳곳에 적용하여 골키퍼 특유의 강인하고 역동적인 이미지를 표현했습니다. 필드 플레이어의 푸른색 유니폼과 경기장에서 명확하게 구분되며, 화이트 로고와 'YANGSAN CITIZEN FC' 등의 요소가 붉은 배경과 선명하게 대비되도록 구성된 것이 특징입니다. 프로페셔널한 경기용 킷의 분위기를 담아 실제 경기장과 일상 모두에서 시선을 사로잡습니다.",
        "image_url": "/static/images/uniforms/05-gk-home-jersey.png",
        "thumbnail_url": "/static/images/uniforms/05-gk-home-jersey.png",
        "stock": 35,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "badge": "27 SEASON SALE",
        "is_featured": False,
        "is_new": False,
        "sales_count": 860
    },
    {
        "id": 6,
        "name": "27시즌 골키퍼 어웨이 유니폼",
        "slug": "27-season-gk-away-jersey",
        "category": "유니폼",
        "price": 119000,
        "original_price": 139000,
        "description": "밝고 선명한 에메랄드·그린 계열을 중심으로 제작된 27시즌 골키퍼 어웨이 유니폼입니다. 짙은 녹색과 검정색 브러시 패턴을 조합하여 홈 골키퍼 유니폼과 동일한 디자인 계열을 유지하면서 색상으로 확실한 차이를 표현했습니다. 그린 컬러 특유의 생동감과 에너지를 강조해 실제 경기장에서 착용하는 전문 골키퍼 킷과 같은 분위기를 연출합니다. 간결한 실루엣과 스포티하고 현대적인 디자인으로 경기 관람 및 일상 스포츠웨어로도 훌륭한 매치를 보여줍니다.",
        "image_url": "/static/images/uniforms/04-gk-away-jersey.png",
        "thumbnail_url": "/static/images/uniforms/04-gk-away-jersey.png",
        "stock": 35,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "badge": "27 SEASON SALE",
        "is_featured": False,
        "is_new": False,
        "sales_count": 790
    },
    # [응원용품]
    {
        "id": 7,
        "name": "2028 양산시민축구단 오피셜 서포터 머플러",
        "slug": "yangsan-fc-official-supporter-muffler",
        "category": "응원용품",
        "price": 22000,
        "original_price": 25000,
        "description": "양산시민축구단 공식 엠블럼과 로고가 정밀 자카드 편직된 공식 서포터 니트 머플러입니다. 경기장 응원 및 일상 코디에 최적화되었습니다.",
        "image_url": "/static/images/yangsan-fc-muffler.png",
        "thumbnail_url": "/static/images/yangsan-fc-muffler.png",
        "stock": 100,
        "sizes": ["Free"],
        "badge": "BEST",
        "is_featured": True,
        "is_new": True,
        "sales_count": 2850
    },
    {
        "id": 8,
        "name": "2028 양산시민축구단 오피셜 스티커&배지 세트",
        "slug": "yangsan-fc-official-sticker-badge-set",
        "category": "응원용품",
        "price": 12000,
        "original_price": 15000,
        "description": "고급 골드 메탈 프레임 엠블럼 마그네틱/핀 배지와 방수 PVC 공식 그래픽 스티커 5종으로 구성된 구단 오피셜 기프트 세트입니다.",
        "image_url": "/static/images/yangsan-fc-badge-sticker-set.png",
        "thumbnail_url": "/static/images/yangsan-fc-badge-sticker-set.png",
        "stock": 120,
        "sizes": ["Free"],
        "badge": "MD추천",
        "is_featured": True,
        "is_new": True,
        "sales_count": 1470
    },
    # [패션/잡화]
    {
        "id": 9,
        "name": "2028 양산시민축구단 오피셜 엠블럼 볼캡",
        "slug": "yangsan-fc-official-emblem-ballcap",
        "category": "패션/잡화",
        "price": 29000,
        "original_price": 34000,
        "description": "양산FC 시그니처 로열 블루 원단에 정밀 입체 자수 엠블럼과 골드 파이핑 챙 디테일을 더한 공식 경기용 볼캡입니다.",
        "image_url": "/static/images/yangsan-fc-ballcap.png",
        "thumbnail_url": "/static/images/yangsan-fc-ballcap.png",
        "stock": 85,
        "sizes": ["Free"],
        "badge": "HOT",
        "is_featured": True,
        "is_new": True,
        "sales_count": 1920
    },
    {
        "id": 10,
        "name": "2028 양산시민축구단 클래식 엠블럼 토트백",
        "slug": "yangsan-fc-classic-emblem-tote-bag",
        "category": "패션/잡화",
        "price": 24000,
        "original_price": 28000,
        "description": "고밀도 캔버스 코튼 원단에 구단 공식 엠블럼이 실크스크린 프린팅된 데일리 에코 토트백입니다. 넉넉한 수납공간을 제공합니다.",
        "image_url": "/static/images/yangsan-fc-tote-bag.png",
        "thumbnail_url": "/static/images/yangsan-fc-tote-bag.png",
        "stock": 60,
        "sizes": ["Free"],
        "badge": "NEW",
        "is_featured": True,
        "is_new": True,
        "sales_count": 1240
    },
    {
        "id": 11,
        "name": "2028 양산시민축구단 쉴드 엠블럼 키링",
        "slug": "yangsan-fc-shield-emblem-keyring",
        "category": "패션/잡화",
        "price": 9000,
        "original_price": 11000,
        "description": "양산시민축구단의 상징 쉴드 엠블럼을 정밀 양각 메탈로 구현한 공식 키링으로 가방, 열쇠고리, 파우치 등에 고급스럽게 매치할 수 있습니다.",
        "image_url": "/static/images/yangsan-fc-keyring.png",
        "thumbnail_url": "/static/images/yangsan-fc-keyring.png",
        "stock": 150,
        "sizes": ["Free"],
        "badge": "BEST",
        "is_featured": True,
        "is_new": True,
        "sales_count": 2150
    },
    # [생활용품]
    {
        "id": 12,
        "name": "2028 양산시민축구단 블루&골드 엠블럼 머그컵",
        "slug": "yangsan-fc-blue-gold-emblem-mug",
        "category": "생활용품",
        "price": 14000,
        "original_price": 16000,
        "description": "양산FC의 시그니처 딥 네이비와 골드 엠블럼 그래픽이 적용된 세라믹 머그컵(350ml)으로 일상과 사무실에서 팀의 열정을 함께합니다.",
        "image_url": "/static/images/yangsan-fc-mug.png",
        "thumbnail_url": "/static/images/yangsan-fc-mug.png",
        "stock": 80,
        "sizes": ["Free"],
        "badge": "MD추천",
        "is_featured": False,
        "is_new": True,
        "sales_count": 1380
    },
    {
        "id": 13,
        "name": "2028 양산시민축구단 엠블럼 전술 노트",
        "slug": "yangsan-fc-emblem-tactical-notebook",
        "category": "생활용품",
        "price": 8000,
        "original_price": 10000,
        "description": "하드커버 표지에 금박 양각 엠블럼이 새겨진 구단 공식 전술 & 데일리 하드커버 유선 노트입니다. 축구 기록과 일상 메모에 제격입니다.",
        "image_url": "/static/images/yangsan-fc-tactical-notebook.png",
        "thumbnail_url": "/static/images/yangsan-fc-tactical-notebook.png",
        "stock": 90,
        "sizes": ["Free"],
        "badge": "NEW",
        "is_featured": False,
        "is_new": True,
        "sales_count": 960
    }
]

# 2027 시즌 유니폼 디자인 팬 투표 데이터 (실제 유니폼 6종 후보)
INITIAL_VOTE_CANDIDATES = [
    {
        "id": "home-kit",
        "kit_code": "HOME KIT",
        "name": "홈 유니폼",
        "concept": "양산의 푸른 산천과 정체성을 상징하는 시그니처 로열 블루 홈 경기용 유니폼 디자인",
        "image_url": "/static/images/home-kit.png",
        "votes": 0,
        "badge": "1st KIT"
    },
    {
        "id": "away-kit",
        "kit_code": "AWAY KIT",
        "name": "어웨이 유니폼",
        "concept": "깨끗한 화이트 바탕에 푸른색 포인트를 더해 원정 경기에서 돋보이는 산뜻한 저지 디자인",
        "image_url": "/static/images/away-kit.png",
        "votes": 0,
        "badge": "2nd KIT"
    },
    {
        "id": "third-kit-01",
        "kit_code": "THIRD KIT 01",
        "name": "서드 유니폼 1",
        "concept": "갈색과 브론즈 계열을 중심으로 차분하면서도 고급스러운 분위기를 연출한 스페셜 서드 킷",
        "image_url": "/static/images/third-kit-01.png",
        "votes": 0,
        "badge": "3rd KIT"
    },
    {
        "id": "third-kit-02",
        "kit_code": "THIRD KIT 02",
        "name": "서드 유니폼 2",
        "concept": "클래식한 버티컬 골드 & 블루 스트라이프로 구단의 전통과 역동성을 담은 에디션",
        "image_url": "/static/images/third-kit-02.png",
        "votes": 0,
        "badge": "SPECIAL"
    },
    {
        "id": "gk-kit-01",
        "kit_code": "GK KIT 01",
        "name": "골키퍼 유니폼 1",
        "concept": "선명한 레드 컬러와 다이내믹 브러시 패턴으로 골문을 든든하게 지켜내는 수문장 킷",
        "image_url": "/static/images/gk-kit-01.png",
        "votes": 0,
        "badge": "GK 1st"
    },
    {
        "id": "gk-kit-02",
        "kit_code": "GK KIT 02",
        "name": "골키퍼 유니폼 2",
        "concept": "생동감 넘치는 에메랄드 그린과 딥 그린 패턴이 조화를 이루는 전문 골키퍼 킷",
        "image_url": "/static/images/gk-kit-02.png",
        "votes": 0,
        "badge": "GK 2nd"
    }
]

# 투표 상태 메모리 저장소 (추후 Supabase DB 연동 확장)
_vote_store = {c["id"]: c["votes"] for c in INITIAL_VOTE_CANDIDATES}

def get_vote_candidates() -> List[Dict[str, Any]]:
    """투표 후보 목록 및 득표수, 백분율 계산 반환"""
    total = sum(_vote_store.values())
    candidates = []
    for c in INITIAL_VOTE_CANDIDATES:
        votes = _vote_store.get(c["id"], 0)
        percentage = round((votes / total * 100), 1) if total > 0 else 0
        candidates.append({
            **c,
            "votes": votes,
            "percentage": percentage
        })
    return candidates

def cast_vote(candidate_id: str) -> Optional[Dict[str, Any]]:
    """후보에 1표 추가 후 갱신된 투표 현황 반환"""
    if candidate_id in _vote_store:
        _vote_store[candidate_id] += 1
        total = sum(_vote_store.values())
        return {
            "success": True,
            "candidate_id": candidate_id,
            "total_votes": total,
            "results": get_vote_candidates()
        }
    return None
