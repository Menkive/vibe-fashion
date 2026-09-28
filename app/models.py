# app/models.py - 양산시민축구단 공식 스토어 상품 및 투표 데이터 모델
from typing import List, Dict, Any, Optional

# K리그 구단 공식 온라인 스토어 기준 8개 상품 카탈로그
INITIAL_PRODUCTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "2026 어센틱 홈 유니폼",
        "slug": "2026-authentic-home-jersey",
        "category": "유니폼",
        "price": 99000,
        "original_price": 119000,
        "description": "양산의 푸른 투혼을 담은 로열 블루 & 골드 라인 공식 홈 저지. 선수단 실착 어센틱 사양으로 흡습속건 쿨링 테크 원단과 3D 엠블럼이 적용되어 있습니다.",
        "image_url": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=800&q=80",
        "thumbnail_url": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=800&q=80",
        "stock": 50,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "badge": "BEST",
        "is_featured": True,
        "is_new": True,
        "sales_count": 1820
    },
    {
        "id": 2,
        "name": "2026 어센틱 원정 유니폼",
        "slug": "2026-authentic-away-jersey",
        "category": "유니폼",
        "price": 99000,
        "original_price": 119000,
        "description": "원정 경기에서도 빛나는 순백의 화이트 & 로열 블루 포인트 어센틱 저지. 통기성이 뛰어난 에어로 매쉬 패널을 측면에 배치했습니다.",
        "image_url": "https://images.unsplash.com/photo-1577223625816-7546f13df25d?auto=format&fit=crop&w=800&q=80",
        "thumbnail_url": "https://images.unsplash.com/photo-1577223625816-7546f13df25d?auto=format&fit=crop&w=800&q=80",
        "stock": 42,
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "badge": "BEST",
        "is_featured": True,
        "is_new": True,
        "sales_count": 1410
    },
    {
        "id": 3,
        "name": "양산FC 공식 응원 머플러",
        "slug": "yangsan-fc-official-cheering-muffler",
        "category": "액세서리",
        "price": 22000,
        "original_price": 25000,
        "description": "경기장 스탠드를 가득 채울 응원의 필수 아이템! 고밀도 니트 자카드 양면 머플러로 구단 슬로건 '푸른 투혼 양산'이 새겨져 있습니다.",
        "image_url": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=800&q=80",
        "thumbnail_url": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=800&q=80",
        "stock": 120,
        "sizes": ["Free"],
        "badge": "HOT",
        "is_featured": True,
        "is_new": False,
        "sales_count": 2350
    },
    {
        "id": 4,
        "name": "양산FC 공식 세라믹 머그컵",
        "slug": "yangsan-fc-official-mug",
        "category": "생활용품",
        "price": 15000,
        "original_price": 18000,
        "description": "구단 공식 골드 엠블럼이 각인된 350ml 고급 도자기 머그컵. 홈 & 오피스에서 양산FC의 자부심을 함께 느껴보세요.",
        "image_url": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=800&q=80",
        "thumbnail_url": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=800&q=80",
        "stock": 80,
        "sizes": ["Free"],
        "badge": "MD추천",
        "is_featured": False,
        "is_new": False,
        "sales_count": 890
    },
    {
        "id": 5,
        "name": "양산FC 엠블럼 스마트폰 케이스",
        "slug": "yangsan-fc-phone-case",
        "category": "액세서리",
        "price": 19000,
        "original_price": 22000,
        "description": "충격 흡수 범퍼 하드 케이스. 구단 로고와 감각적인 스트라이프 패턴으로 스타일과 내구성을 동시에 잡았습니다.",
        "image_url": "https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?auto=format&fit=crop&w=800&q=80",
        "thumbnail_url": "https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?auto=format&fit=crop&w=800&q=80",
        "stock": 95,
        "sizes": ["Free"],
        "badge": "POPULAR",
        "is_featured": False,
        "is_new": True,
        "sales_count": 920
    },
    {
        "id": 6,
        "name": "양산FC 아크릴 유니폼 키링",
        "slug": "yangsan-fc-jersey-keyring",
        "category": "액세서리",
        "price": 8000,
        "original_price": 10000,
        "description": "2026 시즌 홈 유니폼 모양의 귀여운 아크릴 키링. 가방, 차키, 파우치 등에 가볍게 걸 수 있는 베스트 굿즈입니다.",
        "image_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=800&q=80",
        "thumbnail_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=800&q=80",
        "stock": 200,
        "sizes": ["Free"],
        "badge": "BEST",
        "is_featured": True,
        "is_new": False,
        "sales_count": 3100
    },
    {
        "id": 7,
        "name": "골드 엠블럼 매치 볼캡 (모자)",
        "slug": "yangsan-fc-match-ballcap",
        "category": "의류",
        "price": 29000,
        "original_price": 35000,
        "description": "딥 네이비 원단에 정밀 골드 입체 자수 엠블럼이 포인트인 클래식 코튼 볼캡. 후면 버클 스트랩으로 사이즈 조절이 가능합니다.",
        "image_url": "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?auto=format&fit=crop&w=800&q=80",
        "thumbnail_url": "https://images.unsplash.com/photo-1588850561407-ed78c282e89b?auto=format&fit=crop&w=800&q=80",
        "stock": 65,
        "sizes": ["Free"],
        "badge": "HOT",
        "is_featured": False,
        "is_new": True,
        "sales_count": 1640
    },
    {
        "id": 8,
        "name": "2026 공식 그래픽 스티커팩 (6종)",
        "slug": "yangsan-fc-official-sticker-pack",
        "category": "생활용품",
        "price": 6000,
        "original_price": 8000,
        "description": "방수 코팅 처리된 고급 리무버블 스티커팩 6종 세트. 노트북, 태블릿, 캐리어, 텀블러 등에 부착하기 좋습니다.",
        "image_url": "https://images.unsplash.com/photo-1572375992501-4b0892d50c69?auto=format&fit=crop&w=800&q=80",
        "thumbnail_url": "https://images.unsplash.com/photo-1572375992501-4b0892d50c69?auto=format&fit=crop&w=800&q=80",
        "stock": 150,
        "sizes": ["Free"],
        "badge": "NEW",
        "is_featured": False,
        "is_new": True,
        "sales_count": 1150
    }
]

# 2027 시즌 유니폼 디자인 팬 투표 데이터 (메모리 및 DB 연동 확장용)
INITIAL_VOTE_CANDIDATES = [
    {
        "id": "design-a",
        "name": "Design A - 헤리티지 로열 스트라이프",
        "code": "Design A",
        "concept": "양산의 푸른 산천과 투혼을 담은 클래식 로열 블루 세로 스트라이프와 골드 넥 라인",
        "image_url": "https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&fit=crop&w=800&q=80",
        "votes": 120,
        "badge": "현재 1위"
    },
    {
        "id": "design-b",
        "name": "Design B - 모던 다이내믹 웨이브",
        "code": "Design B",
        "concept": "낙동강의 물결과 선수단의 속도감을 상징하는 기하학적 그라데이션 패턴",
        "image_url": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80",
        "votes": 87,
        "badge": "인기 급상승"
    },
    {
        "id": "design-c",
        "name": "Design C - 미니멀 골드 엣지",
        "code": "Design C",
        "concept": "절제된 다크 로열 네이비 바탕에 소매와 엠블럼을 골드 메탈릭 박으로 마감한 럭셔리 라인",
        "image_url": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=800&q=80",
        "votes": 64,
        "badge": "팬 추천"
    }
]

# 투표 상태 메모리 저장소 (추후 Supabase DB 연동 확장)
_vote_store = {c["id"]: c["votes"] for c in INITIAL_VOTE_CANDIDATES}

def get_vote_candidates() -> List[Dict[str, Any]]:
    """투표 후보 목록 및 득표수, 백분율 계산 반환"""
    total = sum(_vote_store.values()) or 1
    candidates = []
    for c in INITIAL_VOTE_CANDIDATES:
        votes = _vote_store.get(c["id"], 0)
        percentage = round((votes / total) * 100, 1)
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
