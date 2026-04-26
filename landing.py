"""
BituachBot – Landing Page & Signup
Run:  streamlit run landing.py
"""

import io
import json
import os
import random
import re
import time

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

st.set_page_config(
    page_title="BituachBot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── STYLES ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800;900&display=swap');

*, html, body, [class*="css"] {
  font-family: 'Heebo', sans-serif !important;
  box-sizing: border-box;
}

#MainMenu, header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {
  display: none !important;
}
.stApp > header { display: none !important; }
.main .block-container { padding: 0 !important; max-width: 100% !important; }

/* Split layout */
[data-testid="stHorizontalBlock"] {
  gap: 0 !important;
  align-items: stretch !important;
  min-height: 100vh;
}
[data-testid="stHorizontalBlock"] > div:first-child {
  background: #F0FDF4 !important;
  min-height: 100vh !important;
  padding: 64px 56px !important;
  direction: rtl;
  position: relative;
  overflow: hidden;
}
[data-testid="stHorizontalBlock"] > div:last-child {
  background: white !important;
  min-height: 100vh !important;
  padding: 64px 56px !important;
  direction: rtl;
  display: flex;
  align-items: center;
}

/* Hero side */
.badge {
  display: inline-flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,0.85);
  border: 1px solid rgba(22,179,100,0.15);
  color: #16B364; font-weight: 600; font-size: 0.85rem;
  padding: 6px 16px; border-radius: 999px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  margin-bottom: 28px; direction: rtl;
}
.hero-title {
  font-size: 3rem; font-weight: 900;
  color: #111827; line-height: 1.25;
  margin-bottom: 20px; direction: rtl;
}
.hero-title span { color: #16B364; }
.hero-sub {
  font-size: 1.1rem; color: #6B7280;
  margin-bottom: 36px; line-height: 1.65;
  max-width: 400px; direction: rtl;
}
.benefit-item {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 16px; direction: rtl;
}
.benefit-check {
  flex-shrink: 0; width: 28px; height: 28px; border-radius: 50%;
  background: rgba(22,179,100,0.12);
  display: flex; align-items: center; justify-content: center;
  color: #16B364; font-size: 0.85rem; font-weight: 700;
}
.benefit-text { font-size: 1rem; font-weight: 500; color: #1F2937; }
.privacy-note {
  margin-top: 44px; font-size: 0.82rem; color: #9CA3AF; direction: rtl;
}
.circle-deco-1 {
  position: absolute; width: 320px; height: 320px; border-radius: 50%;
  background: rgba(22,179,100,0.05);
  top: -80px; left: -80px; pointer-events: none;
}
.circle-deco-2 {
  position: absolute; width: 200px; height: 200px; border-radius: 50%;
  background: rgba(22,179,100,0.05);
  bottom: 40px; right: 40px; pointer-events: none;
}

/* Form side */
.form-logo {
  display: flex; align-items: center; gap: 8px; justify-content: center;
  margin-bottom: 8px;
}
.form-logo-text { font-size: 1.5rem; font-weight: 700; color: #16B364; }
.form-title {
  font-size: 1.5rem; font-weight: 700; color: #111827;
  text-align: center; margin-bottom: 32px; direction: rtl;
}
.success-wrap { text-align: center; padding: 40px 0; direction: rtl; }
.success-icon { font-size: 3.5rem; margin-bottom: 16px; }
.success-title { font-size: 1.4rem; font-weight: 700; color: #111827; margin-bottom: 8px; }
.success-sub { color: #6B7280; font-size: 1rem; }
.terms-note {
  text-align: center; margin-top: 20px;
  font-size: 0.78rem; color: #9CA3AF; direction: rtl;
}
.terms-note a { color: #16B364; text-decoration: underline; }

/* Input overrides */
.stTextInput > div > div > input {
  background: rgba(240,253,244,0.6) !important;
  border: 1.5px solid #E5E7EB !important;
  border-radius: 12px !important;
  height: 48px !important;
  padding: 0 16px !important;
  direction: rtl !important; text-align: right !important;
  font-size: 0.95rem !important; color: #111827 !important;
  transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stTextInput > div > div > input:focus {
  border-color: #16B364 !important;
  box-shadow: 0 0 0 3px rgba(22,179,100,0.15) !important;
  background: white !important;
}
.stTextInput > div > div > input::placeholder { color: #9CA3AF !important; }
label {
  font-size: 0.875rem !important; font-weight: 500 !important;
  color: #111827 !important; direction: rtl !important;
  margin-bottom: 4px !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
  background: rgba(240,253,244,0.4) !important;
  border: 2px dashed #D1D5DB !important;
  border-radius: 12px !important;
}
[data-testid="stFileUploader"]:hover {
  background: rgba(240,253,244,0.7) !important;
  border-color: #16B364 !important;
}

/* Primary button */
.stButton > button[kind="primary"] {
  background: #16B364 !important;
  border: none !important;
  border-radius: 999px !important;
  height: 52px !important;
  font-size: 1.05rem !important; font-weight: 700 !important;
  color: white !important; width: 100% !important;
  box-shadow: 0 4px 14px rgba(22,179,100,0.35) !important;
  transition: all 0.2s !important;
}
.stButton > button[kind="primary"]:hover {
  background: #12985A !important;
  box-shadow: 0 6px 18px rgba(22,179,100,0.45) !important;
  transform: translateY(-1px) !important;
}

/* Back button */
.stButton > button:not([kind="primary"]) {
  background: transparent !important; border: none !important;
  color: #16B364 !important; font-size: 0.9rem !important;
  padding: 0 !important; text-decoration: underline !important;
}

.stAlert { direction: rtl !important; text-align: right !important; border-radius: 12px !important; }
</style>
""", unsafe_allow_html=True)


# ── SESSION STATE ──────────────────────────────────────────────────────────────
DEFAULTS = {
    "step": "form",          # form | verify | login | dashboard | no_pdf
    "reg_name": "",
    "reg_phone": "",
    "reg_tz": "",
    "reg_annex_codes": [],
    "otp_code": "",
    "otp_expires": 0.0,
    "otp_context": "",       # new_pdf | new_no_pdf | login
    "user_profile": None,
    "user_annexes": [],
}
for k, v in DEFAULTS.items():
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


@st.cache_resource(show_spinner=False)
def _claude() -> Anthropic:
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        return ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _extract_annex_codes(text: str) -> list[str]:
    client = _claude()
    prompt = f"""זהו טקסט ממפרט ביטוח ישראלי. חלץ את כל קודי הנספחים (מספרים בני 4-6 ספרות).
החזר JSON בלבד: {{"annex_codes": ["8713","6792"]}}
טקסט:
{text[:4000]}"""
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
    total = 0
    for i, ch in enumerate(tz):
        d = int(ch) * (1 if i % 2 == 0 else 2)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


def _wa_send(phone: str, message: str) -> bool:
    instance = os.getenv("GREEN_API_INSTANCE")
    token = os.getenv("GREEN_API_TOKEN")
    if not instance or not token:
        return False
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0"):
        digits = "972" + digits[1:]
    url = f"https://api.green-api.com/waInstance{instance}/sendMessage/{token}"
    try:
        r = requests.post(url, json={"chatId": f"{digits}@c.us", "message": message}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def _send_otp(phone: str, name: str) -> str:
    code = str(random.randint(100000, 999999))
    st.session_state.otp_code = code
    st.session_state.otp_expires = time.time() + 600
    _wa_send(phone, f"שלום {name}! 👋\nקוד האימות שלך ל-BituachBot הוא:\n\n*{code}*\n\nתקף ל-10 דקות.")
    return code


def _send_ready(phone: str, name: str):
    _wa_send(phone,
        f"שלום {name}! 🛡️\n\nהכל מוכן! הפוליסה שלך נקלטה במערכת.\n\n"
        f"מה תרצה לדעת? 😊\n\n"
        f"לדוגמה:\n• יש לי כיסוי לכירופרקטיקה?\n• כמה ההשתתפות העצמית ב-MRI?\n• מה הכיסוי לפיזיותרפיה?"
    )


def _send_pending(phone: str, name: str):
    _wa_send(phone,
        f"שלום {name}! 👋\n\nנרשמת בהצלחה ל-BituachBot! 🛡️\n\n"
        f"שמנו לב שעדיין לא העלית את קובץ הפוליסה שלך.\n"
        f"בקרוב אחד מהצוות שלנו יצור איתך קשר כדי לעזור לך להעלות אותה למערכת.\n\n"
        f"נדבר בקרוב! 😊"
    )


# ── LEFT PANEL (hero) ──────────────────────────────────────────────────────────
def _hero():
    bullets_html = "".join(
        f'<div class="benefit-item">'
        f'<span class="benefit-check">✓</span>'
        f'<span class="benefit-text">{b}</span>'
        f'</div>'
        for b in BENEFITS
    )
    st.markdown(f"""
<div class="circle-deco-1"></div>
<div class="circle-deco-2"></div>
<div class="badge">💬 אסיסטנט ביטוח חכם בוואטסאפ</div>
<h1 class="hero-title">עם <span>BituachBot</span><br>תבין סוף סוף מה<br>הביטוח שלך מכסה</h1>
<p class="hero-sub">שלח הודעה בוואטסאפ וקבל תשובה מדויקת — לפי הביטוח האישי שלך.</p>
{bullets_html}
<p class="privacy-note">🔒 המידע שלך מאובטח ומוגן לפי תקנות הפרטיות</p>
""", unsafe_allow_html=True)


# ── PAGES ──────────────────────────────────────────────────────────────────────
def _logo():
    st.markdown('<div class="form-logo"><span style="font-size:2rem">🛡️</span><span class="form-logo-text">BituachBot</span></div>', unsafe_allow_html=True)


def page_form():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo()
        st.markdown('<div class="form-title">רשום פשוט ומהיר</div>', unsafe_allow_html=True)

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
                errors.append("מספר טלפון לא תקין.")
            if not _validate_teudat_zehut(clean_tz):
                errors.append("תעודת זהות לא תקינה.")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                db = _db()
                with st.spinner("רושם..."):
                    ok, msg = db.register_user_with_policies(clean_phone, full_name.strip(), annex_codes, clean_tz)
                if not ok:
                    st.error(msg)
                else:
                    st.session_state.reg_name = full_name.strip()
                    st.session_state.reg_phone = clean_phone
                    st.session_state.reg_tz = clean_tz
                    st.session_state.reg_annex_codes = annex_codes
                    st.session_state.otp_context = "new_pdf" if annex_codes else "new_no_pdf"
                    with st.spinner("שולח קוד אימות..."):
                        _send_otp(clean_phone, full_name.strip())
                    st.session_state.step = "verify"
                    st.rerun()

        st.markdown('<p class="terms-note">בהרשמה אני מסכימ/ה ל<a href="#">תנאי השימוש</a> ול<a href="#">מדיניות הפרטיות</a></p>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<p style="text-align:center;font-size:0.9rem;color:#6B7280;">כבר רשום?</p>', unsafe_allow_html=True)
        if st.button("כניסה עם טלפון", use_container_width=True):
            st.session_state.step = "login"
            st.rerun()


def page_login():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo()
        st.markdown('<div class="form-title">כניסה למערכת</div>', unsafe_allow_html=True)
        phone = st.text_input("טלפון נייד", placeholder="050-1234567")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("שלח קוד אימות לוואטסאפ", type="primary", use_container_width=True):
            clean_phone = phone.strip().replace("-", "").replace(" ", "")
            if not re.match(r"^05\d{8}$", clean_phone):
                st.error("מספר טלפון לא תקין.")
            else:
                db = _db()
                profile = db.get_profile_by_phone(clean_phone)
                if not profile:
                    st.error("מספר טלפון לא נמצא במערכת. אנא הירשם.")
                else:
                    st.session_state.reg_phone = clean_phone
                    st.session_state.reg_name = profile.get("full_name", "")
                    st.session_state.otp_context = "login"
                    with st.spinner("שולח קוד..."):
                        _send_otp(clean_phone, profile.get("full_name", ""))
                    st.session_state.step = "verify"
                    st.rerun()
        if st.button("← חזרה להרשמה"):
            st.session_state.step = "form"
            st.rerun()


def page_verify():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo()
        st.markdown('<div class="form-title">אימות מספר טלפון</div>', unsafe_allow_html=True)
        st.markdown(f'<p style="text-align:center;color:#6B7280;direction:rtl;">שלחנו קוד בן 6 ספרות לוואטסאפ שלך<br><strong>{st.session_state.reg_phone}</strong></p>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        code_input = st.text_input("קוד אימות", placeholder="123456", max_chars=6)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("אמת ➤", type="primary", use_container_width=True):
            if time.time() > st.session_state.otp_expires:
                st.error("הקוד פג תוקף. בקש קוד חדש.")
            elif code_input.strip() != st.session_state.otp_code:
                st.error("קוד שגוי. נסה שוב.")
            else:
                ctx = st.session_state.otp_context
                phone = st.session_state.reg_phone
                name = st.session_state.reg_name
                db = _db()
                if ctx == "new_pdf":
                    _send_ready(phone, name)
                    st.session_state.user_profile = db.get_profile_by_phone(phone)
                    st.session_state.user_annexes = db.get_user_annexes(phone)
                    st.session_state.step = "dashboard"
                elif ctx == "new_no_pdf":
                    _send_pending(phone, name)
                    st.session_state.step = "no_pdf"
                else:
                    st.session_state.user_profile = db.get_profile_by_phone(phone)
                    st.session_state.user_annexes = db.get_user_annexes(phone)
                    st.session_state.step = "dashboard"
                st.rerun()
        if st.button("שלח קוד חדש"):
            _send_otp(st.session_state.reg_phone, st.session_state.reg_name)
            st.success("נשלח קוד חדש!")


def page_no_pdf():
    left, right = st.columns([1, 1])
    with left:
        _hero()
    with right:
        _logo()
        st.markdown(f"""
<div class="success-wrap">
  <div class="success-icon">✅</div>
  <div class="success-title">נרשמת בהצלחה, {st.session_state.reg_name}!</div>
  <div class="success-sub" style="margin-top:12px;">
    שלחנו לך הודעה בוואטסאפ 📱<br><br>
    בקרוב אחד מהצוות שלנו יצור איתך קשר כדי לעזור לך להעלות את קובץ הפוליסה שלך למערכת.
  </div>
</div>
""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← חזרה לדף הבית"):
            st.session_state.step = "form"
            st.rerun()


def page_dashboard():
    profile = st.session_state.user_profile or {}
    annexes = st.session_state.user_annexes or []
    name = profile.get("full_name", "לקוח יקר")

    st.markdown(f"""
<div style="background:#F0FDF4;padding:32px 48px 24px;direction:rtl;border-bottom:1px solid #D1FAE5;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
    <span style="font-size:1.5rem">🛡️</span>
    <span style="font-size:1.2rem;font-weight:700;color:#16B364;">BituachBot</span>
  </div>
  <h2 style="font-size:1.8rem;font-weight:800;color:#111827;margin:0;">שלום, {name}! 👋</h2>
  <p style="color:#6B7280;margin:4px 0 0;">הנה סיכום הפוליסות שלך</p>
</div>
""", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📄 הנספחים שלך")
        if not annexes:
            st.info("לא נמצאו נספחים. העלה קובץ מפרט להוספת הכיסויים שלך.")
        for ann in annexes:
            code = ann.get("annex_code", "")
            ann_name = ann.get("annex_name") or "נספח"
            company = ann.get("company_name", "")
            has_text = bool(ann.get("full_text"))
            icon = "✅" if has_text else "⚠️"
            with st.expander(f"{icon} נספח {code} — {ann_name} | {company}"):
                if has_text:
                    st.caption(ann.get("full_text", "")[:300] + "...")
                else:
                    st.warning("הנספח טרם הועלה לספרייה.")

    with col2:
        st.markdown("### 👤 הפרטים שלך")
        st.markdown(f"""
<div style="background:white;border:1px solid #E5E7EB;border-radius:12px;padding:20px;direction:rtl;">
  <p style="margin:0 0 8px;"><strong>שם:</strong> {profile.get('full_name','')}</p>
  <p style="margin:0 0 8px;"><strong>טלפון:</strong> {profile.get('phone_number','')}</p>
  <p style="margin:0;"><strong>ת.ז.:</strong> {profile.get('teudat_zehut','—')}</p>
</div>
""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 💬 הבוט שלך")
        st.info("שלח הודעה לבוט בוואטסאפ בכל שאלה על הכיסוי שלך!")
        if st.button("🚪 התנתק", use_container_width=True):
            for k in DEFAULTS:
                st.session_state[k] = DEFAULTS[k]
            st.session_state.step = "form"
            st.rerun()


# ── ROUTER ─────────────────────────────────────────────────────────────────────
pages = {
    "form": page_form,
    "login": page_login,
    "verify": page_verify,
    "no_pdf": page_no_pdf,
    "dashboard": page_dashboard,
}
pages.get(st.session_state.step, page_form)()
