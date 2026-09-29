"""BituachBot – Landing Page & Signup"""

import base64
import hashlib
import hmac
import io
import json
import os
import re
import time
from datetime import datetime, timedelta

import requests
import streamlit as st
import streamlit.components.v1 as components
from anthropic import Anthropic
from dotenv import load_dotenv

from modules.insurance_client import InsuranceClientDB, is_hashed, verify_password
from modules.hebrew_text import fix_visual_hebrew

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

load_dotenv()

st.set_page_config(page_title="BituachBot", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800;900&display=swap');
*, html, body, [class*="css"] { font-family: 'Heebo', sans-serif !important; box-sizing: border-box; }
#MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
.stApp > header { display: none !important; }
.main .block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stHorizontalBlock"] { gap: 0 !important; align-items: stretch !important; min-height: 100vh; }
[data-testid="stHorizontalBlock"] > div:first-child {
  background: #F0FDF4 !important; min-height: 100vh !important;
  padding: 64px 56px !important; direction: rtl; position: relative; overflow: hidden;
}
[data-testid="stHorizontalBlock"] > div:last-child {
  background: white !important; min-height: 100vh !important;
  padding: 48px 56px !important; direction: rtl;
}
/* Global RTL for text elements only — not structural divs */
[data-testid="stHorizontalBlock"] > div:last-child p,
[data-testid="stHorizontalBlock"] > div:last-child h1,
[data-testid="stHorizontalBlock"] > div:last-child h2,
[data-testid="stHorizontalBlock"] > div:last-child h3,
[data-testid="stHorizontalBlock"] > div:last-child label {
  text-align: right !important; direction: rtl !important;
}
/* Hide broken Material icon text in expanders, replace with CSS arrow */
[data-testid="stIconMaterial"] { display: none !important; }
[data-testid="stExpander"] details summary {
  direction: rtl !important; display: flex !important;
  align-items: center !important; gap: 8px !important;
  cursor: pointer !important;
}
[data-testid="stExpander"] details summary::after {
  content: "▶"; color: #9CA3AF; font-size: 11px; flex-shrink: 0;
  transition: transform 0.2s ease;
}
[data-testid="stExpander"] details[open] summary::after { content: "▼"; }
.badge {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,0.85); border: 1px solid rgba(22,179,100,0.15);
  color: #16B364; font-weight: 600; font-size: 0.85rem;
  padding: 6px 16px; border-radius: 999px; margin-bottom: 28px;
}
.hero-title { font-size: 3rem; font-weight: 900; color: #111827; line-height: 1.25; margin-bottom: 20px; }
.hero-title span { color: #16B364; }
.hero-sub { font-size: 1.1rem; color: #6B7280; margin-bottom: 36px; line-height: 1.65; max-width: 400px; }
.benefit-item { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.benefit-check {
  flex-shrink: 0; width: 28px; height: 28px; border-radius: 50%;
  background: rgba(22,179,100,0.12); display: flex; align-items: center;
  justify-content: center; color: #16B364; font-size: 0.85rem; font-weight: 700;
}
.benefit-text { font-size: 1rem; font-weight: 500; color: #1F2937; }
.privacy-note { margin-top: 44px; font-size: 0.82rem; color: #9CA3AF; }
.circle-deco-1 {
  position: absolute; width: 320px; height: 320px; border-radius: 50%;
  background: rgba(22,179,100,0.05); top: -80px; left: -80px; pointer-events: none;
}
.circle-deco-2 {
  position: absolute; width: 200px; height: 200px; border-radius: 50%;
  background: rgba(22,179,100,0.05); bottom: 40px; right: 40px; pointer-events: none;
}
.form-logo { display: flex; align-items: center; gap: 8px; justify-content: center; margin-bottom: 8px; }
.form-logo-text { font-size: 1.5rem; font-weight: 700; color: #16B364; }
.form-title { font-size: 1.5rem; font-weight: 700; color: #111827; text-align: center !important; margin-bottom: 24px; }
.form-sub { font-size: 0.9rem; color: #6B7280; text-align: center !important; margin-bottom: 28px; }
.section-title {
  font-size: 1rem; font-weight: 700; color: #111827;
  text-align: right !important; direction: rtl !important;
  margin-bottom: 12px; padding-bottom: 8px;
  border-bottom: 2px solid #F0FDF4;
}
.policy-card {
  background: #F0FDF4; border: 1px solid #D1FAE5; border-radius: 12px;
  padding: 14px 18px; margin-bottom: 10px; direction: rtl; text-align: right;
}
.policy-card .annex-code { font-size: 0.8rem; color: #16B364; font-weight: 700; text-align: right; }
.policy-card .annex-name { font-size: 1rem; font-weight: 600; color: #111827; text-align: right; }
.policy-card .company-name { font-size: 0.85rem; color: #6B7280; text-align: right; }
.profile-box {
  background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 12px;
  padding: 16px 20px; margin-bottom: 24px; direction: rtl; text-align: right;
}
.profile-box div { text-align: right !important; direction: rtl !important; }
.otp-hint { text-align: center !important; color: #6B7280; font-size: 0.9rem; margin-bottom: 20px; }
.stTextInput > div > div > input {
  background: rgba(240,253,244,0.6) !important; border: 1.5px solid #E5E7EB !important;
  border-radius: 12px !important; height: 48px !important; padding: 0 16px !important;
  direction: rtl !important; text-align: right !important;
  font-size: 0.95rem !important; color: #111827 !important;
}
.stTextInput > div > div > input:focus {
  border-color: #16B364 !important; box-shadow: 0 0 0 3px rgba(22,179,100,0.15) !important;
}
label { font-size: 0.875rem !important; font-weight: 500 !important; color: #111827 !important;
  direction: rtl !important; text-align: right !important; display: block !important; }
[data-testid="stFileUploader"] {
  background: rgba(240,253,244,0.4) !important; border: 2px dashed #D1D5DB !important; border-radius: 12px !important;
}
[data-testid="stFileUploader"] section { direction: ltr !important; }
[data-testid="stFileUploader"] section > div { direction: rtl !important; text-align: right !important; }
[data-testid="stFileUploader"] button { direction: ltr !important; }
.stButton > button[kind="primary"] {
  background: #16B364 !important; border: none !important; border-radius: 999px !important;
  height: 52px !important; font-size: 1.05rem !important; font-weight: 700 !important;
  color: white !important; width: 100% !important;
  box-shadow: 0 4px 14px rgba(22,179,100,0.35) !important;
}
.stButton > button[kind="primary"]:hover { background: #12985A !important; }
.stButton > button:not([kind="primary"]) {
  background: transparent !important; border: none !important;
  color: #16B364 !important; font-size: 0.9rem !important; text-decoration: underline !important;
}
.stAlert { direction: rtl !important; text-align: right !important; border-radius: 12px !important; }
.stAlert > div { direction: rtl !important; text-align: right !important; }
/* Global RTL for all text content (admin page + everywhere) */
.main .block-container p,
.main .block-container h1, .main .block-container h2,
.main .block-container h3, .main .block-container h4,
.main .block-container li, .main .block-container label,
.main .block-container .stMarkdown, .main .block-container caption {
  text-align: right !important; direction: rtl !important;
}
[data-testid="stMarkdownContainer"] { text-align: right !important; direction: rtl !important; }
[data-testid="stCaptionContainer"] { text-align: right !important; direction: rtl !important; }
[data-testid="stCheckbox"] label { text-align: right !important; direction: rtl !important; }
[data-testid="stSelectbox"] label { text-align: right !important; direction: rtl !important; }
</style>
""", unsafe_allow_html=True)

# ── AGENT CONTEXT ─────────────────────────────────────────────────────────────
_params = st.query_params
_agent_code = _params.get("agent", "").upper()
_is_admin = _params.get("admin") == "1"
_is_privacy = _params.get("privacy") == "1"


# ── SESSION STATE ──────────────────────────────────────────────────────────────
defaults = {
    "step": "choose",
    "reg_name": "", "reg_phone": "", "reg_user_id": "",
    "annex_count": 0,
    "_otp": "", "_otp_exp": None, "_otp_sent": True,
    "admin_authed": False,
    "admin_client": None,
    "agent_registered_code": "",
    "logged_in_agent": None,
    "agent_bot_messages": [],
    "agent_bot_client_id": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

BENEFITS = [
    "מבוסס על הפוליסה האישית שלך",
    "תשובות מיידיות בעברית, ערבית ורוסית",
    "כירופרקטיקה, MRI, פיזיותרפיה ועוד",
    "ללא המתנה לנציג, 24/7",
]


# ── HELPERS ────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _db() -> InsuranceClientDB:
    return InsuranceClientDB()


@st.cache_data(ttl=60, show_spinner=False)
def _load_agent(code: str) -> dict | None:
    if not code:
        return None
    try:
        return _db().get_agent_by_code(code)
    except Exception:
        return None

_agent = _load_agent(_agent_code) if _agent_code else None


def _get_secret(key: str) -> str:
    try:
        return st.secrets.get(key) or ""
    except Exception:
        return ""


def _bot_whatsapp_number() -> str:
    return _get_secret("BOT_WHATSAPP_NUMBER") or os.getenv("BOT_WHATSAPP_NUMBER", "")


# ── PERSISTENT LOGIN (signed cookie) ─────────────────────────────────────────
SESSION_COOKIE = "bb_session"
SESSION_DAYS = 7


def _session_secret() -> bytes:
    secret = _get_secret("SESSION_SECRET") or os.getenv("SESSION_SECRET", "")
    if not secret:
        base = _get_secret("SUPABASE_KEY") or os.getenv("SUPABASE_KEY", "")
        secret = hashlib.sha256(("bituachbot-session:" + base).encode()).hexdigest()
    return secret.encode()


def _make_session_token(role: str, user_id: str) -> str:
    exp = int(time.time()) + SESSION_DAYS * 86400
    payload = f"{role}|{user_id}|{exp}"
    sig = hmac.new(_session_secret(), payload.encode(), hashlib.sha256).hexdigest()[:40]
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode().rstrip("=")


def _read_session_token(token: str) -> tuple[str, str] | None:
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        role, user_id, exp, sig = raw.split("|")
        payload = f"{role}|{user_id}|{exp}"
        good = hmac.new(_session_secret(), payload.encode(), hashlib.sha256).hexdigest()[:40]
        if not hmac.compare_digest(sig, good) or int(exp) < time.time():
            return None
        return role, user_id
    except Exception:
        return None


def _remember_login(role: str, user_id: str):
    """role: 'a' = agent, 'c' = client. The cookie is written on the next render."""
    if user_id:
        st.session_state["_cookie_op"] = ("set", _make_session_token(role, user_id))
        st.session_state["_logged_out"] = False


def _forget_login():
    st.session_state["_cookie_op"] = ("clear", "")
    st.session_state["_logged_out"] = True


def _flush_cookie_op():
    op = st.session_state.pop("_cookie_op", None)
    if not op:
        return
    action, token = op
    if action == "set":
        cookie = f"{SESSION_COOKIE}={token}; path=/; max-age={SESSION_DAYS * 86400}; SameSite=Lax; Secure"
    else:
        cookie = f"{SESSION_COOKIE}=; path=/; max-age=0; SameSite=Lax; Secure"
    components.html(
        "<script>"
        f"try {{ window.parent.document.cookie = {json.dumps(cookie)}; }} catch (e) {{}}"
        f"try {{ document.cookie = {json.dumps(cookie)}; }} catch (e) {{}}"
        "</script>",
        height=0,
    )


def _restore_session():
    """On a fresh page load, log the agent/client back in from the cookie."""
    if st.session_state.get("_session_checked"):
        return
    st.session_state["_session_checked"] = True
    if st.session_state.get("_logged_out") or st.session_state.step != "choose":
        return
    try:
        cookies = st.context.cookies
        token = cookies.get(SESSION_COOKIE) if cookies else None
    except Exception:
        token = None
    parsed = _read_session_token(token) if token else None
    if not parsed:
        return
    role, user_id = parsed
    if role == "a":
        agent = _db().get_agent_by_id(user_id)
        if agent:
            st.session_state.logged_in_agent = agent
            _remember_login("a", st.session_state.logged_in_agent.get("id", ""))
            st.session_state.step = "agent_dashboard"
    elif role == "c":
        profile = _db().get_profile_by_id(user_id)
        if profile:
            st.session_state.reg_user_id = profile["id"]
            st.session_state.reg_phone = profile.get("phone_number", "")
            st.session_state.reg_name = profile.get("full_name", "")
            st.session_state.step = "dashboard"


def _whatsapp_card(phone: str):
    """Shows a 'save this number' card. phone in format 05XXXXXXXX"""
    if not phone:
        return
    digits = phone.replace("-", "").replace(" ", "")
    wa_digits = "972" + digits[1:] if digits.startswith("0") else digits
    wa_link = f"https://wa.me/{wa_digits}"
    st.markdown(f"""
<div style="background:#F0FDF4;border:2px solid #D1FAE5;border-radius:14px;
     padding:20px 24px;margin:20px 0;direction:rtl;text-align:right">
  <div style="font-size:1.1rem;font-weight:700;color:#111827;margin-bottom:6px">
    💬 שמור את הבוט באנשי הקשר שלך
  </div>
  <div style="font-size:0.9rem;color:#6B7280;margin-bottom:14px">
    כדי לשלוח הודעות לבוט ולקבל תשובות, שמור את המספר הזה:
  </div>
  <div style="font-size:1.6rem;font-weight:800;color:#16B364;
       letter-spacing:2px;margin-bottom:14px;text-align:center">
    {phone}
  </div>
  <a href="{wa_link}" target="_blank" style="
     display:block;background:#25D366;color:white;text-align:center;
     padding:12px;border-radius:999px;font-weight:700;font-size:1rem;
     text-decoration:none;">
    📲 פתח WhatsApp ושמור מספר
  </a>
</div>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def _claude() -> Anthropic:
    api_key = _get_secret("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        st.error("❌ ANTHROPIC_API_KEY לא מוגדר")
        st.stop()
    return Anthropic(api_key=api_key)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """PDF → text in logical Hebrew order (many insurer PDFs come out reversed, see modules/hebrew_text.py)."""
    if not PDF_SUPPORT:
        return ""
    # Try pdfplumber first, fall back to pypdf for complex PDFs
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            parts = []
            for p in pdf.pages:
                try:
                    parts.append(p.extract_text() or "")
                except Exception:
                    parts.append("")
            text = "\n".join(parts)
            if text.strip():
                return fix_visual_hebrew(text)
    except Exception:
        pass
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                parts.append("")
        text = "\n".join(parts)
        if text.strip():
            return fix_visual_hebrew(text)
    except Exception:
        pass
    raise ValueError("לא ניתן לקרוא את קובץ ה-PDF. ייתכן שהוא סרוק או מוגן.")


def _extract_related_codes(text: str, primary_code: str) -> list[str]:
    """Find slash-separated annex codes in PDF text, e.g. '5420/5400' → ['5420', '5400']."""
    found = set()
    for match in re.finditer(r'\b(\d{4,6})(?:/(\d{4,6}))+\b', text):
        codes = re.findall(r'\d{4,6}', match.group())
        if primary_code in codes:
            found.update(codes)
    found.discard(primary_code)
    return list(found)


CLAUDE_FALLBACK_MODELS = ["claude-sonnet-4-5", "claude-haiku-4-5"]


def _claude_model() -> str:
    return _get_secret("CLAUDE_MODEL") or os.getenv("CLAUDE_MODEL", "") or "claude-sonnet-4-6"


def _claude_create(**kwargs):
    """messages.create with the configured model, falling back if the model is rejected."""
    import anthropic
    models = [_claude_model()] + [m for m in CLAUDE_FALLBACK_MODELS if m != _claude_model()]
    last_err = None
    for model in models:
        try:
            return _claude().messages.create(model=model, **kwargs)
        except (anthropic.NotFoundError, anthropic.BadRequestError) as e:
            last_err = e
            msg = str(getattr(e, "message", e)).lower()
            if "model" not in msg:
                break  # not a model problem (e.g. no credit) — trying other models won't help
    raise last_err


def _anthropic_error_he(e: Exception) -> str:
    msg = str(getattr(e, "message", e))
    low = msg.lower()
    if "credit balance" in low or "billing" in low:
        return "אין קרדיט בחשבון Anthropic — יש לטעון קרדיט ב-console.anthropic.com."
    if "api key" in low or "authentication" in low or "x-api-key" in low:
        return "מפתח ה-API של Anthropic לא תקין."
    return f"שגיאה בשירות ה-AI: {msg[:200]}"


# Same wording as the WhatsApp bot prompt (whatsapp_flow.json → AI Agent)
AI_NOTE_CLIENT = ("ℹ️ התשובה מתייחסת לנספחים שבפוליסה שלך ונוצרה ע״י בינה מלאכותית, ולכן אינה מהווה אישור כיסוי. "
                  "לפני כל פעולה — מומלץ לוודא מול הסוכן או חברת הביטוח.")
AI_NOTE_AGENT = "ℹ️ נוצר ע״י בינה מלאכותית על סמך הנספחים של הלקוח — מומלץ לאמת מול נוסח הפוליסה לפני שמתחייבים ללקוח."

ANALYZE_PROMPT = """אתה מנתח מסמכי ביטוח ישראליים. קבע מה סוג המסמך:
• "policy" — מפרט / דף פרטי ביטוח של מבוטח מסוים: רשימת הכיסויים והנספחים שנרכשו (בדרך כלל עם שם מבוטח, מספר פוליסה, פרמיה).
• "annex" — חוברת התנאים של נספח / כיסוי / פרק / תכנית עצמם: הנוסח הכללי (הגדרות, כיסויים, חריגים, סכומים) ולא של מבוטח מסוים.
• "other" — כל דבר אחר.

annex_codes:
• ב-policy: כל קודי הנספחים שברשימת הכיסויים של המבוטח.
• ב-annex: רק הקודים שהמסמך הזה עצמו מגדיר — הקודים שבכותרת (למשל "פרק 6650", "נספח 8713", "תכנית 5986"). לא קודים של נספחים אחרים שרק מוזכרים בטקסט.
• תמיד: מספרים בני 4-6 ספרות בלבד. לא סכומים, תאריכים, מספרי פוליסה, מספרי סוכן או טלפונים.
annex_name: ב-annex — שם הנספח כפי שמופיע בכותרת. אחרת "".
version_year: ב-annex — שנת הנוסח אם מופיעה (למשל 2016). אחרת null.
company: שם חברת הביטוח אם מופיע, אחרת "".

החזר JSON בלבד, בלי הסברים:
{"doc_type": "annex", "annex_codes": ["6650"], "annex_name": "ביטוח לשירותים אמבולטוריים", "version_year": 2016, "company": "הפניקס"}

טקסט המסמך:
"""


def _analyze_document(text: str) -> dict:
    """Classify an insurance PDF and pull out its codes.
    policy → the codes the client has. annex → the codes of the נספח this document IS (it goes to the library).
    Never raises: on AI failure returns doc_type 'other' with an 'error' message."""
    info = {"doc_type": "other", "codes": [], "name": "", "year": None, "company": "", "error": ""}
    cache = st.session_state.setdefault("_doc_analysis", {})
    key = hashlib.sha256(text.encode()).hexdigest()
    if key in cache:
        return dict(cache[key])
    try:
        resp = _claude_create(max_tokens=700, messages=[{"role": "user", "content": ANALYZE_PROMPT + text[:40000]}])
    except Exception as e:
        print(f"[landing] _analyze_document: {e}")
        info["error"] = _anthropic_error_he(e)
        return info
    raw = re.sub(r"```json|```", "", resp.content[0].text).strip()
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            data = json.loads(m.group()) if m else {}
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    doc_type = data.get("doc_type") if data.get("doc_type") in ("policy", "annex", "other") else "policy"
    codes = [str(c).strip() for c in (data.get("annex_codes") or [])]
    codes = list(dict.fromkeys(c for c in codes if re.fullmatch(r"\d{4,6}", c)))
    try:
        year = int(data.get("version_year") or 0)
    except (TypeError, ValueError):
        year = 0
    info.update(
        doc_type=doc_type,
        codes=codes if doc_type == "annex" else sorted(codes),
        name=str(data.get("annex_name") or "").strip()[:200],
        year=year if 1990 <= year <= datetime.now().year + 1 else None,
        company=str(data.get("company") or "").strip()[:100],
    )
    cache[key] = dict(info)
    return info


def _validate_teudat_zehut(tz: str) -> bool:
    tz = tz.strip().zfill(9)
    if not tz.isdigit() or len(tz) != 9:
        return False
    total = sum(
        (d - 9 if (d := int(ch) * (1 if i % 2 == 0 else 2)) > 9 else d)
        for i, ch in enumerate(tz)
    )
    return total % 10 == 0


def _otp_valid(code: str) -> bool:
    return (
        st.session_state._otp == code.strip()
        and st.session_state._otp_exp is not None
        and datetime.now() < st.session_state._otp_exp
    )


def _send_otp(phone: str) -> str:
    code = InsuranceClientDB.generate_otp()
    st.session_state._otp = code
    st.session_state._otp_exp = datetime.now() + timedelta(minutes=10)
    sent = _db().send_otp(phone, code)
    st.session_state._otp_sent = sent
    st.session_state._otp_error = "" if sent else (_db().last_whatsapp_error or "שגיאה לא ידועה")
    return code


def _otp_failed_notice(agent: bool = False):
    """Shown when the WhatsApp code could not be sent. Never shows the code itself."""
    if st.session_state.get("_otp_sent", True):
        return
    st.error("❌ לא הצלחנו לשלוח את קוד האימות בוואטסאפ. נסה שוב בעוד רגע"
             + (", או היכנס עם אימייל וסיסמה." if agent else "."))
    st.caption(f"פרטים טכניים: {st.session_state.get('_otp_error', '')}")


def _auto_agent_code(name: str, email: str) -> str:
    import random as _rand
    if "@" in email:
        prefix = re.sub(r"[^A-Za-z0-9]", "", email.split("@")[0]).upper()[:6]
    else:
        prefix = re.sub(r"[^A-Za-z]", "", name).upper()[:4]
    if len(prefix) < 2:
        prefix = "AGENT"
    return prefix + str(_rand.randint(100, 999))


@st.cache_data(ttl=60, show_spinner=False)
def _all_agents() -> list[dict]:
    try:
        return _db().get_all_agents()
    except Exception:
        return []


# ── HERO PANEL ─────────────────────────────────────────────────────────────────
def _hero():
    bullets = "".join(
        f'<div class="benefit-item">'
        f'<span class="benefit-check">✓</span>'
        f'<span class="benefit-text">{b}</span>'
        f'</div>'
        for b in BENEFITS
    )
    st.markdown(f"""
<div class="circle-deco-1"></div><div class="circle-deco-2"></div>
<div class="badge">💬 אסיסטנט ביטוח חכם בוואטסאפ</div>
<h1 class="hero-title">עם <span>BituachBot</span><br>תבין סוף סוף מה<br>הביטוח שלך מכסה</h1>
<p class="hero-sub">שלח הודעה בוואטסאפ וקבל תשובה מדויקת — לפי הביטוח האישי שלך.</p>
{bullets}
<p class="privacy-note">🔒 המידע שלך מאובטח ומוגן לפי תקנות הפרטיות</p>
""", unsafe_allow_html=True)


def _logo(title: str, sub: str = ""):
    st.markdown(
        f'<div class="form-logo"><span style="font-size:2rem">🛡️</span>'
        f'<span class="form-logo-text">BituachBot</span></div>'
        f'<div class="form-title">{title}</div>'
        + (f'<div class="form-sub">{sub}</div>' if sub else ""),
        unsafe_allow_html=True,
    )


# ── PAGES ──────────────────────────────────────────────────────────────────────

STATUS_LABELS = {
    "ready": ("✅", "מוכן — הבוט עונה"),
    "partial": ("🟡", "חלק מהנספחים חסרים"),
    "waiting_annex": ("⏳", "הנספחים חסרים במאגר"),
    "empty": ("❌", "לא הועלתה פוליסה"),
}


def _flash(kind: str, msg: str):
    """Queue a message that survives st.rerun() (kind: success | info | warning | error)."""
    queue = st.session_state.get("_flash") or []
    queue.append((kind, msg))
    st.session_state["_flash"] = queue


def _show_flash():
    for kind, msg in st.session_state.pop("_flash", None) or []:
        getattr(st, kind, st.info)(msg)


def _render_documents(user_id: str, key_prefix: str, reanalyze_by: str = ""):
    """List a client's uploaded PDFs with download links. reanalyze_by='agent' adds a re-analyze button."""
    docs = _db().list_client_documents(user_id)
    if not docs:
        st.caption("לא הועלו מסמכים עדיין.")
        return
    who_label = {"client": "הלקוח", "agent": "הסוכן", "bot": "וואטסאפ"}
    for i, d in enumerate(docs):
        url = _db().document_url(d["path"])
        who = who_label.get(d.get("uploaded_by", ""), "")
        meta = " · ".join(x for x in [d.get("uploaded_at", ""), who] if x)
        line = (f"📄 [{d['name']}]({url})" if url else f"📄 {d['name']}") + \
               f" <span style='color:#9CA3AF;font-size:0.8rem'>{meta}</span>"
        if not reanalyze_by:
            st.markdown(line, unsafe_allow_html=True)
            continue
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(line, unsafe_allow_html=True)
        with c2:
            if st.button("🔍 נתח שוב", key=f"{key_prefix}_re_{i}", use_container_width=True,
                         help="מזהה שוב את הנספחים. אם זה מסמך של נספח — הוא נכנס למאגר."):
                data = _db().download_client_document(d["path"])
                if not data:
                    _flash("error", "❌ לא הצלחנו להוריד את הקובץ מהאחסון.")
                else:
                    info = _process_pdf(data)
                    res = _apply_document(user_id, info, reanalyze_by)
                    for m in _document_messages(res, info):
                        _flash(*m)
                st.rerun()


def _process_pdf(pdf_bytes: bytes) -> dict:
    """Read a PDF and analyze it. Always returns an info dict (see _analyze_document) plus 'text'."""
    try:
        text = _extract_pdf_text(pdf_bytes)
    except ValueError as e:
        return {"doc_type": "other", "codes": [], "name": "", "year": None, "company": "", "text": "", "error": str(e)}
    if not text.strip():
        return {"doc_type": "other", "codes": [], "name": "", "year": None, "company": "", "text": "",
                "error": "לא נמצא טקסט בקובץ (ייתכן שהוא סרוק)."}
    with st.spinner("מנתח את המסמך..."):
        info = _analyze_document(text)
    info["text"] = text
    return info


def _apply_document(user_id: str, info: dict, by: str) -> dict:
    """Link the document's codes to the client; a נספח document also goes into the library.
    by='agent' may overwrite library text, by='client' only fills codes the library doesn't have yet."""
    res = {"codes": info.get("codes") or [], "linked": 0, "library": [], "library_skipped": [],
           "is_annex": info.get("doc_type") == "annex" and bool(info.get("codes"))}
    if res["is_annex"]:
        res["library"], res["library_skipped"] = _db().add_annex_document(
            res["codes"], info.get("name", ""), info.get("text", ""), info.get("year"),
            info.get("company", ""), overwrite=(by == "agent"),
        )
    if res["codes"] and user_id:
        res["linked"], _ = _db().link_annex_codes(user_id, res["codes"])
    return res


def _document_messages(res: dict, info: dict) -> list[tuple[str, str]]:
    msgs = []
    if info.get("error"):
        msgs.append(("error", f"❌ לא הצלחנו לנתח את המסמך: {info['error']}"))
    if res["is_annex"]:
        name = f" ({info['name']})" if info.get("name") else ""
        if res["library"]:
            msgs.append(("success", f"📚 זה מסמך של נספח{name} — נשמר במאגר תחת: {' · '.join(res['library'])}. "
                                    "כל הלקוחות עם הקודים האלה עודכנו."))
        if res["library_skipped"]:
            msgs.append(("info", f"ℹ️ נספח {' · '.join(res['library_skipped'])} כבר קיים במאגר — הנוסח שם לא שונה."))
    elif res["codes"]:
        msgs.append(("success", f"✅ זוהו {len(res['codes'])} נספחים ({res['linked']} חדשים): {' · '.join(res['codes'])}"))
    elif not info.get("error"):
        msgs.append(("warning", "לא זוהו קודי נספחים במסמך."))
    return msgs


def page_choose():
    """Landing: choose client or agent registration."""
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("ברוכים הבאים!", "במה תרצה להתחיל?")
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
<div style="display:flex;flex-direction:column;gap:16px;direction:rtl">
  <div style="background:#F0FDF4;border:2px solid #D1FAE5;border-radius:16px;padding:24px;text-align:right;cursor:pointer">
    <div style="font-size:2rem;margin-bottom:8px">👤</div>
    <div style="font-weight:700;font-size:1.1rem;color:#111827;margin-bottom:6px">אני לקוח</div>
    <div style="font-size:0.9rem;color:#6B7280">רוצה לדעת מה הביטוח שלי מכסה</div>
  </div>
</div>
""", unsafe_allow_html=True)
        if st.button("המשך כלקוח", type="primary", use_container_width=True):
            st.session_state.step = "form"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
<div style="background:#F8FAFF;border:2px solid #DBEAFE;border-radius:16px;padding:24px;text-align:right">
  <div style="font-size:2rem;margin-bottom:8px">🏢</div>
  <div style="font-weight:700;font-size:1.1rem;color:#111827;margin-bottom:6px">אני סוכן ביטוח</div>
  <div style="font-size:0.9rem;color:#6B7280">רוצה להציע את הכלי ללקוחות שלי</div>
</div>
""", unsafe_allow_html=True)
        if st.button("המשך כסוכן", use_container_width=True):
            st.session_state.step = "agent_register"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("כבר נרשמת? כניסה"):
            st.session_state.step = "login_choose"
            st.rerun()


def page_agent_register():
    """Agent self-registration."""
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("הרשמה כסוכן ביטוח", "צור את הסביבה שלך ב-BituachBot")

        full_name = st.text_input("שם מלא", placeholder="ישראל ישראלי")
        email = st.text_input("אימייל", placeholder="israel@example.com")
        agent_phone = st.text_input("טלפון נייד (לקבלת התראות בוואטסאפ)", placeholder="050-1234567")
        password = st.text_input("סיסמת ניהול", type="password", placeholder="בחר סיסמה חזקה")
        password2 = st.text_input("אימות סיסמה", type="password", placeholder="חזור על הסיסמה")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("צור חשבון סוכן", type="primary", use_container_width=True):
            errors = []
            if not full_name.strip():
                errors.append("נא להזין שם מלא.")
            if not email.strip():
                errors.append("נא להזין אימייל.")
            clean_agent_phone = agent_phone.strip().replace("-", "").replace(" ", "")
            if not re.match(r"^05\d{8}$", clean_agent_phone):
                errors.append("מספר טלפון לא תקין (חייב להתחיל ב-05 ולהיות בן 10 ספרות).")
            elif _db().get_agent_by_phone(clean_agent_phone):
                errors.append("מספר הטלפון כבר רשום לסוכן אחר.")
            if not password or len(password) < 6:
                errors.append("סיסמה חייבת להכיל לפחות 6 תווים.")
            if password != password2:
                errors.append("הסיסמאות אינן תואמות.")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                for _ in range(5):
                    code = _auto_agent_code(full_name.strip(), email.strip())
                    ok, result = _db().create_agent(code, full_name.strip(), password, email.strip(),
                                                    clean_agent_phone)
                    if ok:
                        st.session_state.agent_registered_code = code
                        st.session_state.step = "agent_success"
                        st.rerun()
                    elif result != "agent_exists":
                        st.error(f"שגיאה: {result}")
                        break
                else:
                    st.error("לא ניתן ליצור קוד ייחודי. נסה שוב.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← חזרה"):
            st.session_state.step = "choose"
            st.rerun()


def page_agent_success():
    """Shown after successful agent registration."""
    code = st.session_state.agent_registered_code
    base_url = "https://bituachbot.streamlit.app"
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("החשבון שלך מוכן! 🎉")
        st.markdown(f"""
<div style="direction:rtl;text-align:right">
  <p style="color:#374151;font-size:1rem;line-height:1.8">
    שלום! הסביבה שלך ב-BituachBot מוכנה.<br>
    שלח את הקישורים האלה ללקוחות שלך:
  </p>

  <div style="background:#F0FDF4;border:1px solid #D1FAE5;border-radius:12px;padding:16px;margin:16px 0">
    <div style="font-size:0.8rem;color:#16B364;font-weight:700;margin-bottom:6px">🔗 קישור לרישום לקוחות</div>
    <code style="font-size:0.9rem;color:#111827;word-break:break-all">{base_url}/?agent={code}</code>
  </div>

  <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px;margin:16px 0">
    <div style="font-size:0.8rem;color:#EA580C;font-weight:700;margin-bottom:6px">🔐 פאנל הניהול שלך</div>
    <code style="font-size:0.9rem;color:#111827;word-break:break-all">{base_url}/?agent={code}&admin=1</code>
  </div>
</div>
""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("כניסה לפאנל הניהול", type="primary", use_container_width=True):
            agent = _db().get_agent_by_code(code)
            if agent:
                st.session_state.logged_in_agent = agent
                _remember_login("a", st.session_state.logged_in_agent.get("id", ""))
                st.session_state.step = "agent_dashboard"
                st.rerun()
            else:
                st.error("שגיאה בטעינת נתוני הסוכן")


def page_form():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("רשום פשוט ומהיר")

        full_name = st.text_input("שם מלא", placeholder="ישראל ישראלי")
        phone = st.text_input("טלפון נייד", placeholder="050-1234567")
        teudat_zehut = st.text_input("תעודת זהות", placeholder="123456789", max_chars=9)

        # Agent selector — only show when client arrives WITHOUT an agent link
        selected_agent_id = _agent["id"] if _agent else ""
        if not _agent_code:
            agents = _all_agents()
            if agents:
                options = ["ללא סוכן (לקוח עצמאי)"] + [f"{a['full_name']}" for a in agents]
                choice = st.selectbox("הסוכן שלך (רשות)", options,
                                      help="בחר את הסוכן שרשם אותך, או השאר ריק")
                if choice != options[0]:
                    idx = options.index(choice) - 1
                    selected_agent_id = agents[idx]["id"]

        uploaded = st.file_uploader("העלאת קובץ PDF (רשות)", type=["pdf"])

        annex_codes: list[str] = []
        pdf_bytes: bytes = b""
        pdf_info: dict | None = None
        if uploaded and PDF_SUPPORT:
            pdf_bytes = uploaded.getvalue()
            pdf_info = _process_pdf(pdf_bytes)
            annex_codes = pdf_info["codes"]
            if pdf_info.get("error"):
                st.error(f"❌ {pdf_info['error']}")
            elif pdf_info["doc_type"] == "annex" and annex_codes:
                st.success(f"זוהה מסמך של נספח: {' · '.join(annex_codes)}")
            elif annex_codes:
                st.success(f"זוהו {len(annex_codes)} נספחים: {' · '.join(annex_codes)}")

        st.markdown("<br>", unsafe_allow_html=True)

        privacy_ok = st.checkbox(
            "קראתי ואני מסכים/ה ל[מדיניות הפרטיות](/?privacy=1) ולתנאי השימוש, "
            "כולל עיבוד נתוני הביטוח שלי באמצעות בינה מלאכותית לצורך מתן שירות.",
            key="privacy_consent"
        )

        if st.button("הירשמו — זה בחינם!", type="primary", use_container_width=True):
            errors = []
            clean_phone = phone.strip().replace("-", "").replace(" ", "")
            clean_tz = teudat_zehut.strip()
            if not full_name.strip():
                errors.append("נא להזין שם מלא.")
            if not re.match(r"^05\d{8}$", clean_phone):
                errors.append("מספר טלפון לא תקין (חייב להתחיל ב-05 ולהיות בן 10 ספרות).")
            if not _validate_teudat_zehut(clean_tz):
                errors.append("תעודת זהות לא תקינה.")
            if not privacy_ok:
                errors.append("יש לאשר את מדיניות הפרטיות ותנאי השימוש כדי להמשיך.")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                db = _db()
                ok, result = db.register_user_with_policies(
                    clean_phone, full_name.strip(), annex_codes, clean_tz, selected_agent_id
                )
                if ok:
                    st.session_state.reg_name = full_name.strip()
                    st.session_state.reg_phone = clean_phone
                    st.session_state.reg_user_id = result
                    st.session_state.annex_count = len(annex_codes)
                    if pdf_bytes:
                        db.upload_client_document(result, uploaded.name, pdf_bytes, "client")
                    if pdf_info and pdf_info["doc_type"] == "annex":
                        _apply_document(result, pdf_info, "client")  # fills the library if the code is missing
                    if selected_agent_id:
                        db.notify_agent_new_client(selected_agent_id, result)
                    _send_otp(clean_phone)
                    if not annex_codes:
                        db.send_no_pdf_notice(clean_phone, full_name.strip())
                    st.session_state.step = "verify_new"
                    st.rerun()
                elif result == "already_registered":
                    st.warning("מספר הטלפון כבר רשום. השתמש באפשרות 'כבר נרשמת'.")
                else:
                    st.error(result)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("כבר נרשמת? כניסה"):
            st.session_state.step = "login"
            st.rerun()

        terms_url   = _get_secret("TERMS_URL")   or os.getenv("TERMS_URL",   "#")
        privacy_url = _get_secret("PRIVACY_URL") or os.getenv("PRIVACY_URL", "#")
        st.markdown(
            f'<p style="text-align:center;font-size:0.78rem;color:#9CA3AF;margin-top:16px">'
            f'בהרשמה אני מסכימ/ה ל<a href="{terms_url}" target="_blank" style="color:#16B364">תנאי השימוש</a>'
            f' ול<a href="{privacy_url}" target="_blank" style="color:#16B364">מדיניות הפרטיות</a></p>',
            unsafe_allow_html=True,
        )


def page_verify(is_new: bool):
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo(
            "אימות מספר טלפון",
            f"שלחנו קוד בן 6 ספרות לוואטסאפ שלך ({st.session_state.reg_phone})",
        )

        _otp_failed_notice()

        code = st.text_input("קוד אימות", placeholder="123456", max_chars=6)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("אמת וכנס", type="primary", use_container_width=True):
            if _otp_valid(code):
                if is_new and st.session_state.annex_count:
                    _db().send_ready(
                        st.session_state.reg_phone,
                        st.session_state.reg_name,
                        st.session_state.annex_count,
                    )
                _remember_login("c", st.session_state.reg_user_id)
                st.session_state.step = "dashboard"
                st.rerun()
            else:
                st.error("קוד שגוי או שפג תוקפו. נסה שנית.")

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("שלח קוד מחדש"):
                _send_otp(st.session_state.reg_phone)
                if st.session_state._otp_sent:
                    _flash("success", "✅ קוד חדש נשלח לוואטסאפ.")
                st.rerun()
        with col2:
            if st.button("← חזרה"):
                st.session_state.step = "form" if is_new else "login"
                st.rerun()


def page_pending():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("נרשמת בהצלחה! 🎉")
        st.markdown(f"""
<div style="text-align:center;padding:20px 0;direction:rtl">
  <div style="font-size:3rem;margin-bottom:16px">📞</div>
  <div style="font-size:1.1rem;color:#374151;margin-bottom:12px">
    שלום <strong>{st.session_state.reg_name}</strong>!
  </div>
  <div style="color:#6B7280;line-height:1.7">
    קיבלנו את פרטיך.<br>
    בקרוב אחד מהנציגים שלנו ייצור איתך קשר<br>
    כדי לעזור לך להעלות את קובץ הפוליסה 🙏
  </div>
</div>
""", unsafe_allow_html=True)
        bot_num = _bot_whatsapp_number()
        if bot_num:
            _whatsapp_card(bot_num)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← חזרה לדף הראשי"):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()


def page_dashboard():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo(f"שלום, {st.session_state.reg_name}! 👋")

        profile = (_db().get_profile_by_id(st.session_state.reg_user_id)
                   or _db().get_profile_by_phone(st.session_state.reg_phone))
        if profile:
            st.session_state.reg_user_id = profile["id"]
            st.markdown(f"""
<div class="profile-box">
  <div style="font-weight:600;font-size:1rem;margin-bottom:8px">פרטי חשבון</div>
  <div style="color:#374151;font-size:0.9rem;line-height:1.8">
    📱 {profile.get('phone_number','')}<br>
    👤 {profile.get('full_name','')}<br>
    🆔 {profile.get('teudat_zehut','—')}
  </div>
</div>
""", unsafe_allow_html=True)
            with st.expander("✏️ עדכון פרטים אישיים", expanded=False):
                upd_name = st.text_input("שם מלא", value=profile.get("full_name", ""), key="upd_name")
                upd_tz = st.text_input("תעודת זהות", value=profile.get("teudat_zehut", ""), key="upd_tz")
                if st.button("💾 שמור פרטים", key="save_profile"):
                    if not upd_name.strip():
                        st.error("שם מלא הוא שדה חובה")
                    elif _db().update_profile(profile["id"], upd_name, upd_tz):
                        st.success("✅ הפרטים עודכנו בהצלחה!")
                        st.rerun()
                    else:
                        st.error("שגיאה בעדכון הפרטים")

                st.markdown("---")
                st.markdown("**📱 החלפת מספר טלפון**")
                pending_phone = st.session_state.get("_new_phone", "")
                if not pending_phone:
                    new_phone = st.text_input("מספר חדש", placeholder="050-1234567", key="client_new_phone")
                    if st.button("שלח קוד אימות למספר החדש", key="client_phone_send"):
                        clean_new = new_phone.strip().replace("-", "").replace(" ", "")
                        if not re.match(r"^05\d{8}$", clean_new):
                            st.error("מספר טלפון לא תקין.")
                        elif clean_new == profile.get("phone_number"):
                            st.info("זה כבר המספר שלך.")
                        elif _db().get_profile_by_phone(clean_new):
                            st.error("המספר כבר רשום במערכת.")
                        else:
                            _send_otp(clean_new)
                            st.session_state["_new_phone"] = clean_new
                            st.rerun()
                else:
                    st.caption(f"שלחנו קוד לוואטסאפ של {pending_phone}")
                    _otp_failed_notice()
                    phone_code = st.text_input("קוד אימות", max_chars=6, key="client_phone_code")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ אשר והחלף", key="client_phone_confirm", type="primary"):
                            if _otp_valid(phone_code):
                                ok, err = _db().update_profile_phone(profile["id"], pending_phone)
                                if ok:
                                    st.session_state.reg_phone = pending_phone
                                    st.session_state.pop("_new_phone", None)
                                    st.success("✅ מספר הטלפון עודכן!")
                                    st.rerun()
                                else:
                                    st.error("המספר כבר רשום במערכת." if err == "phone_taken" else "שגיאה בעדכון.")
                            else:
                                st.error("קוד שגוי או שפג תוקפו.")
                    with c2:
                        if st.button("ביטול", key="client_phone_cancel"):
                            st.session_state.pop("_new_phone", None)
                            st.rerun()

            # ── MY AGENT ───────────────────────────────────────────────────────
            my_agent = _db().get_agent_by_id(profile.get("agent_id") or "")
            if my_agent:
                agent_phone = my_agent.get("phone_number") or ""
                wa = ""
                if agent_phone:
                    intl = "972" + agent_phone[1:] if agent_phone.startswith("0") else agent_phone
                    wa = (f' · <a href="https://wa.me/{intl}" target="_blank" '
                          f'style="color:#16B364">💬 {agent_phone}</a>')
                st.markdown(f"""
<div class="profile-box">
  <div style="font-weight:600;font-size:1rem;margin-bottom:6px">🧑‍💼 הסוכן שלך</div>
  <div style="color:#374151;font-size:0.95rem">{my_agent.get('full_name','')}{wa}</div>
</div>""", unsafe_allow_html=True)
            else:
                with st.expander("🧑‍💼 הסוכן שלך — לא נבחר", expanded=True):
                    agents = _all_agents()
                    if agents:
                        names = [a["full_name"] for a in agents]
                        pick = st.selectbox("בחר את סוכן הביטוח שלך", ["—"] + names, key="client_pick_agent")
                        if pick != "—" and st.button("💾 שמור סוכן", key="client_save_agent"):
                            chosen = agents[names.index(pick)]
                            if _db().assign_agent(profile["id"], chosen["id"]):
                                _db().notify_agent_new_client(chosen["id"], profile["id"])
                                st.success(f"✅ {pick} הוא הסוכן שלך")
                                st.rerun()
                    else:
                        st.caption("אין סוכנים במערכת כרגע.")

        policies = _db().get_user_policies(st.session_state.reg_user_id)
        if policies:
            ready = [p for p in policies if p["has_data"]]
            pending = [p for p in policies if not p["has_data"]]
            st.markdown(f'<div class="section-title">הנספחים שלך ({len(policies)})</div>', unsafe_allow_html=True)
            for p in ready:
                st.markdown(f"""
<div class="policy-card">
  <div class="annex-code">נספח {p['annex_code']} ✅</div>
  <div class="annex-name">{p['annex_name']}</div>
  <div class="company-name">{p['company']}</div>
</div>""", unsafe_allow_html=True)
            for p in pending:
                st.markdown(f"""
<div class="policy-card" style="opacity:0.6;border-color:#E5E7EB;background:#F9FAFB">
  <div class="annex-code" style="color:#9CA3AF">נספח {p['annex_code']} ⏳</div>
  <div class="annex-name" style="color:#6B7280">{p['annex_name']}</div>
  <div class="company-name">מידע בעיבוד — בקרוב</div>
</div>""", unsafe_allow_html=True)
        else:
            st.info("לא נמצאו נספחים — העלה את קובץ הפוליסה כאן למטה, או שהסוכן שלך יעשה זאת עבורך.")

        st.markdown('<div class="section-title">📤 העלאת מסמכים</div>', unsafe_allow_html=True)
        st.caption("פוליסה, נספחים או כל מסמך ביטוח — נזהה את הנספחים אוטומטית.")
        client_pdf = st.file_uploader("בחר קובץ PDF", type=["pdf"], key="client_upload_pdf")
        if client_pdf and st.button("⬆️ העלה מסמך", type="primary", use_container_width=True, key="client_upload_btn"):
            data = client_pdf.getvalue()
            uid = st.session_state.reg_user_id
            info = _process_pdf(data)
            _db().upload_client_document(uid, client_pdf.name, data, "client")
            res = _apply_document(uid, info, "client")
            if profile and profile.get("agent_id"):
                _db().notify_agent_client_upload(profile["agent_id"], uid, res["codes"], res["library"])
            _flash("success", "✅ המסמך נשמר.")
            for m in _document_messages(res, info):
                if m[0] == "warning":
                    m = ("info", "לא זוהו במסמך קודי נספחים — הסוכן שלך יעבור עליו.")
                _flash(*m)
            st.rerun()

        with st.expander("📁 המסמכים שלי", expanded=False):
            _render_documents(st.session_state.reg_user_id, "client_docs")

        bot_num = _bot_whatsapp_number()
        if bot_num:
            _whatsapp_card(bot_num)

        st.markdown("<br>", unsafe_allow_html=True)

        with st.expander("🗑️ מחיקת חשבון", expanded=False):
            st.warning("פעולה זו תמחק את כל הנתונים שלך לצמיתות ואינה ניתנת לביטול.")
            confirm_delete = st.checkbox("אני מבין/ה ורוצה למחוק את החשבון שלי", key="confirm_delete")
            if st.button("מחק חשבון לצמיתות", type="primary", key="delete_account_btn"):
                if not confirm_delete:
                    st.error("יש לסמן את תיבת האישור קודם.")
                else:
                    user_id = st.session_state.get("reg_user_id", "")
                    if user_id and _db().delete_profile(user_id):
                        st.success("✅ החשבון נמחק בהצלחה.")
                        for k, v in defaults.items():
                            st.session_state[k] = v
                        _forget_login()
                        st.rerun()
                    else:
                        st.error("שגיאה במחיקת החשבון. נסה שוב או צור קשר עם הסוכן.")

        if st.button("← יציאה"):
            for k, v in defaults.items():
                st.session_state[k] = v
            _forget_login()
            st.rerun()


def page_login_choose():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("כניסה", "בחר את סוג המשתמש שלך")
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
<div style="background:#F0FDF4;border:2px solid #D1FAE5;border-radius:16px;padding:20px 24px;text-align:right;margin-bottom:16px">
  <div style="font-size:1.6rem;margin-bottom:6px">👤</div>
  <div style="font-weight:700;font-size:1rem;color:#111827;margin-bottom:4px">כניסה כלקוח</div>
  <div style="font-size:0.88rem;color:#6B7280">אימות בקוד וואטסאפ</div>
</div>
""", unsafe_allow_html=True)
        if st.button("כניסה כלקוח", type="primary", use_container_width=True):
            st.session_state.step = "login"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
<div style="background:#F8FAFF;border:2px solid #DBEAFE;border-radius:16px;padding:20px 24px;text-align:right;margin-bottom:16px">
  <div style="font-size:1.6rem;margin-bottom:6px">🏢</div>
  <div style="font-weight:700;font-size:1rem;color:#111827;margin-bottom:4px">כניסה כסוכן</div>
  <div style="font-size:0.88rem;color:#6B7280">אימייל וסיסמה</div>
</div>
""", unsafe_allow_html=True)
        if st.button("כניסה כסוכן", use_container_width=True):
            st.session_state.step = "agent_login"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← חזרה"):
            st.session_state.step = "choose"
            st.rerun()


def page_agent_login():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("כניסה כסוכן", "הזן את פרטי הגישה שלך")

        login_method = st.radio("שיטת כניסה", ["אימייל וסיסמה", "טלפון + קוד וואטסאפ"],
                                horizontal=True, label_visibility="collapsed")

        if login_method == "אימייל וסיסמה":
            email = st.text_input("אימייל", placeholder="israel@example.com")
            password = st.text_input("סיסמה", type="password", placeholder="הסיסמה שלך")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("כניסה", type="primary", use_container_width=True):
                if not email.strip() or not password:
                    st.error("נא למלא אימייל וסיסמה.")
                else:
                    agent = _db().get_agent_by_email_and_password(email.strip(), password)
                    if agent:
                        st.session_state.logged_in_agent = agent
                        _remember_login("a", st.session_state.logged_in_agent.get("id", ""))
                        st.session_state.step = "agent_dashboard"
                        st.rerun()
                    else:
                        st.error("האימייל או הסיסמה שגויים.")
        else:
            phone = st.text_input("טלפון נייד", placeholder="050-1234567")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("שלח קוד אימות", type="primary", use_container_width=True):
                clean = phone.strip().replace("-", "").replace(" ", "")
                if not re.match(r"^05\d{8}$", clean):
                    st.error("מספר טלפון לא תקין.")
                else:
                    agent = _db().get_agent_by_phone(clean)
                    if not agent:
                        st.error("מספר טלפון לא נמצא. השתמש בכניסה עם אימייל.")
                    else:
                        st.session_state.reg_phone = clean
                        st.session_state.reg_name = agent.get("full_name", "")
                        st.session_state._agent_otp_id = agent.get("id")
                        _send_otp(clean)
                        st.session_state.step = "agent_verify_otp"
                        st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← חזרה"):
                st.session_state.step = "login_choose"
                st.rerun()
        with col2:
            if st.button("שכחתי סיסמה"):
                st.session_state.step = "agent_reset_password"
                st.rerun()


def page_agent_verify_otp():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("אימות סוכן", f"שלחנו קוד לוואטסאפ שלך ({st.session_state.reg_phone})")

        _otp_failed_notice(agent=True)

        code = st.text_input("קוד אימות", placeholder="123456", max_chars=6)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("כנס לפאנל הניהול", type="primary", use_container_width=True):
            if _otp_valid(code):
                agent = _db().get_agent_by_phone(st.session_state.reg_phone)
                if agent:
                    st.session_state.logged_in_agent = agent
                    _remember_login("a", st.session_state.logged_in_agent.get("id", ""))
                    st.session_state.step = "agent_dashboard"
                    st.rerun()
                else:
                    st.error("שגיאה בטעינת נתוני הסוכן")
            else:
                st.error("קוד שגוי או שפג תוקפו.")

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← חזרה"):
                st.session_state.step = "agent_login"
                st.rerun()
        with col2:
            if st.button("שלח קוד מחדש"):
                _send_otp(st.session_state.reg_phone)
                if st.session_state._otp_sent:
                    _flash("success", "✅ קוד חדש נשלח לוואטסאפ.")
                st.rerun()


def page_agent_reset_password():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("איפוס סיסמה", "הזן את פרטיך לאימות")

        email = st.text_input("אימייל", placeholder="israel@example.com")
        full_name = st.text_input("שם מלא (כפי שנרשמת)", placeholder="ישראל ישראלי")
        new_password = st.text_input("סיסמה חדשה", type="password", placeholder="לפחות 6 תווים")
        new_password2 = st.text_input("אימות סיסמה", type="password", placeholder="חזור על הסיסמה")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("עדכן סיסמה", type="primary", use_container_width=True):
            errors = []
            if not email.strip() or not full_name.strip():
                errors.append("נא למלא את כל השדות.")
            if not new_password or len(new_password) < 6:
                errors.append("סיסמה חייבת להכיל לפחות 6 תווים.")
            if new_password != new_password2:
                errors.append("הסיסמאות אינן תואמות.")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                ok = _db().reset_agent_password(email.strip(), full_name.strip(), new_password)
                if ok:
                    st.success("✅ הסיסמה עודכנה בהצלחה! כעת תוכל להתחבר.")
                    st.session_state.step = "agent_login"
                    st.rerun()
                else:
                    st.error("האימייל או השם לא תואמים לחשבון קיים.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← חזרה לכניסה"):
            st.session_state.step = "agent_login"
            st.rerun()


def page_login():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("כניסה", "הזן את מספר הטלפון שלך לקבלת קוד אימות")

        phone = st.text_input("טלפון נייד", placeholder="050-1234567")
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("שלח קוד אימות", type="primary", use_container_width=True):
            clean_phone = phone.strip().replace("-", "").replace(" ", "")
            if not re.match(r"^05\d{8}$", clean_phone):
                st.error("מספר טלפון לא תקין.")
            else:
                profile = _db().get_profile_by_phone(clean_phone)
                if not profile:
                    st.error("מספר הטלפון לא נמצא במערכת. האם נרשמת?")
                else:
                    st.session_state.reg_phone = clean_phone
                    st.session_state.reg_name = profile.get("full_name", "")
                    st.session_state.reg_user_id = profile.get("id", "")
                    _send_otp(clean_phone)
                    st.session_state.step = "verify_login"
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← חזרה להרשמה"):
            st.session_state.step = "form"
            st.rerun()


BASE_URL = "https://bituachbot.streamlit.app"


def _clean_phone(raw: str) -> str:
    return (raw or "").strip().replace("-", "").replace(" ", "")


def _admin_header(agent: dict):
    st.markdown("""
<style>
.admin-header {
  background: #1F2937; color: white; padding: 16px 24px; border-radius: 12px;
  font-size: 1.1rem; font-weight: 700; margin-bottom: 24px; direction: rtl;
  display: flex; align-items: center; gap: 10px;
}
.client-card {
  background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 12px;
  padding: 16px 20px; margin-bottom: 16px; direction: rtl;
}
</style>
""", unsafe_allow_html=True)
    st.markdown(f'<div class="admin-header">🔐 BituachBot — ממשק ניהול | {agent.get("full_name", "מנהל")}</div>',
                unsafe_allow_html=True)
    if agent.get("agent_code"):
        st.markdown('<div style="direction:rtl;font-size:0.85rem;font-weight:600;color:#374151;margin-bottom:6px">'
                    '🔗 קישור רישום לקוחות — שתף עם הלקוחות שלך</div>', unsafe_allow_html=True)
        st.code(f"{BASE_URL}/?agent={agent['agent_code']}", language=None)


def _agent_phone_form(agent: dict, key: str, button_label: str = "💾 שמור טלפון") -> bool:
    """Phone input + save. Returns True when saved."""
    new_phone = st.text_input("טלפון נייד (לקבלת התראות וואטסאפ)", placeholder="050-1234567",
                              value=agent.get("phone_number") or "", key=f"{key}_phone")
    if st.button(button_label, key=f"{key}_save", type="primary"):
        clean = _clean_phone(new_phone)
        other = _db().get_agent_by_phone(clean) if re.match(r"^05\d{8}$", clean) else None
        if not re.match(r"^05\d{8}$", clean):
            st.error("מספר טלפון לא תקין (חייב להתחיל ב-05 ולהיות בן 10 ספרות).")
        elif other and other.get("id") != agent.get("id"):
            st.error("המספר כבר רשום לסוכן אחר.")
        elif _db().update_agent_phone(agent["id"], clean):
            st.session_state.logged_in_agent["phone_number"] = clean
            st.success("✅ הטלפון נשמר!")
            return True
        else:
            st.error("שגיאה בעדכון")
    return False


def _agent_settings(agent: dict):
    with st.expander("⚙️ הגדרות חשבון — טלפון, אימייל, סיסמה", expanded=False):
        st.markdown("**📱 טלפון** — לקבלת התראות על לקוחות חדשים ולכניסה בקוד וואטסאפ")
        if _agent_phone_form(agent, "settings"):
            st.rerun()

        st.markdown("---")
        st.markdown("**✉️ אימייל**")
        new_email = st.text_input("אימייל", placeholder="israel@example.com",
                                  value=agent.get("email") or "", key="agent_new_email")
        if st.button("💾 שמור אימייל", key="save_agent_email"):
            clean_email = new_email.strip()
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", clean_email):
                st.error("כתובת אימייל לא תקינה")
            elif _db().update_agent_email(agent["id"], clean_email):
                st.session_state.logged_in_agent["email"] = clean_email.lower()
                st.success("✅ האימייל עודכן!")
            else:
                st.error("שגיאה בעדכון")

        st.markdown("---")
        st.markdown("**🔑 שינוי סיסמה**")
        new_pwd = st.text_input("סיסמה חדשה", type="password", placeholder="לפחות 6 תווים", key="agent_new_pwd")
        new_pwd2 = st.text_input("אימות סיסמה", type="password", placeholder="חזור על הסיסמה", key="agent_new_pwd2")
        if st.button("🔑 שנה סיסמה", key="save_agent_pwd"):
            if len(new_pwd) < 6:
                st.error("סיסמה חייבת להכיל לפחות 6 תווים")
            elif new_pwd != new_pwd2:
                st.error("הסיסמאות אינן תואמות")
            elif _db().update_agent_password(agent["id"], new_pwd):
                st.success("✅ הסיסמה עודכנה!")
            else:
                st.error("שגיאה בעדכון")


def _agent_logout():
    st.session_state.logged_in_agent = None
    st.session_state.admin_client = None
    st.session_state.step = "choose"
    _forget_login()
    st.rerun()


def page_agent_dashboard():
    """Session-based agent dashboard (no URL params needed)."""
    agent = st.session_state.logged_in_agent
    if not agent:
        st.session_state.step = "login_choose"
        st.rerun()
        return
    fresh = _db().get_agent_by_id(agent.get("id", ""))
    if fresh:
        agent.update(fresh)
        st.session_state.logged_in_agent = agent

    _admin_header(agent)

    # Phone is required: it is where new-client alerts are sent.
    if not agent.get("phone_number"):
        st.warning("📱 כדי להמשיך, הוסף את מספר הטלפון שלך — אליו נשלח התראות וואטסאפ על לקוחות חדשים.")
        if _agent_phone_form(agent, "gate", "💾 שמור והמשך"):
            st.rerun()
        if st.button("← יציאה", key="gate_logout"):
            _agent_logout()
        return

    _agent_settings(agent)
    _render_admin_content(agent)

    st.markdown("---")
    with st.expander("🔧 בדיקת חיבור WhatsApp", expanded=False):
        instance = _get_secret("GREEN_API_INSTANCE") or os.getenv("GREEN_API_INSTANCE", "")
        token    = _get_secret("GREEN_API_TOKEN")    or os.getenv("GREEN_API_TOKEN", "")
        inst_status = ("✅ " + instance[:4] + "****") if instance else "❌ לא מוגדר"
        token_status = "✅ מוגדר" if token else "❌ לא מוגדר"
        subdomain = instance[:4] if instance else "????"
        built_url = f"https://{subdomain}.api.greenapi.com/waInstance{instance or '???'}/sendMessage/***"
        st.markdown(f"""
- **GREEN_API_INSTANCE**: `{inst_status}`
- **GREEN_API_TOKEN**: `{token_status}`
- **URL**: `{built_url}`
""")
        test_phone = st.text_input("טלפון לבדיקה", placeholder="0501234567", key="debug_wa_phone")
        if st.button("📤 שלח הודעת בדיקה", key="debug_wa_btn"):
            if not instance or not token:
                st.error("חסרים credentials של Green API")
            elif not test_phone.strip():
                st.error("הזן מספר טלפון")
            else:
                digits = re.sub(r"\D", "", test_phone)
                if digits.startswith("0"):
                    digits = "972" + digits[1:]
                url = f"https://{instance[:4]}.api.greenapi.com/waInstance{instance}/sendMessage/{token}"
                st.code(f"POST {url}\nchatId: {digits}@c.us")
                try:
                    r = requests.post(
                        url,
                        json={"chatId": f"{digits}@c.us", "message": "🧪 BituachBot test"},
                        timeout=10,
                    )
                    st.write(f"**Status:** `{r.status_code}`")
                    st.code(r.text)
                    if r.status_code == 200:
                        st.success("✅ נשלח בהצלחה!")
                    else:
                        st.error("❌ שגיאה בשליחה")
                except Exception as e:
                    st.error(f"Exception: {e}")
    if st.button("← יציאה מממשק הניהול"):
        _agent_logout()


# The in-app bot gets the annex texts in its prompt. Coverage details are often deep in the
# document (physiotherapy was on page 6 of 10), so send whole annexes, within a total budget.
CHAT_TEXT_PER_ANNEX = 40000
CHAT_TEXT_BUDGET = 160000

AUTO_YEAR = "זיהוי אוטומטי"


def _annex_upload_form(key: str, code: str = ""):
    """Upload one נספח PDF to the shared library. If `code` is given it is fixed.
    One document can cover several codes (e.g. plan 5986 + chapter 6650): extra codes can be typed,
    and the codes in the document's own header are detected and saved too."""
    c1, c2 = st.columns([1, 2])
    with c1:
        if code:
            st.text_input("קוד נספח", value=code, key=f"{key}_code", disabled=True)
            extra_in = st.text_input("קודים נוספים לאותו מסמך (רשות)", placeholder="5986", key=f"{key}_extra")
            codes_text = f"{code} {extra_in}"
        else:
            codes_text = st.text_input("קוד/ים (ריק = זיהוי אוטומטי)", placeholder="6650, 5986", key=f"{key}_code")
    with c2:
        name_in = st.text_input("שם נספח (ריק = זיהוי אוטומטי)", placeholder="אבחנה מהירה", key=f"{key}_name")
    current_year = datetime.now().year
    year_choice = st.selectbox("שנת הנוסח", [AUTO_YEAR] + list(range(current_year, 1999, -1)), key=f"{key}_year")
    typed = list(dict.fromkeys(re.findall(r"\d{4,6}", codes_text or "")))
    if typed:
        versions = _db().get_annex_versions(typed[0])
        if versions:
            st.caption(f"גרסאות קיימות במאגר ל-{typed[0]}: {' · '.join(str(y) for y in versions)}")
    pdf = st.file_uploader("PDF של הנספח", type=["pdf"], key=f"{key}_pdf")
    if st.button("💾 שמור נספח במאגר", type="primary", key=f"{key}_save"):
        if not pdf:
            st.error("בחר קובץ PDF של הנספח.")
        elif _save_annex_pdf(pdf.getvalue(), typed, name_in, year_choice):
            st.rerun()


def _save_annex_pdf(pdf_bytes: bytes, typed: list[str], name: str, year_choice) -> bool:
    """Library upload by the agent. Saves under the typed codes + the codes in the document's own header."""
    info = _process_pdf(pdf_bytes)
    text = info.get("text", "")
    if not text.strip():
        st.error(f"❌ {info.get('error') or 'לא ניתן לקרוא טקסט מהקובץ.'}")
        return False
    detected = info["codes"] if info["doc_type"] == "annex" else []
    codes = list(typed)
    if detected and (not typed or set(detected) & set(typed)):
        codes += detected
    elif detected:
        _flash("warning", f"⚠️ בכותרת הקובץ מופיעים קודים אחרים ({' · '.join(detected)}) — "
                          f"נשמר רק תחת {' · '.join(typed)}. ודא שזה הנספח הנכון.")
    for c in typed:
        codes += _extract_related_codes(text, c)
    codes = list(dict.fromkeys(codes))
    if not codes:
        st.error("לא הצלחנו לזהות את קוד הנספח — הזן אותו ידנית." +
                 (f" ({info['error']})" if info.get("error") else ""))
        return False
    if info["doc_type"] == "policy":
        _flash("warning", "⚠️ הקובץ נראה כמו מפרט פוליסה של לקוח ולא כמו חוברת תנאים של נספח — בדוק שהעלית את הקובץ הנכון.")
    year = year_choice if year_choice != AUTO_YEAR else (info.get("year") or datetime.now().year)
    saved, _ = _db().add_annex_document(
        codes, (name or "").strip() or info.get("name", ""), text, year, info.get("company", ""), overwrite=True
    )
    if not saved:
        st.error("שגיאה בשמירת הנספח במאגר.")
        return False
    _flash("success", f"✅ נספח {' · '.join(saved)} ({year}) נשמר במאגר — כל הלקוחות עם הקודים האלה עודכנו.")
    return True


def _render_client_card(client: dict, agent_id: str):
    """Everything about one client: status, annexes, missing annexes, documents, upload, bot chat."""
    client = _db().get_profile_by_id(client.get("id", "")) or client
    policies = _db().get_user_policies(client["id"])
    ready = [p for p in policies if p.get("has_data")]
    missing = [p for p in policies if not p.get("has_data")]
    docs = _db().list_client_documents(client["id"])
    status = InsuranceClientDB.client_status(ready, missing, len(docs))
    icon, label = STATUS_LABELS[status]

    head_l, head_r = st.columns([5, 1])
    with head_l:
        st.markdown(f"## 👤 {client.get('full_name','')}")
    with head_r:
        if st.button("✖ סגור", key="close_client", use_container_width=True):
            st.session_state.admin_client = None
            st.rerun()
    st.markdown(f"""
<div class="client-card">
  <div style="color:#374151;font-size:0.95rem;line-height:1.9">
    📱 {client.get('phone_number','')} &nbsp;·&nbsp; 🆔 {client.get('teudat_zehut') or '—'}
    &nbsp;·&nbsp; 📅 נרשם {(client.get('created_at') or '')[:10]}<br>
    <strong>{icon} {label}</strong> &nbsp;·&nbsp; ✅ {len(ready)} נספחים במאגר
    &nbsp;·&nbsp; ⏳ {len(missing)} חסרים &nbsp;·&nbsp; 📄 {len(docs)} מסמכים
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown("#### 📋 נספחים")
    if not policies:
        st.info("עדיין אין נספחים ללקוח — העלה את הפוליסה שלו למטה.")
    for p in ready:
        company = f" · {p['company']}" if p.get("company") else ""
        st.markdown(f"✅ **{p['annex_code']}** — {p.get('annex_name','')}{company}")
    for p in missing:
        st.markdown(f"⏳ **{p['annex_code']}** — חסר במאגר, הבוט לא יכול לענות עליו עדיין")
        with st.expander(f"📤 העלה את נספח {p['annex_code']}", expanded=False):
            _annex_upload_form(f"card_{client['id'][:8]}_{p['annex_code']}", p["annex_code"])

    st.markdown(f"#### 📄 העלה פוליסה ל{client.get('full_name','לקוח')}")
    st.caption("הקובץ נשמר בתיק של הלקוח הזה. הנספחים שבו יזוהו אוטומטית, ואם זה מסמך של נספח (חוברת תנאים) — הוא ייכנס גם למאגר.")
    pdf_file = st.file_uploader("בחר קובץ PDF", type=["pdf"], key=f"admin_pdf_{client['id'][:8]}")
    if pdf_file and st.button("⬆️ שמור בתיק הלקוח וזהה נספחים", type="primary", key="admin_pdf_save"):
        data = pdf_file.getvalue()
        info = _process_pdf(data)
        saved = _db().upload_client_document(client["id"], pdf_file.name, data, "agent")
        res = _apply_document(client["id"], info, "agent")
        msgs = _document_messages(res, info)
        if res["codes"]:
            after = _db().get_user_policies(client["id"])
            now_missing = [p["annex_code"] for p in after if not p.get("has_data") and p["annex_code"] in res["codes"]]
            if now_missing:
                msgs.append(("warning", f"⏳ חסרים במאגר: {' · '.join(now_missing)} — העלה אותם כדי שהבוט יוכל לענות."))
            if res["linked"]:
                ready_count = len([p for p in after if p.get("has_data")])
                if ready_count:
                    _db().send_ready(client["phone_number"], client["full_name"], ready_count)
        if not saved:
            msgs.append(("warning", "⚠️ הקובץ עצמו לא נשמר באחסון (בדוק את הגדרות Supabase Storage)."))
        for m in msgs:
            _flash(*m)
        st.rerun()

    with st.expander(f"📁 מסמכים ({len(docs)})", expanded=False):
        st.caption("🔍 נתח שוב — מזהה מחדש את הנספחים במסמך. מסמך של נספח ייכנס למאגר.")
        _render_documents(client["id"], "agent_docs", reanalyze_by="agent")

    _render_client_chat(client)


def _render_client_chat(client: dict):
    st.markdown("---")
    st.markdown("### 💬 שאל את הבוט עבור הלקוח")

    client_id = client.get("id", "")
    if st.session_state.get("agent_bot_client_id") != client_id:
        st.session_state.agent_bot_client_id = client_id
        st.session_state.agent_bot_messages = []

    policies = _db().get_user_policies(client_id)
    ready_policies = [p for p in policies if p.get("has_data") and p.get("full_text")]

    if not ready_policies:
        st.info("אין נספחים זמינים לבוט עבור לקוח זה — העלה PDF קודם.")
    else:
        st.caption(
            f"בוט מבוסס על {len(ready_policies)} נספחים: "
            + " · ".join(p["annex_code"] for p in ready_policies)
        )

        for msg in st.session_state.agent_bot_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_q = st.chat_input(f"שאל שאלה לגבי {client.get('full_name', 'הלקוח')}...")
        if user_q:
            st.session_state.agent_bot_messages.append({"role": "user", "content": user_q})
            with st.chat_message("user"):
                st.markdown(user_q)

            system_lines = [
                "אתה מומחה ביטוח בריאות ישראלי. אתה עוזר לסוכן ביטוח לענות על שאלות לגבי פוליסת לקוח ספציפי.",
                f"פרטי הלקוח: {client.get('full_name', '')} | טלפון: {client.get('phone_number', '')}",
                "",
                "נספחי הלקוח:",
            ]
            for p in ready_policies:
                system_lines.append(
                    f"\n--- נספח {p['annex_code']} ({p['annex_name']}"
                    + (f", {p['company']}" if p.get("company") else "")
                    + ") ---"
                )
                room = max(0, CHAT_TEXT_BUDGET - sum(len(x) for x in system_lines))
                system_lines.append(p["full_text"][:min(CHAT_TEXT_PER_ANNEX, room)])

            system_lines += [
                "",
                "ענה בעברית. הסתמך על הנספחים. אם המידע לא קיים, ציין זאת בבירור — לעולם אל תנחש מספרים או תנאים.",
                "אל תיתן ייעוץ רפואי (אבחנות, בדיקות, טיפולים) — התייחס רק למה שהנספחים מכסים.",
                "בסוף כל תשובה שעוסקת בכיסוי, סכומים, השתתפות עצמית, תנאים או זכאות, הוסף בשורה נפרדת בדיוק:",
                AI_NOTE_AGENT,
            ]

            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.agent_bot_messages
            ]
            with st.chat_message("assistant"):
                with st.spinner("חושב..."):
                    try:
                        resp = _claude_create(
                            max_tokens=1024,
                            system="\n".join(system_lines),
                            messages=history,
                        )
                        answer = resp.content[0].text
                    except Exception as e:
                        print(f"[landing] agent bot chat: {e}")
                        answer = f"❌ {_anthropic_error_he(e)}"
                st.markdown(answer)
            if not answer.startswith("❌"):
                st.session_state.agent_bot_messages.append({"role": "assistant", "content": answer})
            else:
                st.session_state.agent_bot_messages.pop()

        if st.session_state.agent_bot_messages:
            if st.button("🗑️ נקה שיחה", key="clear_bot_chat"):
                st.session_state.agent_bot_messages = []
                st.rerun()


def _render_new_client_form(agent: dict):
    with st.expander("➕ לקוח חדש — רשום לקוח בעצמך", expanded=False):
        st.caption("ללקוח שמעדיף שתעשה את זה בשבילו. הלקוח יקבל הודעת וואטסאפ עם מספר הבוט.")
        with st.form("new_client_form", clear_on_submit=False):
            name = st.text_input("שם מלא")
            phone = st.text_input("טלפון נייד", placeholder="050-1234567")
            tz = st.text_input("תעודת זהות (רשות)", max_chars=9)
            pdf = st.file_uploader("פוליסה PDF (רשות)", type=["pdf"])
            send_welcome = st.checkbox("שלח ללקוח הודעת וואטסאפ עם מספר הבוט", value=True)
            submitted = st.form_submit_button("✅ צור לקוח", type="primary")
        if not submitted:
            return
        clean = _clean_phone(phone)
        errors = []
        if not name.strip():
            errors.append("נא להזין שם מלא.")
        if not re.match(r"^05\d{8}$", clean):
            errors.append("מספר טלפון לא תקין.")
        if tz.strip() and not _validate_teudat_zehut(tz.strip()):
            errors.append("תעודת זהות לא תקינה.")
        if errors:
            for e in errors:
                st.error(e)
            return
        existing = _db().get_profile_by_phone(clean)
        if existing:
            if existing.get("agent_id") == agent["id"]:
                st.info("הלקוח כבר רשום אצלך — פתחתי את התיק שלו.")
                st.session_state.admin_client = existing
                st.rerun()
            elif not existing.get("agent_id"):
                _db().assign_agent(existing["id"], agent["id"])
                st.success("הלקוח כבר היה רשום בלי סוכן — שייכתי אותו אליך.")
                st.session_state.admin_client = existing
                st.rerun()
            else:
                st.error("המספר כבר רשום אצל סוכן אחר.")
            return
        data = pdf.getvalue() if pdf else b""
        info = _process_pdf(data) if data else None
        ok, user_id = _db().register_user_with_policies(clean, name.strip(), [], tz.strip(), agent["id"])
        if not ok:
            st.error(user_id)
            return
        _flash("success", f"✅ {name.strip()} נרשם")
        if data:
            _db().upload_client_document(user_id, pdf.name, data, "agent")
            for m in _document_messages(_apply_document(user_id, info, "agent"), info):
                _flash(*m)
        if send_welcome:
            _db().send_welcome_from_agent(clean, name.strip(), agent.get("full_name", ""), BASE_URL)
        st.session_state.admin_client = _db().get_profile_by_id(user_id)
        st.rerun()


def _render_admin_content(agent: dict):
    """Agent workspace. agent['id'] empty = main admin (sees all clients)."""
    agent_id = agent.get("id", "")

    # ── OPEN CLIENT (shown first) ─────────────────────────────────────────────
    if st.session_state.admin_client:
        _render_client_card(st.session_state.admin_client, agent_id)
        st.markdown("---")

    # ── NEW CLIENT ────────────────────────────────────────────────────────────
    if agent_id:
        _render_new_client_form(agent)

    # ── MY CLIENTS ────────────────────────────────────────────────────────────
    clients = _db().get_agent_clients(agent_id)
    st.markdown(f"### 👥 הלקוחות שלי ({len(clients)})")
    if not clients:
        st.info("עדיין אין לקוחות. שתף את הקישור למעלה, או רשום לקוח ב'➕ לקוח חדש'.")
    else:
        counts = {k: sum(1 for c in clients if c["status"] == k) for k in STATUS_LABELS}
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("✅ מוכנים", counts["ready"])
        m2.metric("🟡 חלקי", counts["partial"])
        m3.metric("⏳ חסר נספח במאגר", counts["waiting_annex"])
        m4.metric("❌ בלי פוליסה", counts["empty"])

        f1, f2 = st.columns(2)
        with f1:
            status_filter = st.selectbox(
                "סינון", ["הכל"] + [f"{v[0]} {v[1]}" for v in STATUS_LABELS.values()], key="clients_filter"
            )
        with f2:
            search = st.text_input("חיפוש לפי שם או טלפון", key="clients_search", placeholder="שם / 05...")
        shown = clients
        if status_filter != "הכל":
            wanted = [k for k, v in STATUS_LABELS.items() if f"{v[0]} {v[1]}" == status_filter][0]
            shown = [c for c in shown if c["status"] == wanted]
        if search.strip():
            q = search.strip().replace("-", "")
            shown = [c for c in shown if q in (c.get("full_name") or "") or q in (c.get("phone_number") or "")]

        for c in shown:
            icon, label = STATUS_LABELS[c["status"]]
            col_a, col_b = st.columns([5, 1])
            with col_a:
                details = []
                if c["ready_codes"]:
                    details.append(f"✅ {', '.join(c['ready_codes'])}")
                if c["pending_codes"]:
                    details.append(f"⏳ חסרים: {', '.join(c['pending_codes'])}")
                details.append(f"📄 {c['doc_count']} מסמכים")
                st.markdown(
                    f"{icon} **{c.get('full_name','')}** — {c.get('phone_number','')} "
                    f"<span style='color:#9CA3AF;font-size:0.82rem'>(נרשם {(c.get('created_at') or '')[:10]})</span><br>"
                    f"<span style='font-size:0.85rem;color:#4B5563'>{label} · {' · '.join(details)}</span>",
                    unsafe_allow_html=True,
                )
            with col_b:
                if st.button("פתח", key=f"open_{c['id']}", use_container_width=True):
                    st.session_state.admin_client = c
                    st.rerun()

    # ── FIND / CLAIM BY PHONE ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔎 חיפוש לקוח לפי טלפון")
    s1, s2 = st.columns([3, 1])
    with s1:
        phone_input = st.text_input("טלפון", placeholder="0501234567", key="find_phone",
                                    label_visibility="collapsed")
    with s2:
        do_find = st.button("חפש", key="find_btn", use_container_width=True)
    if do_find:
        clean = _clean_phone(phone_input)
        if not re.match(r"^05\d{8}$", clean):
            st.error("מספר טלפון לא תקין")
            st.session_state.pop("_found_client", None)
        else:
            found = _db().get_profile_by_phone(clean)
            if not found:
                st.error(f"לקוח עם מספר {clean} לא נמצא — אפשר לרשום אותו ב'➕ לקוח חדש'.")
                st.session_state.pop("_found_client", None)
            else:
                st.session_state["_found_client"] = found
    found = st.session_state.get("_found_client")
    if found:
        owner = found.get("agent_id")
        if not agent_id or owner == agent_id:
            st.session_state.admin_client = found
            st.session_state.pop("_found_client", None)
            st.rerun()
        elif not owner:
            st.info(f"**{found.get('full_name','')}** ({found.get('phone_number','')}) רשום בלי סוכן.")
            if st.button("🤝 שייך אליי", key="claim_client", type="primary"):
                if _db().assign_agent(found["id"], agent_id):
                    st.session_state.admin_client = found
                    st.session_state.pop("_found_client", None)
                    st.success("✅ הלקוח שויך אליך")
                    st.rerun()
        else:
            st.error("הלקוח משויך לסוכן אחר.")

    # ── MISSING ANNEXES ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📌 נספחים שחסרים במאגר")
    st.caption("קודים שיש ללקוחות שלך אבל עדיין לא הועלו למאגר — עד שתעלה אותם, הבוט לא יכול לענות עליהם.")
    pending_codes = _db().get_pending_annex_codes(agent_id)
    if not pending_codes:
        st.success("✅ אין נספחים חסרים")
    else:
        for item in pending_codes:
            names = item["clients"]
            with st.expander(
                f"⏳ נספח {item['annex_code']} — {len(names)} לקוחות: "
                f"{', '.join(names[:4])}{' ...' if len(names) > 4 else ''}",
                expanded=False,
            ):
                _annex_upload_form(f"pending_{item['annex_code']}", item["annex_code"])

    # ── ANY ANNEX ─────────────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("➕ הוסף / עדכן נספח במאגר (כל קוד)", expanded=False):
        st.caption("מאגר משותף — כל הלקוחות שיש להם את הקוד יתעדכנו אוטומטית.")
        _annex_upload_form("nispaj")



# ── PRIVACY POLICY PAGE ────────────────────────────────────────────────────────

def page_privacy():
    st.markdown("""
<style>
.privacy-container { max-width: 760px; margin: 0 auto; direction: rtl; text-align: right; padding: 40px 24px; }
.privacy-container h1 { font-size: 1.8rem; font-weight: 800; color: #111827; margin-bottom: 8px; }
.privacy-container h2 { font-size: 1.1rem; font-weight: 700; color: #16B364; margin-top: 32px; margin-bottom: 10px; border-bottom: 2px solid #F0FDF4; padding-bottom: 6px; }
.privacy-container p, .privacy-container li { font-size: 0.95rem; color: #374151; line-height: 1.85; }
.privacy-container ul { padding-right: 20px; }
.privacy-date { font-size: 0.82rem; color: #9CA3AF; margin-bottom: 28px; }
</style>
<div class="privacy-container">
<h1>🛡️ מדיניות פרטיות — BituachBot</h1>
<div class="privacy-date">עדכון אחרון: מאי 2026</div>

<h2>1. מי אנחנו</h2>
<p>BituachBot היא פלטפורמה דיגיטלית המיועדת לסיוע ללקוחות ביטוח בישראל להבין את תכני הפוליסות שלהם. השירות מופעל על ידי סוכנות ביטוח מורשית.</p>

<h2>2. אילו מידע אנו אוספים</h2>
<ul>
  <li><strong>שם מלא</strong> — לצורך זיהוי וקשר אישי</li>
  <li><strong>מספר טלפון נייד</strong> — לצורך אימות זהות ושליחת עדכונים</li>
  <li><strong>תעודת זהות</strong> — לצורך אימות זהות ומניעת כפילויות</li>
  <li><strong>מסמכי פוליסת ביטוח (PDF)</strong> — לצורך ניתוח הכיסויים ומתן מענה אישי</li>
  <li><strong>שיחות עם הבוט</strong> — לצורך שיפור השירות ומתן מענה רציף</li>
</ul>

<h2>3. כיצד אנו משתמשים במידע</h2>
<ul>
  <li>הצגת תכני הפוליסה האישית שלך בפורמט קריא</li>
  <li>מענה על שאלות הקשורות לכיסוי הביטוחי שלך</li>
  <li>יצירת קשר עם הסוכן שלך בנושא הפוליסה</li>
  <li>שיפור מתמיד של השירות</li>
</ul>

<h2>4. שיתוף מידע עם גורמים חיצוניים</h2>
<p>המידע שלך מועבר לספקי שירות הבאים אך ורק לצורך מתן השירות:</p>
<ul>
  <li><strong>Supabase Inc. (ארה"ב)</strong> — אחסון המידע בצורה מאובטחת</li>
  <li><strong>Anthropic PBC (ארה"ב)</strong> — עיבוד טקסט הפוליסה באמצעות בינה מלאכותית לצורך מענה על שאלותיך. <em>הערה: טקסט הפוליסה שלך נשלח לשרתי Anthropic לעיבוד.</em></li>
  <li><strong>Green API</strong> — שליחת הודעות WhatsApp לאימות ועדכונים</li>
  <li><strong>הסוכן שלך</strong> — רואה את פרטיך ואת הנספחים שלך לצורך סיוע</li>
</ul>
<p>אנו לא מוכרים, לא משכירים ולא מעבירים את המידע שלך לצדדים שלישיים למטרות שיווק.</p>

<h2>5. אבטחת מידע</h2>
<p>המידע שלך מאוחסן בצורה מוצפנת בשרתי Supabase. הגישה מוגבלת לצוות המורשה בלבד. אנו מיישמים אמצעי אבטחה סבירים בהתאם לתקנות הגנת הפרטיות (אבטחת מידע), תשע"ז-2017.</p>

<h2>6. שמירת מידע</h2>
<p>המידע שלך נשמר כל עוד חשבונך פעיל. אתה רשאי לבקש מחיקת חשבונך וכל המידע הקשור אליו בכל עת.</p>

<h2>7. הזכויות שלך</h2>
<p>בהתאם לחוק הגנת הפרטיות, תשמ"א-1981, יש לך זכות ל:</p>
<ul>
  <li>עיין במידע שנאסף עליך</li>
  <li>תקן מידע שגוי</li>
  <li>מחק את חשבונך ואת כל המידע שלך</li>
  <li>בקש הסבר על אופן השימוש במידע שלך</li>
</ul>
<p>למימוש זכויות אלו: פנה דרך הבוט בוואטסאפ או צור קשר ישירות עם הסוכן שלך.</p>

<h2>8. עדכונים למדיניות</h2>
<p>אנו עשויים לעדכן מדיניות זו מעת לעת. עדכונים מהותיים יישלחו בהודעת וואטסאפ.</p>

<h2>9. יצירת קשר</h2>
<p>לכל שאלה בנושא פרטיות: פנה אל הסוכן שלך או שלח הודעת WhatsApp לבוט.</p>
</div>
""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← חזרה"):
        st.query_params.clear()
        st.rerun()


# ── ADMIN PAGE ─────────────────────────────────────────────────────────────────

def page_admin():
    """Legacy URL-based admin (?agent=CODE&admin=1). Kept for backward compat."""
    agent_for_admin = _agent
    if not agent_for_admin:
        correct_password = _get_secret("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", "")
        if not correct_password:
            st.error("❌ לא נמצא סוכן. השתמש בקישור ?agent=CODE&admin=1")
            return
        if not st.session_state.admin_authed:
            pwd = st.text_input("סיסמה", type="password", placeholder="הכנס סיסמה")
            if st.button("כניסה", type="primary"):
                if pwd == correct_password:
                    st.session_state.admin_authed = True
                    st.rerun()
                else:
                    st.error("סיסמה שגויה")
            return
    elif not st.session_state.admin_authed:
        correct_password = _agent.get("admin_password", "")
        pwd = st.text_input("סיסמה", type="password", placeholder="הכנס סיסמה")
        if st.button("כניסה", type="primary"):
            if verify_password(pwd, correct_password):
                if not is_hashed(correct_password) and _agent.get("id"):
                    _db().update_agent_password(_agent["id"], pwd)
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("סיסמה שגויה")
        return

    _admin_agent = agent_for_admin or {"full_name": "מנהל ראשי", "id": "", "agent_code": ""}
    _admin_header(_admin_agent)
    _render_admin_content(_admin_agent)

    st.markdown("---")
    if st.button("← יציאה מממשק הניהול"):
        st.session_state.admin_authed = False
        st.session_state.admin_client = None
        st.query_params.clear()
        st.rerun()


@st.cache_resource(show_spinner=False)
def _repair_library_once() -> tuple:
    """Once per server start: fix annex texts that were saved with reversed Hebrew."""
    try:
        fixed = _db().repair_reversed_annexes()
        if fixed:
            print(f"[landing] repaired reversed Hebrew in annexes: {fixed}")
        return tuple(fixed)
    except Exception as e:
        print(f"[landing] _repair_library_once: {e}")
        return ()


# ── ROUTER ─────────────────────────────────────────────────────────────────────
if not (_is_privacy or _is_admin or _agent_code):
    _restore_session()
_flush_cookie_op()
_repair_library_once()
_show_flash()

if _is_privacy:
    page_privacy()
elif _is_admin:
    page_admin()
else:
    step = st.session_state.step
    if step == "agent_dashboard":
        page_agent_dashboard()
    elif step == "verify_new":
        page_verify(is_new=True)
    elif step == "verify_login":
        page_verify(is_new=False)
    elif step == "pending":
        page_pending()
    elif step == "dashboard":
        page_dashboard()
    elif step == "login":
        page_login()
    elif step == "login_choose":
        page_login_choose()
    elif step == "agent_login":
        page_agent_login()
    elif step == "agent_verify_otp":
        page_agent_verify_otp()
    elif step == "agent_reset_password":
        page_agent_reset_password()
    elif step == "agent_register":
        page_agent_register()
    elif step == "agent_success":
        page_agent_success()
    elif step == "form":
        page_form()
    elif _agent:
        # Direct ?agent=CODE link — skip choose screen
        page_form()
    else:
        page_choose()
