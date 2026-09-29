# app/routes/auth.py - Supabase Auth 기반 회원 인증 라우트 및 데코레이터
import os
import re
import sys
import logging
from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from app.routes.main import get_supabase_client

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 서비스 기본 URL 설정
SITE_URL = os.getenv("SITE_URL", "http://localhost:5000")


def login_required(f):
    """
    로그인 필수 데코레이터:
    Flask session에 user_id가 없으면 로그인 페이지로 리다이렉트합니다.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", error="login_required"))
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# 1. 로그인 (GET/POST /auth/login)
# ==============================================================================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """이메일/비밀번호 로그인 처리"""
    if request.method == 'GET':
        # 이미 로그인되어 있는 경우 마이페이지로 이동
        if session.get('user_id'):
            return redirect(url_for('main.mypage'))
        return render_template('auth/login.html')

    # POST 처리
    email = (request.form.get('email') or '').strip()
    password = request.form.get('password') or ''

    if not email or not password:
        return redirect(url_for('auth.login', error='invalid_credentials'))

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for('auth.login', error='server_error'))

    try:
        auth_res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        user = auth_res.user
        if not user:
            return redirect(url_for('auth.login', error='invalid_credentials'))

        # 이메일 인증 완료 여부 확인
        # Supabase user 객체의 confirmed_at 또는 email_confirmed_at 속성 검사
        is_confirmed = False
        if getattr(user, 'email_confirmed_at', None) or getattr(user, 'confirmed_at', None):
            is_confirmed = True

        if not is_confirmed:
            # 이메일 미인증 상태일 때 세션 저장 없이 에러 처리
            return redirect(url_for('auth.login', error='email_not_confirmed'))

        # 세션에 회원 정보 저장
        user_metadata = getattr(user, 'user_metadata', {}) or {}
        user_name = user_metadata.get('full_name') or user_metadata.get('name') or email.split('@')[0]

        session['user_id'] = str(user.id)
        session['email'] = user.email
        session['user'] = {
            "id": str(user.id),
            "email": user.email,
            "name": user_name,
            "phone": user_metadata.get('phone', '')
        }
        if auth_res.session:
            session['access_token'] = auth_res.session.access_token
            if getattr(auth_res.session, 'refresh_token', None):
                session['refresh_token'] = auth_res.session.refresh_token

        return redirect(url_for('main.mypage'))

    except Exception as e:
        err_msg = str(e).lower()
        logger.warning(f"로그인 실패: {e}")
        if "invalid login credentials" in err_msg or "invalid credentials" in err_msg:
            return redirect(url_for('auth.login', error='invalid_credentials'))
        elif "email not confirmed" in err_msg:
            return redirect(url_for('auth.login', error='email_not_confirmed'))
        return redirect(url_for('auth.login', error='login_failed'))


# ==============================================================================
# 2. 회원가입 (GET/POST /auth/signup)
# ==============================================================================

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """회원가입 처리 및 이메일 인증 발송"""
    if request.method == 'GET':
        if session.get('user_id'):
            return redirect(url_for('main.mypage'))
        return render_template('auth/signup.html')

    # POST 처리
    email = (request.form.get('email') or '').strip()
    password = request.form.get('password') or ''
    password_confirm = request.form.get('password_confirm') or ''

    # 이메일 형식 정규식 검사
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not email or not re.match(email_regex, email):
        return redirect(url_for('auth.signup', error='invalid_email'))

    if not password or len(password) < 6:
        return redirect(url_for('auth.signup', error='password_too_short'))

    if password != password_confirm:
        return redirect(url_for('auth.signup', error='password_mismatch'))

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for('auth.signup', error='server_error'))

    try:
        # 이메일 인증 후 돌아올 URL 설정 ({SITE_URL}/auth/confirm)
        confirm_redirect_url = f"{SITE_URL.rstrip('/')}/auth/confirm"

        auth_res = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "email_redirect_to": confirm_redirect_url
            }
        })

        if not auth_res or not auth_res.user:
            return redirect(url_for('auth.signup', error='signup_failed'))

        return redirect(url_for('auth.signup_complete', email=email))

    except Exception as e:
        err_msg = str(e).lower()
        logger.warning(f"회원가입 실패: {e}")
        if "user already registered" in err_msg or "already exists" in err_msg:
            return redirect(url_for('auth.signup', error='already_registered'))
        return redirect(url_for('auth.signup', error='signup_failed'))


# ==============================================================================
# 3. 회원가입 완료 안내 (GET /auth/signup-complete)
# ==============================================================================

@auth_bp.route('/signup-complete', methods=['GET'])
def signup_complete():
    """회원가입 완료 및 이메일 인증 안내 화면"""
    email = request.args.get('email', '')
    return render_template('auth/signup_complete.html', email=email)


@auth_bp.route('/resend-confirmation', methods=['POST'])
def resend_confirmation():
    """회원가입 인증 이메일 재전송 (Supabase Auth resend)"""
    data = request.get_json(silent=True) or request.form
    email = (data.get('email') or '').strip()
    is_json = request.is_json or bool(request.get_json(silent=True))

    if not email:
        if is_json:
            return jsonify({"success": False, "message": "이메일 주소를 입력해 주세요."}), 400
        return redirect(url_for('auth.signup_complete', error='missing_email'))

    supabase = get_supabase_client()
    if not supabase:
        if is_json:
            return jsonify({"success": False, "message": "인증 서버에 연결할 수 없습니다."}), 503
        return redirect(url_for('auth.signup_complete', error='server_error'))

    try:
        base_url = SITE_URL
        if request.host_url:
            base_url = request.host_url.rstrip('/')
        confirm_redirect_url = f"{base_url}/auth/confirm"

        supabase.auth.resend({
            "type": "signup",
            "email": email,
            "options": {
                "email_redirect_to": confirm_redirect_url
            }
        })

        msg = "인증 메일이 재발송되었습니다. 메일함을 확인해 주세요."
        if is_json:
            return jsonify({"success": True, "message": msg})
        return redirect(url_for('auth.signup_complete', success='resend_success', email=email))

    except Exception as e:
        logger.warning(f"인증 메일 재전송 실패: {e}")
        msg = "인증 메일이 재발송되었습니다. 메일함을 확인해 주세요."
        if is_json:
            return jsonify({"success": True, "message": msg})
        return redirect(url_for('auth.signup_complete', success='resend_success', email=email))


# ==============================================================================
# 4. 이메일 인증 처리 (GET /auth/confirm)
# ==============================================================================

@auth_bp.route('/confirm', methods=['GET'])
def confirm():
    """
    Supabase 이메일 인증 링크 클릭 시 호출되는 라우트.
    token_hash, type 또는 token/otp 파라미터를 읽어 verify_otp를 실행합니다.
    """
    token_hash = request.args.get('token_hash')
    otp_type = request.args.get('type', 'email')
    token = request.args.get('token')
    email = request.args.get('email')

    supabase = get_supabase_client()
    if not supabase:
        return redirect(url_for('auth.login', error='email_confirmation_failed'))

    try:
        auth_res = None
        # token_hash 방식 확인
        if token_hash:
            auth_res = supabase.auth.verify_otp({
                "token_hash": token_hash,
                "type": otp_type
            })
        elif token and email:
            # 이메일 + 토큰 방식
            auth_res = supabase.auth.verify_otp({
                "email": email,
                "token": token,
                "type": otp_type
            })

        if auth_res and auth_res.user:
            user = auth_res.user
            user_metadata = getattr(user, 'user_metadata', {}) or {}
            user_name = user_metadata.get('full_name') or user_metadata.get('name') or (user.email.split('@')[0] if user.email else '')

            # 세션에 정보 저장
            session['user_id'] = str(user.id)
            session['email'] = user.email
            session['user'] = {
                "id": str(user.id),
                "email": user.email,
                "name": user_name,
                "phone": user_metadata.get('phone', '')
            }
            if auth_res.session:
                session['access_token'] = auth_res.session.access_token
                if getattr(auth_res.session, 'refresh_token', None):
                    session['refresh_token'] = auth_res.session.refresh_token

            return redirect(url_for('main.mypage', success='email_confirmed'))
        else:
            return redirect(url_for('auth.login', error='email_confirmation_failed'))

    except Exception as e:
        logger.warning(f"이메일 인증 확인 오류: {e}")
        return redirect(url_for('auth.login', error='email_confirmation_failed'))


# ==============================================================================
# 5. 비밀번호 찾기 (GET/POST /auth/forgot-password)
# ==============================================================================

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """비밀번호 재설정 링크 발송"""
    if request.method == 'GET':
        return render_template('auth/forgot_password.html')

    # POST 처리 (JSON 또는 form 지원)
    data = request.get_json(silent=True) or request.form
    email = (data.get('email') or '').strip()
    is_json = request.is_json or bool(request.get_json(silent=True))

    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not email:
        if is_json:
            return jsonify({"success": False, "message": "이메일 주소를 입력해 주세요."}), 400
        return redirect(url_for('auth.forgot_password', error='missing_email'))

    if not re.match(email_regex, email):
        if is_json:
            return jsonify({"success": False, "message": "올바른 이메일 주소를 입력해 주세요."}), 400
        return redirect(url_for('auth.forgot_password', error='invalid_email'))

    supabase = get_supabase_client()
    if not supabase:
        if is_json:
            return jsonify({"success": False, "message": "인증 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."}), 503
        return redirect(url_for('auth.forgot_password', error='server_error'))

    try:
        # 현재 사이트 호스트(URL) 기준으로 redirectTo 구성
        base_url = SITE_URL
        if request.host_url:
            base_url = request.host_url.rstrip('/')
        reset_redirect_url = f"{base_url}/auth/reset-password"

        supabase.auth.reset_password_for_email(
            email,
            options={"redirect_to": reset_redirect_url}
        )
        # 보안상 해당 이메일의 가입 여부와 무관하게 성공 메시지 전달
        msg = "비밀번호 재설정 이메일을 발송했습니다.\n이메일의 안내에 따라 비밀번호를 변경해 주세요."
        if is_json:
            return jsonify({"success": True, "message": msg})
        return redirect(url_for('auth.forgot_password', success='email_sent'))

    except Exception as e:
        logger.warning(f"비밀번호 재설정 이메일 발송 오류: {e}")
        msg = "비밀번호 재설정 이메일을 발송했습니다.\n이메일의 안내에 따라 비밀번호를 변경해 주세요."
        if is_json:
            return jsonify({"success": True, "message": msg})
        return redirect(url_for('auth.forgot_password', success='email_sent'))


# ==============================================================================
# 6. 비밀번호 재설정 (GET/POST /auth/reset-password)
# ==============================================================================

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """비밀번호 재설정 처리"""
    if request.method == 'GET':
        # 토큰 파라미터가 링크에 포함되어 들어올 수 있으므로 세션 복구 시도
        token_hash = request.args.get('token_hash')
        otp_type = request.args.get('type', 'recovery')
        access_token = request.args.get('access_token')
        refresh_token = request.args.get('refresh_token')

        supabase = get_supabase_client()
        if supabase:
            if token_hash:
                try:
                    auth_res = supabase.auth.verify_otp({
                        "token_hash": token_hash,
                        "type": otp_type
                    })
                    if auth_res and auth_res.session:
                        session['access_token'] = auth_res.session.access_token
                        if getattr(auth_res.session, 'refresh_token', None):
                            session['refresh_token'] = auth_res.session.refresh_token
                        if auth_res.user:
                            session['reset_user_id'] = str(auth_res.user.id)
                except Exception as e:
                    logger.warning(f"리셋 토큰 인증 실패: {e}")
            elif access_token:
                session['access_token'] = access_token
                if refresh_token:
                    session['refresh_token'] = refresh_token

        return render_template('auth/reset_password.html')

    # POST 처리 (JSON 또는 form 지원)
    data = request.get_json(silent=True) or request.form
    is_json = request.is_json or bool(request.get_json(silent=True))

    password = data.get('password') or ''
    password_confirm = data.get('password_confirm') or ''
    access_token = data.get('access_token') or session.get('access_token')
    refresh_token = data.get('refresh_token') or session.get('refresh_token')

    if not password:
        if is_json:
            return jsonify({"success": False, "message": "새 비밀번호를 입력해 주세요."}), 400
        return redirect(url_for('auth.reset_password', error='missing_password'))

    if len(password) < 6:
        if is_json:
            return jsonify({"success": False, "message": "비밀번호는 최소 6자 이상이어야 합니다."}), 400
        return redirect(url_for('auth.reset_password', error='password_too_short'))

    if password != password_confirm:
        if is_json:
            return jsonify({"success": False, "message": "비밀번호가 일치하지 않습니다."}), 400
        return redirect(url_for('auth.reset_password', error='password_mismatch'))

    supabase = get_supabase_client()
    if not supabase:
        if is_json:
            return jsonify({"success": False, "message": "인증 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."}), 503
        return redirect(url_for('auth.reset_password', error='server_error'))

    try:
        # access_token이 있으면 세션 복구 후 update_user 실행
        if access_token:
            try:
                supabase.auth.set_session(access_token, refresh_token or "")
            except Exception as se:
                logger.warning(f"세션 설정 실패: {se}")

        # Supabase 사용자 비밀번호 변경 호출
        supabase.auth.update_user({
            "password": password
        })

        # 임시 리셋 세션 정보 정리
        session.pop('reset_user_id', None)

        msg = "비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해 주세요."
        if is_json:
            return jsonify({"success": True, "message": msg})
        return redirect(url_for('auth.login', success='password_reset'))

    except Exception as e:
        err_msg = str(e).lower()
        logger.warning(f"비밀번호 변경 실패: {e}")
        if "session" in err_msg or "token" in err_msg or "expired" in err_msg or "unauthorized" in err_msg:
            if is_json:
                return jsonify({"success": False, "message": "비밀번호 재설정 세션이 만료되었습니다. 재설정 이메일을 다시 요청해 주세요."}), 400
            return redirect(url_for('auth.reset_password', error='invalid_or_expired_token'))
        if is_json:
            return jsonify({"success": False, "message": "비밀번호 재설정에 실패했습니다. 잠시 후 다시 시도해 주세요."}), 400
        return redirect(url_for('auth.reset_password', error='reset_failed'))
