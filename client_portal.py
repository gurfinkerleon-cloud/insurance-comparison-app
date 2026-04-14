"""
אסיסטנט ביטוח חכם - פורטל לקוחות
Insurance Smart Assistant - Client Portal

Run:  streamlit run client_portal.py

Required env vars (in .env or Streamlit secrets):
  SUPABASE_URL          - https://xqbkkvqtdezyhthdlhv.supabase.co
  SUPABASE_SERVICE_KEY  - Service Role key
  ANTHROPIC_API_KEY     - Claude API key
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

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="אסיסטנט ביטוח חכם",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── GLOBAL CSS (RTL + design) ─────────────────────────────────────────────────
st.markdown(
    """
<style>
    /* RTL everywhere */
    html, body, [class*="css"] { direction: rtl !important; }
    .main .block-container { direction: rtl !important; text-align: right !important; }
    .stMarkdown, .stMarkdown * { direction: rtl !important; text-align: right !important; }
    .stAlert, .stInfo, .stSuccess, .stWarning, .stError {
        direction: rtl !important; text-align: right !important;
    }
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        text-align: right !important; direction: rtl !important;
    }
    h1, h2, h3, h4, h5, h6 { text-align: right !important; direction: rtl !important; }
    .stButton > button { width: 100%; font-size: 1rem; }
    label, p, div, span { direction: rtl !important; }

    /* Chat bubbles */
    .chat-user {
        background: #DCF8C6; border-radius: 12px 12px 4px 12px;
        padding: 10px 14px; margin: 6px 0; max-width: 80%; float: right; clear: both;
        direction: rtl; text-align: right;
    }
    .chat-assistant {
        background: #F0F0F0; border-radius: 12px 12px 12px 4px;
        padding: 10px 14px; margin: 6px 0; max-width: 80%; float: left; clear: both;
        direction: rtl; text-align: right;
    }
    .clearfix { clear: both; }

    /* Policy card */
    .policy-card {
        border: 1px solid #e0e0e0; border-radius: 10px;
        padding: 14px 18px; margin-bottom: 10px;
        background: #FAFAFA;
    }
    .policy-card h4 { margin: 0 0 4px 0; color: #1a73e8; }
    .policy-card code { font-size: 0.8rem; color: #555; }
</style>
""",
    unsafe_allow_html=True,
)


# ── SESSION STATE ─────────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "page": "login",          # login | home | chat
        "phone": None,
        "profile": None,
        "annexes": [],
        "chat_history": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── DB / API HELPERS ──────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_db() -> InsuranceClientDB:
    return InsuranceClientDB()


@st.cache_resource(show_spinner=False)
def get_claude() -> Anthropic:
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _db() -> InsuranceClientDB:
    try:
        return get_db()
    except ValueError as e:
        st.error(f"❌ שגיאת חיבור: {e}")
        st.stop()


def _claude() -> Anthropic:
    try:
        return get_claude()
    except Exception as e:
        st.error(f"❌ שגיאת Claude: {e}")
        st.stop()


# ── PDF PROCESSING ────────────────────────────────────────────────────────────
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF file."""
    if not PDF_SUPPORT:
        return ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def extract_data_from_mifrat(text: str) -> dict:
    """
    Use Claude to extract the insured's name and annex codes from
    the raw text of a Mifrat (מפרט) PDF.

    Returns {"full_name": str, "annex_codes": [str, ...]}
    """
    client = _claude()
    prompt = f"""זהו טקסט שחולץ ממפרט ביטוח ישראלי.
אנא חלץ את הפרטים הבאים:
1. שם המבוטח המלא (full_name)
2. רשימת כל קודי הנספחים - מספרים בני 4-6 ספרות שמופיעים ליד המילה "נספח" (annex_codes)

החזר JSON בלבד, ללא הסברים:
{{"full_name": "שם מלא", "annex_codes": ["8713", "6792"]}}

טקסט המפרט (עד 4000 תווים ראשונים):
{text[:4000]}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt a loose extraction of the JSON object
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        return {"full_name": "", "annex_codes": []}


# ── CHAT HELPER ───────────────────────────────────────────────────────────────
def ask_insurance_question(question: str, annexes: list) -> str:
    """
    Answer a Hebrew insurance question using the full_text of the user's
    linked annexes as context.
    """
    client = _claude()

    if not annexes:
        return "לא נמצאו נספחים מקושרים לחשבון שלך. אנא העלה את קובץ המפרט כדי שאוכל לעזור."

    # Build context from the user's annexes
    context_parts = []
    for ann in annexes:
        name = ann.get("annex_name") or ann.get("name", "נספח")
        code = ann.get("annex_code", "")
        full_text = ann.get("full_text", "")
        if full_text:
            context_parts.append(
                f"=== נספח {code} – {name} ===\n{full_text[:2000]}"
            )

    context = "\n\n".join(context_parts) if context_parts else "אין מידע זמין בספרייה."

    system = """אתה מומחה בכיר לביטוח בריאות בישראל.
ענה אך ורק על פי הטקסט הרשמי של הנספחים המופיעים בהקשר.
סדר את התשובה בנקודות. אל תמציא נתונים שאינם בטקסט.
ענה תמיד בעברית רהוטה ומקצועית."""

    messages = [
        *[
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.chat_history[-8:]  # last 8 turns for context
        ],
        {
            "role": "user",
            "content": f"הקשר – נספחים של הלקוח:\n{context}\n\nשאלה: {question}",
        },
    ]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return response.content[0].text


# ── PAGES ─────────────────────────────────────────────────────────────────────

def page_login():
    st.title("🏥 אסיסטנט ביטוח חכם")
    st.markdown("#### ברוכים הבאים! מלאו את מספר הטלפון שלכם כדי להתחיל")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        phone_input = st.text_input(
            "מספר טלפון",
            placeholder="050-1234567",
            key="phone_input_field",
        )

        if st.button("כניסה / רישום", type="primary"):
            phone = phone_input.strip().replace("-", "").replace(" ", "")
            if len(phone) < 9:
                st.warning("אנא הכניסו מספר טלפון תקין.")
                return

            db = _db()
            with st.spinner("בודק..."):
                profile = db.get_profile_by_phone(phone)

            st.session_state.phone = phone
            if profile:
                st.session_state.profile = profile
                with st.spinner("טוען פוליסות..."):
                    st.session_state.annexes = db.get_user_annexes(phone)
                st.session_state.page = "home"
                st.rerun()
            else:
                # New user → go to registration
                st.session_state.profile = None
                st.session_state.page = "register"
                st.rerun()


def page_register():
    st.title("📝 רישום לקוח חדש")

    phone = st.session_state.phone or ""
    st.info(f"מספר הטלפון שלך: **{phone}**")

    tab_pdf, tab_manual = st.tabs(["📄 העלאת קובץ מפרט (PDF)", "✏️ הזנה ידנית"])

    # ── Tab 1: PDF upload ──────────────────────────────────────────────────
    with tab_pdf:
        if not PDF_SUPPORT:
            st.error("ספריית pdfplumber אינה מותקנת. השתמש בכרטיסיית ההזנה הידנית.")
        else:
            st.markdown("העלה את קובץ **המפרט** שלך (PDF) – הבינה המלאכותית תזהה את הנספחים אוטומטית.")
            uploaded = st.file_uploader(
                "בחר קובץ PDF", type=["pdf"], key="pdf_uploader"
            )

            if uploaded:
                with st.spinner("מחלץ טקסט מה-PDF..."):
                    pdf_text = extract_text_from_pdf(uploaded.read())

                if not pdf_text.strip():
                    st.error("לא ניתן לחלץ טקסט מהקובץ. ייתכן שה-PDF סרוק. נסה הזנה ידנית.")
                else:
                    with st.spinner("הבינה המלאכותית מנתחת את המפרט..."):
                        extracted = extract_data_from_mifrat(pdf_text)

                    full_name = extracted.get("full_name", "")
                    annex_codes = extracted.get("annex_codes", [])

                    st.success("✅ הנתונים זוהו:")
                    c1, c2 = st.columns(2)
                    c1.metric("שם המבוטח", full_name or "לא זוהה")
                    c2.metric("קודי נספחים שזוהו", len(annex_codes))

                    if annex_codes:
                        st.write("**קודים שזוהו:**", " | ".join(annex_codes))

                    # Allow user to correct name
                    corrected_name = st.text_input(
                        "שם מלא (ניתן לתקן)", value=full_name, key="pdf_name"
                    )

                    if st.button("✅ אשר ושמור", type="primary", key="pdf_save"):
                        if not corrected_name.strip():
                            st.warning("אנא הכניסו שם מלא.")
                            return
                        db = _db()
                        with st.spinner("שומר במסד הנתונים..."):
                            ok, msg = db.register_user_with_policies(
                                phone, corrected_name.strip(), annex_codes
                            )
                        if ok:
                            st.success(msg)
                            st.session_state.profile = {"full_name": corrected_name.strip(), "phone_number": phone}
                            st.session_state.annexes = db.get_user_annexes(phone)
                            st.session_state.page = "home"
                            st.rerun()
                        else:
                            st.error(msg)

    # ── Tab 2: Manual entry ────────────────────────────────────────────────
    with tab_manual:
        st.markdown("הכנס את שמך ואת קודי הנספחים מהמפרט שלך.")

        manual_name = st.text_input("שם מלא", key="manual_name")
        manual_codes_raw = st.text_input(
            "קודי נספחים (מופרדים בפסיקים)",
            placeholder="8713, 6792, 5409",
            key="manual_codes",
        )

        if st.button("✅ שמור", type="primary", key="manual_save"):
            if not manual_name.strip():
                st.warning("אנא הכניסו שם מלא.")
                return
            codes = [c.strip() for c in manual_codes_raw.split(",") if c.strip()]
            db = _db()
            with st.spinner("שומר..."):
                ok, msg = db.register_user_with_policies(
                    phone, manual_name.strip(), codes
                )
            if ok:
                st.success(msg)
                st.session_state.profile = {"full_name": manual_name.strip(), "phone_number": phone}
                st.session_state.annexes = db.get_user_annexes(phone)
                st.session_state.page = "home"
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    if st.button("← חזרה"):
        st.session_state.page = "login"
        st.rerun()


def page_home():
    profile = st.session_state.profile or {}
    full_name = profile.get("full_name", "לקוח יקר")
    annexes = st.session_state.annexes

    st.title(f"שלום, {full_name}! 👋")

    # ── Sidebar ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"**{full_name}**")
        st.caption(st.session_state.phone or "")
        st.divider()
        if st.button("💬 שאל שאלה על הכיסוי", use_container_width=True):
            st.session_state.page = "chat"
            st.rerun()
        st.divider()
        # Upload new PDF to update policies
        if st.button("🔄 עדכן פוליסה (PDF חדש)", use_container_width=True):
            st.session_state.page = "register"
            st.rerun()
        if st.button("🚪 התנתק", use_container_width=True):
            for k in ("phone", "profile", "annexes", "chat_history"):
                st.session_state[k] = [] if k == "annexes" else None
            st.session_state.page = "login"
            st.rerun()

    # ── Main content ───────────────────────────────────────────────────────
    if not annexes:
        st.info("לא נמצאו נספחים. העלה קובץ מפרט כדי לראות את הכיסויים שלך.")
        if st.button("📄 העלאת מפרט"):
            st.session_state.page = "register"
            st.rerun()
        return

    st.subheader(f"הנספחים שלך ({len(annexes)})")
    st.markdown("---")

    for ann in annexes:
        code = ann.get("annex_code", "")
        name = ann.get("annex_name") or ann.get("name") or "נספח"
        company = ann.get("company_name", "")
        full_text = ann.get("full_text", "")

        # Brief preview (first 200 chars)
        preview = full_text[:200].strip() if full_text else "אין מידע בספרייה עדיין."
        if len(full_text) > 200:
            preview += "..."

        in_library = bool(full_text)
        badge = "✅" if in_library else "⚠️"

        with st.expander(f"{badge} נספח {code} – {name}  |  {company}"):
            if in_library:
                st.markdown(preview)
                st.caption("לשאלות מפורטות על נספח זה, לחץ על 'שאל שאלה' בתפריט הצד.")
            else:
                st.warning(
                    "נספח זה טרם הועלה לספרייה המרכזית. "
                    "המידע יתווסף בקרוב."
                )

    st.divider()
    if st.button("💬 שאל שאלה על הכיסוי שלך", type="primary"):
        st.session_state.page = "chat"
        st.rerun()


def page_chat():
    profile = st.session_state.profile or {}
    full_name = profile.get("full_name", "לקוח")
    annexes = st.session_state.annexes

    # ── Sidebar ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"**{full_name}**")
        st.caption(st.session_state.phone or "")
        st.divider()
        if st.button("🏠 חזרה לדף הבית", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
        if st.button("🗑️ נקה שיחה", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
        st.divider()
        # Show which annexes are available for context
        if annexes:
            st.markdown("**נספחים פעילים:**")
            for ann in annexes:
                code = ann.get("annex_code", "")
                name = ann.get("annex_name") or ""
                has_text = bool(ann.get("full_text"))
                icon = "✅" if has_text else "⚠️"
                st.caption(f"{icon} {code} – {name}")

    st.title("💬 שאל את אסיסטנט הביטוח")
    st.markdown("שאל שאלות על הכיסויים, ההשתתפות העצמית, זמני ההמתנה ועוד.")

    # ── Chat history display ────────────────────────────────────────────────
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="chat-user">{msg["content"]}</div>'
                    '<div class="clearfix"></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="chat-assistant">{msg["content"]}</div>'
                    '<div class="clearfix"></div>',
                    unsafe_allow_html=True,
                )

    # ── Input ───────────────────────────────────────────────────────────────
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "שאלתך",
            placeholder="לדוגמה: כמה ההשתתפות העצמית ב-MRI?",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("שלח ➤", use_container_width=True)

    if submitted and user_input.strip():
        question = user_input.strip()
        st.session_state.chat_history.append({"role": "user", "content": question})

        with st.spinner("מעבד..."):
            answer = ask_insurance_question(question, annexes)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()


# ── ROUTER ────────────────────────────────────────────────────────────────────
def main():
    page = st.session_state.page

    if page == "login":
        page_login()
    elif page == "register":
        page_register()
    elif page == "home":
        page_home()
    elif page == "chat":
        page_chat()
    else:
        st.session_state.page = "login"
        st.rerun()


if __name__ == "__main__":
    main()
