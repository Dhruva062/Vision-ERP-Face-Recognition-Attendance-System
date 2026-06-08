"""
oauth_manager.py  —  Vision ERP  OAuth 2.0 helper
===================================================
Supports Google and Microsoft (Azure AD) as providers.

Flow used:  Authorization Code  (desktop / localhost redirect)
  1. App opens browser → provider's /authorize URL
  2. Provider redirects to http://localhost:PORT/?code=... 
  3. App captures code via tiny embedded HTTP server
  4. App exchanges code → access_token + id_token
  5. id_token (JWT) is decoded to get user email / name
  6. email is matched against users.json  `oauth_email` field

Dependencies (install once):
    pip install requests PyJWT cryptography

oauth_config.json  (created automatically on first save, stored next to erp_main.py):
{
  "google": {
    "client_id": "",
    "client_secret": "",
    "enabled": true
  },
  "microsoft": {
    "client_id": "",
    "client_secret": "",
    "tenant_id": "common",
    "enabled": false
  }
}
"""

from __future__ import annotations
import json, os, threading, webbrowser, secrets, hashlib, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from typing import Optional

import requests  # type: ignore

# ── optional JWT decode ────────────────────────────────────────────────
try:
    import jwt as _pyjwt        # PyJWT
    _JWT_OK = True
except ImportError:
    _JWT_OK = False

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OAUTH_CFG   = os.path.join(BASE_DIR, "oauth_config.json")
REDIRECT_PORT = 9753
REDIRECT_URI  = f"http://localhost:{REDIRECT_PORT}/"

# ── Provider endpoint tables ───────────────────────────────────────────
PROVIDERS = {
    "google": {
        "auth_url":   "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url":  "https://oauth2.googleapis.com/token",
        "jwks_url":   "https://www.googleapis.com/oauth2/v3/certs",
        "scope":      "openid email profile",
        "label":      "Google",
        "icon":       "🔴",
    },
    "microsoft": {
        "auth_url":   "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token_url":  "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "jwks_url":   "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys",
        "scope":      "openid email profile",
        "label":      "Microsoft",
        "icon":       "🔵",
    },
}


# ══════════════════════════════════════════════════════════════════════
#  CONFIG  I/O
# ══════════════════════════════════════════════════════════════════════
def load_oauth_config() -> dict:
    if os.path.exists(OAUTH_CFG):
        with open(OAUTH_CFG) as f:
            return json.load(f)
    return {
        "google":    {"client_id": "", "client_secret": "", "enabled": False},
        "microsoft": {"client_id": "", "client_secret": "", "tenant_id": "common", "enabled": False},
    }

def save_oauth_config(cfg: dict):
    with open(OAUTH_CFG, "w") as f:
        json.dump(cfg, f, indent=2)


# ══════════════════════════════════════════════════════════════════════
#  PKCE helpers
# ══════════════════════════════════════════════════════════════════════
def _pkce_pair():
    verifier  = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ══════════════════════════════════════════════════════════════════════
#  TINY LOCAL HTTP SERVER  (captures the redirect)
# ══════════════════════════════════════════════════════════════════════
class _CallbackHandler(BaseHTTPRequestHandler):
    code  : Optional[str] = None
    error : Optional[str] = None
    _done : threading.Event = None   # set by __init__ of OAuthFlow

    def log_message(self, *a): pass  # silence access log

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        if "code" in qs:
            _CallbackHandler.code  = qs["code"][0]
            body = b"<h2>Success! You may close this tab.</h2>"
        else:
            _CallbackHandler.error = qs.get("error", ["unknown"])[0]
            body = b"<h2>OAuth error. You may close this tab.</h2>"
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(body)
        if _CallbackHandler._done:
            _CallbackHandler._done.set()


# ══════════════════════════════════════════════════════════════════════
#  MAIN FLOW OBJECT
# ══════════════════════════════════════════════════════════════════════
class OAuthFlow:
    """
    Usage:
        flow = OAuthFlow("google")
        result = flow.run()          # blocks until success or timeout
        # result = {"email":..., "name":..., "provider":...}  or None
    """

    def __init__(self, provider: str):
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")
        self.provider  = provider
        self.cfg       = load_oauth_config().get(provider, {})
        self.pinfo     = PROVIDERS[provider]
        self._done     = threading.Event()
        self._result   = None
        self._server   = None

    # ── build /authorize URL ───────────────────────────────────────
    def _auth_url(self) -> tuple[str, str, str]:
        """Returns (url, state, code_verifier)."""
        state    = secrets.token_urlsafe(16)
        verifier, challenge = _pkce_pair()

        tenant   = self.cfg.get("tenant_id", "common")
        base     = self.pinfo["auth_url"].replace("{tenant}", tenant)
        scope    = self.pinfo["scope"]

        params = {
            "client_id":             self.cfg["client_id"],
            "response_type":         "code",
            "redirect_uri":          REDIRECT_URI,
            "scope":                 scope,
            "state":                 state,
            "code_challenge":        challenge,
            "code_challenge_method": "S256",
            "access_type":           "offline",   # Google: request refresh_token
            "prompt":                "select_account",
        }
        return base + "?" + urlencode(params), state, verifier

    # ── exchange code → tokens ─────────────────────────────────────
    def _exchange(self, code: str, verifier: str) -> Optional[dict]:
        tenant = self.cfg.get("tenant_id", "common")
        url    = self.pinfo["token_url"].replace("{tenant}", tenant)
        data   = {
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
            "client_id":     self.cfg["client_id"],
            "client_secret": self.cfg["client_secret"],
            "code_verifier": verifier,
        }
        try:
            r = requests.post(url, data=data, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[OAuth] token exchange failed: {e}")
            return None

    # ── decode id_token (best-effort, no sig verification needed for local ERP) ──
    @staticmethod
    def _decode_id_token(id_token: str) -> dict:
        try:
            if _JWT_OK:
                return _pyjwt.decode(id_token, options={"verify_signature": False})
            # fallback: manual base64 decode of payload
            parts   = id_token.split(".")
            payload = parts[1] + "=="   # fix padding
            return json.loads(base64.urlsafe_b64decode(payload))
        except Exception:
            return {}

    # ── public: run the full flow (blocking) ──────────────────────
    def run(self, timeout: int = 120) -> Optional[dict]:
        """
        Opens browser, waits for callback.
        Returns dict with email/name/provider, or None on failure/timeout.
        """
        if not self.cfg.get("client_id") or not self.cfg.get("client_secret"):
            raise RuntimeError(
                f"OAuth not configured for {self.provider}. "
                "Go to Admin → Settings → OAuth Providers."
            )

        auth_url, _state, verifier = self._auth_url()

        # reset handler state
        _CallbackHandler.code  = None
        _CallbackHandler.error = None
        _CallbackHandler._done = self._done

        # start local HTTP server in daemon thread
        self._server = HTTPServer(("localhost", REDIRECT_PORT), _CallbackHandler)
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()

        webbrowser.open(auth_url)
        got = self._done.wait(timeout=timeout)
        self._server.shutdown()

        if not got or _CallbackHandler.error:
            return None
        if not _CallbackHandler.code:
            return None

        tokens = self._exchange(_CallbackHandler.code, verifier)
        if not tokens:
            return None

        id_token = tokens.get("id_token","")
        claims   = self._decode_id_token(id_token) if id_token else {}

        # also try userinfo endpoint for Google if claims are empty
        if not claims.get("email") and tokens.get("access_token"):
            try:
                ui = requests.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {tokens['access_token']}"},
                    timeout=10
                ).json()
                claims.update(ui)
            except Exception:
                pass

        email = claims.get("email","").lower().strip()
        name  = claims.get("name", claims.get("given_name", email))

        if not email:
            return None

        return {"email": email, "name": name, "provider": self.provider}


# ══════════════════════════════════════════════════════════════════════
#  USER MATCHING
# ══════════════════════════════════════════════════════════════════════
def find_user_by_oauth(email: str, users: dict) -> Optional[tuple[str, dict]]:
    """
    Returns (username, user_dict) if a user has oauth_email == email
    AND oauth_enabled == True.  Otherwise None.
    """
    email = email.lower().strip()
    for uname, ud in users.items():
        if (ud.get("oauth_enabled") and
                ud.get("oauth_email","").lower().strip() == email):
            return uname, ud
    return None
