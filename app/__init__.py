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

    # 로케일 통화 필터 (한국 숫자 포맷)
    @app.template_filter('locale_currency')
    def locale_currency_filter(value):
        if value is None or value == '':
            return '0원'
        try:
            num = int(float(value))
            return f"{num:,}원"
        except (ValueError, TypeError):
            return f"{value}원"

    # routes 폴더에서 블루프린트(라우트 모듈) 가져오기
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp

    # 앱에 블루프린트 등록
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    # 전역 요청 가드: 약관 동의를 완료하지 않은 소셜 로그인 회원은 /auth/social-signup 외 다른 페이지 접근 제한
    from flask import request as flask_req, redirect, url_for, session as flask_sess
    @app.before_request
    def check_pending_social_signup():
        if flask_sess.get('pending_social_signup'):
            allowed_paths = [
                '/auth/social-signup',
                '/auth/social-signup/complete',
                '/auth/logout',
                '/logout',
                '/static/'
            ]
            req_path = flask_req.path
            if not any(req_path.startswith(p) for p in allowed_paths):
                return redirect(url_for('auth.social_signup_step'))

    return app

# Gunicorn에서 'app' 패키지 자체를 import할 때 'app' 속성을 찾을 수 있도록 기본 인스턴스 생성
app = create_app()

