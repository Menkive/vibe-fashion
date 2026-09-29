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
# 3-1. 카카오 소셜 로그인 (GET /auth/kakao, GET /auth/callback)
# ==============================================================================

@auth_bp.route('/kakao')
def kakao_login():
    """
    카카오 OAuth 소셜 로그인 시작:
    1순위 (직접 인가): KAKAO_CLIENT_ID가 설정되어 있거나 Supabase에 등록된 REST API 키를 사용하여
                     카카오 공식 인가 엔드포인트(kauth.kakao.com)로 직접 요청합니다.
                     (이 방식은 Supabase의 기본 account_email 강제 요구로 인한 개인앱 KOE205 에러를 완벽히 우회합니다.)
    2순위: Supabase Auth 내장 Provider ('kakao')
    """
    base_url = SITE_URL
    if request.host_url:
        base_url = request.host_url.rstrip('/')
    callback_url = f"{base_url}/auth/callback"

    # 카카오 REST API 키 (환경변수 또는 Supabase 프로젝트에 등록된 클라이언트 키)
    kakao_client_id = (
        os.getenv("KAKAO_CLIENT_ID") or
        os.getenv("KAKAO_REST_API_KEY") or
        "8d2260c46401c073f2873b4919c1f169"  # Supabase 설정에 등록된 카카오 앱 REST API 키
    )

    if kakao_client_id:
        import secrets
        import urllib.parse
        state = secrets.token_urlsafe(16)
        session['kakao_oauth_state'] = state

        kakao_params = {
            "client_id": kakao_client_id,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": "profile_nickname,profile_image",
            "state": state
        }
        kakao_auth_url = f"https://kauth.kakao.com/oauth/authorize?{urllib.parse.urlencode(kakao_params)}"
        return redirect(kakao_auth_url)

    # 대체 방식: Supabase Auth 내장 Provider
    supabase = get_supabase_client()
    if supabase:
        try:
            res = supabase.auth.sign_in_with_oauth({
                "provider": "kakao",
                "options": {
                    "redirect_to": callback_url
                }
            })
            if res and res.url:
                return redirect(res.url)
        except Exception as e:
            logger.warning(f"Supabase Kakao OAuth URL 생성 예외: {e}")

    logger.error("카카오 로그인 설정(KAKAO_CLIENT_ID)이 필요합니다.")
    return redirect(url_for('main.login', error='kakao_not_configured'))


@auth_bp.route('/google')
def google_login():
    """
    Google OAuth 소셜 로그인 시작:
    Supabase Auth 내장 Provider ('google')를 호출하여 Google OAuth 동의 화면으로 리다이렉트합니다.
    """
    base_url = SITE_URL
    if request.host_url:
        base_url = request.host_url.rstrip('/')
    callback_url = f"{base_url}/auth/callback"

    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase 클라이언트를 초기화할 수 없습니다.")
        return redirect(url_for('main.login', error='google_failed'))

    try:
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": callback_url
            }
        })
        if res and res.url:
            # PKCE flow를 위한 code_verifier를 Flask 세션에 백업
            try:
                code_verifier = supabase.auth._storage.get_item(f"{supabase.auth._storage_key}-code-verifier")
                if code_verifier:
                    session['oauth_code_verifier'] = code_verifier
            except Exception as ve:
                logger.debug(f"code_verifier 백업 알림: {ve}")

            return redirect(res.url)
        else:
            logger.error("Supabase Google OAuth URL 생성 실패 (응답 URL 없음)")
            return redirect(url_for('main.login', error='google_not_configured'))
    except Exception as e:
        logger.error(f"Supabase Google OAuth URL 생성 오류: {e}")
        return redirect(url_for('main.login', error='google_failed'))


@auth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """
    Supabase OAuth 공통 콜백 처리 라우트 (카카오 / Google):
    OAuth 로그인 인증 후 code를 교환하여 세션을 생성하고 로그인 상태로 전환합니다.
    """
    # 사용자가 OAuth 로그인 화면에서 취소하거나 에러가 반환된 경우
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    if error:
        logger.warning(f"OAuth 로그인 취소/실패: {error} ({error_description})")
        if 'access_denied' in str(error).lower() or 'cancel' in str(error).lower():
            return redirect(url_for('main.login', error='oauth_cancelled'))
        return redirect(url_for('main.login', error='oauth_failed'))

    code = request.args.get('code')
    if not code:
        logger.warning("OAuth 콜백에 code 파라미터가 없습니다.")
        return redirect(url_for('main.login', error='oauth_failed'))

    base_url = SITE_URL
    if request.host_url:
        base_url = request.host_url.rstrip('/')
    callback_url = f"{base_url}/auth/callback"

    supabase = get_supabase_client()
    session_established = False

    # 1. Supabase PKCE Code Exchange 시도 (Google 및 Supabase 연동 카카오)
    if supabase:
        try:
            code_verifier = session.pop('oauth_code_verifier', None)
            exchange_params = {
                "auth_code": code,
                "redirect_to": callback_url
            }
            if code_verifier:
                exchange_params["code_verifier"] = code_verifier

            auth_res = supabase.auth.exchange_code_for_session(exchange_params)
            if auth_res and auth_res.user:
                user = auth_res.user
                user_metadata = getattr(user, 'user_metadata', {}) or {}
                app_metadata = getattr(user, 'app_metadata', {}) or {}
                provider = app_metadata.get('provider') or 'oauth'

                user_name = (
                    user_metadata.get('full_name') or
                    user_metadata.get('name') or
                    user_metadata.get('nickname') or
                    (user.email.split('@')[0] if user.email else f"{provider}회원")
                )

                session['user_id'] = str(user.id)
                session['email'] = user.email or f"{provider}_{user.id[:8]}@yangsanfc.local"
                session['user'] = {
                    "id": str(user.id),
                    "email": session['email'],
                    "name": user_name,
                    "phone": user_metadata.get('phone', ''),
                    "provider": provider,
                    "avatar_url": user_metadata.get('avatar_url') or user_metadata.get('picture', '')
                }
                if auth_res.session:
                    session['access_token'] = auth_res.session.access_token
                    if getattr(auth_res.session, 'refresh_token', None):
                        session['refresh_token'] = auth_res.session.refresh_token

                session_established = True
                logger.info(f"Supabase OAuth 로그인 성공 ({provider}): {user_name} ({user.id})")
        except Exception as se:
            logger.warning(f"Supabase exchange_code_for_session 실패: {se}")

    # 2. Supabase 내장 교환 실패 시: 카카오 REST 직접 연동 토큰 및 프로필 조회 폴백
    if not session_established:
        kakao_client_id = os.getenv("KAKAO_CLIENT_ID") or os.getenv("KAKAO_REST_API_KEY")
        kakao_client_secret = os.getenv("KAKAO_CLIENT_SECRET")

        if kakao_client_id:
            try:
                import httpx
                # 토큰 발급 요청
                token_data = {
                    "grant_type": "authorization_code",
                    "client_id": kakao_client_id,
                    "redirect_uri": callback_url,
                    "code": code
                }
                if kakao_client_secret:
                    token_data["client_secret"] = kakao_client_secret

                token_res = httpx.post(
                    "https://kauth.kakao.com/oauth/token",
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
                    timeout=10.0
                )

                if token_res.status_code == 200:
                    tokens = token_res.json()
                    kakao_access_token = tokens.get("access_token")

                    # 카카오 사용자 정보 조회
                    user_res = httpx.get(
                        "https://kapi.kakao.com/v2/user/me",
                        headers={"Authorization": f"Bearer {kakao_access_token}"},
                        timeout=10.0
                    )

                    if user_res.status_code == 200:
                        kakao_user = user_res.json()
                        kakao_id = str(kakao_user.get("id"))
                        kakao_account = kakao_user.get("kakao_account", {})
                        profile = kakao_account.get("profile", {})

                        nickname = profile.get("nickname") or f"양산팬_{kakao_id[-4:]}"
                        email = kakao_account.get("email") or f"kakao_{kakao_id}@yangsanfc.local"
                        avatar_url = profile.get("profile_image_url") or profile.get("thumbnail_image_url") or ""

                        # 세션에 카카오 회원 로그인 상태 등록
                        user_uuid = f"kakao-{kakao_id}"
                        session['user_id'] = user_uuid
                        session['email'] = email
                        session['user'] = {
                            "id": user_uuid,
                            "email": email,
                            "name": nickname,
                            "phone": "",
                            "provider": "kakao",
                            "avatar_url": avatar_url
                        }
                        session['kakao_access_token'] = kakao_access_token
                        session_established = True
                        logger.info(f"카카오 직접 토큰 인증 로그인 성공: {nickname} ({user_uuid})")
                    else:
                        logger.error(f"카카오 사용자 정보 요청 실패: {user_res.text}")
                else:
                    logger.error(f"카카오 토큰 발급 요청 실패: {token_res.text}")
            except Exception as ke:
                logger.error(f"카카오 직접 인증 처리 중 오류: {ke}")

    if session_established:
        return redirect(url_for('main.index'))
    else:
        return redirect(url_for('main.login', error='kakao_failed'))


# ==============================================================================
# 3-2. 네이버 소셜 로그인 (GET /auth/naver & GET /auth/naver/callback)
# ==============================================================================

@auth_bp.route('/naver', methods=['GET'])
def naver_login():
    """
    네이버 OAuth 인가 요청 시작 라우트:
    CSRF 방지를 위한 state 토큰을 생성하고 네이버 인가 페이지로 리다이렉트합니다.
    """
    import secrets
    import urllib.parse

    client_id = os.getenv("NAVER_CLIENT_ID")
    if not client_id:
        logger.error("네이버 로그인 설정(NAVER_CLIENT_ID)이 필요합니다.")
        return redirect(url_for('main.login', error='naver_not_configured'))

    base_url = SITE_URL
    if request.host_url:
        base_url = request.host_url.rstrip('/')
    callback_url = f"{base_url}/auth/naver/callback"

    # CSRF 방어용 state 난수 생성 및 세션 저장
    state = secrets.token_urlsafe(16)
    session['naver_oauth_state'] = state

    naver_auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback_url,
        "state": state
    }
    naver_auth_url = f"https://nid.naver.com/oauth2.0/authorize?{urllib.parse.urlencode(naver_auth_params)}"
    return redirect(naver_auth_url)


@auth_bp.route('/naver/callback', methods=['GET'])
def naver_callback():
    """
    네이버 OAuth 콜백 처리 라우트:
    인가 코드 및 state 검증 후 토큰을 교환하고 프로필 정보를 세션에 등록합니다.
    """
    # 사용자가 인증을 취소하거나 오류가 반환된 경우
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    if error:
        logger.warning(f"네이버 로그인 취소/실패: {error} ({error_description})")
        return redirect(url_for('main.login', error='naver_cancelled'))

    code = request.args.get('code')
    state = request.args.get('state')

    # CSRF state 검증
    saved_state = session.pop('naver_oauth_state', None)
    if not state or state != saved_state:
        logger.warning("네이버 OAuth state 불일치 (CSRF 가능성 또는 만료)")
        return redirect(url_for('main.login', error='naver_state_invalid'))

    if not code:
        logger.warning("네이버 콜백에 code 파라미터가 없습니다.")
        return redirect(url_for('main.login', error='naver_failed'))

    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error("네이버 Client ID 또는 Client Secret 환경변수가 설정되지 않았습니다.")
        return redirect(url_for('main.login', error='naver_not_configured'))

    base_url = SITE_URL
    if request.host_url:
        base_url = request.host_url.rstrip('/')
    callback_url = f"{base_url}/auth/naver/callback"

    try:
        import httpx
        # 1. 네이버 접근 토큰(Access Token) 발급 요청
        token_params = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "state": state,
            "redirect_uri": callback_url
        }

        token_res = httpx.post(
            "https://nid.naver.com/oauth2.0/token",
            data=token_params,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
            timeout=10.0
        )

        if token_res.status_code != 200:
            logger.error(f"네이버 토큰 요청 실패: {token_res.text}")
            return redirect(url_for('main.login', error='naver_failed'))

        token_json = token_res.json()
        access_token = token_json.get("access_token")
        if not access_token:
            logger.error(f"네이버 응답에 access_token 부재: {token_json}")
            return redirect(url_for('main.login', error='naver_failed'))

        # 2. 네이버 회원 프로필 정보 조회
        profile_res = httpx.get(
            "https://openapi.naver.com/v1/nid/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0
        )

        if profile_res.status_code != 200:
            logger.error(f"네이버 프로필 조회 실패: {profile_res.text}")
            return redirect(url_for('main.login', error='naver_failed'))

        profile_data = profile_res.json()
        response_data = profile_data.get("response", {})
        naver_id = str(response_data.get("id") or "")
        if not naver_id:
            logger.error(f"네이버 응답에 고유 회원 ID 부재: {profile_data}")
            return redirect(url_for('main.login', error='naver_failed'))

        name = response_data.get("name") or response_data.get("nickname") or f"네이버회원_{naver_id[:6]}"
        email = response_data.get("email") or f"naver_{naver_id[:8]}@yangsanfc.local"
        phone = response_data.get("mobile") or ""
        avatar_url = response_data.get("profile_image") or ""

        # 3. Flask 세션에 사용자 정보 저장 (기존 Supabase Auth 및 카카오 세션 규격과 100% 일치)
        user_uuid = f"naver-{naver_id}"
        session['user_id'] = user_uuid
        session['email'] = email
        session['user'] = {
            "id": user_uuid,
            "email": email,
            "name": name,
            "phone": phone,
            "provider": "naver",
            "avatar_url": avatar_url
        }
        session['naver_access_token'] = access_token
        logger.info(f"네이버 OAuth 로그인 성공: {name} ({user_uuid})")

        return redirect(url_for('main.index'))

    except Exception as e:
        logger.error(f"네이버 로그인 처리 중 예외 발생: {e}")
        return redirect(url_for('main.login', error='naver_failed'))


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
