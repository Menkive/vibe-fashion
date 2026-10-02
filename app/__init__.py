# app/__init__.py - VIBE-FASHION 앱 팩토리 파일
from flask import Flask, jsonify, request, session
from dotenv import load_dotenv
import os
import secrets
import hmac

def create_app():
    """
    Flask 애플리케이션 팩토리 함수:
    앱 인스턴스를 생성하고 환경 설정 및 블루프린트(라우트)를 등록합니다.
    """
    # .env 파일에서 환경 변수 불러오기
    load_dotenv()

    # Flask 앱 객체 생성
    app = Flask(__name__)

    # 운영 환경은 고정 비밀 키가 반드시 환경변수로 제공되어야 한다.
    secret_key = os.getenv('SECRET_KEY')
    is_production = (
        os.getenv('APP_ENV', '').lower() == 'production'
        or os.getenv('FLASK_ENV', '').lower() == 'production'
        or bool(os.getenv('WEBSITE_INSTANCE_ID'))
    )
    if not secret_key and is_production:
        raise RuntimeError('운영 환경에서는 SECRET_KEY 환경변수가 필요합니다.')
    app.config['SECRET_KEY'] = secret_key or secrets.token_hex(32)

    secure_cookie_setting = os.getenv('SESSION_COOKIE_SECURE')
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=(
            secure_cookie_setting.strip().lower() in {'1', 'true', 'yes', 'on'}
            if secure_cookie_setting is not None
            else is_production
        ),
    )

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

    @app.context_processor
    def inject_csrf_token():
        def generate_csrf_token():
            token = session.get('_csrf_token')
            if not token:
                token = secrets.token_urlsafe(32)
                session['_csrf_token'] = token
            return token

        return {'csrf_token': generate_csrf_token}

    csrf_protected_endpoints = {
        'main.login', 'main.signup', 'main.logout',
        'auth.login', 'auth.signup', 'auth.resend_confirmation',
        'auth.complete_social_signup', 'auth.forgot_password', 'auth.reset_password',
        'admin.adjust_inventory', 'admin.add_product_option', 'admin.update_product_option',
    }

    @app.before_request
    def protect_auth_posts():
        if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return None
        if request.endpoint not in csrf_protected_endpoints:
            return None

        submitted_token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        session_token = session.get('_csrf_token')
        if not submitted_token or not session_token or not hmac.compare_digest(submitted_token, session_token):
            if request.is_json:
                return jsonify({'success': False, 'message': '요청 보안 토큰이 만료되었습니다. 페이지를 새로고침해 주세요.'}), 400
            return '요청 보안 토큰이 올바르지 않습니다. 페이지를 새로고침해 주세요.', 400
        return None

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

