# app/__init__.py - VIBE-FASHION 앱 팩토리 파일
from flask import Flask
from dotenv import load_dotenv
import os

def create_app():
    """
    Flask 애플리케이션 팩토리 함수:
    앱 인스턴스를 생성하고 환경 설정 및 블루프린트(라우트)를 등록합니다.
    """
    # .env 파일에서 환경 변수 불러오기
    load_dotenv()

    # Flask 앱 객체 생성
    app = Flask(__name__)

    # 기본 비밀 키 설정 (세션 및 보안에 사용)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-vibe-fashion-secret-key')

    # Jinja2 템플릿 필터 등록: 가격 포맷팅 시 ValueError 방지
    @app.template_filter('currency')
    def currency_filter(value):
        if value is None or value == '':
            return ''
        if isinstance(value, str):
            if '원' in value:
                return value
            # 문자열 숫자 처리
            clean_str = value.replace(',', '').strip()
            try:
                num = int(float(clean_str))
                return f"{num:,}원"
            except (ValueError, TypeError):
                return f"{value}원"
        try:
            return f"{int(value):,}원"
        except (ValueError, TypeError):
            return f"{value}원"

    # routes 폴더에서 블루프린트(라우트 모듈) 가져오기
    from app.routes.main import main_bp

    # 앱에 블루프린트 등록
    app.register_blueprint(main_bp)

    return app

# Gunicorn에서 'app' 패키지 자체를 import할 때 'app' 속성을 찾을 수 있도록 기본 인스턴스 생성
app = create_app()

