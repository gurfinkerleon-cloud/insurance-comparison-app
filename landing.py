"""
BituachBot – Landing Page & Signup
Run:  streamlit run landing.py

Required env vars:
  SUPABASE_URL          - https://...supabase.co
  SUPABASE_SERVICE_KEY  - Service Role key
  ANTHROPIC_API_KEY     - Claude API key (for PDF extraction)
"""

import io
import json
import os
import re

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
    page_title="BituachBot – האסיסטנט לביטוח שלך",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── STYLES ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;700;800&display=swap');

  html, body, [class*="css"] {
    font-family: 'Heebo', sans-serif !important;
    direction: rtl !important;
  }
  .main .block-container {
    padding-top: 0 !important;
    max-width: 900px;
  }

  /* ── Hero ── */
  .hero {
    background: linear-gradient(135deg, #1a237e 0%, #0d47a1 60%, #1565c0 100%);
    color: white;
    padding: 70px 40px 60px;
    text-align: center;
    border-radius: 0 0 32px 32px;
    margin-bottom: 48px;
  }
  .hero h1 { font-size: 2.8rem; font-weight: 800; margin-bottom: 16px; }
  .hero p  { font-size: 1.2rem; font-weight: 300; opacity: 0.9; max-width: 600px; margin: 0 auto 28px; }
  .badge {
    display: inline-block; background: rgba(255,255,255,0.18);
    border: 1px solid rgba(255,255,255,0.35);
    border-radius: 20px; padding: 4px 16px; font-size: 0.85rem;
    margin-bottom: 18px;
  }

  /* ── Feature cards ── */
  .features { display: flex; gap: 20px; margin-bottom: 48px; flex-wrap: wrap; }
  .feature-card {
    flex: 1; min-width: 220px;
    background: white; border: 1px solid #e8eaf6;
    border-radius: 16px; padding: 28px 22px; text-align: center;
    box-shadow: 0 2px 12px rgba(26,35,126,0.07);
  }
  .feature-card .icon { font-size: 2.2rem; margin-bottom: 12px; }
  .feature-card h3 { font-size: 1.05rem; font-weight: 700; color: #1a237e; margin-bottom: 8px; }
  .feature-card p  { font-size: 0.9rem; color: #555; line-height: 1.5; margin: 0; }

  /* ── Form card ── */
  .form-card {
    background: white; border: 1px solid #e8eaf6;
    border-radius: 20px; padding: 40px 36px;
    box-shadow: 0 4px 24px rgba(26,35,126,0.10);
    margin-bottom: 48px;
  }
  .form-card h2 { color: #1a237e; font-size: 1.6rem; font-weight: 700; margin-bottom: 6px; }
  .form-card .subtitle { color: #666; margin-bottom: 28px; font-size: 0.95rem; }

  /* ── Success card ── */
  .success-card {
    background: linear-gradient(135deg, #e8f5e9 0%, #f1f8e9 100%);
    border: 1px solid #a5d6a7; border-radius: 20px;
    padding: 48px 36px; text-align: center; margin-bottom: 48px;
  }
  .success-card h2 { color: #2e7d32; font-size: 2rem; margin-bottom: 12px; }
  .success-card p  { color: #388e3c; font-size: 1.05rem; margin: 0; }

  /* ── How it works ── */
  .steps { display: flex; gap: 16px; margin-bottom: 48px; flex-wrap: wrap; }
  .step {
    flex: 1; min-width: 180px; text-align: center;
    padding: 24px 16px;
  }
  .step-num {
    width: 44px; height: 44px; border-radius: 50%;
    background: #1a237e; color: white;
    font-size: 1.2rem; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 14px;
  }
  .step h4 { font-size: 0.95rem; font-weight: 700; color: #1a237e; margin-bottom: 6px; }
  .step p  { font-size: 0.85rem; color: #666; margin: 0; }

  /* ── Input overrides ── */
  .stTextInput > div > div > input,
  .stTextArea > div > div > textarea {
    direction: rtl !important; text-align: right !important;
    border-radius: 10px !important;
  }
  label { direction: rtl !important; font-weight: 600 !important; }
  .stButton > button {
    border-radius: 12px !important; font-size: 1rem !important;
    padding: 0.6rem 0 !important; font-weight: 700 !important;
  }
  .stAlert { direction: rtl !important; text-align: right !important; }

  /* ── Footer ── */
  .footer {
    text-align: center; color: #999; font-size: 0.8rem;
    padding: 24px 0 32px;
  }
</style>
""", unsafe_allow_html=True)


# ── SESSION STATE ──────────────────────────────────────────────────────────────
def _init():
    for k, v in {"step": "landing", "registered_name": "", "registered_phone": ""}.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


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
    """Ask Claude to pull annex codes from the mifrat text."""
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
    """Israeli ID checksum validation."""
    tz = tz.strip().zfill(9)
    if not tz.isdigit() or len(tz) != 9:
        return False
    total = 0
    for i, ch in enumerate(tz):
        d = int(ch) * (1 if i % 2 == 0 else 2)
        total += d - 9 if d > 9 else d
    return total % 10 == 0


# ── HERO + FEATURES (shown on landing & form steps) ───────────────────────────
def _render_hero():
    st.markdown("""
<div class="hero">
  <div class="badge">🇮🇱 לשוק הישראלי</div>
  <h1>🛡️ BituachBot</h1>
  <p>האסיסטנט החכם שמסביר לך בדיוק מה מכסה הביטוח שלך — בשניות, בשפה שלך.</p>
</div>
""", unsafe_allow_html=True)


def _render_features():
    st.markdown("""
<div class="features">
  <div class="feature-card">
    <div class="icon">🔍</div>
    <h3>תשובות מיידיות</h3>
    <p>שאל בוואטסאפ "יש לי כיסוי ל-MRI?" וקבל תשובה מפורטת תוך שניות.</p>
  </div>
  <div class="feature-card">
    <div class="icon">📄</div>
    <h3>מבוסס על הפוליסה שלך</h3>
    <p>הבוט קורא את הנספחים שלך ועונה בדיוק לפי הכיסוי האישי שלך.</p>
  </div>
  <div class="feature-card">
    <div class="icon">🌐</div>
    <h3>עברית | ערבית | רוסית</h3>
    <p>שאל בכל שפה שנוחה לך — הבוט מבין ועונה.</p>
  </div>
</div>
""", unsafe_allow_html=True)


def _render_how_it_works():
    st.markdown("""
<div class="steps">
  <div class="step"><div class="step-num">1</div><h4>נרשמים פה</h4><p>ממלאים את הפרטים ומעלים את המפרט</p></div>
  <div class="step"><div class="step-num">2</div><h4>מוסיפים לאנשי קשר</h4><p>שומרים את מספר הבוט בוואטסאפ</p></div>
  <div class="step"><div class="step-num">3</div><h4>שואלים בחופשיות</h4><p>"יש לי כיסוי לכירופרקטיקה?" "מה ההשתתפות בניתוח?"</p></div>
</div>
""", unsafe_allow_html=True)


# ── LANDING PAGE ───────────────────────────────────────────────────────────────
def page_landing():
    _render_hero()
    _render_features()
    _render_how_it_works()

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown("## רוצה להצטרף? זה לוקח דקה אחת ↓")
    if st.button("✅ הרשמה חינם", type="primary", use_container_width=True):
        st.session_state.step = "form"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="footer">BituachBot © 2025 · הנתונים שלך מאובטחים ולא משותפים עם גורמים חיצוניים.</div>', unsafe_allow_html=True)


# ── SIGNUP FORM ────────────────────────────────────────────────────────────────
def page_form():
    _render_hero()

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown("## 📝 הרשמה לשירות")
    st.markdown('<p class="subtitle">מלא את הפרטים הבאים. כל השדות חובה למעט העלאת המפרט.</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        full_name = st.text_input("שם מלא *", placeholder="ישראל ישראלי")
    with col2:
        phone = st.text_input("מספר טלפון *", placeholder="0501234567")

    teudat_zehut = st.text_input("תעודת זהות *", placeholder="9 ספרות", max_chars=9)

    st.divider()
    st.markdown("**העלאת מפרט ביטוח** (רשות — ניתן לשלוח מאוחר יותר)")
    st.caption("העלה את קובץ המפרט (PDF) כדי שנזהה אוטומטית את הנספחים שלך.")

    uploaded = st.file_uploader("בחר קובץ מפרט (PDF)", type=["pdf"], key="mifrat_upload")

    annex_codes: list[str] = []
    if uploaded and PDF_SUPPORT:
        with st.spinner("מנתח את המפרט..."):
            pdf_text = _extract_pdf_text(uploaded.read())
        if pdf_text.strip():
            with st.spinner("מזהה נספחים..."):
                annex_codes = _extract_annex_codes(pdf_text)
            if annex_codes:
                st.success(f"זוהו {len(annex_codes)} נספחים: {' | '.join(annex_codes)}")
            else:
                st.warning("לא זוהו קודי נספחים. ניתן להוסיף ידנית לאחר ההרשמה.")
        else:
            st.warning("לא ניתן לחלץ טקסט מהקובץ (ייתכן שמדובר ב-PDF סרוק).")

    st.markdown("<br>", unsafe_allow_html=True)
    submit = st.button("✅ סיים הרשמה", type="primary", use_container_width=True)

    if submit:
        # ── Validation ──
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
            with st.spinner("רושם אותך במערכת..."):
                ok, msg = db.register_user_with_policies(
                    clean_phone, full_name.strip(), annex_codes, clean_tz
                )
            if ok:
                st.session_state.registered_name = full_name.strip()
                st.session_state.registered_phone = clean_phone
                st.session_state.step = "success"
                st.rerun()
            else:
                st.error(msg)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← חזרה", use_container_width=False):
        st.session_state.step = "landing"
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ── SUCCESS PAGE ───────────────────────────────────────────────────────────────
def page_success():
    _render_hero()

    name = st.session_state.registered_name
    st.markdown(f"""
<div class="success-card">
  <div style="font-size:3.5rem; margin-bottom:16px">🎉</div>
  <h2>ברוכים הבאים, {name}!</h2>
  <p>הרישום הושלם בהצלחה. עכשיו אפשר להתחיל לשאול שאלות.</p>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown("## 📱 השלב הבא — וואטסאפ")
    st.markdown("""
שמור את מספר הבוט בטלפון שלך ושלח לו הודעה:

> **"שלום, אני רוצה לדעת מה הכיסוי שלי"**

הבוט יזהה אותך לפי מספר הטלפון שמסרת וישיב לשאלות שלך לפי הנספחים שלך.
""")

    st.info("📌 **לא קיבלת את מספר הבוט?** צור איתנו קשר ונשלח לך אותו.")

    st.divider()
    st.markdown("### שאלות נפוצות שאפשר לשאול את הבוט")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
- "יש לי כיסוי לכירופרקטיקה?"
- "כמה ההשתתפות העצמית ב-MRI?"
- "מה מספר הטיפולים בשנה לפיזיותרפיה?"
""")
    with col2:
        st.markdown("""
- "יש זמן המתנה לניתוח?"
- "אלו ספקים מאושרים?"
- "מה הכיסוי לרפואה משלימה?"
""")

    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🏠 חזרה לדף הבית", use_container_width=True):
        st.session_state.step = "landing"
        st.rerun()

    st.markdown('<div class="footer">BituachBot © 2025 · הנתונים שלך מאובטחים ולא משותפים עם גורמים חיצוניים.</div>', unsafe_allow_html=True)


# ── ROUTER ─────────────────────────────────────────────────────────────────────
{
    "landing": page_landing,
    "form": page_form,
    "success": page_success,
}.get(st.session_state.step, page_landing)()
