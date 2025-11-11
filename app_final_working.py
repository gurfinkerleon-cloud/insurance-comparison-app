import streamlit as st
# import sqlite3  # ❌ Comentado - ya no se usa
from anthropic import Anthropic
from modules.database_supabase import SupabaseDatabase
# from modules.storage_supabase import SupabaseStorage  # ❌ Not used - using local storage
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
    /* Global RTL for all content */
    .main .block-container { 
        direction: rtl !important; 
        text-align: right !important; 
    }
    
    /* All text elements */
    .stMarkdown, .stMarkdown p, .stMarkdown div, .stMarkdown li, .stMarkdown ul, .stMarkdown ol {
        direction: rtl !important;
        text-align: right !important;
    }
    
    /* Info boxes */
    .stAlert, .stInfo, .stSuccess, .stWarning, .stError {
        direction: rtl !important;
        text-align: right !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader, [data-testid="stExpander"] {
        direction: rtl !important;
        text-align: right !important;
    }
    
    [data-testid="stExpander"] > details > summary {
        text-align: right !important;
        direction: rtl !important;
    }
    
    [data-testid="stExpander"] > details > div {
        text-align: right !important;
        direction: rtl !important;
    }
    
    /* Text inputs and textareas */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { 
        text-align: right !important; 
        direction: rtl !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 { 
        text-align: right !important; 
        direction: rtl !important;
    }
    
    /* Buttons */
    .stButton>button { 
        width: 100%; 
    }
    
    /* All paragraphs and divs */
    p, div, span, label {
        direction: rtl !important;
    }
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

# Insurance Companies General Information
COMPANIES_INFO = {
    "הראל": {
        "full_name": "הראל חברה לביטוח בע\"מ",
        "website": "www.harel-group.co.il",
        "phone": "*2407",
        "strengths": ["חברה גדולה ומובילה", "שירות לקוחות טוב", "רשת רחבה של נותני שירות"],
        "known_for": ["ביטוח בריאות מקיף", "מוצרי פנסיה", "חיסכון והשקעות"]
    },
    "מגדל": {
        "full_name": "מגדל חברה לביטוח בע\"מ",
        "website": "www.migdal.co.il",
        "phone": "*2679",
        "strengths": ["חברת ביטוח ופיננסים מובילה", "מגוון רחב של מוצרים", "דיגיטציה מתקדמת"],
        "known_for": ["ביטוח חיים ובריאות", "קרנות פנסיה", "ניהול תיקים"]
    },
    "כלל": {
        "full_name": "כלל חברה לביטוח בע\"מ",
        "website": "www.clalbit.co.il",
        "phone": "*2800",
        "strengths": ["חדשנות דיגיטלית", "מוצרים ייחודיים", "שירות מהיר"],
        "known_for": ["ביטוח בריאות", "ביטוח רכב", "ביטוח דירה"]
    },
    "מנורה": {
        "full_name": "מנורה מבטחים ביטוח בע\"מ",
        "website": "www.menoramivt.co.il",
        "phone": "*2000",
        "strengths": ["אחת הגדולות בישראל", "יציבות פיננסית", "מוניטין ותיק"],
        "known_for": ["ביטוח חיים ובריאות", "פנסיה", "חיסכון לטווח ארוך"]
    },
    "הפניקס": {
        "full_name": "הפניקס הישראלי חברה לביטוח בע\"מ",
        "website": "www.fnx.co.il",
        "phone": "*6836",
        "strengths": ["חדשנות", "מוצרים מותאמים אישית", "שירות דיגיטלי"],
        "known_for": ["ביטוח בריאות", "ביטוח חיים", "פנסיה"]
    },
    "איילון": {
        "full_name": "איילון חברה לביטוח בע\"מ",
        "website": "www.ayalon-ins.co.il",
        "phone": "*5620",
        "strengths": ["חברת ביטוח כללי", "מחירים תחרותיים", "שירות אישי"],
        "known_for": ["ביטוח רכב", "ביטוח בריאות", "ביטוח דירה"]
    }
}

# Nispach (Appendix) Information Database
NISPACH_INFO = {
    "8713": {
        "name": "אבחנה מהירה",
        "description": "כתב שירות המאפשר גישה מהירה לבדיקות דימות וייעוצים רפואיים",
        "includes": ["בדיקות CT ו-MRI", "בדיקות PET-CT", "ייעוצים מומחים", "בדיקות מעבדה מורכבות"],
        "reimbursement": {
            "CT": "החזר מלא",
            "MRI": "החזר מלא",
            "PET-CT": "החזר מלא",
            "ייעוץ מומחה": "החזר מלא"
        },
        "limits": {"שנתי": "ללא הגבלה", "לבדיקה": "ללא מגבלה"},
        "notes": "ללא תקופת המתנה, גישה ישירה למומחים"
    },
    "5409": {
        "name": "ניתוחים בחו\"ל",
        "description": "כיסוי להוצאות ניתוח ומחליפי ניתוח מחוץ לישראל",
        "includes": ["הוצאות ניתוח", "טיסות", "אשפוז", "מלווה אחד", "החזר נסיעות"],
        "reimbursement": {
            "ניתוח": "עד תקרת הפוליסה",
            "טיסה": "החזר מלא",
            "לינה": "החזר מלא",
            "מלווה": "טיסה + לינה"
        },
        "limits": {"שנתי": "לפי תקרת הפוליסה", "לניתוח": "משתנה"},
        "notes": "כפוף לאישור מראש מהחברה"
    },
    "6792": {
        "name": "רפואה משלימה",
        "description": "כתב שירות לטיפולים ברפואה משלימה",
        "includes": ["אוסטאופתיה", "כירופרקטיקה", "דיקור סיני", "הומאופתיה", "נטורופתיה"],
        "reimbursement": {
            "טיפול בודד": "50-80 ש\"ח לטיפול",
            "שיעור החזר": "לפי תעריפון"
        },
        "limits": {"שנתי": "12-20 טיפולים", "לטיפול": "עד 150 ש\"ח"},
        "notes": "מוגבל למספר טיפולים בשנה"
    },
    "5404": {
        "name": "השתלות וטיפולים מיוחדים בחו\"ל",
        "description": "כיסוי להשתלות איברים וטיפולים מתקדמים בחו\"ל",
        "includes": ["השתלת איברים", "טיפולים אונקולוגיים מתקדמים", "הוצאות נסיעה", "אשפוז"],
        "reimbursement": {
            "השתלה": "החזר מלא עד תקרה",
            "טיפולים מתקדמים": "עד תקרת הפוליסה",
            "נסיעה": "החזר מלא"
        },
        "limits": {"שנתי": "עד מיליון דולר", "לאירוע": "לפי אישור"},
        "notes": "דורש אישור רפואי מוקדם"
    },
    "6417": {
        "name": "הרחבה לתרופות אקסטרה",
        "description": "כיסוי לתרופות שאינן בסל הבריאות הממשלתי",
        "includes": ["תרופות מחוץ לסל", "תרופות ביולוגיות", "תרופות מתקדמות לסרטן"],
        "reimbursement": {
            "תרופות מחוץ לסל": "80-100% החזר",
            "תרופות ביולוגיות": "החזר מלא"
        },
        "limits": {"שנתי": "50,000-100,000 ש\"ח", "לתרופה": "לפי מחירון"},
        "notes": "עם אישור רופא מומחה"
    },
    "5406": {
        "name": "סל הזהב - תרופות שלא בסל",
        "description": "כיסוי מורחב לתרופות יקרות שלא בסל הבריאות",
        "includes": ["תרופות אונקולוגיות", "תרופות ביולוגיות", "תרופות לטרשת נפוצה", "תרופות נדירות"],
        "reimbursement": {
            "תרופות אונקולוגיות": "100% החזר",
            "תרופות ביולוגיות": "100% החזר",
            "תרופות נדירות": "החזר מלא"
        },
        "limits": {"שנתי": "עד 300,000 ש\"ח", "לתרופה": "ללא מגבלה"},
        "notes": "סכום ביטוח שנתי מוגבל"
    },
    "6784": {
        "name": "ניתוחים עם נותן שירות שבהסכם",
        "description": "כיסוי לניתוחים, ייעוצים וטיפולים מחליפי ניתוח בישראל",
        "includes": ["ניתוחים אלקטיביים", "ייעוצים מומחים", "טיפולים מחליפי ניתוח", "בדיקות טרום ניתוח"],
        "reimbursement": {
            "ניתוח": "החזר מלא דרך רשת",
            "ייעוץ מומחה": "החזר מלא",
            "טיפול מחליף": "100% החזר"
        },
        "limits": {"שנתי": "ללא הגבלה", "לניתוח": "דרך רשת בלבד"},
        "notes": "דרך רשת נותני שירות של החברה"
    },
    "6650": {
        "name": "שירותים אמבולטוריים",
        "description": "כיסוי לטיפולים וייעוצים ללא אשפוז",
        "includes": ["ייעוצים רפואיים", "בדיקות מעבדה", "בדיקות הדמייה", "טיפולים פרה-רפואיים"],
        "reimbursement": {
            "MRI": "החזר של 70-80%",
            "CT": "החזר של 70-80%",
            "בדיקות מעבדה": "החזר של 80%",
            "ייעוץ מומחה": "החזר של 75-80%",
            "אולטרסאונד": "החזר של 80%"
        },
        "limits": {"שנתי": "עד 10,000-15,000 ש\"ח", "לבדיקה": "עד 1,500 ש\"ח"},
        "notes": "כולל בדיקות מניעה"
    },
    "773755": {
        "name": "קרן אור טופ - פיצוי למחלות קשות",
        "description": "תשלום חד פעמי במקרה של אבחון מחלה קשה",
        "includes": ["סרטן", "אוטם שריר הלב", "שבץ מוחי", "כשל כלייתי", "מחלות לב"],
        "reimbursement": {
            "תשלום חד פעמי": "סכום קבוע מראש",
            "סרטן": "לפי חומרת המחלה",
            "אוטם": "תשלום מלא"
        },
        "limits": {"לאירוע": "50,000-100,000 ש\"ח", "כולל": "לפי הפוליסה"},
        "notes": "סכום פיצוי קבוע מראש"
    },
    "799712": {
        "name": "ייעוץ ובדיקות אמבולטורי",
        "description": "גישה לייעוצים רפואיים ובדיקות אבחנתיות",
        "includes": ["ייעוצי מומחים", "בדיקות CT/MRI", "בדיקות מעבדה מתקדמות", "אולטרסאונד"],
        "reimbursement": {
            "ייעוץ": "החזר של 75-100%",
            "MRI/CT": "החזר מלא או 80%",
            "מעבדה": "החזר של 80-90%"
        },
        "limits": {"שנתי": "ללא הגבלה בדרך כלל", "לבדיקה": "ללא מגבלה"},
        "notes": "ללא צורך באישור מראש"
    },
    "799716": {
        "name": "טיפולים טופ - רפואה משלימה",
        "description": "כתב שירות לטיפולים ברפואה אלטרנטיבית",
        "includes": ["פיזיותרפיה", "דיקור סיני", "אוסטאופתיה", "עיסוי רפואי"],
        "reimbursement": {
            "טיפול": "50-100 ש\"ח לטיפול",
            "שיעור החזר": "לפי תעריפון החברה"
        },
        "limits": {"שנתי": "15-25 טיפולים", "לטיפול": "עד 150 ש\"ח"},
        "notes": "מוגבל למספר טיפולים שנתי"
    },
    "5420": {
        "name": "כיסוי בריאות בסיסי",
        "description": "כיסוי בסיסי לשירותי בריאות",
        "includes": ["אשפוזים", "ניתוחים", "בדיקות בסיסיות"],
        "reimbursement": {
            "אשפוז": "החזר מלא",
            "ניתוח": "החזר מלא"
        },
        "limits": {"שנתי": "ללא הגבלה", "לאירוע": "ללא מגבלה"},
        "notes": "תנאים כלליים לבריאות 2016"
    },
    "7401": {
        "name": "ניתוחים בישראל",
        "description": "כיסוי מלא לניתוחים בארץ",
        "includes": ["ניתוחים פלסטיים משחזרים", "ניתוחים אורתופדיים", "ניתוחים כלליים"],
        "reimbursement": {
            "ניתוח": "החזר מלא דרך רשת",
            "בדיקות טרום": "החזר מלא"
        },
        "limits": {"שנתי": "ללא הגבלה", "לניתוח": "דרך רשת"},
        "notes": "דרך רשת בתי חולים מוסכמת"
    },
    "5411": {
        "name": "כיסוי שיניים",
        "description": "טיפולי שיניים מתקדמים",
        "includes": ["שתלים", "כתרים וגשרים", "יישור שיניים", "טיפולי שורש"],
        "reimbursement": {
            "שתל": "החזר של 50-70%",
            "כתר": "החזר של 60-80%",
            "יישור": "החזר חלקי"
        },
        "limits": {"שנתי": "5,000-15,000 ש\"ח", "לטיפול": "לפי סוג"},
        "notes": "עם תקופת המתנה"
    },
    "5413": {
        "name": "אשפוז כללי",
        "description": "כיסוי הוצאות אשפוז בבתי חולים",
        "includes": ["מיטה פרטית", "ליווי", "ניתוחים במהלך אשפוז"],
        "reimbursement": {
            "אשפוז": "החזר מלא",
            "מיטה פרטית": "תוספת מלאה"
        },
        "limits": {"שנתי": "ללא הגבלה", "ליום": "ללא מגבלה"},
        "notes": "ללא הגבלת ימי אשפוז"
    },
    "6800": {
        "name": "סיעוד",
        "description": "ביטוח לצורכי סיעוד ארוך טווח",
        "includes": ["מענק חד פעמי", "קצבה חודשית", "שירותי סיעוד בבית"],
        "reimbursement": {
            "מענק": "50,000-150,000 ש\"ח",
            "קצבה חודשית": "3,000-8,000 ש\"ח"
        },
        "limits": {"חודשי": "לפי דרגת סיעוד", "חד פעמי": "לפי הפוליסה"},
        "notes": "החל מגיל מסוים"
    },
    "5408": {
        "name": "ביטוח נסיעות לחו\"ל",
        "description": "כיסוי רפואי בנסיעות לחו\"ל",
        "includes": ["טיפול רפואי חירום", "אשפוז", "פינוי רפואי", "החזר הוצאות"],
        "reimbursement": {
            "טיפול חירום": "החזר מלא",
            "אשפוז": "החזר מלא",
            "פינוי": "החזר מלא"
        },
        "limits": {"לנסיעה": "עד 60 ימים", "שנתי": "מספר נסיעות"},
        "notes": "מוגבל למספר ימים בשנה"
    },
    "5415": {
        "name": "אובדן כושר עבודה",
        "description": "קצבה במקרה של אובדן יכולת עבודה",
        "includes": ["קצבה חודשית", "שיקום תעסוקתי", "הכשרה מקצועית"],
        "reimbursement": {
            "קצבה": "50-75% מהשכר",
            "תקופת תשלום": "עד גיל פרישה"
        },
        "limits": {"חודשי": "עד 20,000 ש\"ח", "תקופה": "עד פרישה"},
        "notes": "לאחר תקופת המתנה"
    }
}

def get_nispach_info(nispach_number):
    """Get information about a specific nispach"""
    # Clean the nispach number (remove common separators)
    clean_number = nispach_number.replace("/", "").replace("-", "").replace(" ", "")
    
    # Try to find the nispach
    if clean_number in NISPACH_INFO:
        return NISPACH_INFO[clean_number]
    
    # Try to find partial match (e.g., "5420" in "5420/8713")
    for key in NISPACH_INFO.keys():
        if key in clean_number or clean_number in key:
            return NISPACH_INFO[key]
    
    return None

def search_nispach_online(nispach_number, query_context=""):
    """Search for nispach information online using web_search"""
    try:
        # Import web_search if available
        from anthropic import Anthropic
        
        search_query = f"נספח {nispach_number} ביטוח בריאות {query_context}"
        
        # Note: This would require web_search tool integration
        # For now, return None - will be implemented when tool is available
        return None
    except:
        return None

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def extract_text_from_pdf(pdf_file_or_bytes):
    """Extract text from PDF with improved handling for different formats"""
    if not PDF_SUPPORT: 
        return "❌ PDF support not available", 0
    
    try:
        text = ""
        page_count = 0
        
        # Handle both file objects and bytes
        if isinstance(pdf_file_or_bytes, bytes):
            import io
            pdf_file_or_bytes = io.BytesIO(pdf_file_or_bytes)
        
        with pdfplumber.open(pdf_file_or_bytes) as pdf:
            page_count = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                try:
                    # Try extracting text
                    page_text = page.extract_text()
                    
                    # If no text, try extracting tables
                    if not page_text or len(page_text.strip()) < 20:
                        tables = page.extract_tables()
                        if tables:
                            page_text = ""
                            for table in tables:
                                for row in table:
                                    if row:
                                        page_text += " | ".join([str(cell) if cell else "" for cell in row]) + "\n"
                    
                    if page_text:
                        text += f"=== עמוד {i+1} ===\n{page_text}\n\n---PAGE_BREAK---\n\n"
                    else:
                        text += f"=== עמוד {i+1} ===\n[לא נמצא טקסט בעמוד זה]\n\n---PAGE_BREAK---\n\n"
                        
                except Exception as page_error:
                    text += f"=== עמוד {i+1} ===\n[שגיאה בחילוץ עמוד: {str(page_error)}]\n\n---PAGE_BREAK---\n\n"
        
        # Check if we extracted meaningful content
        if len(text.strip()) < 100:
            return "⚠️ לא הצלחנו לחלץ טקסט מספיק מה-PDF. ייתכן שהוא מבוסס תמונות או בפורמט לא נתמך.", page_count
        
        return text, page_count
        
    except Exception as e:
        return f"❌ שגיאה בקריאת PDF: {str(e)}", 0

def detect_company(text):
    """Detect insurance company from PDF text with priority indicators"""
    text_lower = text.lower()
    
    # Priority 1: Check for company-specific websites and emails (most reliable)
    if 'fnx.co.il' in text_lower or 'myinfo.fnx' in text_lower:
        return "הפניקס"
    elif 'clal.co.il' in text_lower or 'clalbit.co.il' in text_lower or 'bit.clal.co.il' in text_lower or '@clal-ins.co.il' in text_lower or 'clal-ins.co.il' in text_lower:
        return "כלל"
    elif 'harel-group.co.il' in text_lower or 'hrl.co.il' in text_lower:
        return "הראל"
    elif 'migdal.co.il' in text_lower:
        return "מגדל"
    elif 'menoramivt.co.il' in text_lower:
        return "מנורה"
    elif 'ayalon-ins.co.il' in text_lower:
        return "איילון"
    
    # Priority 2: Check for company phone numbers
    if '3455*' in text or '*3455' in text or '03-7332222' in text:
        return "הפניקס"
    elif '*2800' in text or '2800*' in text or '03-6376666' in text or '077-6383290' in text or '6136902' in text:
        return "כלל"
    elif '*2407' in text or '2407*' in text:
        return "הראל"
    elif '*2679' in text or '2679*' in text:
        return "מגדל"
    elif '*2000' in text or '2000*' in text:
        return "מנורה"
    elif '*5620' in text or '5620*' in text:
        return "איילון"
    
    # Priority 3: Check for unique company identifiers
    if 'כלל חברה לביטוח' in text or 'כלל תכנית הגריאטריות' in text or 'ביטוח וסיכונים' in text:
        return "כלל"
    
    # Priority 4: Check for company names (less reliable)
    if 'פניקס' in text or 'הפניקס' in text or 'phoenix' in text_lower or 'fnx' in text_lower:
        return "הפניקס"
    elif 'כלל ביטוח' in text or 'clalbit' in text_lower or 'clal insurance' in text_lower:
        return "כלל"
    elif 'הראל' in text or 'harel' in text_lower:
        return "הראל"
    elif 'מגדל' in text or 'migdal' in text_lower:
        return "מגדל"
    elif 'מנורה' in text or 'menora' in text_lower or 'מנורה מבטחים' in text:
        return "מנורה"
    elif 'איילון' in text or 'ayalon' in text_lower:
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
    # Initialize Supabase
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        st.error("⚠️ Supabase credentials not configured!")
        st.stop()
    
    db = SupabaseDatabase(url=url, key=key)
    # storage_client = SupabaseStorage(url=url, key=key)  # Not used - using local storage for PDFs
    
    # Initialize Claude
    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").strip()
    claude = None
    if api_key:
        try: claude = Anthropic(api_key=api_key)
        except: pass
    
    return db, claude

db, claude_client = init_connections()

# LOGIN / REGISTER PAGE
if not st.session_state.authenticated:
    st.title("🔐 השוואת פוליסות ביטוח")
    
    tab1, tab2, tab3 = st.tabs(["🔑 כניסה", "✨ הרשמה", "🔓 שכחתי סיסמה"])
    
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
    
    with tab3:
        st.subheader("איפוס סיסמה")
        
        # Initialize reset state
        if 'reset_step' not in st.session_state:
            st.session_state.reset_step = 1
        if 'reset_email' not in st.session_state:
            st.session_state.reset_email = None
        if 'reset_code_generated' not in st.session_state:
            st.session_state.reset_code_generated = None
        
        if st.session_state.reset_step == 1:
            # Step 1: Enter email
            st.write("הזן את כתובת האימייל שלך לקבלת קוד איפוס")
            
            with st.form("reset_email_form"):
                reset_email = st.text_input("אימייל")
                send_code = st.form_submit_button("שלח קוד", type="primary", use_container_width=True)
                
                if send_code:
                    if reset_email:
                        code, error = db.create_reset_code(reset_email)
                        if code:
                            st.session_state.reset_code_generated = code
                            st.session_state.reset_email = reset_email
                            st.session_state.reset_step = 2
                            st.success(f"✅ קוד נשלח!")
                            st.info(f"🔢 **קוד האיפוס שלך:** {code}")
                            st.caption("(במציאות יישלח למייל - זה רק לדמו)")
                            st.rerun()
                        else:
                            st.error(error)
                    else:
                        st.warning("נא להזין אימייל")
        
        elif st.session_state.reset_step == 2:
            # Step 2: Enter code and new password
            st.write(f"קוד נשלח ל: **{st.session_state.reset_email}**")
            st.info(f"🔢 הקוד שלך: **{st.session_state.reset_code_generated}**")
            
            with st.form("reset_password_form"):
                reset_code_input = st.text_input("קוד איפוס (6 ספרות)")
                new_pass = st.text_input("סיסמה חדשה", type="password")
                new_pass_confirm = st.text_input("אישור סיסמה חדשה", type="password")
                reset_submit = st.form_submit_button("אפס סיסמה", type="primary", use_container_width=True)
                
                if reset_submit:
                    if not all([reset_code_input, new_pass, new_pass_confirm]):
                        st.warning("נא למלא את כל השדות")
                    elif new_pass != new_pass_confirm:
                        st.error("הסיסמאות לא תואמות")
                    elif len(new_pass) < 6:
                        st.error("הסיסמה חייבת להכיל לפחות 6 תווים")
                    else:
                        valid, user_id = db.verify_reset_code(st.session_state.reset_email, reset_code_input)
                        if valid:
                            db.reset_password(user_id, new_pass, reset_code_input)
                            st.success("✅ הסיסמה אופסה בהצלחה!")
                            st.info("עבור ללשונית 'כניסה' כדי להתחבר")
                            # Reset state
                            st.session_state.reset_step = 1
                            st.session_state.reset_email = None
                            st.session_state.reset_code_generated = None
                        else:
                            st.error(user_id)  # Error message
            
            if st.button("ביטול", use_container_width=True):
                st.session_state.reset_step = 1
                st.session_state.reset_email = None
                st.session_state.reset_code_generated = None
                st.rerun()
    
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
                    # Delete all local files for this investigation
                    try:
                        policies = db.get_policies(st.session_state.current_investigation_id)
                        for pol in policies:
                            if pol.get('file_path') and os.path.exists(pol['file_path']):
                                os.remove(pol['file_path'])
                    except Exception as e:
                        pass  # Files might already be deleted
                    
                    # Delete from database
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
pages = ["🏠 בית", "📥 איך להשיג פוליסות", "📤 העלאה", "❓ שאלות", "📚 מדריך נספחים", "⚖️ השוואה", "📜 היסטוריה"]
if st.session_state.username == "admin":
    pages.append("👑 ניהול")

for page in pages:
    if st.sidebar.button(page, use_container_width=True, key=f"nav_{page}"):
        st.session_state.page = page

# MAIN CONTENT
if not st.session_state.current_investigation_id and st.session_state.page not in ["🏠 בית", "📥 איך להשיג פוליסות", "📚 מדריך נספחים", "👑 ניהול"]:
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

elif st.session_state.page == "📥 איך להשיג פוליסות":
    st.title("📥 איך להשיג את הפוליסות שלך")
    st.write("מדריך פשוט לקבלת פוליסות מכל חברות הביטוח")
    
    st.markdown("---")
    
    # Introduction
    st.info("💡 **טיפ:** רוב חברות הביטוח מאפשרות להוריד את הפוליסות שלך דרך האזור האישי באתר")
    
    st.markdown("---")
    
    # Migdal
    with st.expander("🏢 מגדל - Migdal"):
        st.markdown("""
        ### שלבים לקבלת הפוליסה:
        
        1. **כנס לאתר:** [www.migdal.co.il](https://www.migdal.co.il)
        2. **התחבר לאזור האישי** (למעלה בצד ימין)
        3. **לחץ על "הפוליסות שלי"**
        4. **בחר את הפוליסה** שרוצה להוריד
        5. **לחץ על "הורד פוליסה"** או "PDF"
        
        📞 **מוקד שירות:** *2679
        📧 **אימייל:** info@migdal.co.il
        """)
    
    # Harel
    with st.expander("🏢 הראל - Harel"):
        st.markdown("""
        ### שלבים לקבלת הפוליסה:
        
        1. **כנס לאתר:** [www.harel-group.co.il](https://www.harel-group.co.il)
        2. **התחבר לאזור האישי**
        3. **לחץ על "הפוליסות שלי"**
        4. **בחר "ביטוח בריאות" / "חיסכון" / "פנסיה"** (לפי סוג הפוליסה)
        5. **הורד PDF של הפוליסה**
        
        📞 **מוקד שירות:** *2407
        📧 **אימייל:** service@harel-group.co.il
        """)
    
    # Clal
    with st.expander("🏢 כלל - Clal"):
        st.markdown("""
        ### שלבים לקבלת הפוליסה:
        
        1. **כנס לאתר:** [www.clalbit.co.il](https://www.clalbit.co.il)
        2. **התחבר לאזור האישי**
        3. **בחר "הפוליסות שלי"**
        4. **לחץ על הפוליסה הרלוונטית**
        5. **הורד את קובץ ה-PDF**
        
        📞 **מוקד שירות:** *2800
        📧 **אימייל:** digital@clalbit.co.il
        """)
    
    # Menora
    with st.expander("🏢 מנורה - Menora"):
        st.markdown("""
        ### שלבים לקבלת הפוליסה:
        
        1. **כנס לאתר:** [www.menoramivt.co.il](https://www.menoramivt.co.il)
        2. **התחבר לאזור האישי**
        3. **לחץ על "הפוליסות שלי"**
        4. **בחר את סוג הביטוח** (בריאות/חיים/פנסיה)
        5. **הורד את הפוליסה בפורמט PDF**
        
        📞 **מוקד שירות:** *2000
        📧 **אימייל:** moked-health@menora.co.il
        """)
    
    # Phoenix
    with st.expander("🏢 הפניקס - Phoenix"):
        st.markdown("""
        ### שלבים לקבלת הפוליסה:
        
        1. **כנס לאתר:** [www.fnx.co.il](https://www.fnx.co.il)
        2. **התחבר לאזור האישי**
        3. **בחר "הפוליסות שלי"**
        4. **לחץ על הפוליסה שרוצה לראות**
        5. **הורד PDF**
        
        📞 **מוקד שירות:** *6836
        📧 **אימייל:** service@fnx.co.il
        """)
    
    # Ayalon
    with st.expander("🏢 איילון - Ayalon"):
        st.markdown("""
        ### שלבים לקבלת הפוליסה:
        
        1. **כנס לאתר:** [www.ayalon-ins.co.il](https://www.ayalon-ins.co.il)
        2. **התחבר לאזור האישי**
        3. **לחץ על "פוליסות"**
        4. **בחר את הפוליסה הרלוונטית**
        5. **הורד כ-PDF**
        
        📞 **מוקד שירות:** *5620
        📧 **אימייל:** digital@ayalon-ins.co.il
        """)
    
    st.markdown("---")
    
    # Alternative method - Har Habituch
    st.markdown("### 🏔️ דרך נוספת: הר הביטוח")
    st.info("""
    **הר הביטוח** הוא אתר ממשלתי שמאפשר לראות את **כל הפוליסות** שלך ממקום אחד!
    
    🔗 **כניסה:** [www.har-habituh.gov.il](https://www.har-habituh.gov.il)
    
    **איך זה עובד:**
    1. כניסה עם תעודת זהות
    2. כל הפוליסות שלך במקום אחד
    3. אפשרות להוריד PDF של כל פוליסה
    """)
    
    st.markdown("---")
    
    # Tips
    st.markdown("### 💡 טיפים חשובים")
    st.success("""
    ✅ **וודא שהפוליסה מעודכנת** - בדוק שהתאריך עדכני
    
    ✅ **שמור את כל העמודים** - לפעמים יש מספר קבצים
    
    ✅ **בעיות בהתחברות?** - פנה למוקד השירות, הם ישלחו לך במייל
    
    ✅ **אין לך גישה לאינטרנט?** - אפשר להתקשר ולבקש שישלחו במייל
    """)
    
    st.markdown("---")
    
    # Need help
    st.markdown("### 🆘 צריך עזרה?")
    st.write("אם אתה מתקשה להשיג את הפוליסות, אנחנו כאן לעזור!")
    st.write("📧 צור קשר עם הסוכן שלך או עם מוקד השירות של חברת הביטוח")

elif st.session_state.page == "📤 העלאה":
    st.title("📤 העלאה")
    
    inv = db.get_investigation(st.session_state.current_investigation_id)
    st.info(f"📍 לקוח: **{inv['client_name']}**")
    
    uploaded_file = st.file_uploader("PDF", type=['pdf'])
    
    if uploaded_file:
        with st.spinner("מעבד..."):
            try:
                # Get file bytes
                file_bytes = uploaded_file.getvalue()
                
                # Extract text from bytes directly
                text, total_pages = extract_text_from_pdf(file_bytes)
                
                # Check if extraction failed
                if not text or text.startswith("❌") or text.startswith("⚠️"):
                    st.error(text if text else "לא הצלחנו לקרוא את הקובץ")
                    st.warning("💡 טיפים:")
                    st.markdown("""
                    - ודא שהקובץ אינו מוגן בסיסמה
                    - ודא שהקובץ מכיל טקסט (לא רק תמונות)
                    - נסה לשמור את הקובץ מחדש מהמקור
                    """)
                else:
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
                    st.info(f"📄 {total_pages} עמודים | {len(text)} תווים")
                    
                    with st.form("form"):
                        company = st.selectbox("חברה", COMPANIES, 
                                              index=COMPANIES.index(detected_company) if detected_company in COMPANIES else 0)
                        custom_name = st.text_input("שם הפוליסה", value=auto_name,
                                                   help="השם שיוצג ברשימה")
                        
                        if st.form_submit_button("💾 שמור", type="primary"):
                            # Save PDF locally (Supabase Storage has issues with PDFs in free tier)
                            safe_filename = f"{company}_{uuid.uuid4().hex[:8]}.pdf"
                            file_path = os.path.join(UPLOAD_DIR, safe_filename)
                            
                            # Write file to local storage
                            with open(file_path, 'wb') as f:
                                f.write(file_bytes)
                            
                            chunks = create_chunks(text)
                            
                            policy_id = db.insert_policy(
                                st.session_state.current_investigation_id,
                                company,
                                uploaded_file.name,
                                custom_name,
                                file_path,
                                total_pages
                            )
                            db.insert_chunks(policy_id, chunks)
                            
                            st.success(f"✅ נשמר: **{custom_name}**")
                            st.balloons()
                            
                            st.rerun()
            
            except Exception as e:
                st.error(f"❌ שגיאה בעיבוד הקובץ: {str(e)}")
    
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
                        # Delete local file
                        try:
                            if pol.get('file_path') and os.path.exists(pol['file_path']):
                                os.remove(pol['file_path'])
                        except Exception as e:
                            pass  # File might already be deleted
                        
                        # Delete from database
                        db.delete_policy(pol['id'])
                        st.success("נמחק!")
                        st.rerun()
    else:
        st.info(f"אין פוליסות עבור {inv['client_name']}")
        st.caption("העלה PDF כדי להתחיל")

elif st.session_state.page == "❓ שאלות":
    st.title("❓ שאלות")
    
    # Mode selector
    mode = st.radio(
        "בחר סוג שאלה:",
        ["📄 שאל על הפוליסות שלי", "🌐 מידע כללי על ביטוחים"],
        horizontal=True
    )
    
    if mode == "📄 שאל על הפוליסות שלי":
        # Original functionality - questions about uploaded policies
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
                            # Check if question is about a specific nispach
                            import re
                            nispach_match = re.search(r'נספח\s*(\d+[/-]?\d*)', query)
                            nispach_info_text = ""
                        
                            if nispach_match:
                                nispach_number = nispach_match.group(1)
                                nispach_data = get_nispach_info(nispach_number)
                                
                                if nispach_data:
                                    # Build detailed nispach info including reimbursement
                                    nispach_info_text = f"""

📋 מידע כללי על נספח {nispach_number} - {nispach_data['name']}:

תיאור: {nispach_data['description']}

כולל:
{chr(10).join(['- ' + item for item in nispach_data['includes']])}

💰 שיעורי החזר:
{chr(10).join([f'- {k}: {v}' for k, v in nispach_data.get('reimbursement', {}).items()])}

📊 מגבלות:
{chr(10).join([f'- {k}: {v}' for k, v in nispach_data.get('limits', {}).items()])}

💡 הערות: {nispach_data['notes']}
"""
                            
                            # Also check for specific services mentioned (MRI, CT, etc.)
                            services_mentioned = []
                            if any(word in query.lower() for word in ['mri', 'אם.אר.איי', 'מגנט']):
                                services_mentioned.append('MRI')
                            if any(word in query.lower() for word in ['ct', 'סי.טי', 'ציאוטי']):
                                services_mentioned.append('CT')
                            if 'מעבדה' in query or 'בדיקות דם' in query:
                                services_mentioned.append('בדיקות מעבדה')
                            if 'ייעוץ' in query or 'מומחה' in query:
                                services_mentioned.append('ייעוץ מומחה')
                            
                            # If services are mentioned, add relevant nispach info
                            if services_mentioned and not nispach_match:
                                # Find relevant nispachim
                                relevant_nispachim = []
                                for num, data in NISPACH_INFO.items():
                                    for service in services_mentioned:
                                        if service in str(data.get('reimbursement', {})):
                                            relevant_nispachim.append((num, data, service))
                                            break
                                
                                if relevant_nispachim:
                                    nispach_info_text += "\n\n🔍 נספחים רלוונטיים:\n"
                                    for num, data, service in relevant_nispachim[:3]:  # Limit to 3
                                        reimbursement_info = data.get('reimbursement', {}).get(service, 'לא צוין')
                                        nispach_info_text += f"\n- נספח {num} ({data['name']}): {service} - {reimbursement_info}"
                            
                            selected_ids = [policy_options[name] for name in selected_names]
                            all_contexts = []
                            
                            for name, pol_id in zip(selected_names, selected_ids):
                                chunks = db.search_chunks(pol_id, query, top_k=10)
                                if chunks:
                                    context = f"=== פוליסה: {name} ===\n" + "\n\n".join([c['text'] for c in chunks[:5]])
                                    all_contexts.append(context)
                            
                            if all_contexts or nispach_info_text:
                                combined = "\n\n".join(all_contexts) if all_contexts else ""
                                
                                system_prompt = """אתה מומחה ביטוח ישראלי. חלץ מידע מדויק מפוליסות.

כללים:
1. חפש טבלאות מחירים והצג אותן במדויק
2. אל תמציא מידע
3. **אם השאלה היא "איזו פוליסה זו?" או "מה זה?" - תן תשובה ברורה ומדויקת על הפוליסה הספציפית**
4. אם אין מידע בפוליסה אבל יש מידע כללי - הסבר זאת בבירור
5. ענה בעברית פשוטה וברורה
6. השווה בין פוליסות אם יש יותר מאחת
7. אם יש מידע על שיעורי החזר - הצג אותו בבירור
8. הפרד בין מידע ספציפי מהפוליסה למידע כללי

**חשוב במיוחד:**
- אם שואלים "איזו פוליסה זו?" - זהה את שם הפוליסה, מספר הפוליסה, חברת הביטוח והנספחים
- אם שואלים על נספח ספציפי - אשר שהוא קיים בפוליסה ותן פרטים ממנה

פורמט תשובה מומלץ:
### 📄 מה נמצא בפוליסה
[מידע ספציפי מהפוליסה שהועלתה - כולל מספר פוליסה, חברה, נספחים]

### 💡 מידע כללי על הנספח
[מידע נוסף רלוונטי]

### 💰 שיעורי החזר
[פירוט שיעורי החזר אם ידועים]"""
                                
                                user_content = f"""שאלה: {query}

תוכן מהפוליסות:
{combined if combined else "(לא נמצא מידע ספציפי בפוליסה)"}
{nispach_info_text}

ענה בדיוק על סמך המידע. אם יש מידע כללי על נספח, הוסף אותו בסוף התשובה.
אם השאלה היא על שיעורי החזר או מגבלות - הדגש את המידע הזה בתשובה."""
                                
                                response = claude_client.messages.create(
                                    model="claude-sonnet-4-20250514",
                                    max_tokens=1800,
                                    system=system_prompt,
                                    messages=[{"role": "user", "content": user_content}]
                                )
                                
                                answer = response.content[0].text
                                st.markdown("### 💡 תשובה:")
                                st.success(answer)
                                
                                db.save_qa(st.session_state.current_investigation_id, query, answer, selected_names)
                            else:
                                st.warning("❌ לא נמצא מידע רלוונטי")
                        except Exception as e:
                            st.error(f"❌ שגיאה: {str(e)}")
    
    else:  # General information mode
        st.info("💡 **במצב זה אתה יכול לשאול שאלות כלליות על ביטוחים ללא צורך בפוליסות**")
        
        # Optional: Select specific companies to compare
        with st.expander("🏢 השווה חברות ספציפיות (אופציונלי)"):
            selected_companies = st.multiselect(
                "בחר חברות להשוואה:",
                COMPANIES,
                help="השאר ריק לשאלה כללית על כל השוק"
            )
        
        # Example questions
        with st.expander("📝 דוגמאות לשאלות"):
            st.markdown("""
            - מה ההבדל בין מגדל להראל בביטוח בריאות?
            - כמה עולה ביטוח בריאות מקיף לגיל 35?
            - מה הכיסויים החשובים ביותר בביטוח בריאות?
            - האם כדאי להוסיף נספח ניתוחים בחו״ל?
            - מהן החברות עם השירות הטוב ביותר?
            - השוואת מחירים בין החברות הגדולות
            - מה זה נספח אמבולטורי ולמה אני צריך אותו?
            """)
        
        query = st.text_area(
            "שאל שאלה כללית:",
            placeholder="לדוגמה: מה ההבדל בין מגדל להראל?",
            height=100
        )
        
        if st.button("🔍 שאל", type="primary") and query and claude_client:
            with st.spinner("מחפש מידע..."):
                try:
                    # Build context with company info if specific companies selected
                    company_context = ""
                    if selected_companies:
                        company_context = "\n\nמידע על החברות שנבחרו:\n"
                        for company in selected_companies:
                            if company in COMPANIES_INFO:
                                info = COMPANIES_INFO[company]
                                company_context += f"""
\n{company} ({info['full_name']}):
- אתר: {info['website']}
- טלפון: {info['phone']}
- יתרונות: {', '.join(info['strengths'])}
- ידועה ב: {', '.join(info['known_for'])}
"""
                    
                    # Add nispach info if question mentions specific nispach
                    import re
                    nispach_match = re.search(r'נספח\s*(\d+[/-]?\d*)', query)
                    nispach_context = ""
                    
                    if nispach_match:
                        nispach_number = nispach_match.group(1)
                        nispach_data = get_nispach_info(nispach_number)
                        if nispach_data:
                            nispach_context = f"""
\nמידע על נספח {nispach_number} - {nispach_data['name']}:
תיאור: {nispach_data['description']}
כולל: {', '.join(nispach_data['includes'])}
שיעורי החזר: {', '.join([f'{k}: {v}' for k, v in nispach_data.get('reimbursement', {}).items()])}
מגבלות: {', '.join([f'{k}: {v}' for k, v in nispach_data.get('limits', {}).items()])}
"""
                    
                    # Check for service mentions
                    services_context = ""
                    if any(word in query.lower() for word in ['mri', 'ct', 'בדיקה', 'ייעוץ', 'טיפול']):
                        services_context = "\n\nמידע נוסף מבסיס הנתונים שלנו:\n"
                        for num, data in list(NISPACH_INFO.items())[:5]:  # Top 5 relevant
                            services_context += f"- נספח {num} ({data['name']}): {data['description']}\n"
                    
                    system_prompt = """אתה יועץ ביטוח מקצועי ישראלי. תפקידך לספק מידע כללי ומקצועי על ביטוחים.

כללים:
1. ספק מידע מבוסס על הידע שלך ועל המידע שנמסר לך
2. אם מדובר בהשוואה בין חברות - היה אובייקטיבי
3. הסבר מושגים בצורה פשוטה וברורה
4. ציין אם המידע הוא כללי או משתנה בין חברות
5. המלץ תמיד לבדוק עם חברת הביטוח את הפרטים המדויקים
6. אם יש מידע על מחירים - תן טווחים כלליים
7. הדגש את הנקודות החשובות ביותר

פורמט תשובה מומלץ:
### 📋 תשובה
[תשובה ישירה לשאלה]

### 💡 מידע נוסף
[פרטים רלוונטיים נוספים]

### ⚠️ חשוב לזכור
[נקודות חשובות להתייחסות]"""
                    
                    user_content = f"""שאלה: {query}
{company_context}
{nispach_context}
{services_context}

ענה על השאלה בצורה מקצועית ומפורטת. אם יש מידע ספציפי על חברות או נספחים - שלב אותו בתשובה."""
                    
                    response = claude_client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=2000,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_content}]
                    )
                    
                    answer = response.content[0].text
                    st.markdown("### 💡 תשובה:")
                    st.success(answer)
                    
                    # Save to history with special marker for general questions
                    db.save_qa(st.session_state.current_investigation_id, query, answer, ["מידע כללי"])
                    
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

elif st.session_state.page == "📚 מדריך נספחים":
    st.title("📚 מדריך נספחים - מה כל נספח מכסה?")
    st.write("מידע מפורט על נספחים נפוצים בפוליסות ביטוח בריאות")
    
    st.markdown("---")
    
    # Search box
    search_term = st.text_input("🔍 חפש נספח לפי מספר או שם:", placeholder="לדוגמה: 8713 או אבחנה מהירה")
    
    if search_term:
        # Search in nispach database
        found_nispachim = []
        search_lower = search_term.lower()
        
        for nispach_num, data in NISPACH_INFO.items():
            if (search_term in nispach_num or 
                search_lower in data['name'].lower() or 
                search_lower in data['description'].lower()):
                found_nispachim.append((nispach_num, data))
        
        if found_nispachim:
            st.success(f"נמצאו {len(found_nispachim)} תוצאות:")
            for nispach_num, data in found_nispachim:
                with st.expander(f"📋 נספח {nispach_num} - {data['name']}", expanded=True):
                    st.markdown(f"**תיאור:** {data['description']}")
                    st.markdown("**כולל:**")
                    for item in data['includes']:
                        st.markdown(f"- {item}")
                    
                    # Show reimbursement info
                    if 'reimbursement' in data:
                        st.markdown("**💰 שיעורי החזר:**")
                        for service, amount in data['reimbursement'].items():
                            st.markdown(f"- {service}: **{amount}**")
                    
                    # Show limits
                    if 'limits' in data:
                        st.markdown("**📊 מגבלות:**")
                        for limit_type, limit_value in data['limits'].items():
                            st.markdown(f"- {limit_type}: {limit_value}")
                    
                    st.info(f"💡 {data['notes']}")
        else:
            st.warning("לא נמצאו תוצאות. נסה מספר נספח אחר או מילת חיפוש אחרת.")
    
    st.markdown("---")
    st.markdown("### 📑 רשימת כל הנספחים")
    
    # Group nispachim by category
    categories = {
        "🏥 כיסויים בסיסיים": ["5420", "5413", "7401"],
        "🔬 אבחון וייעוץ": ["8713", "799712", "6650"],
        "✈️ טיפולים בחו\"ל": ["5409", "5404", "5408"],
        "💊 תרופות": ["6417", "5406"],
        "🌿 רפואה משלימה": ["6792", "799716"],
        "⚕️ ניתוחים": ["6784", "7401"],
        "🦷 שיניים וסיעוד": ["5411", "6800"],
        "❤️ מחלות קשות": ["773755"],
        "💼 אובדן כושר עבודה": ["5415"]
    }
    
    for category, nispach_list in categories.items():
        st.markdown(f"### {category}")
        for nispach_num in nispach_list:
            if nispach_num in NISPACH_INFO:
                data = NISPACH_INFO[nispach_num]
                with st.expander(f"נספח {nispach_num} - {data['name']}"):
                    st.markdown(f"**תיאור:** {data['description']}")
                    st.markdown("**כולל:**")
                    for item in data['includes']:
                        st.markdown(f"- {item}")
                    
                    # Show reimbursement info
                    if 'reimbursement' in data:
                        st.markdown("**💰 שיעורי החזר:**")
                        for service, amount in data['reimbursement'].items():
                            st.markdown(f"- {service}: **{amount}**")
                    
                    # Show limits
                    if 'limits' in data:
                        st.markdown("**📊 מגבלות:**")
                        for limit_type, limit_value in data['limits'].items():
                            st.markdown(f"- {limit_type}: {limit_value}")
                    
                    st.info(f"💡 {data['notes']}")
        st.markdown("---")
    
    # Disclaimer
    st.caption("""
    ⚠️ **הערה חשובה:** המידע המוצג כאן הוא כללי ועשוי להשתנות בין חברות ביטוח שונות ובין פוליסות שונות.
    תמיד יש לבדוק את הפרטים המדויקים בפוליסה עצמה או ליצור קשר עם חברת הביטוח.
    """)

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
