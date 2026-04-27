"""BituachBot – Landing Page & Signup"""

import io
import json
import os
import re
from datetime import datetime, timedelta

import requests
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

from modules.insurance_client import InsuranceClientDB

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
.form-title { font-size: 1.5rem; font-weight: 700; color: #111827; text-align: center; margin-bottom: 24px; }
.form-sub { font-size: 0.9rem; color: #6B7280; text-align: center; margin-bottom: 28px; }
.policy-card {
  background: #F0FDF4; border: 1px solid #D1FAE5; border-radius: 12px;
  padding: 14px 18px; margin-bottom: 10px; direction: rtl;
}
.policy-card .annex-code { font-size: 0.8rem; color: #16B364; font-weight: 700; }
.policy-card .annex-name { font-size: 1rem; font-weight: 600; color: #111827; }
.policy-card .company-name { font-size: 0.85rem; color: #6B7280; }
.profile-box {
  background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 12px;
  padding: 16px 20px; margin-bottom: 24px; direction: rtl;
}
.otp-hint { text-align: center; color: #6B7280; font-size: 0.9rem; margin-bottom: 20px; }
.stTextInput > div > div > input {
  background: rgba(240,253,244,0.6) !important; border: 1.5px solid #E5E7EB !important;
  border-radius: 12px !important; height: 48px !important; padding: 0 16px !important;
  direction: rtl !important; text-align: right !important;
  font-size: 0.95rem !important; color: #111827 !important;
}
.stTextInput > div > div > input:focus {
  border-color: #16B364 !important; box-shadow: 0 0 0 3px rgba(22,179,100,0.15) !important;
}
label { font-size: 0.875rem !important; font-weight: 500 !important; color: #111827 !important; direction: rtl !important; }
[data-testid="stFileUploader"] {
  background: rgba(240,253,244,0.4) !important; border: 2px dashed #D1D5DB !important; border-radius: 12px !important;
}
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
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ──────────────────────────────────────────────────────────────
defaults = {
    "step": "form",
    "reg_name": "", "reg_phone": "", "reg_user_id": "",
    "annex_count": 0,
    "_otp": "", "_otp_exp": None,
    "admin_authed": False,
    "admin_client": None,  # dict with profile data of selected client
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


def _get_secret(key: str) -> str:
    try:
        return st.secrets.get(key) or ""
    except Exception:
        return ""


@st.cache_resource(show_spinner=False)
def _claude() -> Anthropic:
    api_key = _get_secret("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        st.error("❌ ANTHROPIC_API_KEY לא מוגדר")
        st.stop()
    return Anthropic(api_key=api_key)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        return ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _extract_annex_codes(text: str) -> list[str]:
    client = _claude()
    prompt = (
        'זהו טקסט ממפרט ביטוח ישראלי. חלץ את כל קודי הנספחים (מספרים בני 4-6 ספרות).\n'
        'החזר JSON בלבד: {"annex_codes": ["8713","6792"]}\n'
        f'טקסט:\n{text[:4000]}'
    )
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = re.sub(r"```json|```", "", resp.content[0].text).strip()
    try:
        return json.loads(raw).get("annex_codes", [])
    except Exception:
        m = re.search(r"\[.*?\]", raw, re.DOTALL)
        return json.loads(m.group()) if m else []


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
    _db().send_otp(phone, code)
    return code


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

def page_form():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo("רשום פשוט ומהיר")

        full_name = st.text_input("שם מלא", placeholder="ישראל ישראלי")
        phone = st.text_input("טלפון נייד", placeholder="050-1234567")
        teudat_zehut = st.text_input("תעודת זהות", placeholder="123456789", max_chars=9)
        uploaded = st.file_uploader("העלאת קובץ PDF (רשות)", type=["pdf"])

        annex_codes: list[str] = []
        if uploaded and PDF_SUPPORT:
            with st.spinner("מנתח מפרט..."):
                pdf_text = _extract_pdf_text(uploaded.read())
            if pdf_text.strip():
                with st.spinner("מזהה נספחים..."):
                    annex_codes = _extract_annex_codes(pdf_text)
                if annex_codes:
                    st.success(f"זוהו {len(annex_codes)} נספחים: {' · '.join(annex_codes)}")

        st.markdown("<br>", unsafe_allow_html=True)

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
            if errors:
                for e in errors:
                    st.error(e)
            else:
                db = _db()
                ok, result = db.register_user_with_policies(
                    clean_phone, full_name.strip(), annex_codes, clean_tz
                )
                if ok:
                    st.session_state.reg_name = full_name.strip()
                    st.session_state.reg_phone = clean_phone
                    st.session_state.reg_user_id = result
                    st.session_state.annex_count = len(annex_codes)
                    _send_otp(clean_phone)
                    if annex_codes:
                        st.session_state.step = "verify_new"
                    else:
                        db.send_no_pdf_notice(clean_phone, full_name.strip())
                        st.session_state.step = "pending"
                    st.rerun()
                elif result == "already_registered":
                    st.warning("מספר הטלפון כבר רשום. השתמש באפשרות 'כבר נרשמת'.")
                else:
                    st.error(result)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("כבר נרשמת? כניסה"):
            st.session_state.step = "login"
            st.rerun()

        st.markdown(
            '<p style="text-align:center;font-size:0.78rem;color:#9CA3AF;margin-top:16px">'
            'בהרשמה אני מסכימ/ה ל<a href="#" style="color:#16B364">תנאי השימוש</a>'
            ' ול<a href="#" style="color:#16B364">מדיניות הפרטיות</a></p>',
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

        code = st.text_input("קוד אימות", placeholder="123456", max_chars=6)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("אמת וכנס", type="primary", use_container_width=True):
            if _otp_valid(code):
                if is_new:
                    _db().send_ready(
                        st.session_state.reg_phone,
                        st.session_state.reg_name,
                        st.session_state.annex_count,
                    )
                st.session_state.step = "dashboard"
                st.rerun()
            else:
                st.error("קוד שגוי או שפג תוקפו. נסה שנית.")

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("שלח קוד מחדש"):
                _send_otp(st.session_state.reg_phone)
                st.success("קוד חדש נשלח!")
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

        profile = _db().get_profile_by_phone(st.session_state.reg_phone)
        if profile:
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

        policies = _db().get_user_policies(st.session_state.reg_user_id)
        if policies:
            st.markdown(f"**הנספחים שלך ({len(policies)})**")
            for p in policies:
                annex = p.get("master_annexes") or {}
                company = (annex.get("insurance_companies") or {}).get("name", "")
                st.markdown(f"""
<div class="policy-card">
  <div class="annex-code">נספח {annex.get('annex_code','')}</div>
  <div class="annex-name">{annex.get('annex_name','')}</div>
  <div class="company-name">{company}</div>
</div>
""", unsafe_allow_html=True)
        else:
            st.info("לא נמצאו נספחים — הנציג שלנו ייצור איתך קשר בקרוב.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← יציאה"):
            for k, v in defaults.items():
                st.session_state[k] = v
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


# ── ADMIN PAGE ─────────────────────────────────────────────────────────────────

def page_admin():
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

    st.markdown('<div class="admin-header">🔐 BituachBot — ממשק ניהול</div>', unsafe_allow_html=True)

    admin_password = _get_secret("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", "")

    if not st.session_state.admin_authed:
        st.markdown("**סיסמת מנהל**")
        pwd = st.text_input("סיסמה", type="password", placeholder="הכנס סיסמה")
        if st.button("כניסה", type="primary"):
            if admin_password and pwd == admin_password:
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("סיסמה שגויה")
        return

    st.success("✅ מחובר כמנהל")

    st.markdown("---")
    st.markdown("### העלאת פוליסה עבור לקוח קיים")

    phone_input = st.text_input("חפש לקוח לפי טלפון", placeholder="0501234567")
    if st.button("חפש לקוח"):
        clean = phone_input.strip().replace("-", "").replace(" ", "")
        if not re.match(r"^05\d{8}$", clean):
            st.error("מספר טלפון לא תקין")
        else:
            profile = _db().get_profile_by_phone(clean)
            if not profile:
                st.error(f"לקוח עם מספר {clean} לא נמצא במערכת")
                st.session_state.admin_client = None
            else:
                st.session_state.admin_client = profile
                st.rerun()

    client = st.session_state.admin_client
    if client:
        st.markdown(f"""
<div class="client-card">
  <div style="font-weight:700;font-size:1rem;margin-bottom:8px">פרטי לקוח</div>
  <div style="color:#374151;font-size:0.92rem;line-height:1.9">
    👤 <strong>{client.get('full_name','')}</strong><br>
    📱 {client.get('phone_number','')}<br>
    🆔 {client.get('teudat_zehut','—')}<br>
    🔑 ID: <code style="font-size:0.78rem">{client.get('id','')}</code>
  </div>
</div>
""", unsafe_allow_html=True)

        existing = _db().get_user_policies(client["id"])
        if existing:
            st.markdown(f"**נספחים קיימים ({len(existing)})**")
            for p in existing:
                annex = p.get("master_annexes") or {}
                st.markdown(
                    f"- נספח **{annex.get('annex_code','')}** — {annex.get('annex_name','')}",
                )

        st.markdown("---")
        st.markdown("#### העלה PDF של הפוליסה")
        pdf_file = st.file_uploader("בחר קובץ PDF", type=["pdf"], key="admin_pdf")

        if pdf_file:
            with st.spinner("מנתח PDF..."):
                pdf_text = _extract_pdf_text(pdf_file.read())

            if not pdf_text.strip():
                st.error("לא ניתן לקרוא טקסט מהקובץ. ייתכן שהוא סרוק — נסה קובץ אחר.")
            else:
                with st.spinner("מזהה נספחים בעזרת AI..."):
                    annex_codes = _extract_annex_codes(pdf_text)

                if not annex_codes:
                    st.warning("לא זוהו קודי נספחים בקובץ.")
                else:
                    st.info(f"זוהו {len(annex_codes)} נספחים: **{' · '.join(annex_codes)}**")

                    if st.button("✅ קשר נספחים ללקוח", type="primary"):
                        linked, skipped = _db().link_annex_codes(client["id"], annex_codes)
                        if linked > 0:
                            st.success(f"✅ קושרו {linked} נספחים חדשים בהצלחה!")
                            _db().send_ready(
                                client["phone_number"],
                                client["full_name"],
                                linked,
                            )
                            st.info("📱 נשלחה הודעת WhatsApp ללקוח")
                        else:
                            st.warning("לא נוספו נספחים חדשים (ייתכן שכולם כבר קיימים או לא נמצאו ב-master_annexes)")
                        if skipped:
                            st.caption(f"נספחים שדולגו (לא נמצאו ב-master_annexes): {', '.join(skipped)}")
                        st.session_state.admin_client = None
                        st.rerun()

    st.markdown("---")
    if st.button("← יציאה מממשק הניהול"):
        st.session_state.admin_authed = False
        st.session_state.admin_client = None
        st.query_params.clear()
        st.rerun()


# ── ROUTER ─────────────────────────────────────────────────────────────────────
_params = st.query_params
if _params.get("admin") == "1":
    page_admin()
else:
    step = st.session_state.step
    if step == "verify_new":
        page_verify(is_new=True)
    elif step == "verify_login":
        page_verify(is_new=False)
    elif step == "pending":
        page_pending()
    elif step == "dashboard":
        page_dashboard()
    elif step == "login":
        page_login()
    else:
        page_form()
