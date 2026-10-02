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

import streamlit as st
import streamlit.components.v1 as components
from anthropic import Anthropic
from dotenv import load_dotenv

from modules.insurance_client import InsuranceClientDB, is_hashed, verify_password
from modules.hebrew_text import fix_visual_hebrew
from modules import ui

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

load_dotenv()

st.set_page_config(page_title="BituachBot", page_icon=":material/shield:", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown(f"<style>{ui.BASE_CSS}</style>", unsafe_allow_html=True)

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
SESSION_DAYS = 90  # renewed on every visit, so an active user stays logged in


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
            _remember_login("c", profile["id"])
            st.session_state.step = "dashboard"


def _whatsapp_card(phone: str):
    """'Save this number' card. phone in format 05XXXXXXXX"""
    if not phone:
        return
    digits = phone.replace("-", "").replace(" ", "")
    wa_digits = "972" + digits[1:] if digits.startswith("0") else digits
    st.markdown(
        f'<div class="bb-card"><div class="bb-label">הבוט בוואטסאפ</div>'
        f'<div class="bb-big">שומרים את המספר ושולחים שאלה: {ui.ltr(phone)}</div>'
        f'<div class="bb-meta" style="margin:4px 0 12px">למשל: "יש לי כיסוי לפיזיותרפיה?" או "כמה ההשתתפות העצמית ב-MRI?"</div>'
        f'<a class="bb-btn" href="https://wa.me/{wa_digits}" target="_blank" rel="noopener">{ui.ms("chat")}פתיחת שיחה בוואטסאפ</a>'
        f'</div>', unsafe_allow_html=True)


def _claude() -> Anthropic:
    api_key = _get_secret("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        st.error("ANTHROPIC_API_KEY לא מוגדר.")
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
TYPO_RULE = ("השואל עשוי לכתוב עם שגיאות כתיב, קיצורים, סלנג או תעתיק (למשל 'פיזו', 'פזיותרפיה', 'אם אר איי', "
             "'רופא עיניים') — הבן את הכוונה וחפש בנספחים לפי המשמעות ולפי מילים נרדפות (החזר = שיפוי, "
             "פיזיו = פיזיותרפיה), לא לפי התאמה מדויקת של מילים. אם באמת לא ברור — שאל 'התכוונת ל...?'.")
POLICY_CHANGE_NOTE = ("המידע כאן רלוונטי עבורך כל עוד לא ביצעת שינוי בפוליסה. אם שינית משהו מאז "
                      "(הוספת, ביטלת או עדכנת כיסוי) — העלה את הפוליסה המעודכנת או עדכן את הסוכן שלך.")
AI_NOTE_CLIENT = ("ℹ️ התשובה מתייחסת לנספחים שבפוליסה שלך כפי שהיא במערכת (אם לא בוצע בה שינוי מאז) ונוצרה ע״י "
                  "בינה מלאכותית, ולכן אינה מהווה אישור כיסוי. לפני כל פעולה — מומלץ לוודא מול הסוכן או חברת הביטוח.")
AI_NOTE_AGENT = "הערה: נוצר ע״י בינה מלאכותית על סמך הנספחים של הלקוח — מומלץ לאמת מול נוסח הפוליסה לפני שמתחייבים ללקוח."

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
    st.error("לא הצלחנו לשלוח את קוד האימות בוואטסאפ. נסה שוב בעוד רגע"
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
def _hero(audience: str = "client"):
    """Auth pages: the ink side panel (wide screens only) + the centred-form layout."""
    st.markdown(f"<style>{ui.AUTH_CSS}</style>{ui.side_panel(audience)}", unsafe_allow_html=True)


def _split():
    """(panel, form) containers for the auth pages. Kept as two containers so page code reads
    `with left: _hero()` / `with right: ...`; the panel is positioned by CSS, not by columns."""
    return st.container(), st.container()


def _clean_license(value: str) -> str:
    """Insurance agent license number: digits only (dashes/spaces ignored), 4-12 digits."""
    digits = re.sub(r"[\s\-/]", "", value or "")
    return digits if re.fullmatch(r"\d{4,12}", digits) else ""


def _license_text(agent: dict) -> str:
    lic = (agent or {}).get("license_number")
    return f"סוכן ביטוח מורשה · רישיון מס' {lic}" if lic else "סוכן ביטוח מורשה"


def _agent_badge_html(agent: dict, title: str) -> str:
    return (f'<div class="bb-card"><div class="bb-label">{title}</div>'
            f'<div class="bb-big">{agent.get("full_name", "")}</div>'
            f'<div class="bb-meta">{_license_text(agent)}</div></div>')


def _logo(title: str, sub: str = ""):
    st.markdown(ui.form_head(title, sub), unsafe_allow_html=True)


def _topbar(who: str, menu_label: str):
    """Ink bar with the brand and an account dropdown. Returns the popover to fill."""
    st.markdown("<style>[data-testid='stMainBlockContainer']{max-width:920px !important}</style>", unsafe_allow_html=True)
    with st.container(key="bb_topbar"):
        c1, c2 = st.columns([5, 2], vertical_alignment="center")
        with c1:
            st.markdown(ui.brand(who), unsafe_allow_html=True)
        with c2:
            return st.popover(menu_label, icon=":material/account_circle:")


def _client_logout():
    for k, v in defaults.items():
        st.session_state[k] = v
    _forget_login()
    st.rerun()


# ── PAGES ──────────────────────────────────────────────────────────────────────

STATUS_LABELS = {
    "ready": ("ok", "מוכן"),
    "partial": ("part", "חלקי"),
    "waiting_annex": ("wait", "חסר נספח"),
    "empty": ("none", "בלי פוליסה"),
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
        st.caption("עדיין לא הועלו מסמכים.")
        return
    who_label = {"client": "הלקוח", "agent": "הסוכן", "bot": "וואטסאפ"}
    for i, d in enumerate(docs):
        url = _db().document_url(d["path"])
        who = who_label.get(d.get("uploaded_by", ""), "")
        meta = " · ".join(x for x in [d.get("uploaded_at", ""), who] if x)
        name = (f'<a class="bb-link" href="{url}" target="_blank" rel="noopener">{d["name"]}</a>' if url
                else f'<b>{d["name"]}</b>')
        line = f'{ui.ms("description")} {name} <span class="bb-meta" style="color:#8B94A7;font-size:.82rem">{meta}</span>'
        if not reanalyze_by:
            st.markdown(line, unsafe_allow_html=True)
            continue
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        with c1:
            st.markdown(line, unsafe_allow_html=True)
        with c2:
            if st.button("ניתוח מחדש", key=f"{key_prefix}_re_{i}", use_container_width=True,
                         help="מזהה שוב את הנספחים. אם זה מסמך של נספח — הוא נכנס למאגר."):
                data = _db().download_client_document(d["path"])
                if not data:
                    _flash("error", "לא הצלחנו להוריד את הקובץ מהאחסון.")
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
        msgs.append(("error", f"לא הצלחנו לנתח את המסמך: {info['error']}"))
    if res["is_annex"]:
        name = f" ({info['name']})" if info.get("name") else ""
        if res["library"]:
            msgs.append(("success", f"זה מסמך של נספח{name} — נשמר במאגר תחת: {' · '.join(res['library'])}. "
                                    "כל הלקוחות עם הקודים האלה עודכנו."))
        if res["library_skipped"]:
            msgs.append(("info", f"נספח {' · '.join(res['library_skipped'])} כבר קיים במאגר — הנוסח שם לא שונה."))
    elif res["codes"]:
        msgs.append(("success", f"זוהו {len(res['codes'])} נספחים ({res['linked']} חדשים): {' · '.join(res['codes'])}"))
    elif not info.get("error"):
        msgs.append(("warning", "לא זוהו קודי נספחים במסמך."))
    return msgs


MAX_FILES = 20


def _ingest_files(user_id: str, files: list, by: str) -> tuple[list[tuple[str, str]], dict]:
    """Store and analyze several PDFs for one client. Returns (messages to flash, totals)."""
    msgs: list[tuple[str, str]] = []
    totals = {"codes": [], "library": [], "linked": 0, "saved_all": True, "count": 0}
    files = list(files or [])[:MAX_FILES]
    many = len(files) > 1
    bar = st.progress(0.0, text=f"מעבד 0/{len(files)} מסמכים...") if many else None
    for i, f in enumerate(files, 1):
        data = f.getvalue()
        info = _process_pdf(data)
        totals["saved_all"] &= _db().upload_client_document(user_id, f.name, data, by)
        res = _apply_document(user_id, info, by)
        prefix = f"{f.name} — " if many else ""
        for kind, m in _document_messages(res, info):
            msgs.append((kind, prefix + m))
        totals["codes"] += [c for c in res["codes"] if c not in totals["codes"]]
        totals["library"] += [c for c in res["library"] if c not in totals["library"]]
        totals["linked"] += res["linked"]
        totals["count"] += 1
        if bar:
            bar.progress(i / len(files), text=f"מעבד {i}/{len(files)} מסמכים...")
    return msgs, totals


def page_choose():
    """Landing. BituachBot is a tool for licensed agents: clients join only through their agent's link."""
    left, right = _split()
    with left:
        _hero("agent")
    with right:
        _logo("ברוכים הבאים", "BituachBot הוא כלי עבודה לסוכני ביטוח מורשים.")

        st.markdown(ui.choice("סוכן ביטוח מורשה", "פתיחת חשבון: קישור אישי ללקוחות, פאנל ניהול ובוט שעונה בשמך."),
                    unsafe_allow_html=True)
        if st.button("הצטרפות כסוכן", type="primary", use_container_width=True, icon=":material/badge:"):
            st.session_state.step = "agent_register"
            st.rerun()

        st.markdown(ui.choice("כבר רשומים?", "כניסה לסוכנים ולקוחות קיימים."), unsafe_allow_html=True)
        if st.button("כניסה", use_container_width=True, icon=":material/login:"):
            st.session_state.step = "login_choose"
            st.rerun()

        st.caption("לקוחות נרשמים דרך הקישור האישי שמקבלים מסוכן הביטוח שלהם.")


def page_agent_register():
    """Agent self-registration."""
    left, right = _split()
    with left:
        _hero("agent")
    with right:
        _logo("הרשמה כסוכן ביטוח", "צור את הסביבה שלך ב-BituachBot")

        full_name = st.text_input("שם מלא", placeholder="ישראל ישראלי")
        email = st.text_input("אימייל", placeholder="israel@example.com")
        agent_phone = st.text_input("טלפון נייד (לקבלת התראות בוואטסאפ)", placeholder="050-1234567")
        license_in = st.text_input("מספר רישיון סוכן ביטוח (רשות שוק ההון)", placeholder="מספר הרישיון",
                                   help="BituachBot מיועד לסוכני ביטוח מורשים בלבד. המספר מוצג ללקוחות שלך.")
        password = st.text_input("סיסמת ניהול", type="password", placeholder="בחר סיסמה חזקה")
        password2 = st.text_input("אימות סיסמה", type="password", placeholder="חזור על הסיסמה")

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
            clean_license = _clean_license(license_in)
            if not clean_license:
                errors.append("נא להזין מספר רישיון סוכן ביטוח תקין (ספרות בלבד).")
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
                                                    clean_agent_phone, clean_license)
                    if ok:
                        st.session_state.agent_registered_code = code
                        st.session_state.step = "agent_success"
                        st.rerun()
                    elif result != "agent_exists":
                        st.error(f"שגיאה: {result}")
                        break
                else:
                    st.error("לא ניתן ליצור קוד ייחודי. נסה שוב.")

        if st.button("חזרה", type="tertiary", icon=":material/arrow_forward:"):
            st.session_state.step = "choose"
            st.rerun()


def page_agent_success():
    """Shown after successful agent registration."""
    code = st.session_state.agent_registered_code
    left, right = _split()
    with left:
        _hero("agent")
    with right:
        _logo("החשבון שלך מוכן", "זה הקישור האישי שלך. שולחים אותו ללקוחות, והם נרשמים אצלך.")
        st.code(f"{BASE_URL}/?agent={code}", language=None)
        st.caption("הקישור מופיע תמיד גם בפאנל, בלשונית הלקוחות.")
        if st.button("כניסה לפאנל", type="primary", use_container_width=True, icon=":material/login:"):
            agent = _db().get_agent_by_code(code)
            if agent:
                st.session_state.logged_in_agent = agent
                _remember_login("a", st.session_state.logged_in_agent.get("id", ""))
                st.session_state.step = "agent_dashboard"
                st.rerun()
            else:
                st.error("לא הצלחנו לטעון את החשבון. נסו להיכנס מדף הכניסה.")


def page_form():
    left, right = _split()
    with left:
        _hero()
    with right:
        _logo("רשום פשוט ומהיר")

        if not _agent:
            if _agent_code:
                st.error("הקישור אינו תקין או שאינו פעיל — בקש מסוכן הביטוח שלך קישור חדש.")
            else:
                st.info("ההרשמה ל-BituachBot נעשית דרך סוכן הביטוח שלך. בקשו ממנו את הקישור האישי.")
            if st.button("כבר רשום? כניסה", type="primary", use_container_width=True):
                st.session_state.step = "login"
                st.rerun()
            if st.button("חזרה", type="tertiary", icon=":material/arrow_forward:"):
                st.session_state.step = "choose"
                st.rerun()
            return
        st.markdown(_agent_badge_html(_agent, "נרשמים דרך הסוכן"), unsafe_allow_html=True)

        full_name = st.text_input("שם מלא", placeholder="ישראל ישראלי")
        phone = st.text_input("טלפון נייד", placeholder="050-1234567")
        teudat_zehut = st.text_input("תעודת זהות", placeholder="123456789", max_chars=9)

        selected_agent_id = _agent["id"]

        uploads = st.file_uploader("העלאת קובצי PDF — פוליסה ונספחים (רשות, אפשר כמה ביחד)", type=["pdf"],
                                   accept_multiple_files=True)

        annex_codes: list[str] = []
        pdf_items: list[tuple] = []  # (uploaded file, bytes, info)
        if uploads and PDF_SUPPORT:
            for up in list(uploads)[:MAX_FILES]:
                data = up.getvalue()
                info = _process_pdf(data)
                pdf_items.append((up, data, info))
                annex_codes += [c for c in info["codes"] if c not in annex_codes]
                label = f"{up.name}: " if len(uploads) > 1 else ""
                if info.get("error"):
                    st.error(f"{label}{info['error']}")
                elif info["doc_type"] == "annex" and info["codes"]:
                    st.success(f"{label}זוהה מסמך של נספח: {' · '.join(info['codes'])}")
                elif info["codes"]:
                    st.success(f"{label}זוהו {len(info['codes'])} נספחים: {' · '.join(info['codes'])}")


        privacy_ok = st.checkbox(
            "קראתי ואני מסכים/ה ל[מדיניות הפרטיות](/?privacy=1) ולתנאי השימוש, כולל עיבוד מסמכי הביטוח "
            "ושאלותיי — שעשויים לכלול מידע רפואי — באמצעות בינה מלאכותית ובשרתים מחוץ לישראל, "
            "לצורך מתן השירות מטעם סוכן הביטוח שלי.",
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
                    for up, data, info in pdf_items:
                        db.upload_client_document(result, up.name, data, "client")
                        if info["doc_type"] == "annex":
                            _apply_document(result, info, "client")  # fills the library if the code is missing
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

        if st.button("כבר נרשמת? כניסה", type="tertiary"):
            st.session_state.step = "login"
            st.rerun()


def page_verify(is_new: bool):
    left, right = _split()
    with left:
        _hero()
    with right:
        _logo(
            "אימות מספר טלפון",
            f"שלחנו קוד בן 6 ספרות לוואטסאפ שלך ({st.session_state.reg_phone})",
        )

        _otp_failed_notice()

        code = st.text_input("קוד אימות", placeholder="123456", max_chars=6)

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

        col1, col2 = st.columns(2)
        with col1:
            if st.button("שלח קוד מחדש"):
                _send_otp(st.session_state.reg_phone)
                if st.session_state._otp_sent:
                    _flash("success", "קוד חדש נשלח לוואטסאפ.")
                st.rerun()
        with col2:
            if st.button("חזרה", type="tertiary", icon=":material/arrow_forward:"):
                st.session_state.step = "form" if is_new else "login"
                st.rerun()


def page_pending():
    left, right = _split()
    with left:
        _hero()
    with right:
        _logo("נרשמת בהצלחה", f"שלום {st.session_state.reg_name}, קיבלנו את הפרטים שלך. "
                               "הסוכן שלך ייצור איתך קשר כדי להשלים את קובץ הפוליסה.")
        bot_num = _bot_whatsapp_number()
        if bot_num:
            _whatsapp_card(bot_num)
        if st.button("חזרה לדף הראשי", type="tertiary", icon=":material/arrow_forward:"):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()


def page_dashboard():
    """Client area: my agent, my annexes, upload, documents."""
    uid = st.session_state.reg_user_id
    profile = _db().get_profile_by_id(uid) or _db().get_profile_by_phone(st.session_state.reg_phone)
    if profile:
        st.session_state.reg_user_id = uid = profile["id"]
    first_name = (st.session_state.reg_name or "").split(" ")[0]

    menu = _topbar("האזור האישי", first_name or "החשבון שלי")
    with menu:
        if profile:
            st.markdown(
                f'<div class="bb-kv" style="flex-direction:column;gap:4px;margin-bottom:10px">'
                f'<span><b>{profile.get("full_name", "")}</b></span>'
                f'<span>טלפון {ui.ltr(profile.get("phone_number", ""))}</span>'
                f'<span>ת"ז {ui.ltr(profile.get("teudat_zehut") or "—")}</span></div>', unsafe_allow_html=True)
        if st.button("יציאה", key="client_logout", icon=":material/logout:", use_container_width=True):
            _client_logout()

    st.markdown(ui.h1(f"שלום, {first_name}" if first_name else "שלום"), unsafe_allow_html=True)

    # ── MY AGENT ───────────────────────────────────────────────────────────────
    my_agent = _db().get_agent_by_id((profile or {}).get("agent_id") or "")
    if my_agent:
        agent_phone = my_agent.get("phone_number") or ""
        wa = ""
        if agent_phone:
            intl = "972" + agent_phone[1:] if agent_phone.startswith("0") else agent_phone
            wa = (f' <a class="bb-link" href="https://wa.me/{intl}" target="_blank" rel="noopener">'
                  f'{ui.ms("chat")} {ui.ltr(agent_phone)}</a>')
        st.markdown(
            f'<div class="bb-card"><div class="bb-label">הסוכן שלך</div>'
            f'<div class="bb-big">{my_agent.get("full_name", "")}{wa}</div>'
            f'<div class="bb-meta">{_license_text(my_agent)} · BituachBot הוא העוזר הדיגיטלי שלו</div></div>',
            unsafe_allow_html=True)
    elif profile:
        with st.expander("הסוכן שלך — לא נבחר", expanded=True):
            agents = _all_agents()
            if agents:
                names = [a["full_name"] for a in agents]
                pick = st.selectbox("בחר את סוכן הביטוח שלך", ["—"] + names, key="client_pick_agent")
                if pick != "—" and st.button("שמור סוכן", key="client_save_agent", type="primary"):
                    chosen = agents[names.index(pick)]
                    if _db().assign_agent(profile["id"], chosen["id"]):
                        _db().notify_agent_new_client(chosen["id"], profile["id"])
                        _flash("success", f"{pick} הוא הסוכן שלך.")
                        st.rerun()
            else:
                st.caption("אין סוכנים במערכת כרגע.")

    # ── MY ANNEXES ─────────────────────────────────────────────────────────────
    policies = _db().get_user_policies(uid)
    ready = [p for p in policies if p["has_data"]]
    pending = [p for p in policies if not p["has_data"]]
    if policies:
        note = f"{len(ready)} מוכנים" + (f" · {len(pending)} בעיבוד" if pending else "")
        st.markdown(ui.h2(f"הנספחים שלך ({len(policies)})", note), unsafe_allow_html=True)
        st.markdown(ui.ledger(
            [{"code": p["annex_code"], "name": p["annex_name"], "meta": p.get("company") or "", "ready": True} for p in ready]
            + [{"code": p["annex_code"], "name": p["annex_name"], "meta": "הסוכן שלך משלים את הנספח — בקרוב", "ready": False}
               for p in pending]), unsafe_allow_html=True)
        st.caption(POLICY_CHANGE_NOTE)
    else:
        st.markdown(ui.h2("הנספחים שלך"), unsafe_allow_html=True)
        st.info("עדיין אין נספחים. העלו כאן את קובץ הפוליסה, או שהסוכן שלכם יעשה זאת עבורכם.")

    # ── UPLOAD ─────────────────────────────────────────────────────────────────
    st.markdown(ui.h2("העלאת מסמכים"), unsafe_allow_html=True)
    client_pdfs = st.file_uploader("פוליסה, נספחים או כל מסמך ביטוח — אפשר כמה קבצים ביחד", type=["pdf"],
                                   accept_multiple_files=True, key="client_upload_pdf")
    if client_pdfs and st.button(f"העלאת {len(client_pdfs)} מסמכים" if len(client_pdfs) > 1 else "העלאת המסמך",
                                 type="primary", use_container_width=True, key="client_upload_btn",
                                 icon=":material/upload:"):
        msgs, tot = _ingest_files(uid, client_pdfs, "client")
        if profile and profile.get("agent_id"):
            _db().notify_agent_client_upload(profile["agent_id"], uid, tot["codes"], tot["library"])
        _flash("success", "המסמך נשמר." if tot["count"] == 1 else f"{tot['count']} מסמכים נשמרו.")
        for kind, m in msgs:
            if kind == "warning":
                kind, m = "info", m.replace("לא זוהו קודי נספחים במסמך.", "לא זוהו במסמך קודי נספחים — הסוכן שלך יעבור עליו.")
            _flash(kind, m)
        st.rerun()

    with st.expander("המסמכים שלי", expanded=False):
        _render_documents(uid, "client_docs")

    bot_num = _bot_whatsapp_number()
    if bot_num:
        st.markdown(ui.h2("שאלות על הפוליסה"), unsafe_allow_html=True)
        _whatsapp_card(bot_num)

    # ── ACCOUNT ────────────────────────────────────────────────────────────────
    if profile:
        st.markdown(ui.h2("החשבון שלי"), unsafe_allow_html=True)
        with st.expander("עדכון פרטים אישיים", expanded=False):
            upd_name = st.text_input("שם מלא", value=profile.get("full_name", ""), key="upd_name")
            upd_tz = st.text_input("תעודת זהות", value=profile.get("teudat_zehut", ""), key="upd_tz")
            if st.button("שמירת פרטים", key="save_profile"):
                if not upd_name.strip():
                    st.error("שם מלא הוא שדה חובה.")
                elif _db().update_profile(profile["id"], upd_name, upd_tz):
                    st.session_state.reg_name = upd_name.strip()
                    _flash("success", "הפרטים עודכנו.")
                    st.rerun()
                else:
                    st.error("לא הצלחנו לעדכן את הפרטים. נסו שוב.")

        with st.expander("החלפת מספר טלפון", expanded=bool(st.session_state.get("_new_phone"))):
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
                    if st.button("אשר והחלף", key="client_phone_confirm", type="primary", use_container_width=True):
                        if _otp_valid(phone_code):
                            ok, err = _db().update_profile_phone(profile["id"], pending_phone)
                            if ok:
                                st.session_state.reg_phone = pending_phone
                                st.session_state.pop("_new_phone", None)
                                _flash("success", "מספר הטלפון עודכן.")
                                st.rerun()
                            else:
                                st.error("המספר כבר רשום במערכת." if err == "phone_taken" else "לא הצלחנו לעדכן. נסו שוב.")
                        else:
                            st.error("קוד שגוי או שפג תוקפו.")
                with c2:
                    if st.button("ביטול", key="client_phone_cancel", use_container_width=True):
                        st.session_state.pop("_new_phone", None)
                        st.rerun()

        with st.expander("מחיקת חשבון", expanded=False):
            st.warning("המחיקה סופית: הפרטים, הנספחים, המסמכים והשיחות נמחקים ולא ניתן לשחזר אותם.")
            confirm_delete = st.checkbox("אני מבין/ה ורוצה למחוק את החשבון שלי", key="confirm_delete")
            if st.button("מחיקת החשבון לצמיתות", key="delete_account_btn"):
                if not confirm_delete:
                    st.error("יש לסמן את תיבת האישור קודם.")
                elif uid and _db().delete_profile(uid):
                    _flash("success", "החשבון נמחק.")
                    _client_logout()
                else:
                    st.error("לא הצלחנו למחוק את החשבון. נסו שוב או פנו לסוכן.")


def page_login_choose():
    left, right = _split()
    with left:
        _hero("agent")
    with right:
        _logo("כניסה", "איך תרצו להיכנס?")

        st.markdown(ui.choice("לקוח", "אימות בקוד שנשלח לוואטסאפ."), unsafe_allow_html=True)
        if st.button("כניסה כלקוח", type="primary", use_container_width=True, icon=":material/person:"):
            st.session_state.step = "login"
            st.rerun()

        st.markdown(ui.choice("סוכן ביטוח", "אימייל וסיסמה, או קוד בוואטסאפ."), unsafe_allow_html=True)
        if st.button("כניסה כסוכן", use_container_width=True, icon=":material/badge:"):
            st.session_state.step = "agent_login"
            st.rerun()

        if st.button("חזרה", type="tertiary", icon=":material/arrow_forward:"):
            st.session_state.step = "choose"
            st.rerun()


def page_agent_login():
    left, right = _split()
    with left:
        _hero("agent")
    with right:
        _logo("כניסה כסוכן", "הזן את פרטי הגישה שלך")

        login_method = st.radio("שיטת כניסה", ["אימייל וסיסמה", "טלפון + קוד וואטסאפ"],
                                horizontal=True, label_visibility="collapsed")

        if login_method == "אימייל וסיסמה":
            email = st.text_input("אימייל", placeholder="israel@example.com")
            password = st.text_input("סיסמה", type="password", placeholder="הסיסמה שלך")
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

        col1, col2 = st.columns(2)
        with col1:
            if st.button("חזרה", type="tertiary", icon=":material/arrow_forward:"):
                st.session_state.step = "login_choose"
                st.rerun()
        with col2:
            if st.button("שכחתי סיסמה"):
                st.session_state.step = "agent_reset_password"
                st.rerun()


def page_agent_verify_otp():
    left, right = _split()
    with left:
        _hero("agent")
    with right:
        _logo("אימות סוכן", f"שלחנו קוד לוואטסאפ שלך ({st.session_state.reg_phone})")

        _otp_failed_notice(agent=True)

        code = st.text_input("קוד אימות", placeholder="123456", max_chars=6)

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

        col1, col2 = st.columns(2)
        with col1:
            if st.button("חזרה", type="tertiary", icon=":material/arrow_forward:"):
                st.session_state.step = "agent_login"
                st.rerun()
        with col2:
            if st.button("שלח קוד מחדש"):
                _send_otp(st.session_state.reg_phone)
                if st.session_state._otp_sent:
                    _flash("success", "קוד חדש נשלח לוואטסאפ.")
                st.rerun()


def page_agent_reset_password():
    left, right = _split()
    with left:
        _hero("agent")
    with right:
        _logo("איפוס סיסמה", "הזן את פרטיך לאימות")

        email = st.text_input("אימייל", placeholder="israel@example.com")
        full_name = st.text_input("שם מלא (כפי שנרשמת)", placeholder="ישראל ישראלי")
        new_password = st.text_input("סיסמה חדשה", type="password", placeholder="לפחות 6 תווים")
        new_password2 = st.text_input("אימות סיסמה", type="password", placeholder="חזור על הסיסמה")

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
                    st.success("הסיסמה עודכנה. אפשר להתחבר.")
                    st.session_state.step = "agent_login"
                    st.rerun()
                else:
                    st.error("האימייל או השם לא תואמים לחשבון קיים.")

        if st.button("חזרה לכניסה", type="tertiary", icon=":material/arrow_forward:"):
            st.session_state.step = "agent_login"
            st.rerun()


def page_login():
    left, right = _split()
    with left:
        _hero()
    with right:
        _logo("כניסה", "הזן את מספר הטלפון שלך לקבלת קוד אימות")

        phone = st.text_input("טלפון נייד", placeholder="050-1234567")

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

        if st.button("חזרה", type="tertiary", icon=":material/arrow_forward:"):
            st.session_state.step = "form" if _agent else "choose"
            st.rerun()


BASE_URL = "https://bituachbot.streamlit.app"


def _clean_phone(raw: str) -> str:
    return (raw or "").strip().replace("-", "").replace(" ", "")


def _admin_header(agent: dict, on_logout=None):
    """Top bar + account dropdown for the agent workspace."""
    name = agent.get("full_name", "מנהל")
    menu = _topbar("פאנל סוכן" if agent.get("id") else "ניהול ראשי", name.split(" ")[0])
    with menu:
        lic = f'<span>{_license_text(agent)}</span>' if agent.get("id") else ""
        st.markdown(f'<div class="bb-kv" style="flex-direction:column;gap:4px;margin-bottom:10px">'
                    f'<span><b>{name}</b></span>{lic}</div>', unsafe_allow_html=True)
        if st.button("יציאה", key="agent_logout_btn", icon=":material/logout:", use_container_width=True):
            (on_logout or _agent_logout)()


def _agent_phone_form(agent: dict, key: str, button_label: str = "שמירת טלפון") -> bool:
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
            st.success("הטלפון נשמר.")
            return True
        else:
            st.error("שגיאה בעדכון")
    return False


def _agent_license_form(agent: dict, key: str, button_label: str = "שמירת מספר רישיון") -> bool:
    lic = st.text_input("מספר רישיון סוכן ביטוח (רשות שוק ההון)", value=agent.get("license_number") or "",
                        key=f"{key}_license", placeholder="מספר הרישיון")
    if st.button(button_label, key=f"{key}_license_save", type="primary"):
        clean = _clean_license(lic)
        if not clean:
            st.error("מספר רישיון לא תקין (ספרות בלבד).")
        elif _db().update_agent_license(agent["id"], clean):
            st.session_state.logged_in_agent["license_number"] = clean
            st.success("מספר הרישיון נשמר.")
            return True
        else:
            st.error("שגיאה בשמירה")
    return False


def _agent_settings(agent: dict):
    with st.expander("טלפון להתראות", expanded=False):
        st.caption("לכאן נשלחות התראות וואטסאפ על לקוחות חדשים, ובמספר הזה אפשר להיכנס עם קוד.")
        if _agent_phone_form(agent, "settings"):
            st.rerun()

    if _db().has_license_column():
        with st.expander("רישיון סוכן ביטוח", expanded=False):
            st.caption("מוצג ללקוחות שלך ובהודעות הבוט.")
            if _agent_license_form(agent, "settings"):
                st.rerun()

    with st.expander("אימייל", expanded=False):
        new_email = st.text_input("אימייל", placeholder="israel@example.com",
                                  value=agent.get("email") or "", key="agent_new_email")
        if st.button("שמירת אימייל", key="save_agent_email"):
            clean_email = new_email.strip()
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", clean_email):
                st.error("כתובת אימייל לא תקינה.")
            elif _db().update_agent_email(agent["id"], clean_email):
                st.session_state.logged_in_agent["email"] = clean_email.lower()
                st.success("האימייל עודכן.")
            else:
                st.error("לא הצלחנו לעדכן. נסו שוב.")

    with st.expander("סיסמה", expanded=False):
        new_pwd = st.text_input("סיסמה חדשה", type="password", placeholder="לפחות 6 תווים", key="agent_new_pwd")
        new_pwd2 = st.text_input("אימות סיסמה", type="password", placeholder="חזור על הסיסמה", key="agent_new_pwd2")
        if st.button("החלפת סיסמה", key="save_agent_pwd"):
            if len(new_pwd) < 6:
                st.error("סיסמה חייבת להכיל לפחות 6 תווים.")
            elif new_pwd != new_pwd2:
                st.error("הסיסמאות אינן תואמות.")
            elif _db().update_agent_password(agent["id"], new_pwd):
                st.success("הסיסמה עודכנה.")
            else:
                st.error("לא הצלחנו לעדכן. נסו שוב.")

    _whatsapp_debug()


def _whatsapp_debug():
    with st.expander("בדיקת חיבור וואטסאפ", expanded=False):
        instance = _get_secret("GREEN_API_INSTANCE") or os.getenv("GREEN_API_INSTANCE", "")
        token = _get_secret("GREEN_API_TOKEN") or os.getenv("GREEN_API_TOKEN", "")
        st.caption(f"Instance: {(instance[:4] + '****') if instance else 'לא מוגדר'} · Token: {'מוגדר' if token else 'לא מוגדר'}")
        test_phone = st.text_input("טלפון לבדיקה", placeholder="0501234567", key="debug_wa_phone")
        if st.button("שליחת הודעת בדיקה", key="debug_wa_btn"):
            if not test_phone.strip():
                st.error("הזינו מספר טלפון.")
            elif _db()._whatsapp(test_phone, "BituachBot — הודעת בדיקה"):
                st.success("ההודעה נשלחה.")
            else:
                st.error(f"השליחה נכשלה. {_db().last_whatsapp_error}")


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
        st.markdown(ui.h2("עוד צעד אחד"), unsafe_allow_html=True)
        st.warning("כדי להמשיך, הוסף את מספר הטלפון שלך — אליו נשלח התראות וואטסאפ על לקוחות חדשים.")
        if _agent_phone_form(agent, "gate", "שמור והמשך"):
            st.rerun()
        return

    # License is required: BituachBot answers clients on behalf of a licensed agent.
    if not _db().has_license_column():
        st.caption("למנהל המערכת: הרץ את supabase/agent_license.sql ב-Supabase כדי לשמור מספרי רישיון.")
    elif not agent.get("license_number"):
        st.markdown(ui.h2("עוד צעד אחד"), unsafe_allow_html=True)
        st.warning("BituachBot מיועד לסוכני ביטוח מורשים. כדי להמשיך, הזן את מספר רישיון סוכן הביטוח שלך — "
                   "הוא יוצג ללקוחות שלך, כי הבוט עונה להם בשמך.")
        if _agent_license_form(agent, "gate", "שמור והמשך"):
            st.rerun()
        return

    _render_admin_content(agent)


# The in-app bot gets the annex texts in its prompt. Coverage details are often deep in the
# document (physiotherapy was on page 6 of 10), so send whole annexes, within a total budget.
CHAT_TEXT_PER_ANNEX = 40000
CHAT_TEXT_BUDGET = 160000

AUTO_YEAR = "זיהוי אוטומטי"


def _annex_upload_form(key: str, code: str = ""):
    """Upload נספח PDFs to the shared library. If `code` is given it is fixed.
    One document can cover several codes (e.g. plan 5986 + chapter 6650): extra codes can be typed,
    and the codes in the document's own header are detected and saved too."""
    if code:
        pdfs = st.file_uploader(f"קובץ ה-PDF של נספח {code}", type=["pdf"], key=f"{key}_pdf")
        pdfs = [pdfs] if pdfs else []
    else:
        pdfs = st.file_uploader("קובצי PDF של נספחים — אפשר כמה ביחד", type=["pdf"],
                                accept_multiple_files=True, key=f"{key}_pdf") or []
    b1, b2 = st.columns([2, 1], vertical_alignment="bottom")
    with b2:
        with st.popover("פרטים ידניים", use_container_width=True, icon=":material/tune:"):
            st.caption("רשות. בלי פרטים — הקוד, השם והשנה מזוהים מהקובץ." +
                       (" בהעלאת כמה קבצים הזיהוי תמיד אוטומטי." if not code else ""))
            if code:
                extra_in = st.text_input("קודים נוספים לאותו מסמך", placeholder="5986", key=f"{key}_extra")
                codes_text = f"{code} {extra_in}"
            else:
                codes_text = st.text_input("קוד או קודים", placeholder="6650, 5986", key=f"{key}_code")
            name_in = st.text_input("שם הנספח", placeholder="אבחון מהיר", key=f"{key}_name")
            current_year = datetime.now().year
            year_choice = st.selectbox("שנת הנוסח", [AUTO_YEAR] + list(range(current_year, 1999, -1)), key=f"{key}_year")
    typed = list(dict.fromkeys(re.findall(r"\d{4,6}", codes_text or "")))
    with b1:
        save = st.button("שמירה במאגר", type="primary", key=f"{key}_save", use_container_width=True,
                         icon=":material/library_add:")
    if typed:
        versions = _db().get_annex_versions(typed[0])
        if versions:
            st.caption(f"גרסאות שכבר במאגר ל-{typed[0]}: {' · '.join(str(y) for y in versions)}")
    if save:
        if not pdfs:
            st.error("בחרו קובץ PDF של הנספח.")
            return
        many = len(pdfs) > 1
        bar = st.progress(0.0, text=f"מעבד 0/{len(pdfs)}...") if many else None
        for i, f in enumerate(pdfs[:MAX_FILES], 1):
            if many:
                _save_annex_pdf(f.getvalue(), [], "", AUTO_YEAR, label=f"{f.name} — ")
                bar.progress(i / len(pdfs), text=f"מעבד {i}/{len(pdfs)}...")
            else:
                _save_annex_pdf(f.getvalue(), typed, name_in, year_choice)
        st.rerun()


def _save_annex_pdf(pdf_bytes: bytes, typed: list[str], name: str, year_choice, label: str = "") -> bool:
    """Library upload by the agent. Saves under the typed codes + the codes in the document's own header.
    All feedback goes through _flash (the caller reruns)."""
    info = _process_pdf(pdf_bytes)
    text = info.get("text", "")
    if not text.strip():
        _flash("error", f"{label}{info.get('error') or 'לא ניתן לקרוא טקסט מהקובץ.'}")
        return False
    detected = info["codes"] if info["doc_type"] == "annex" else []
    codes = list(typed)
    if detected and (not typed or set(detected) & set(typed)):
        codes += detected
    elif detected:
        _flash("warning", f"{label}בכותרת הקובץ מופיעים קודים אחרים ({' · '.join(detected)}) — "
                          f"נשמר רק תחת {' · '.join(typed)}. ודא שזה הנספח הנכון.")
    for c in typed:
        codes += _extract_related_codes(text, c)
    codes = list(dict.fromkeys(codes))
    if not codes:
        _flash("error", f"{label}לא הצלחנו לזהות את קוד הנספח — העלה את הקובץ לבד והזן את הקוד ידנית." +
               (f" ({info['error']})" if info.get("error") else ""))
        return False
    if info["doc_type"] == "policy":
        _flash("warning", f"{label}הקובץ נראה כמו מפרט פוליסה של לקוח ולא כמו חוברת תנאים של נספח — בדוק שהעלית את הקובץ הנכון.")
    year = year_choice if year_choice != AUTO_YEAR else (info.get("year") or datetime.now().year)
    saved, _ = _db().add_annex_document(
        codes, (name or "").strip() or info.get("name", ""), text, year, info.get("company", ""), overwrite=True
    )
    if not saved:
        _flash("error", f"{label}שגיאה בשמירת הנספח במאגר.")
        return False
    _flash("success", f"{label}נספח {' · '.join(saved)} ({year}) נשמר במאגר — כל הלקוחות עם הקודים האלה עודכנו.")
    return True


def _render_client_card(client: dict, agent_id: str):
    """One client: status, annexes, missing annexes, upload, documents, conversations, bot chat."""
    client = _db().get_profile_by_id(client.get("id", "")) or client
    policies = _db().get_user_policies(client["id"])
    ready = [p for p in policies if p.get("has_data")]
    missing = [p for p in policies if not p.get("has_data")]
    docs = _db().list_client_documents(client["id"])
    kind, label = STATUS_LABELS[InsuranceClientDB.client_status(ready, missing, len(docs))]

    if st.button("חזרה לרשימת הלקוחות", key="close_client", type="tertiary", icon=":material/arrow_forward:"):
        st.session_state.admin_client = None
        st.rerun()
    st.markdown(
        f'<div class="bb-titlerow"><div class="bb-h1 bb-serif">{client.get("full_name", "")}</div>'
        f'{ui.pill(kind, label)}</div>'
        f'<div class="bb-kv" style="margin:6px 0 4px">'
        f'<span>טלפון <b>{ui.ltr(client.get("phone_number", ""))}</b></span>'
        f'<span>ת"ז <b>{ui.ltr(client.get("teudat_zehut") or "—")}</b></span>'
        f'<span>נרשם <b>{ui.ltr((client.get("created_at") or "")[:10])}</b></span>'
        f'<span><b>{len(docs)}</b> מסמכים</span></div>', unsafe_allow_html=True)

    note = f"{len(ready)} במאגר" + (f" · {len(missing)} חסרים" if missing else "")
    st.markdown(ui.h2(f"נספחים ({len(policies)})", note if policies else ""), unsafe_allow_html=True)
    if not policies:
        st.info("עדיין אין נספחים ללקוח. העלו את הפוליסה שלו כאן למטה.")
    else:
        st.markdown(ui.ledger(
            [{"code": p["annex_code"], "name": p.get("annex_name") or "", "meta": p.get("company") or "",
              "ready": True, "pill": "במאגר"} for p in ready]
            + [{"code": p["annex_code"], "name": f"נספח {p['annex_code']}",
                "meta": "חסר במאגר — הבוט עדיין לא יכול לענות עליו", "ready": False, "pill": "חסר"} for p in missing]),
            unsafe_allow_html=True)
    for p in missing:
        with st.expander(f"העלאת נספח {p['annex_code']}", expanded=False):
            _annex_upload_form(f"card_{client['id'][:8]}_{p['annex_code']}", p["annex_code"])

    st.markdown(ui.h2("העלאת מסמכים לתיק הלקוח"), unsafe_allow_html=True)
    pdf_files = st.file_uploader("פוליסה ונספחים — אפשר כמה קבצים ביחד. מסמך של נספח נכנס גם למאגר.", type=["pdf"],
                                 accept_multiple_files=True, key=f"admin_pdf_{client['id'][:8]}")
    if pdf_files and st.button("שמירה בתיק וזיהוי נספחים", type="primary", key="admin_pdf_save",
                               icon=":material/upload:"):
        msgs, tot = _ingest_files(client["id"], pdf_files, "agent")
        if tot["codes"]:
            after = _db().get_user_policies(client["id"])
            now_missing = [p["annex_code"] for p in after if not p.get("has_data") and p["annex_code"] in tot["codes"]]
            if now_missing:
                msgs.append(("warning", f"חסרים במאגר: {' · '.join(now_missing)} — העלו אותם כדי שהבוט יוכל לענות."))
            if tot["linked"]:
                ready_count = len([p for p in after if p.get("has_data")])
                if ready_count:
                    _db().send_ready(client["phone_number"], client["full_name"], ready_count)
        if not tot["saved_all"]:
            msgs.append(("warning", "חלק מהקבצים לא נשמרו באחסון (בדקו את הגדרות Supabase Storage)."))
        if tot["count"] > 1:
            msgs.insert(0, ("success", f"{tot['count']} מסמכים נשמרו בתיק הלקוח."))
        for m in msgs:
            _flash(*m)
        st.rerun()

    with st.expander(f"מסמכים ({len(docs)})", expanded=False):
        st.caption("ניתוח מחדש מזהה שוב את הנספחים במסמך. מסמך של נספח נכנס למאגר.")
        _render_documents(client["id"], "agent_docs", reanalyze_by="agent")

    log = _db().get_bot_messages(client["id"])
    if log is not None:
        with st.expander(f"שיחות הלקוח עם הבוט בוואטסאפ ({len(log)})", expanded=False):
            if not log:
                st.caption("עדיין אין שיחות שמורות.")
            for m in log:
                who = "הלקוח" if m.get("role") == "user" else "הבוט"
                when = (m.get("created_at") or "")[:16].replace("T", " ")
                st.markdown(f"**{who}** <span style='color:#8B94A7;font-size:.78rem'>{ui.ltr(when)}</span>",
                            unsafe_allow_html=True)
                st.text(m.get("content") or "")

    with st.container():  # inside a container the chat input stays in the page flow instead of pinning to the bottom
        _render_client_chat(client)


def _render_client_chat(client: dict):
    st.markdown(ui.h2("שאלה לבוט על הלקוח"), unsafe_allow_html=True)

    client_id = client.get("id", "")
    if st.session_state.get("agent_bot_client_id") != client_id:
        st.session_state.agent_bot_client_id = client_id
        st.session_state.agent_bot_messages = []

    policies = _db().get_user_policies(client_id)
    ready_policies = [p for p in policies if p.get("has_data") and p.get("full_text")]

    if not ready_policies:
        st.info("לבוט עדיין אין נספחים של הלקוח הזה. העלו קודם את הפוליסה או את הנספחים החסרים.")
    else:
        st.caption(
            f"הבוט עונה לפי {len(ready_policies)} נספחים: "
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
                TYPO_RULE,
                "אתה כלי עזר לסוכן ביטוח מורשה: הצג עובדות מהנספחים בלבד. אם נשאלת אם כדאי ללקוח לקנות, לבטל או להחליף "
                "ביטוח — פרט את מה שכתוב בנספחים הרלוונטיים, וציין שההחלטה המקצועית היא של הסוכן.",
                "בסוף כל תשובה שעוסקת בכיסוי, סכומים, השתתפות עצמית, תנאים או זכאות, הוסף בשורה נפרדת בדיוק:",
                AI_NOTE_AGENT,
            ]

            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.agent_bot_messages
            ]
            with st.chat_message("assistant"):
                failed = False
                with st.spinner("קורא את הנספחים..."):
                    try:
                        resp = _claude_create(
                            max_tokens=1024,
                            system="\n".join(system_lines),
                            messages=history,
                        )
                        answer = resp.content[0].text
                    except Exception as e:
                        print(f"[landing] agent bot chat: {e}")
                        answer, failed = _anthropic_error_he(e), True
                (st.error if failed else st.markdown)(answer)
            if not failed:
                st.session_state.agent_bot_messages.append({"role": "assistant", "content": answer})
            else:
                st.session_state.agent_bot_messages.pop()

        if st.session_state.agent_bot_messages:
            if st.button("ניקוי השיחה", key="clear_bot_chat", type="tertiary"):
                st.session_state.agent_bot_messages = []
                st.rerun()


def _render_new_client_form(agent: dict):
    with st.expander("לקוח חדש", expanded=False):
        st.caption("ללקוח שמעדיף שתרשמו אותו בעצמכם. הוא יקבל הודעת וואטסאפ עם מספר הבוט.")
        with st.form("new_client_form", clear_on_submit=False):
            name = st.text_input("שם מלא")
            phone = st.text_input("טלפון נייד", placeholder="050-1234567")
            tz = st.text_input("תעודת זהות (רשות)", max_chars=9)
            pdfs = st.file_uploader("פוליסה ונספחים PDF (רשות, אפשר כמה ביחד)", type=["pdf"], accept_multiple_files=True)
            send_welcome = st.checkbox("שלח ללקוח הודעת וואטסאפ עם מספר הבוט", value=True)
            submitted = st.form_submit_button("צור לקוח", type="primary", icon=":material/person_add:")
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
        ok, user_id = _db().register_user_with_policies(clean, name.strip(), [], tz.strip(), agent["id"])
        if not ok:
            st.error(user_id)
            return
        _flash("success", f"{name.strip()} נרשם.")
        if pdfs:
            msgs, _ = _ingest_files(user_id, pdfs, "agent")
            for m in msgs:
                _flash(*m)
        if send_welcome:
            _db().send_welcome_from_agent(clean, name.strip(), agent.get("full_name", ""), BASE_URL,
                                          agent.get("license_number") or "")
        st.session_state.admin_client = _db().get_profile_by_id(user_id)
        st.rerun()


def _open_client_from_jump():
    """on_change of the client dropdown: open the picked client and reset the dropdown."""
    cid = st.session_state.get("client_jump")
    if cid:
        st.session_state.admin_client = {"id": cid}
        st.session_state.client_jump = None


def _tab_clients(agent: dict, clients: list[dict]):
    agent_id = agent.get("id", "")
    if agent.get("agent_code"):
        st.caption("הקישור האישי שלך להרשמת לקוחות. שולחים אותו ללקוח, והוא נרשם אצלך:")
        st.code(f"{BASE_URL}/?agent={agent['agent_code']}", language=None)
    if agent_id:
        _render_new_client_form(agent)
    if not clients:
        st.info("עדיין אין לקוחות. שלחו ללקוחות את הקישור האישי שלמעלה, או רשמו לקוח ב\"לקוח חדש\".")
    else:
        kinds = {k: v[0] for k, v in STATUS_LABELS.items()}
        counts = {kinds[k]: sum(1 for c in clients if c["status"] == k) for k in STATUS_LABELS}
        st.markdown(ui.status_bar(counts, {v[0]: v[1] for v in STATUS_LABELS.values()}), unsafe_allow_html=True)

        f1, f2 = st.columns([3, 2])
        with f1:
            by_id = {c["id"]: c for c in clients}
            st.selectbox("מעבר ללקוח", list(by_id), index=None, key="client_jump", on_change=_open_client_from_jump,
                         placeholder="חיפוש לפי שם או טלפון",
                         format_func=lambda i: f"{by_id[i].get('full_name', '')} · {by_id[i].get('phone_number', '')}")
        with f2:
            status_filter = st.selectbox("סטטוס", ["all"] + list(STATUS_LABELS), key="clients_filter",
                                         format_func=lambda k: "כל הסטטוסים" if k == "all" else STATUS_LABELS[k][1])
        shown = clients if status_filter == "all" else [c for c in clients if c["status"] == status_filter]
        if not shown:
            st.caption("אין לקוחות בסטטוס הזה.")
        for c in shown:
            kind, label = STATUS_LABELS[c["status"]]
            details = []
            if c["ready_codes"]:
                details.append(f"במאגר: {', '.join(c['ready_codes'])}")
            if c["pending_codes"]:
                details.append(f"חסרים: {', '.join(c['pending_codes'])}")
            details.append(f"{c['doc_count']} מסמכים")
            details.append(f"נרשם {(c.get('created_at') or '')[:10]}")
            with st.container(key=f"row_{c['id']}"):
                col_a, col_b = st.columns([6, 1], vertical_alignment="center")
                with col_a:
                    st.markdown(
                        f'<div class="bb-top"><span class="bb-name">{c.get("full_name", "")}</span>'
                        f'{ui.pill(kind, label)}<span class="bb-meta">{ui.ltr(c.get("phone_number", ""))}</span></div>'
                        f'<div class="bb-meta">{" · ".join(details)}</div>', unsafe_allow_html=True)
                with col_b:
                    if st.button("פתיחה", key=f"open_{c['id']}", use_container_width=True):
                        st.session_state.admin_client = c
                        st.rerun()

    # ── FIND / CLAIM BY PHONE ─────────────────────────────────────────────────
    with st.expander("שיוך לקוח קיים לפי טלפון", expanded=bool(st.session_state.get("_found_client"))):
        st.caption("לקוח שכבר רשום בלי סוכן — מחפשים לפי טלפון ומשייכים אותו אליכם.")
        s1, s2 = st.columns([3, 1], vertical_alignment="bottom")
        with s1:
            phone_input = st.text_input("טלפון", placeholder="0501234567", key="find_phone")
        with s2:
            do_find = st.button("חיפוש", key="find_btn", use_container_width=True)
        if do_find:
            clean = _clean_phone(phone_input)
            if not re.match(r"^05\d{8}$", clean):
                st.error("מספר טלפון לא תקין.")
                st.session_state.pop("_found_client", None)
            else:
                found = _db().get_profile_by_phone(clean)
                if not found:
                    st.error(f"לא נמצא לקוח עם המספר {clean}. אפשר לרשום אותו ב\"לקוח חדש\".")
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
                st.info(f"{found.get('full_name', '')} ({found.get('phone_number', '')}) רשום בלי סוכן.")
                if st.button("שייך אליי", key="claim_client", type="primary"):
                    if _db().assign_agent(found["id"], agent_id):
                        st.session_state.admin_client = found
                        st.session_state.pop("_found_client", None)
                        _flash("success", "הלקוח שויך אליך.")
                        st.rerun()
            else:
                st.error("הלקוח משויך לסוכן אחר.")


def _tab_missing(pending_codes: list[dict]):
    st.caption("קודים שיש ללקוחות שלך ועדיין לא הועלו למאגר. עד שמעלים אותם, הבוט לא יכול לענות עליהם.")
    if not pending_codes:
        st.success("אין נספחים חסרים — כל הנספחים של הלקוחות שלך במאגר.")
    for item in pending_codes:
        names = item["clients"]
        with st.expander(f"נספח {item['annex_code']} — {len(names)} לקוחות: "
                         f"{', '.join(names[:4])}{' ...' if len(names) > 4 else ''}", expanded=False):
            _annex_upload_form(f"pending_{item['annex_code']}", item["annex_code"])


def _tab_library(lib: list[dict]):
    """Shared נספחים library: upload annexes without any client + see what is already in it."""
    st.caption("נספח שנכנס למאגר מופיע אוטומטית כמוכן אצל כל לקוח שיש לו את הקוד — גם אצל לקוחות שיירשמו בעתיד.")
    with st.expander("העלאת נספחים למאגר (בלי לקוח)", expanded=not lib):
        _annex_upload_form("nispaj")
    if lib:
        q = st.text_input("חיפוש במאגר", key="lib_search", placeholder="קוד, שם נספח או חברה — למשל 2210 / פיזיותרפיה / מגדל")
        shown = [r for r in lib if not q.strip() or q.strip() in f"{r['annex_code']} {r['annex_name']} {r['company']}"]
        if not shown:
            st.caption("לא נמצא נספח מתאים במאגר.")
        else:
            st.markdown(ui.ledger([
                {"code": r["annex_code"], "name": r["annex_name"], "ready": True, "pill": "במאגר",
                 "meta": " · ".join(str(x) for x in (r["company"], r["version_year"]) if x)} for r in shown[:60]]),
                unsafe_allow_html=True)
        if len(shown) > 60:
            st.caption(f"ועוד {len(shown) - 60} — חפשו כדי לצמצם.")


def _render_admin_content(agent: dict):
    """Agent workspace. agent['id'] empty = main admin (sees all clients)."""
    agent_id = agent.get("id", "")

    # An open client replaces the lists (master → detail).
    if st.session_state.admin_client:
        _render_client_card(st.session_state.admin_client, agent_id)
        return

    clients = _db().get_agent_clients(agent_id)
    pending_codes = _db().get_pending_annex_codes(agent_id)
    lib = _db().list_library()
    tabs = {"clients": f"לקוחות ({len(clients)})", "missing": f"נספחים חסרים ({len(pending_codes)})",
            "library": f"מאגר הנספחים ({len(lib)})"}
    if agent_id:
        tabs["settings"] = "הגדרות"
    if st.session_state.get("agent_tab") not in tabs:
        st.session_state["agent_tab"] = "clients"
    tab = st.segmented_control("תצוגה", list(tabs), format_func=lambda k: tabs[k], key="agent_tab",
                               label_visibility="collapsed") or "clients"
    if tab == "clients":
        _tab_clients(agent, clients)
    elif tab == "missing":
        _tab_missing(pending_codes)
    elif tab == "library":
        _tab_library(lib)
    else:
        _agent_settings(agent)


# ── PRIVACY POLICY PAGE ────────────────────────────────────────────────────────

def page_privacy():
    st.markdown("""
<style>
[data-testid="stMainBlockContainer"] { max-width: 760px !important; }
.stApp .privacy-container.privacy-container.privacy-container h1, .stApp .privacy-container.privacy-container.privacy-container h1 * { font-family: var(--serif) !important; }
.stApp .privacy-container h1 { font-size: 1.9rem; font-weight: 900; color: var(--ink); margin-bottom: 6px; }
.stApp .privacy-container.privacy-container.privacy-container h2, .stApp .privacy-container.privacy-container.privacy-container h2 * { font-family: var(--serif) !important; }
.stApp .privacy-container h2 { font-size: 1.15rem; font-weight: 700; color: var(--ink);
  margin-top: 30px; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid var(--line); }
.privacy-container p, .privacy-container li { font-size: .95rem; color: #2E3A52; line-height: 1.8; }
.privacy-container ul { padding-right: 20px; }
.privacy-date { font-size: .82rem; color: var(--ink-3); margin-bottom: 24px; }
</style>
<div class="privacy-container">
<h1>מדיניות פרטיות — BituachBot</h1>
<div class="privacy-date">עדכון אחרון: אוקטובר 2026</div>

<h2>1. מי אנחנו</h2>
<p>BituachBot הוא כלי עבודה דיגיטלי לסוכני ביטוח מורשים. השירות ניתן לך מטעם סוכן הביטוח שלך — בעל רישיון מרשות שוק ההון, ביטוח וחיסכון — שהוא האחראי על הקשר איתך. שם הסוכן ומספר הרישיון שלו מופיעים באזור האישי שלך.</p>
<p>BituachBot מסביר את נוסח הפוליסה שלך. הוא <strong>אינו</strong> ממליץ על רכישה, ביטול או החלפה של ביטוח — את זה עושה הסוכן שלך — <strong>ואינו</strong> נותן ייעוץ רפואי.</p>

<h2>2. אילו מידע אנו אוספים</h2>
<ul>
  <li><strong>שם מלא</strong> — לצורך זיהוי וקשר אישי</li>
  <li><strong>מספר טלפון נייד</strong> — לצורך אימות זהות ושליחת עדכונים</li>
  <li><strong>תעודת זהות</strong> — לצורך אימות זהות ומניעת כפילויות</li>
  <li><strong>מסמכי פוליסת ביטוח (PDF)</strong> — לצורך ניתוח הכיסויים ומתן מענה אישי</li>
  <li><strong>שיחות עם הבוט</strong> — נשמרות כדי לתעד את התשובות שניתנו ולאפשר לסוכן שלך לעקוב ולעזור</li>
</ul>
<p><strong>מידע רפואי:</strong> הפוליסה ושאלותיך עשויות לכלול מידע רפואי, שהוא "מידע בעל רגישות מיוחדת" לפי חוק הגנת הפרטיות. אנו מעבדים אותו רק לצורך מתן השירות ובהסכמתך, ולא משתמשים בו לשום מטרה אחרת.</p>

<h2>בינה מלאכותית</h2>
<p>התשובות בוואטסאפ ובאזור האישי נוצרות אוטומטית ע״י בינה מלאכותית, על סמך הנספחים שבפוליסה שלך כפי שהיא במערכת. הן עלולות לכלול טעויות ואינן מהוות אישור כיסוי. לפני כל פעולה — ובכל עת שתרצה לדבר עם אדם — פנה ישירות לסוכן שלך.</p>

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
  <li><strong>n8n</strong> — הפעלת הבוט בוואטסאפ</li>
  <li><strong>הסוכן שלך</strong> — רואה את פרטיך, את הנספחים, את המסמכים ואת השיחות שלך עם הבוט לצורך מתן השירות</li>
</ul>
<p>חלק מספקי השירות מאחסנים ומעבדים את המידע בשרתים מחוץ לישראל. ההעברה נעשית רק לצורך מתן השירות ובכפוף להסכמתך.</p>
<p>אנו לא מוכרים, לא משכירים ולא מעבירים את המידע שלך לצדדים שלישיים למטרות שיווק.</p>

<h2>5. אבטחת מידע</h2>
<p>המידע שלך מאוחסן בצורה מוצפנת בשרתי Supabase. הגישה מוגבלת לצוות המורשה בלבד. אנו מיישמים אמצעי אבטחה סבירים בהתאם לתקנות הגנת הפרטיות (אבטחת מידע), תשע"ז-2017.</p>

<h2>6. שמירת מידע</h2>
<p>המידע שלך נשמר כל עוד חשבונך פעיל. אפשר למחוק את החשבון וכל המידע הקשור אליו (פרטים, נספחים, מסמכים ושיחות) בכל עת — ישירות באזור האישי, או דרך הסוכן שלך.</p>

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

    if st.button("חזרה", type="tertiary", icon=":material/arrow_forward:"):
        st.query_params.clear()
        st.rerun()


# ── ADMIN PAGE ─────────────────────────────────────────────────────────────────

def _render_agents_registry():
    """Main admin only: every agent with license number, to verify against the CMA registry."""
    agents = _db().get_all_agents()
    with st.expander(f"סוכנים רשומים ({len(agents)}) — בדיקת רישיונות", expanded=False):
        st.caption("BituachBot מיועד לסוכנים מורשים בלבד. בדקו כל מספר רישיון במאגר בעלי הרישיון של רשות שוק ההון.")
        st.markdown(ui.ledger([
            {"code": a.get("license_number") or "—", "name": a.get("full_name", ""), "ready": bool(a.get("license_number")),
             "pill": "רישיון הוזן" if a.get("license_number") else "חסר רישיון",
             "meta": " · ".join(x for x in (a.get("phone_number"), a.get("email"), a.get("agent_code")) if x)}
            for a in agents]), unsafe_allow_html=True)


def _admin_logout():
    st.session_state.admin_authed = False
    st.session_state.admin_client = None
    st.query_params.clear()
    st.rerun()


def page_admin():
    """Legacy URL-based admin (?agent=CODE&admin=1). Kept for backward compat."""
    agent_for_admin = _agent
    if not st.session_state.admin_authed:
        correct_password = (_agent.get("admin_password", "") if agent_for_admin
                            else _get_secret("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", ""))
        left, right = _split()
        with left:
            _hero("agent")
        with right:
            _logo("כניסת מנהל", "פאנל הניהול של BituachBot")
            if not agent_for_admin and not correct_password:
                st.error("לא נמצא סוכן. השתמשו בקישור ?agent=CODE&admin=1")
                return
            pwd = st.text_input("סיסמה", type="password", placeholder="הסיסמה שלך")
            if st.button("כניסה", type="primary", use_container_width=True):
                ok = verify_password(pwd, correct_password) if agent_for_admin else (pwd == correct_password)
                if ok:
                    if agent_for_admin and not is_hashed(correct_password) and _agent.get("id"):
                        _db().update_agent_password(_agent["id"], pwd)
                    st.session_state.admin_authed = True
                    st.rerun()
                else:
                    st.error("סיסמה שגויה.")
        return

    _admin_agent = agent_for_admin or {"full_name": "מנהל ראשי", "id": "", "agent_code": ""}
    _admin_header(_admin_agent, on_logout=_admin_logout)
    if not agent_for_admin and not st.session_state.admin_client:
        _render_agents_registry()
    _render_admin_content(_admin_agent)


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
    elif _agent_code:
        # Direct ?agent=CODE link — skip choose screen (page_form explains an invalid code)
        page_form()
    else:
        page_choose()
