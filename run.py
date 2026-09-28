# run.py - 애플리케이션 진입점 실행 파일
from app import create_app

# create_app() 팩토리 함수를 호출하여 Flask 인스턴스 생성
app = create_app()

if __name__ == '__main__':
    # 디버그 모드로 로컬 서버 실행 (포트 5000)
    print("\n" + "="*60, flush=True)
    print(" 양산시민축구단 공식 온라인 스토어 웹 서버가 시작되었습니다!", flush=True)
    print(" 접속 주소: http://127.0.0.1:5000", flush=True)
    print("="*60 + "\n", flush=True)
    app.run(host='127.0.0.1', port=5000, debug=True)
