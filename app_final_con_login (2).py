import streamlit as st
import sqlite3
from anthropic import Anthropic
import os
from dotenv import load_dotenv
import tempfile
import uuid
import json
import shutil
import re
import hashlib

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

load_dotenv()

st.set_page_config(page_title="השוואת פוליסות", page_icon="📄", layout="wide")

st.markdown("""
<style>
    .main .block-container { direction: rtl; text-align: right; }
    .stButton>button { width: 100%; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { text-align: right; }
    h1, h2, h3 { text-align: right; }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'page' not in st.session_state:
    st.session_state.page = "🏠 בית"
if 'current_investigation_id' not in st.session_state:
    st.session_state.current_investigation_id = None

COMPANIES = ["הראל", "מגדל", "כלל", "מנורה", "הפניקס", "איילון"]
UPLOAD_DIR = "policy_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("insurance.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    def create_tables(self):
        cur = self.conn.cursor()
        
        # Users table
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        
        # Investigations (now with user_id)
        cur.execute("""CREATE TABLE IF NOT EXISTS investigations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            client_name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)""")
        
        cur.execute("""CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            investigation_id TEXT NOT NULL,
            company TEXT,
            file_name TEXT NOT NULL,
            custom_name TEXT,
            file_path TEXT,
            total_pages INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE)""")
        
        cur.execute("""CREATE TABLE IF NOT EXISTS policy_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE)""")
        
        cur.execute("""CREATE TABLE IF NOT EXISTS qa_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            policy_names TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE)""")
        
        self.conn.commit()
    
    # User management
    def create_user(self, username, email, password):
        """Create new user"""
        try:
            user_id = str(uuid.uuid4())
            password_hash = hash_password(password)
            self.conn.execute("INSERT INTO users (id, username, email, password_hash) VALUES (?, ?, ?, ?)",
                            (user_id, username, email, password_hash))
            self.conn.commit()
            return user_id, None
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                return None, "שם משתמש כבר קיים"
            elif 'email' in str(e):
                return None, "אימייל כבר קיים"
            return None, "שגיאה ביצירת משתמש"
    
    def verify_user(self, username, password):
        """Verify user credentials"""
        password_hash = hash_password(password)
        user = self.conn.execute("SELECT id, username FROM users WHERE username = ? AND password_hash = ?",
                                (username, password_hash)).fetchone()
        if user:
            return user['id'], user['username']
        return None, None
    
    def get_user_by_id(self, user_id):
        """Get user info by ID"""
        return self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    # Investigation management (filtered by user)
    def create_investigation(self, user_id, client_name, description=None):
        inv_id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO investigations (id, user_id, client_name, description) VALUES (?, ?, ?, ?)",
                         (inv_id, user_id, client_name, description))
        self.conn.commit()
        return inv_id
    
    def get_all_investigations(self, user_id):
        """Get investigations for specific user only"""
        investigations = self.conn.execute(
            "SELECT * FROM investigations WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)).fetchall()
        result = []
        for inv in investigations:
            p_count = self.conn.execute("SELECT COUNT(*) FROM policies WHERE investigation_id = ?", 
                                       (inv['id'],)).fetchone()[0]
            q_count = self.conn.execute("SELECT COUNT(*) FROM qa_history WHERE investigation_id = ?", 
                                       (inv['id'],)).fetchone()[0]
            result.append({'id': inv['id'], 'client_name': inv['client_name'], 
                          'description': inv['description'], 'created_at': inv['created_at'],
                          'policy_count': p_count, 'question_count': q_count})
        return result
    
    def get_investigation(self, inv_id):
        return self.conn.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)).fetchone()
    
    def delete_investigation(self, inv_id):
        files = self.conn.execute("SELECT file_path FROM policies WHERE investigation_id = ?", 
                                 (inv_id,)).fetchall()
        for f in files:
            if f['file_path'] and os.path.exists(f['file_path']):
                try: os.remove(f['file_path'])
                except: pass
        self.conn.execute("DELETE FROM investigations WHERE id = ?", (inv_id,))
        self.conn.commit()
    
    def get_company_count(self, inv_id, company):
        return self.conn.execute("SELECT COUNT(*) FROM policies WHERE investigation_id = ? AND company = ?",
                                (inv_id, company)).fetchone()[0]
    
    def insert_policy(self, inv_id, company, file_name, custom_name, file_path, total_pages):
        policy_id = str(uuid.uuid4())
        self.conn.execute("""INSERT INTO policies (id, investigation_id, company, file_name, custom_name, file_path, total_pages)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                         (policy_id, inv_id, company, file_name, custom_name, file_path, total_pages))
        self.conn.commit()
        return policy_id
    
    def get_policies(self, inv_id):
        return self.conn.execute("SELECT * FROM policies WHERE investigation_id = ? ORDER BY created_at DESC", 
                                (inv_id,)).fetchall()
    
    def delete_policy(self, policy_id):
        row = self.conn.execute("SELECT file_path FROM policies WHERE id = ?", (policy_id,)).fetchone()
        if row and row['file_path'] and os.path.exists(row['file_path']):
            try: os.remove(row['file_path'])
            except: pass
        self.conn.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
        self.conn.commit()
    
    def insert_chunks(self, policy_id, chunks):
        for chunk in chunks:
            self.conn.execute("INSERT INTO policy_chunks (policy_id, chunk_text) VALUES (?, ?)", 
                            (policy_id, chunk))
        self.conn.commit()
    
    def get_all_text(self, policy_id):
        chunks = self.conn.execute("SELECT chunk_text FROM policy_chunks WHERE policy_id = ?", 
                                  (policy_id,)).fetchall()
        return "\n\n".join([row[0] for row in chunks])
    
    def search_chunks(self, policy_id, query, top_k=10):
        chunks = self.conn.execute("SELECT chunk_text FROM policy_chunks WHERE policy_id = ?", 
                                  (policy_id,)).fetchall()
        query_lower = query.lower()
        scored = []
        for row in chunks:
            text = row[0]
            score = 0
            if 'מחיר' in query_lower or 'עלות' in query_lower or 'פרמיה' in query_lower:
                if 'גיל' in text.lower() or 'מחיר' in text.lower() or 'פרמיה' in text.lower():
                    score += 10
            score += sum(1 for word in query_lower.split() if word in text.lower())
            if score > 0: scored.append({'text': text, 'score': score})
        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored[:top_k]
    
    def save_qa(self, inv_id, question, answer, policy_names):
        self.conn.execute("INSERT INTO qa_history (investigation_id, question, answer, policy_names) VALUES (?, ?, ?, ?)",
                         (inv_id, question, answer, json.dumps(policy_names)))
        self.conn.commit()
    
    def get_qa_history(self, inv_id):
        return self.conn.execute(
            "SELECT question, answer, policy_names, created_at FROM qa_history WHERE investigation_id = ? ORDER BY created_at DESC",
            (inv_id,)).fetchall()

def extract_text_from_pdf(pdf_file):
    if not PDF_SUPPORT: return "", 0
    try:
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: text += page_text + "\n\n---PAGE_BREAK---\n\n"
        return text, len(pdf.pages)
    except: return "", 0

def detect_company(text):
    text_lower = text.lower()
    if 'מגדל' in text or 'migdal' in text_lower:
        return "מגדל"
    elif 'הראל' in text or 'harel' in text_lower:
        return "הראל"
    elif 'כלל' in text or 'clal' in text_lower:
        return "כלל"
    elif 'מנורה' in text or 'menora' in text_lower:
        return "מנורה"
    elif 'פניקס' in text or 'phoenix' in text_lower:
        return "הפניקס"
    elif 'איילון' in text:
        return "איילון"
    return None

def create_chunks(text, size=1500, overlap=300):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i + size])
        if len(chunk.strip()) > 100: chunks.append(chunk)
    return chunks

@st.cache_resource
def init_connections():
    db = Database()
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    claude = None
    if api_key:
        try: claude = Anthropic(api_key=api_key)
        except: pass
    return db, claude

db, claude_client = init_connections()

# LOGIN / REGISTER PAGE
if not st.session_state.authenticated:
    st.title("🔐 השוואת פוליסות ביטוח")
    
    tab1, tab2 = st.tabs(["🔑 כניסה", "✨ הרשמה"])
    
    with tab1:
        st.subheader("כניסה למערכת")
        with st.form("login_form"):
            username = st.text_input("שם משתמש")
            password = st.text_input("סיסמה", type="password")
            submit = st.form_submit_button("התחבר", type="primary", use_container_width=True)
            
            if submit:
                if username and password:
                    user_id, user_name = db.verify_user(username, password)
                    if user_id:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_id
                        st.session_state.username = user_name
                        st.success(f"שלום {user_name}!")
                        st.rerun()
                    else:
                        st.error("שם משתמש או סיסמה שגויים")
                else:
                    st.warning("נא למלא את כל השדות")
    
    with tab2:
        st.subheader("הרשמה למערכת")
        with st.form("register_form"):
            new_username = st.text_input("שם משתמש (באנגלית)")
            new_email = st.text_input("אימייל")
            new_password = st.text_input("סיסמה", type="password")
            new_password_confirm = st.text_input("אישור סיסמה", type="password")
            register = st.form_submit_button("הירשם", type="primary", use_container_width=True)
            
            if register:
                if not all([new_username, new_email, new_password, new_password_confirm]):
                    st.warning("נא למלא את כל השדות")
                elif new_password != new_password_confirm:
                    st.error("הסיסמאות לא תואמות")
                elif len(new_password) < 6:
                    st.error("הסיסמה חייבת להכיל לפחות 6 תווים")
                else:
                    user_id, error = db.create_user(new_username, new_email, new_password)
                    if user_id:
                        st.success("נרשמת בהצלחה! עבור ללשונית 'כניסה'")
                    else:
                        st.error(error)
    
    st.stop()

# MAIN APP (AUTHENTICATED USERS ONLY)

# SIDEBAR
with st.sidebar:
    st.title("🔍 חקירות")
    
    # User info and logout
    st.info(f"👤 {st.session_state.username}")
    if st.button("🚪 התנתק", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.current_investigation_id = None
        st.rerun()
    
    st.markdown("---")
    
    if st.session_state.current_investigation_id:
        inv = db.get_investigation(st.session_state.current_investigation_id)
        if inv:
            st.success(f"**{inv['client_name']}**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ סגור", use_container_width=True):
                    st.session_state.current_investigation_id = None
                    st.rerun()
            with col2:
                if st.button("🗑️ מחק", use_container_width=True):
                    db.delete_investigation(st.session_state.current_investigation_id)
                    st.session_state.current_investigation_id = None
                    st.rerun()
    
    st.markdown("---")
    
    with st.expander("➕ חדש", expanded=not st.session_state.current_investigation_id):
        client_name = st.text_input("לקוח")
        if st.button("צור", type="primary", use_container_width=True):
            if client_name:
                inv_id = db.create_investigation(st.session_state.user_id, client_name, "")
                st.session_state.current_investigation_id = inv_id
                st.rerun()
    
    st.markdown("---")
    investigations = db.get_all_investigations(st.session_state.user_id)
    
    if investigations:
        st.caption(f"החקירות שלי ({len(investigations)})")
        for inv in investigations:
            if st.button(f"🟢 {inv['client_name']}", key=f"inv_{inv['id']}", use_container_width=True):
                st.session_state.current_investigation_id = inv['id']
                st.rerun()
    else:
        st.info("אין חקירות. צור חקירה חדשה!")

st.sidebar.markdown("---")

# Navigation menu - add Admin page only for admin user
pages = ["🏠 בית", "📤 העלאה", "❓ שאלות", "⚖️ השוואה", "📜 היסטוריה"]
if st.session_state.username == "admin":
    pages.append("👑 ניהול")

for page in pages:
    if st.sidebar.button(page, use_container_width=True, key=f"nav_{page}"):
        st.session_state.page = page

# MAIN CONTENT
if not st.session_state.current_investigation_id and st.session_state.page not in ["🏠 בית", "👑 ניהול"]:
    st.warning("⚠️ בחר חקירה")
    st.stop()

if st.session_state.page == "🏠 בית":
    st.title("🏠 השוואת פוליסות")
    st.write(f"שלום **{st.session_state.username}**! 👋")
    
    all_inv = db.get_all_investigations(st.session_state.user_id)
    col1, col2 = st.columns(2)
    with col1: st.metric("החקירות שלי", len(all_inv))
    with col2: st.metric("פוליסות", sum(inv['policy_count'] for inv in all_inv))
    
    if all_inv:
        st.markdown("### 📊 החקירות האחרונות")
        for inv in all_inv[:5]:
            with st.expander(f"🔍 {inv['client_name']}"):
                st.write(f"**פוליסות:** {inv['policy_count']}")
                st.write(f"**שאלות:** {inv['question_count']}")
                st.caption(f"נוצר: {inv['created_at']}")

elif st.session_state.page == "📤 העלאה":
    st.title("📤 העלאה")
    
    inv = db.get_investigation(st.session_state.current_investigation_id)
    st.info(f"📍 לקוח: **{inv['client_name']}**")
    
    uploaded_file = st.file_uploader("PDF", type=['pdf'])
    
    if uploaded_file:
        with st.spinner("מעבד..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            text, total_pages = extract_text_from_pdf(tmp_path)
            
            if text:
                detected_company = detect_company(text)
                
                if detected_company:
                    count = db.get_company_count(st.session_state.current_investigation_id, detected_company)
                    if count == 0:
                        auto_name = detected_company
                    else:
                        auto_name = f"{detected_company} {count + 1}"
                else:
                    auto_name = uploaded_file.name.replace('.pdf', '').replace('-', ' ')
                
                st.success(f"✅ זוהתה חברה: **{detected_company or 'לא זוהה'}**")
                
                with st.form("form"):
                    company = st.selectbox("חברה", COMPANIES, 
                                          index=COMPANIES.index(detected_company) if detected_company in COMPANIES else 0)
                    custom_name = st.text_input("שם הפוליסה", value=auto_name,
                                               help="השם שיוצג ברשימה")
                    st.info(f"📄 {total_pages} עמודים")
                    
                    if st.form_submit_button("💾 שמור", type="primary"):
                        safe_filename = f"{company}_{uuid.uuid4().hex[:8]}.pdf"
                        final_path = os.path.join(UPLOAD_DIR, safe_filename)
                        shutil.copy2(tmp_path, final_path)
                        
                        chunks = create_chunks(text)
                        
                        policy_id = db.insert_policy(
                            st.session_state.current_investigation_id,
                            company,
                            uploaded_file.name,
                            custom_name,
                            final_path,
                            total_pages
                        )
                        db.insert_chunks(policy_id, chunks)
                        
                        st.success(f"✅ נשמר: **{custom_name}**")
                        st.balloons()
                        
                        try: os.unlink(tmp_path)
                        except: pass
                        
                        st.rerun()
            else:
                st.error("❌ לא ניתן לחלץ טקסט")
                try: os.unlink(tmp_path)
                except: pass
    
    st.markdown("---")
    
    policies = db.get_policies(st.session_state.current_investigation_id)
    
    if policies:
        st.markdown(f"### 📄 פוליסות של {inv['client_name']}")
        st.caption(f"סה״כ: {len(policies)} פוליסות")
        
        for pol in policies:
            with st.expander(f"📄 {pol['custom_name']}"):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**חברה:** {pol['company']}")
                    st.write(f"**עמודים:** {pol['total_pages']}")
                    st.caption(f"קובץ מקורי: {pol['file_name']}")
                with col2:
                    if st.button("🗑️ מחק", key=f"del_{pol['id']}"):
                        db.delete_policy(pol['id'])
                        st.success("נמחק!")
                        st.rerun()
    else:
        st.info(f"אין פוליסות עבור {inv['client_name']}")
        st.caption("העלה PDF כדי להתחיל")

elif st.session_state.page == "❓ שאלות":
    st.title("❓ שאלות")
    policies = db.get_policies(st.session_state.current_investigation_id)
    
    if not policies:
        st.warning("⚠️ העלה פוליסות")
    else:
        policy_options = {pol['custom_name']: pol['id'] for pol in policies}
        selected_names = st.multiselect("בחר פוליסות:", list(policy_options.keys()), 
                                       default=list(policy_options.keys()))
        
        if selected_names:
            query = st.text_area("שאל שאלה:", 
                                placeholder="למשל: מה המחיר החודשי לגיל 30?",
                                height=100)
            
            if st.button("🔍 שאל", type="primary") and query and claude_client:
                with st.spinner("מחפש ומנתח..."):
                    try:
                        selected_ids = [policy_options[name] for name in selected_names]
                        all_contexts = []
                        
                        for name, pol_id in zip(selected_names, selected_ids):
                            chunks = db.search_chunks(pol_id, query, top_k=10)
                            if chunks:
                                context = f"=== פוליסה: {name} ===\n" + "\n\n".join([c['text'] for c in chunks[:5]])
                                all_contexts.append(context)
                        
                        if all_contexts:
                            combined = "\n\n".join(all_contexts)
                            
                            response = claude_client.messages.create(
                                model="claude-sonnet-4-20250514",
                                max_tokens=1200,
                                system="""אתה מומחה ביטוח ישראלי. חלץ מידע מדויק מפוליסות.

כללים:
1. חפש טבלאות מחירים והצג אותן במדויק
2. אל תמציא מידע
3. אם אין מידע - אמר זאת
4. ענה בעברית פשוטה
5. השווה בין פוליסות

פורמט:
### [שם הפוליסה]
[המידע]""",
                                messages=[{"role": "user", "content": f"""שאלה: {query}

תוכן:
{combined}

ענה בדיוק על סמך המידע."""}]
                            )
                            
                            answer = response.content[0].text
                            st.markdown("### 💡 תשובה:")
                            st.success(answer)
                            
                            db.save_qa(st.session_state.current_investigation_id, query, answer, selected_names)
                        else:
                            st.warning("❌ לא נמצא מידע")
                    except Exception as e:
                        st.error(f"❌ שגיאה: {str(e)}")

elif st.session_state.page == "⚖️ השוואה":
    st.title("⚖️ השוואה")
    policies = db.get_policies(st.session_state.current_investigation_id)
    
    if len(policies) < 2:
        st.warning("⚠️ העלה לפחות 2 פוליסות")
    else:
        policy_options = {pol['custom_name']: pol['id'] for pol in policies}
        selected_names = st.multiselect("בחר פוליסות:", list(policy_options.keys()), 
                                       default=list(policy_options.keys())[:2])
        
        if len(selected_names) >= 2:
            if st.button("🔍 השווה", type="primary") and claude_client:
                with st.spinner("מכין השוואה..."):
                    try:
                        selected_ids = [policy_options[name] for name in selected_names]
                        all_texts = []
                        
                        for name, pol_id in zip(selected_names, selected_ids):
                            full_text = db.get_all_text(pol_id)
                            all_texts.append(f"=== {name} ===\n{full_text[:6000]}")
                        
                        combined = "\n\n".join(all_texts)
                        
                        response = claude_client.messages.create(
                            model="claude-sonnet-4-20250514",
                            max_tokens=2500,
                            system="""מומחה השוואת פוליסות. הכן השוואה מקיפה.

פורמט:
# 📊 השוואה

## 💰 מחירים
[טבלה]

## 🏥 כיסויים

## 💵 השתתפות עצמית

## 🎯 המלצה""",
                            messages=[{"role": "user", "content": f"""השווה:

{combined}"""}]
                        )
                        
                        comparison = response.content[0].text
                        st.markdown(comparison)
                        
                        db.save_qa(st.session_state.current_investigation_id, "השוואה מפורטת", 
                                  comparison, selected_names)
                    except Exception as e:
                        st.error(f"❌ {str(e)}")

elif st.session_state.page == "📜 היסטוריה":
    st.title("📜 היסטוריה")
    history = db.get_qa_history(st.session_state.current_investigation_id)
    
    if history:
        for idx, (question, answer, policy_names_json, created_at) in enumerate(history, 1):
            try:
                policies = json.loads(policy_names_json)
                pol_str = ", ".join(policies)
            except:
                pol_str = ""
            
            with st.expander(f"{idx}. {question[:60]}..."):
                if pol_str:
                    st.caption(f"פוליסות: {pol_str}")
                st.success(answer)
    else:
        st.info("אין היסטוריה")

elif st.session_state.page == "👑 ניהול":
    # Admin page - only accessible by admin user
    if st.session_state.username != "admin":
        st.error("⛔ אין לך הרשאה לצפות בדף זה")
        st.stop()
    
    st.title("👑 פאנל ניהול")
    st.caption("מידע זה זמין רק למנהל המערכת")
    
    # Get all users
    all_users = db.conn.execute("SELECT id, username, email, created_at FROM users ORDER BY created_at DESC").fetchall()
    
    # Statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👥 סך משתמשים", len(all_users))
    with col2:
        total_investigations = db.conn.execute("SELECT COUNT(*) FROM investigations").fetchone()[0]
        st.metric("🔍 סך חקירות", total_investigations)
    with col3:
        total_policies = db.conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
        st.metric("📄 סך פוליסות", total_policies)
    
    st.markdown("---")
    
    # User list with details
    st.subheader("📋 רשימת משתמשים")
    
    for user in all_users:
        user_id = user[0]
        username = user[1]
        email = user[2]
        created_at = user[3]
        
        # Get user statistics
        user_investigations = db.conn.execute(
            "SELECT COUNT(*) FROM investigations WHERE user_id = ?", (user_id,)).fetchone()[0]
        
        user_policies = db.conn.execute(
            """SELECT COUNT(*) FROM policies 
               WHERE investigation_id IN (SELECT id FROM investigations WHERE user_id = ?)""", 
            (user_id,)).fetchone()[0]
        
        user_questions = db.conn.execute(
            """SELECT COUNT(*) FROM qa_history 
               WHERE investigation_id IN (SELECT id FROM investigations WHERE user_id = ?)""", 
            (user_id,)).fetchone()[0]
        
        with st.expander(f"👤 {username} ({email})"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**אימייל:** {email}")
                st.write(f"**תאריך הצטרפות:** {created_at}")
                st.caption(f"🔍 {user_investigations} חקירות | 📄 {user_policies} פוליסות | ❓ {user_questions} שאלות")
            with col2:
                if username != "admin":
                    if st.button("🗑️ מחק", key=f"delete_user_{user_id}"):
                        # Delete user and all their data
                        db.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                        db.conn.commit()
                        st.success(f"משתמש {username} נמחק")
                        st.rerun()
    
    st.markdown("---")
    
    # Recent activity
    st.subheader("📊 פעילות אחרונה")
    recent_activity = db.conn.execute("""
        SELECT u.username, i.client_name, i.created_at 
        FROM investigations i 
        JOIN users u ON i.user_id = u.id 
        ORDER BY i.created_at DESC 
        LIMIT 10
    """).fetchall()
    
    if recent_activity:
        for username, client_name, created_at in recent_activity:
            st.caption(f"🔍 {username} יצר חקירה: **{client_name}** ({created_at})")
    else:
        st.info("אין פעילות עדיין")

st.markdown("---")
st.caption(f"מערכת השוואת פוליסות | משתמש: {st.session_state.username}")
