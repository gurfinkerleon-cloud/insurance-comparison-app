"""
BituachBot – Landing Page & Signup
Run:  streamlit run landing.py
"""

import io
import json
import os
import re

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

# ── GLOBAL STYLES ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;700;800&display=swap');

/* Reset & base */
*, html, body, [class*="css"] {
  font-family: 'Heebo', sans-serif !important;
  box-sizing: border-box;
}
html, body { margin: 0; padding: 0; }

/* Hide Streamlit chrome */
#MainMenu, header, footer { display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
.stApp > header { display: none !important; }

/* Remove default page padding */
.main .block-container {
  padding: 0 !important;
  max-width: 100% !important;
}

/* ── Split layout ── */
[data-testid="stHorizontalBlock"] {
  gap: 0 !important;
  align-items: stretch !important;
  min-height: 100vh;
}

/* Left panel – lavender */
[data-testid="stHorizontalBlock"] > div:first-child {
  background: #EEEEFF !important;
  min-height: 100vh !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 60px 48px !important;
  direction: rtl;
}

/* Right panel – white */
[data-testid="stHorizontalBlock"] > div:last-child {
  background: white !important;
  min-height: 100vh !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 60px 48px !important;
  direction: rtl;
}

/* Typography */
.panel-tagline {
  font-size: 2.4rem;
  font-weight: 800;
  color: #1a1a2e;
  line-height: 1.35;
  text-align: right;
  direction: rtl;
}
.panel-tagline span { color: #3b4cca; }
.panel-sub {
  font-size: 1.05rem;
  color: #555;
  margin-top: 16px;
  line-height: 1.6;
  text-align: right;
  direction: rtl;
}
.bullet-list {
  list-style: none;
  padding: 0;
  margin-top: 28px;
}
.bullet-list li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
  font-size: 0.95rem;
  color: #333;
  direction: rtl;
}
.bullet-list li::before {
  content: "✓";
  color: #3b4cca;
  font-weight: 700;
  flex-shrink: 0;
}

/* Form card */
.form-logo {
  font-size: 1.6rem;
  font-weight: 800;
  color: #3b4cca;
  text-align: center;
  margin-bottom: 28px;
  letter-spacing: -0.5px;
}
.form-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1a1a2e;
  text-align: center;
  margin-bottom: 6px;
  direction: rtl;
}
.form-sub {
  text-align: center;
  color: #888;
  font-size: 0.9rem;
  margin-bottom: 28px;
  direction: rtl;
}
.form-sub a { color: #3b4cca; text-decoration: none; }

/* Input styling */
.stTextInput > div > div > input {
  background: #F5F6FF !important;
  border: 1.5px solid #E0E3FF !important;
  border-radius: 10px !important;
  padding: 10px 14px !important;
  direction: rtl !important;
  text-align: right !important;
  font-size: 0.95rem !important;
  transition: border-color 0.2s;
}
.stTextInput > div > div > input:focus {
  border-color: #3b4cca !important;
  background: white !important;
}
label {
  font-size: 0.85rem !important;
  font-weight: 600 !important;
  color: #444 !important;
  direction: rtl !important;
}

/* Primary button */
.stButton > button[kind="primary"] {
  background: #3b4cca !important;
  border: none !important;
  border-radius: 50px !important;
  font-size: 1rem !important;
  font-weight: 700 !important;
  padding: 0.7rem 0 !important;
  width: 100% !important;
  color: white !important;
  cursor: pointer !important;
  transition: background 0.2s, transform 0.1s !important;
}
.stButton > button[kind="primary"]:hover {
  background: #2d3bb0 !important;
  transform: translateY(-1px) !important;
}

/* Secondary/back button */
.stButton > button:not([kind="primary"]) {
  background: transparent !important;
  border: none !important;
  color: #3b4cca !important;
  font-size: 0.9rem !important;
  padding: 0 !important;
  text-decoration: underline !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
  background: #F5F6FF !important;
  border: 1.5px dashed #C5CAFF !important;
  border-radius: 10px !important;
  direction: rtl !important;
}

/* Divider */
.custom-divider {
  border: none;
  border-top: 1px solid #EBEBEB;
  margin: 20px 0;
}

/* Success */
.success-wrap { text-align: center; direction: rtl; }
.success-icon { font-size: 3.5rem; margin-bottom: 16px; }
.success-title { font-size: 2rem; font-weight: 800; color: #1a1a2e; margin-bottom: 12px; }
.success-text { font-size: 1rem; color: #555; line-height: 1.7; }
.whatsapp-box {
  background: #F5F6FF;
  border: 1.5px solid #E0E3FF;
  border-radius: 14px;
  padding: 24px 20px;
  margin-top: 24px;
  text-align: right;
  direction: rtl;
}
.whatsapp-box h4 { color: #3b4cca; font-size: 1.05rem; font-weight: 700; margin-bottom: 8px; }
.whatsapp-box p { color: #444; font-size: 0.9rem; line-height: 1.6; margin: 0; }

/* Alerts */
.stAlert { direction: rtl !important; text-align: right !important; border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)


# ── SESSION STATE ──────────────────────────────────────────────────────────────
for k, v in {"step": "form", "reg_name": "", "reg_phone": ""}.items():
    if k not in st.session_state:
        st.session_state[k] = v


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
        model="claude-sonnet-4-6",
        max_tokens=256,
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


def _send_whatsapp_welcome(phone: str, name: str) -> bool:
    """Send a welcome WhatsApp message via Green API."""
    instance = os.getenv("GREEN_API_INSTANCE")
    token = os.getenv("GREEN_API_TOKEN")
    if not instance or not token:
        return False

    # Convert 05XXXXXXXX → 9725XXXXXXXX@c.us
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0"):
        digits = "972" + digits[1:]
    chat_id = f"{digits}@c.us"

    message = (
        f"שלום {name}! 👋\n\n"
        f"ברוכים הבאים ל-BituachBot 🛡️\n\n"
        f"אני כאן כדי לעזור לך להבין בדיוק מה הביטוח שלך מכסה.\n\n"
        f"פשוט שלח לי שאלה — לדוגמה:\n"
        f"• \"יש לי כיסוי לכירופרקטיקה?\"\n"
        f"• \"כמה ההשתתפות העצמית ב-MRI?\"\n"
        f"• \"מה הכיסוי לפיזיותרפיה?\"\n\n"
        f"מה תרצה לדעת? 😊"
    )

    url = f"https://api.green-api.com/waInstance{instance}/sendMessage/{token}"
    try:
        resp = requests.post(url, json={"chatId": chat_id, "message": message}, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


# ── LEFT PANEL ─────────────────────────────────────────────────────────────────
def _left_panel():
    st.markdown("""
<div>
  <div class="panel-tagline">
    עם <span>BituachBot</span><br>
    תבין סוף סוף<br>
    מה הביטוח שלך מכסה
  </div>
  <p class="panel-sub">שאל שאלות על הכיסוי שלך בוואטסאפ — ותקבל תשובה מדויקת לפי הנספחים שלך.</p>
  <ul class="bullet-list">
    <li>מבוסס על הפוליסה האישית שלך</li>
    <li>תשובות מיידיות בעברית, ערבית ורוסית</li>
    <li>כירופרקטיקה, MRI, פיזיותרפיה ועוד</li>
    <li>ללא המתנה לנציג, 24/7</li>
  </ul>
</div>
""", unsafe_allow_html=True)


# ── REGISTRATION FORM ──────────────────────────────────────────────────────────
def page_form():
    left, right = st.columns([1, 1])

    with left:
        _left_panel()

    with right:
        st.markdown('<div class="form-logo">🛡️ BituachBot</div>', unsafe_allow_html=True)
        st.markdown('<div class="form-title">הירשמו! זה מהיר וקל :)</div>', unsafe_allow_html=True)
        st.markdown('<div class="form-sub">כבר רשומים? <a href="#">להתחברות</a></div>', unsafe_allow_html=True)

        full_name = st.text_input("שם מלא", placeholder="ישראל ישראלי", key="f_name")
        phone = st.text_input("טלפון נייד", placeholder="0501234567", key="f_phone")
        teudat_zehut = st.text_input("תעודת זהות", placeholder="9 ספרות", max_chars=9, key="f_tz")

        st.markdown('<hr class="custom-divider">', unsafe_allow_html=True)
        st.markdown("<small style='color:#888;direction:rtl;'>**העלאת מפרט ביטוח** — רשות (ניתן לשלוח מאוחר יותר)</small>", unsafe_allow_html=True)

        uploaded = st.file_uploader("בחר קובץ PDF", type=["pdf"], key="f_pdf", label_visibility="collapsed")

        annex_codes: list[str] = []
        if uploaded and PDF_SUPPORT:
            with st.spinner("מנתח מפרט..."):
                pdf_text = _extract_pdf_text(uploaded.read())
            if pdf_text.strip():
                with st.spinner("מזהה נספחים..."):
                    annex_codes = _extract_annex_codes(pdf_text)
                if annex_codes:
                    st.success(f"זוהו {len(annex_codes)} נספחים: {' · '.join(annex_codes)}")
                else:
                    st.warning("לא זוהו קודי נספחים.")

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
                with st.spinner("רושם..."):
                    ok, msg = db.register_user_with_policies(
                        clean_phone, full_name.strip(), annex_codes, clean_tz
                    )
                if ok:
                    st.session_state.reg_name = full_name.strip()
                    st.session_state.reg_phone = clean_phone
                    _send_whatsapp_welcome(clean_phone, full_name.strip())
                    st.session_state.step = "success"
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown(
            "<p style='text-align:center;font-size:0.75rem;color:#aaa;margin-top:16px;direction:rtl;'>"
            "בלחיצה על הכפתור אתה מאשר את <a href='#' style='color:#3b4cca;'>תנאי השימוש</a> ו<a href='#' style='color:#3b4cca;'>מדיניות הפרטיות</a>"
            "</p>",
            unsafe_allow_html=True,
        )


# ── SUCCESS PAGE ───────────────────────────────────────────────────────────────
def page_success():
    left, right = st.columns([1, 1])

    with left:
        _left_panel()

    with right:
        st.markdown('<div class="form-logo">🛡️ BituachBot</div>', unsafe_allow_html=True)

        name = st.session_state.reg_name
        st.markdown(f"""
<div class="success-wrap">
  <div class="success-icon">🎉</div>
  <div class="success-title">ברוכים הבאים, {name}!</div>
  <div class="success-text">הרישום הושלם בהצלחה.<br>עכשיו אפשר להתחיל לשאול שאלות על הכיסוי שלך.</div>
  <div class="whatsapp-box">
    <h4>📱 השלב הבא — וואטסאפ</h4>
    <p>שמור את מספר הבוט ושלח הודעה:<br>
    <strong>"שלום, רוצה לדעת מה הכיסוי שלי"</strong><br><br>
    הבוט יזהה אותך לפי הטלפון שמסרת ויענה לפי הנספחים שלך.</p>
  </div>
</div>
""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← חזרה לדף הרישום"):
            st.session_state.step = "form"
            st.rerun()


# ── ROUTER ─────────────────────────────────────────────────────────────────────
if st.session_state.step == "success":
    page_success()
else:
    page_form()
