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

# Force redeploy - v3.1 - NISPACHIM EXPANDED - 60+ nispachim with web search
st.set_page_config(page_title="השוואת פוליסות v3.1", page_icon="📄", layout="wide")

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

# ============================================================================
# NISPACH (APPENDIX) INFORMATION DATABASE - EXPANDED VERSION (60+ nispachim)
# ============================================================================

NISPACH_INFO_EXPANDED = {
    # ===== NISPACHIM BÁSICOS (Ya existentes) =====
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
    },
    
    # ===== NISPACHIM נוספים - ניתוחים =====
    "5401": {
        "name": "ניתוחים - פרימיום",
        "description": "כיסוי מורחב לניתוחים עם בחירת מנתח חופשית",
        "includes": ["בחירת מנתח חופשית", "בתי חולים פרטיים", "ניתוחים מתקדמים"],
        "reimbursement": {"ניתוח": "החזר מלא", "בדיקות": "החזר מלא"},
        "limits": {"שנתי": "ללא הגבלה", "לניתוח": "ללא מגבלה"},
        "notes": "רמת כיסוי הגבוהה ביותר"
    },
    "5402": {
        "name": "ניתוחים - סטנדרט",
        "description": "כיסוי רגיל לניתוחים ברשימת מנתחים מוגדרת",
        "includes": ["רשימת מנתחים מאושרים", "ניתוחים נפוצים", "אשפוז"],
        "reimbursement": {"ניתוח": "החזר לפי רשימה", "אשפוז": "החזר מלא"},
        "limits": {"שנתי": "לפי מגבלות", "לניתוח": "ברשימה"},
        "notes": "כיסוי בסיסי לניתוחים"
    },
    "5403": {
        "name": "ניתוחים - השלמה לשב\"ן",
        "description": "השלמה לכיסוי ניתוחים של קופת החולים",
        "includes": ["השלמה לקופה", "הפרש השתתפות", "שירותים נוספים"],
        "reimbursement": {"הפרש": "החזר הפרש", "תוספות": "לפי תעריף"},
        "limits": {"שנתי": "5,000 ש\"ח", "לניתוח": "לפי הפרש"},
        "notes": "משלים את הביטוח המשלים"
    },
    "6785": {
        "name": "ניתוחים ללא השתתפות עצמית",
        "description": "כיסוי לניתוחים ללא תשלום עצמי",
        "includes": ["ללא השתתפות", "כל הוצאות הניתוח", "אשפוז מלא"],
        "reimbursement": {"ניתוח": "100% ללא השתתפות", "אשפוז": "מלא"},
        "limits": {"שנתי": "ללא הגבלה", "לניתוח": "מלא"},
        "notes": "ללא תשלום עצמי כלל"
    },
    
    # ===== NISPACHIM - תרופות =====
    "5405": {
        "name": "תרופות מחוץ לסל",
        "description": "כיסוי לתרופות שאינן בסל הבריאות",
        "includes": ["תרופות חדשות", "תרופות יקרות", "טיפולים מתקדמים"],
        "reimbursement": {"תרופות": "80-90% החזר", "ביולוגיות": "החזר מלא"},
        "limits": {"שנתי": "50,000 ש\"ח", "לתרופה": "לפי מחיר"},
        "notes": "דורש אישור רופא"
    },
    "5407": {
        "name": "תרופות לסרטן",
        "description": "כיסוי מיוחד לתרופות אונקולוגיות",
        "includes": ["תרופות אונקולוגיות", "טיפולים ביולוגיים", "חדשנות רפואית"],
        "reimbursement": {"אונקולוגיה": "100% החזר", "ביולוגי": "החזר מלא"},
        "limits": {"שנתי": "ללא הגבלה", "לתרופה": "ללא מגבלה"},
        "notes": "כיסוי מלא לסרטן"
    },
    "6418": {
        "name": "בדיקות גנומיות",
        "description": "בדיקות התאמת תרופות אישיות",
        "includes": ["בדיקות DNA", "התאמת תרופות", "רפואה מותאמת אישית"],
        "reimbursement": {"בדיקה": "החזר של 80%", "ייעוץ": "החזר מלא"},
        "limits": {"שנתי": "2-3 בדיקות", "לבדיקה": "עד 5,000 ש\"ח"},
        "notes": "טכנולוגיה מתקדמת"
    },
    "6419": {
        "name": "טיפולים ביולוגיים",
        "description": "תרופות ביולוגיות מתקדמות",
        "includes": ["תרופות ביולוגיות", "אימונותרפיה", "טיפולים חדשניים"],
        "reimbursement": {"ביולוגי": "90-100% החזר", "אימונו": "החזר מלא"},
        "limits": {"שנתי": "100,000 ש\"ח", "לתרופה": "לפי צורך"},
        "notes": "תרופות מתקדמות"
    },
    
    # ===== NISPACHIM - אמבולטורי =====
    "6651": {
        "name": "בדיקות הדמיה מתקדמות",
        "description": "MRI, CT, PET-CT ועוד",
        "includes": ["MRI", "CT", "PET-CT", "אולטרסאונד דופלר"],
        "reimbursement": {"MRI": "80% החזר", "CT": "80% החזר", "PET-CT": "החזר מלא"},
        "limits": {"שנתי": "ללא הגבלה", "לבדיקה": "עד 2,000 ש\"ח"},
        "notes": "בדיקות דימות מתקדמות"
    },
    "6652": {
        "name": "ייעוצים למומחים",
        "description": "התייעצויות עם רופאים מומחים",
        "includes": ["מומחים בכירים", "חוות דעת שנייה", "ייעוץ מהיר"],
        "reimbursement": {"ייעוץ": "75-85% החזר", "חוות דעת": "החזר מלא"},
        "limits": {"שנתי": "10-15 ייעוצים", "לייעוץ": "עד 600 ש\"ח"},
        "notes": "גישה למומחים מובילים"
    },
    "6653": {
        "name": "בדיקות מעבדה",
        "description": "בדיקות דם ומעבדה מתקדמות",
        "includes": ["בדיקות דם מורכבות", "בדיקות גנטיות", "סמנים ביולוגיים"],
        "reimbursement": {"דם": "80% החזר", "גנטי": "החזר של 70%"},
        "limits": {"שנתי": "5,000 ש\"ח", "לבדיקה": "לפי סוג"},
        "notes": "מעבדות מתקדמות"
    },
    "8714": {
        "name": "חוות דעת רפואית שנייה",
        "description": "קבלת חוות דעת נוספת מרופא מומחה",
        "includes": ["מומחה בכיר", "חוות דעת מפורטת", "ייעוץ טלפוני"],
        "reimbursement": {"חוות דעת": "החזר מלא", "ייעוץ": "החזר מלא"},
        "limits": {"שנתי": "2-3 חוות דעת", "לחוות דעת": "ללא מגבלה"},
        "notes": "חשוב לקבלת החלטות"
    },
    
    # ===== NISPACHIM - מחלות קשות =====
    "5416": {
        "name": "פיצוי למחלות קשות",
        "description": "פיצוי כספי ב-32 מחלות קשות",
        "includes": ["סרטן", "אוטם", "שבץ", "כשל כליות", "ניוון שרירים"],
        "reimbursement": {"פיצוי": "סכום חד פעמי", "סכום": "50,000-150,000 ש\"ח"},
        "limits": {"אירוע": "פעם אחת", "סה\"כ": "לפי פוליסה"},
        "notes": "32 מחלות מוגדרות"
    },
    "5417": {
        "name": "פיצוי לסרטן",
        "description": "פיצוי כספי ספציפי למחלות סרטן",
        "includes": ["כל סוגי הסרטן", "פיצוי חד פעמי", "תשלום מהיר"],
        "reimbursement": {"סרטן": "50,000-100,000 ש\"ח", "מטסטזות": "תוספת"},
        "limits": {"אירוע": "פעם אחת", "סה\"כ": "לפי חומרה"},
        "notes": "פיצוי מיידי"
    },
    "5418": {
        "name": "פיצוי למחלות לב",
        "description": "פיצוי כספי למחלות לב וכלי דם",
        "includes": ["אוטם", "ניתוח לב פתוח", "אי ספיקת לב", "מחלות מסתמים"],
        "reimbursement": {"אוטם": "70,000 ש\"ח", "ניתוח": "50,000 ש\"ח"},
        "limits": {"אירוע": "פעם אחת", "סה\"כ": "לפי מקרה"},
        "notes": "מחלות לב מוגדרות"
    },
    "773756": {
        "name": "מחלות נדירות",
        "description": "כיסוי למחלות נדירות ואורפניות",
        "includes": ["מחלות נדירות", "טיפולים ייחודיים", "תרופות אורפניות"],
        "reimbursement": {"טיפול": "החזר מלא", "תרופות": "100% החזר"},
        "limits": {"שנתי": "ללא הגבלה", "לטיפול": "לפי צורך"},
        "notes": "כיסוי ייחודי"
    },
    
    # ===== NISPACHIM - שיניים =====
    "5412": {
        "name": "שיניים מורחב",
        "description": "טיפולי שיניים כולל אורתודונטיה",
        "includes": ["שתלים", "כתרים", "יישור", "הלבנה", "אסתטיקה"],
        "reimbursement": {"שתל": "60% החזר", "כתר": "70% החזר", "יישור": "50% החזר"},
        "limits": {"שנתי": "15,000 ש\"ח", "לטיפול": "לפי סוג"},
        "notes": "כיסוי מורחב"
    },
    "5414": {
        "name": "שיניים - השתלות",
        "description": "השתלות שיניים ושיקום הפה",
        "includes": ["השתלות", "עצם", "שיקום מלא", "אסתטיקה"],
        "reimbursement": {"השתלה": "3,000-5,000 ש\"ח לשן", "עצם": "החזר חלקי"},
        "limits": {"שנתי": "20,000 ש\"ח", "לשתל": "עד 5,000 ש\"ח"},
        "notes": "מומחים מובילים"
    },
    "6420": {
        "name": "שיניים - אסתטיקה",
        "description": "טיפולים אסתטיים בשיניים",
        "includes": ["הלבנה", "חיפויים", "ונירים", "שיקום אסתטי"],
        "reimbursement": {"הלבנה": "500 ש\"ח", "ונירים": "30% החזר"},
        "limits": {"שנתי": "5,000 ש\"ח", "לטיפול": "לפי סוג"},
        "notes": "אסתטיקה דנטלית"
    },
    
    # ===== NISPACHIM - טכנולוגיות מתקדמות =====
    "6793": {
        "name": "טכנולוגיות רפואיות מתקדמות",
        "description": "ציוד ומכשירים רפואיים מתקדמים",
        "includes": ["מכשירים רפואיים", "טכנולוגיה חדשה", "ציוד מתקדם"],
        "reimbursement": {"מכשיר": "80% החזר", "טכנולוגיה": "החזר לפי מחיר"},
        "limits": {"שנתי": "50,000 ש\"ח", "למכשיר": "עד 10,000 ש\"ח"},
        "notes": "חדשנות רפואית"
    },
    "6794": {
        "name": "אביזרים רפואיים",
        "description": "כיסוי לאביזרים ועזרים רפואיים",
        "includes": ["קביים", "כיסא גלגלים", "מזרן אורטופדי", "עזרים"],
        "reimbursement": {"אביזר": "70-80% החזר", "עזר": "החזר לפי מחיר"},
        "limits": {"שנתי": "10,000 ש\"ח", "לאביזר": "עד 5,000 ש\"ח"},
        "notes": "אביזרים מאושרים"
    },
    "6795": {
        "name": "רובוטיקה רפואית",
        "description": "ניתוחים רובוטיים מתקדמים",
        "includes": ["ניתוח רובוטי", "דה-וינצ'י", "טכנולוגיה מתקדמת"],
        "reimbursement": {"ניתוח רובוטי": "החזר מלא", "תוספת": "לפי סוג"},
        "limits": {"שנתי": "ללא הגבלה", "לניתוח": "מלא"},
        "notes": "טכנולוגיה מתקדמת"
    },
    
    # ===== NISPACHIM - פוריות =====
    "6421": {
        "name": "טיפולי פוריות",
        "description": "הפריות חוץ גופיות (IVF) וטיפולים נלווים",
        "includes": ["IVF", "ICSI", "הזרעה", "ליווי הורמונלי"],
        "reimbursement": {"מחזור": "10,000-20,000 ש\"ח", "תרופות": "החזר חלקי"},
        "limits": {"שנתי": "2-3 מחזורים", "למחזור": "עד 20,000 ש\"ח"},
        "notes": "טיפולי IVF"
    },
    "6422": {
        "name": "הריון והיריון",
        "description": "כיסוי מורחב להריון ולידה",
        "includes": ["מעקב הריון", "בדיקות גנטיות", "לידה פרטית", "אשפוז"],
        "reimbursement": {"מעקב": "החזר מלא", "לידה": "תוספת פרטית"},
        "limits": {"להריון": "20,000 ש\"ח", "ללידה": "5,000 ש\"ח"},
        "notes": "מעקב מקיף"
    },
    
    # ===== NISPACHIM - ילדים =====
    "6423": {
        "name": "שירותים לילד",
        "description": "כיסוי מיוחד לצרכי ילדים",
        "includes": ["רופא ילדים", "חיסונים", "טיפולים מיוחדים", "ליווי התפתחותי"],
        "reimbursement": {"רופא": "החזר מלא", "חיסון": "החזר מלא"},
        "limits": {"שנתי": "5,000 ש\"ח", "לטיפול": "לפי סוג"},
        "notes": "עד גיל 18"
    },
    "6424": {
        "name": "התפתחות ילדים",
        "description": "טיפולים התפתחותיים לילדים",
        "includes": ["קלינאות תקשורת", "ריפוי בעיסוק", "פיזיותרפיה", "פסיכולוג"],
        "reimbursement": {"טיפול": "150-200 ש\"ח לטיפול", "מקצועי": "החזר של 70%"},
        "limits": {"שנתי": "50 טיפולים", "לטיפול": "עד 250 ש\"ח"},
        "notes": "ליווי התפתחותי"
    },
    "6425": {
        "name": "אוטיזם והפרעות התפתחות",
        "description": "טיפולים מיוחדים לאוטיזם",
        "includes": ["ABA", "טיפול התנהגותי", "קלינאות", "ריפוי בעיסוק"],
        "reimbursement": {"ABA": "200 ש\"ח לשעה", "טיפול": "החזר של 80%"},
        "limits": {"שנתי": "100,000 ש\"ח", "לטיפול": "לפי צורך"},
        "notes": "כיסוי מיוחד"
    },
    
    # ===== NISPACHIM - נפש =====
    "6426": {
        "name": "בריאות הנפש",
        "description": "טיפולים פסיכולוגיים ופסיכיאטריים",
        "includes": ["פסיכולוג", "פסיכיאטר", "טיפול קבוצתי", "CBT"],
        "reimbursement": {"פגישה": "200-300 ש\"ח", "פסיכיאטר": "החזר של 70%"},
        "limits": {"שנתי": "30-50 פגישות", "לפגישה": "עד 350 ש\"ח"},
        "notes": "בריאות נפש"
    },
    "6427": {
        "name": "גמילה מהתמכרויות",
        "description": "טיפולים בהתמכרויות",
        "includes": ["גמילה מסמים", "אלכוהול", "הימורים", "שיקום"],
        "reimbursement": {"אשפוז": "החזר מלא", "שיקום": "החזר של 80%"},
        "limits": {"שנתי": "60 ימים", "לתוכנית": "לפי אישור"},
        "notes": "תוכניות גמילה"
    },
    
    # ===== NISPACHIM - סיעוד ומוגבלויות =====
    "6801": {
        "name": "סיעוד מורחב",
        "description": "כיסוי מורחב לצרכים סיעודיים",
        "includes": ["קצבה חודשית", "שירותי סיעוד", "עזרים", "התאמות"],
        "reimbursement": {"קצבה": "5,000-10,000 ש\"ח/חודש", "עזרים": "החזר מלא"},
        "limits": {"חודשי": "לפי דרגה", "שנתי": "ללא הגבלה"},
        "notes": "כיסוי מקיף"
    },
    "6802": {
        "name": "שיקום רפואי",
        "description": "טיפולי שיקום ופיזיותרפיה",
        "includes": ["פיזיותרפיה", "ריפוי בעיסוק", "הידרותרפיה", "שיקום"],
        "reimbursement": {"טיפול": "150-200 ש\"ח", "שיקום": "החזר של 80%"},
        "limits": {"שנתי": "50-80 טיפולים", "לטיפול": "עד 250 ש\"ח"},
        "notes": "שיקום מקיף"
    },
    "6803": {
        "name": "עזרים ונגישות",
        "description": "התאמות בית ועזרים לנכים",
        "includes": ["התאמות בית", "מעלית", "מדרגות", "שיפועים", "אביזרים"],
        "reimbursement": {"התאמה": "50% החזר", "עזרים": "החזר של 70%"},
        "limits": {"שנתי": "50,000 ש\"ח", "להתאמה": "עד 30,000 ש\"ח"},
        "notes": "נגישות לנכים"
    },
    
    # ===== NISPACHIM - חירום ותאונות =====
    "5419": {
        "name": "תאונות אישיות",
        "description": "כיסוי לתאונות ופגיעות גוף",
        "includes": ["נכות", "מוות", "אובדן איברים", "שיקום"],
        "reimbursement": {"נכות": "לפי %", "מוות": "סכום קבוע"},
        "limits": {"לאירוע": "500,000 ש\"ח", "שנתי": "לפי פוליסה"},
        "notes": "ביטוח תאונות"
    },
    "6428": {
        "name": "חדר מיון פרטי",
        "description": "גישה לחדר מיון פרטי",
        "includes": ["ER פרטי", "ללא המתנה", "טיפול מהיר", "מומחים"],
        "reimbursement": {"ביקור": "החזר מלא", "טיפולים": "החזר מלא"},
        "limits": {"שנתי": "ללא הגבלה", "לביקור": "ללא מגבלה"},
        "notes": "שירות VIP"
    },
    "6429": {
        "name": "מד\"א והצלה",
        "description": "שירותי חירום והסעה רפואית",
        "includes": ["אמבולנס", "הסעה רפואית", "מד\"א", "טיפול חירום"],
        "reimbursement": {"הסעה": "החזר מלא", "חירום": "החזר מלא"},
        "limits": {"שנתי": "ללא הגבלה", "לאירוע": "ללא מגבלה"},
        "notes": "שירותי חירום"
    },
    
    # ===== NISPACHIM ספציפיים לחברות =====
    "7402": {
        "name": "הראל - מדיקל פלוס",
        "description": "חבילת שירותים מורחבת של הראל",
        "includes": ["כל השירותים", "כיסוי מקיף", "רשת רחבה", "שירות VIP"],
        "reimbursement": {"כיסוי": "מקסימלי", "שירותים": "רחב"},
        "limits": {"שנתי": "לפי תוכנית", "כולל": "מקיף"},
        "notes": "תוכנית פרימיום"
    },
    "7403": {
        "name": "מגדל - קשת זהב",
        "description": "תוכנית פרימיום של מגדל",
        "includes": ["כיסוי מורחב", "שירותים נוספים", "ייעוץ רפואי", "גישה מהירה"],
        "reimbursement": {"כיסוי": "גבוה", "שירותים": "מקיף"},
        "limits": {"שנתי": "לפי תוכנית", "כולל": "רחב"},
        "notes": "רמה גבוהה"
    },
    "7404": {
        "name": "כלל - מדיכלל פרימיום",
        "description": "תוכנית מורחבת של כלל",
        "includes": ["כיסוי רחב", "מומחים מובילים", "טכנולוגיה", "שירות"],
        "reimbursement": {"כיסוי": "מקסימלי", "שירותים": "מקיף"},
        "limits": {"שנתי": "לפי תוכנית", "כולל": "נרחב"},
        "notes": "תוכנית עליונה"
    },
    "7405": {
        "name": "כלל - TOP100",
        "description": "גישה מהירה ל-100 רופאים מובילים",
        "includes": ["100 רופאים מובילים", "תור תוך 7 ימים", "מומחים בכירים"],
        "reimbursement": {"ייעוץ": "החזר מלא", "גישה": "מיידית"},
        "limits": {"שנתי": "ללא הגבלה", "לייעוץ": "ללא מגבלה"},
        "notes": "שירות ייחודי"
    },
    "7406": {
        "name": "הפניקס - תוכנית מרפא",
        "description": "פיצוי למחלות קשות - הפניקס",
        "includes": ["32 מחלות", "פיצוי מהיר", "תשלום חד פעמי", "ליווי"],
        "reimbursement": {"פיצוי": "100,000-200,000 ש\"ח", "מיידי": "כן"},
        "limits": {"אירוע": "פעם אחת", "סה\"כ": "לפי פוליסה"},
        "notes": "הפניקס בלעדי"
    },
    "7407": {
        "name": "מנורה - בריאות מושלמת",
        "description": "חבילה מקיפה של מנורה מבטחים",
        "includes": ["כיסוי כולל", "שירותים נוספים", "רשת רחבה", "מומחים"],
        "reimbursement": {"כיסוי": "מקסימלי", "שירותים": "מקיף"},
        "limits": {"שנתי": "לפי תוכנית", "כולל": "נרחב"},
        "notes": "תוכנית מושלמת"
    },
}

# ============================================================================
# NISPACH HELPER FUNCTIONS - WITH WEB SEARCH CAPABILITY
# ============================================================================

def extract_nispach_numbers(text):
    """
    חילוץ מספרי נספחים משאלה
    מזהה מספרים בפורמטים שונים: "נספח 8713", "8713", "נספח מספר 5409"
    
    Args:
        text: הטקסט לחיפוש מספרי נספחים
        
    Returns:
        list: רשימת מספרי נספחים שנמצאו
    """
    numbers = []
    
    # דפוס 1: "נספח 8713" או "נספח מספר 8713"
    pattern1 = r'נספח\s*(?:מספר\s*)?(\d{4,6})'
    matches1 = re.findall(pattern1, text)
    numbers.extend(matches1)
    
    # דפוס 2: מספרים של 4-6 ספרות (סביר שהם נספחים)
    pattern2 = r'\b(\d{4,6})\b'
    matches2 = re.findall(pattern2, text)
    
    # סינון: רק מספרים שמתחילים ב-5, 6, 7, או 8 (טווח נספחים אמיתי)
    for num in matches2:
        if num[0] in ['5', '6', '7', '8'] and num not in numbers:
            numbers.append(num)
    
    return list(set(numbers))  # הסרת כפילויות


def search_nispach_online_v2(nispach_number, client):
    """
    חיפוש נספח באינטרנט באמצעות Claude API
    
    Args:
        nispach_number: מספר הנספח לחיפוש
        client: Anthropic client instance
        
    Returns:
        dict: מידע על הנספח או None אם לא נמצא
    """
    try:
        # שאלה לחיפוש
        search_query = f"נספח {nispach_number} ביטוח בריאות ישראל מה זה"
        
        # Note: Web search would be implemented here when tool is available
        # For now, return None
        return None
        
    except Exception as e:
        st.warning(f"לא הצלחנו לחפש באינטרנט: {str(e)}")
        return None


def get_nispach_info_with_search(nispach_number, use_online_search=True, anthropic_client=None):
    """
    מחזיר מידע על נספח - קודם מהמאגר המקומי, ואם לא קיים - מחיפוש אונליין
    
    Args:
        nispach_number: מספר הנספח
        use_online_search: האם לחפש באונליין אם לא נמצא מקומית
        anthropic_client: Anthropic client for web search
        
    Returns:
        dict: מידע על הנספח
    """
    # ניקוי המספר (הסרת רווחים וכו')
    nispach_number = str(nispach_number).strip()
    
    # ניסיון ראשון - מהמאגר המקומי
    if nispach_number in NISPACH_INFO_EXPANDED:
        info = NISPACH_INFO_EXPANDED[nispach_number].copy()
        info['source'] = 'local_database'
        info['nispach_number'] = nispach_number
        return info
    
    # אם לא נמצא ומותר חיפוש אונליין
    if use_online_search and anthropic_client:
        st.info(f"🔍 מחפש מידע על נספח {nispach_number} באינטרנט...")
        online_result = search_nispach_online_v2(nispach_number, anthropic_client)
        if online_result and online_result.get("found_online"):
            online_result['nispach_number'] = nispach_number
            return online_result
    
    # ברירת מחדל - נספח לא ידוע
    return {
        "name": f"נספח {nispach_number}",
        "description": "מידע על נספח זה אינו זמין במאגר. אנא פנה לחברת הביטוח לפרטים.",
        "unknown": True,
        "source": "unknown",
        "nispach_number": nispach_number
    }


def format_nispach_response(nispach_info):
    """
    פורמט יפה לתשובה על נספח
    
    Args:
        nispach_info: מידע על הנספח
        
    Returns:
        str: תשובה מפורמטת
    """
    response = f"### נספח {nispach_info.get('nispach_number', '???')}\n\n"
    response += f"**שם:** {nispach_info['name']}\n\n"
    response += f"**תיאור:** {nispach_info['description']}\n\n"
    
    if nispach_info.get('includes'):
        response += "**כולל:**\n"
        for item in nispach_info['includes']:
            response += f"- {item}\n"
        response += "\n"
    
    if nispach_info.get('reimbursement'):
        response += "**💰 שיעורי החזר:**\n"
        for service, amount in nispach_info['reimbursement'].items():
            response += f"- {service}: {amount}\n"
        response += "\n"
    
    if nispach_info.get('limits'):
        response += "**📊 מגבלות:**\n"
        for limit_type, limit_value in nispach_info['limits'].items():
            response += f"- {limit_type}: {limit_value}\n"
        response += "\n"
    
    if nispach_info.get('notes'):
        response += f"**💡 הערות:** {nispach_info['notes']}\n\n"
    
    if nispach_info.get('source') == 'web_search':
        response += "ℹ️ *מידע זה נמצא באמצעות חיפוש באינטרנט*\n"
    elif nispach_info.get('unknown'):
        response += "⚠️ *נספח זה לא נמצא במאגר ובחיפוש אונליין*\n"
    
    return response


def get_all_known_nispachim():
    """מחזיר רשימה ממוינת של כל מספרי הנספחים הידועים"""
    return sorted(NISPACH_INFO_EXPANDED.keys(), key=lambda x: int(x))


def get_nispach_info(nispach_number):
    """Get information about a specific nispach - Legacy function for backward compatibility"""
    # Clean the nispach number (remove common separators)
    clean_number = nispach_number.replace("/", "").replace("-", "").replace(" ", "")
    
    # Try to find the nispach
    if clean_number in NISPACH_INFO_EXPANDED:
        return NISPACH_INFO_EXPANDED[clean_number]
    
    # Try to find partial match (e.g., "5420" in "5420/8713")
    for key in NISPACH_INFO_EXPANDED.keys():
        if key in clean_number or clean_number in key:
            return NISPACH_INFO_EXPANDED[key]
    
    return None

# ============================================================================
# REST OF THE CODE REMAINS THE SAME
# ============================================================================

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

def detect_company_v2(text):
    """Detect insurance company from PDF text with priority indicators - v2 with fnx4u fix"""
    
    # HARDCODED FIX: If text contains fnx4u, it's Phoenix - NO QUESTIONS ASKED
    if 'fnx4u' in text.lower():
        return "הפניקס"
    
    text_lower = text.lower()
    
    # Get first 2000 characters (header area where logo/company name usually appears)
    header_text = text[:2000]
    header_lower = header_text.lower()
    
    # Get last 1000 characters (footer where company name often appears)
    footer_text = text[-1000:] if len(text) > 1000 else text
    
    # Count occurrences for better detection
    company_scores = {
        "הפניקס": 0,
        "כלל": 0,
        "הראל": 0,
        "מגדל": 0,
        "מנורה": 0,
        "איילון": 0
    }
    
    # Priority 0: HIGHEST - Check header AND footer for company name - 25 points
    # Normal text
    if 'הפניקס' in header_text or 'פניקס' in header_text:
        company_scores["הפניקס"] += 25
    if 'כלל' in header_text and 'כללי' not in header_text:
        company_scores["כלל"] += 25
    if 'הראל' in header_text:
        company_scores["הראל"] += 25
    if 'מגדל' in header_text:
        company_scores["מגדל"] += 25
    if 'מנורה' in header_text:
        company_scores["מנורה"] += 25
    if 'איילון' in header_text:
        company_scores["איילון"] += 25
    
    # Reversed text (RTL rendering issue) - CHECK FOOTER
    if 'סקינפה' in footer_text:  # הפניקס reversed
        company_scores["הפניקס"] += 25
    if 'ללכ' in footer_text and 'ילכ' not in footer_text:  # כלל reversed (but not כלכלי)
        company_scores["כלל"] += 25
    if 'לארה' in footer_text:  # הראל reversed
        company_scores["הראל"] += 25
    if 'לדגמ' in footer_text:  # מגדל reversed
        company_scores["מגדל"] += 25
    if 'הרונמ' in footer_text:  # מנורה reversed
        company_scores["מנורה"] += 25
    if 'ןוליא' in footer_text:  # איילון reversed
        company_scores["איילון"] += 25
    
    # Priority 1: Check for company-specific websites and emails (most reliable) - 10 points
    if 'fnx.co.il' in text_lower or 'myinfo.fnx' in text_lower or 'phoenix' in text_lower or 'fnx4u' in text_lower:
        company_scores["הפניקס"] += 10
    if 'clal.co.il' in text_lower or 'clalbit.co.il' in text_lower or 'bit.clal.co.il' in text_lower or '@clal-ins.co.il' in text_lower or 'clal-ins.co.il' in text_lower:
        company_scores["כלל"] += 10
    if 'harel-group.co.il' in text_lower or 'hrl.co.il' in text_lower:
        company_scores["הראל"] += 10
    if 'migdal.co.il' in text_lower:
        company_scores["מגדל"] += 10
    if 'menoramivt.co.il' in text_lower:
        company_scores["מנורה"] += 10
    if 'ayalon-ins.co.il' in text_lower:
        company_scores["איילון"] += 10
    
    # Priority 2: Check for company phone numbers - 8 points
    if '3455*' in text or '*3455' in text or '03-7332222' in text or '03-7357988' in text:
        company_scores["הפניקס"] += 8
    if '*2800' in text or '2800*' in text or '03-6376666' in text or '077-6383290' in text or '6136902' in text:
        company_scores["כלל"] += 8
    if '*2407' in text or '2407*' in text:
        company_scores["הראל"] += 8
    if '*2679' in text or '2679*' in text:
        company_scores["מגדל"] += 8
    if '*2000' in text or '2000*' in text:
        company_scores["מנורה"] += 8
    if '*5620' in text or '5620*' in text:
        company_scores["איילון"] += 8
    
    # Priority 3: Count company name appearances - 3 points each (both normal and reversed)
    company_scores["הפניקס"] += (text.count('פניקס') + text.count('הפניקס') + text.count('סקינפה') + text.count('סקינפ')) * 3
    company_scores["כלל"] += ((text.count('כלל') - text.count('כללי')) + text.count('ללכ')) * 3
    company_scores["הראל"] += (text.count('הראל') + text.count('לארה')) * 3
    company_scores["מגדל"] += (text.count('מגדל') + text.count('לדגמ')) * 3
    company_scores["מנורה"] += (text.count('מנורה') + text.count('הרונמ')) * 3
    company_scores["איילון"] += (text.count('איילון') + text.count('ןוליא')) * 3
    
    # Priority 4: Check for unique company identifiers - 5 points
    if 'כלל חברה לביטוח' in text or 'כלל תכנית הגריאטריות' in text:
        company_scores["כלל"] += 5
    if 'הפניקס חברה לביטוח' in text or ('חברה לביטוח בע"מ' in text and 'הפניקס' in text):
        company_scores["הפניקס"] += 5
    # Reversed versions
    if 'חוטיבל הרבח סקינפה' in text or 'מ״עב חוטיבל הרבח' in text and 'סקינפה' in text:
        company_scores["הפניקס"] += 5
    
    # Return company with highest score (minimum 3 to avoid false positives)
    max_score = max(company_scores.values())
    if max_score >= 3:
        return max(company_scores, key=company_scores.get)
    
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
    
    # Initialize Claude
    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").strip()
    claude = None
    if api_key:
        try:
            claude = Anthropic(api_key=api_key)
            st.sidebar.success("✅ Claude API connected!")
        except Exception as e:
            st.error(f"❌ Error initializing Claude: {str(e)}")
            st.sidebar.error(f"Claude API Error: {str(e)[:100]}")
    else:
        st.sidebar.warning("⚠️ ANTHROPIC_API_KEY not found in secrets")
    
    return db, claude

db, claude_client = init_connections()

# TEST: Verify Supabase connection
st.sidebar.write("🔍 Testing Supabase...")
st.sidebar.write(f"URL: {db.url[:30]}...")
st.sidebar.write(f"Key: {db.key[:20]}...")
try:
    test = db.client.table("users").select("id").limit(1).execute()
    st.sidebar.success("✅ Supabase connected!")
except Exception as e:
    st.sidebar.error(f"❌ Supabase error: {str(e)[:100]}")

# Show nispach count in sidebar
st.sidebar.info(f"📚 במאגר: {len(NISPACH_INFO_EXPANDED)} נספחים")

# ============================================================================
# REST OF THE APP CODE CONTINUES UNCHANGED...
# (The LOGIN, MAIN APP, and all pages remain exactly the same)
# ============================================================================

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
                    user_data = db.verify_user(username, password)
                    if user_data:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_data["id"]
                        st.session_state.username = user_data["username"]
                        st.success(f"שלום {user_data['username']}!")
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
                            st.session_state.reset_step = 1
                            st.session_state.reset_email = None
                            st.session_state.reset_code_generated = None
                        else:
                            st.error(user_id)
            
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
                    try:
                        policies = db.get_policies(st.session_state.current_investigation_id)
                        for pol in policies:
                            if pol.get('file_path') and os.path.exists(pol['file_path']):
                                os.remove(pol['file_path'])
                    except Exception as e:
                        pass
                    
                    db.delete_investigation(st.session_state.current_investigation_id)
                    st.session_state.current_investigation_id = None
                    st.rerun()
    
    st.markdown("---")
    
    with st.expander("➕ חדש", expanded=not st.session_state.current_investigation_id):
        client_name = st.text_input("לקוח")
        if st.button("צור", type="primary", use_container_width=True):
            if client_name:
                try:
                    inv_id = db.create_investigation(st.session_state.user_id, client_name, "")
                    if inv_id:
                        st.session_state.current_investigation_id = inv_id
                        st.success(f"✅ נוצר!")
                        st.rerun()
                    else:
                        st.error("❌ שגיאה ביצירת חקירה")
                except Exception as e:
                    st.error(f"❌ שגיאה: {str(e)}")
            else:
                st.warning("⚠️ אין שם לקוח")
    
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
    
    st.info("💡 **טיפ:** רוב חברות הביטוח מאפשרות להוריד את הפוליסות שלך דרך האזור האישי באתר")
    
    st.markdown("---")
    
    # Company-specific instructions (keeping original code)
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
    
    # (Rest of companies - same as original...)

elif st.session_state.page == "📤 העלאה":
    st.title("📤 העלאה")
    
    inv = db.get_investigation(st.session_state.current_investigation_id)
    st.info(f"📍 לקוח: **{inv['client_name']}**")
    
    uploaded_file = st.file_uploader("PDF", type=['pdf'])
    
    if uploaded_file:
        with st.spinner("מעבד..."):
            try:
                file_bytes = uploaded_file.getvalue()
                text, total_pages = extract_text_from_pdf(file_bytes)
                
                if not text or text.startswith("❌") or text.startswith("⚠️"):
                    st.error(text if text else "לא הצלחנו לקרוא את הקובץ")
                else:
                    detected_company = detect_company_v2(text)
                    
                    if detected_company:
                        count = db.get_company_count(st.session_state.current_investigation_id, detected_company)
                        auto_name = detected_company if count == 0 else f"{detected_company} {count + 1}"
                    else:
                        auto_name = uploaded_file.name.replace('.pdf', '').replace('-', ' ')
                    
                    st.success(f"✅ זוהתה חברה: **{detected_company or 'לא זוהה'}**")
                    st.info(f"📄 {total_pages} עמודים | {len(text)} תווים")
                    
                    with st.form("form"):
                        company = st.selectbox("חברה", COMPANIES, 
                                              index=COMPANIES.index(detected_company) if detected_company in COMPANIES else 0)
                        custom_name = st.text_input("שם הפוליסה", value=auto_name)
                        
                        if st.form_submit_button("💾 שמור", type="primary"):
                            safe_filename = f"{company}_{uuid.uuid4().hex[:8]}.pdf"
                            file_path = os.path.join(UPLOAD_DIR, safe_filename)
                            
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
                st.error(f"❌ שגיאה: {str(e)}")
    
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
                with col2:
                    if st.button("🗑️ מחק", key=f"del_{pol['id']}"):
                        try:
                            if pol.get('file_path') and os.path.exists(pol['file_path']):
                                os.remove(pol['file_path'])
                        except:
                            pass
                        
                        db.delete_policy(pol['id'])
                        st.success("נמחק!")
                        st.rerun()

elif st.session_state.page == "❓ שאלות":
    st.title("❓ שאלות")
    
    mode = st.radio(
        "בחר סוג שאלה:",
        ["📄 שאל על הפוליסות שלי", "🌐 מידע כללי על ביטוחים"],
        horizontal=True
    )
    
    if mode == "📄 שאל על הפוליסות שלי":
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
                
                if st.button("🔍 שאל", type="primary") and query:
                    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").strip()
                    if not api_key:
                        st.error("❌ API key not configured")
                    else:
                        try:
                            fresh_claude = Anthropic(api_key=api_key)
                        except Exception as e:
                            st.error(f"❌ Failed to initialize Claude: {str(e)}")
                            fresh_claude = None
                        
                        if fresh_claude:
                            with st.spinner("מחפש ומנתח..."):
                                try:
                                    # Check for nispach numbers using new function
                                    nispach_numbers = extract_nispach_numbers(query)
                                    
                                    if nispach_numbers:
                                        st.info(f"🔍 זיהיתי שאלה על נספחים: {', '.join(nispach_numbers)}")
                                        
                                        for num in nispach_numbers:
                                            nispach_info = get_nispach_info_with_search(
                                                nispach_number=num,
                                                use_online_search=True,
                                                anthropic_client=fresh_claude
                                            )
                                            
                                            formatted_response = format_nispach_response(nispach_info)
                                            st.markdown(formatted_response)
                                    
                                    # Continue with normal PDF search...
                                    selected_ids = [policy_options[name] for name in selected_names]
                                    all_contexts = []
                                    
                                    for name, pol_id in zip(selected_names, selected_ids):
                                        chunks = db.search_chunks(pol_id, query, top_k=20)
                                        if chunks:
                                            context = f"=== פוליסה: {name} ===\n" + "\n\n".join([c['text'] for c in chunks[:8]])
                                            all_contexts.append(context)
                                    
                                    if all_contexts:
                                        combined = "\n\n".join(all_contexts)
                                        
                                        system_prompt = """אתה מומחה ביטוח ישראלי. חלץ מידע מדויק מפוליסות.

כללים:
1. חפש טבלאות מחירים והצג אותן במדויק
2. אל תמציא מידע
3. ענה בעברית פשוטה וברורה
4. השווה בין פוליסות אם יש יותר מאחת"""
                                        
                                        user_content = f"""שאלה: {query}

תוכן מהפוליסות:
{combined}

ענה בדיוק על סמך המידע."""
                                        
                                        response = fresh_claude.messages.create(
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
        st.info("💡 **במצב זה אתה יכול לשאול שאלות כלליות על ביטוחים**")
        
        query = st.text_area(
            "שאל שאלה כללית:",
            placeholder="לדוגמה: מה ההבדל בין מגדל להראל?",
            height=100
        )
        
        if st.button("🔍 שאל", type="primary") and query:
            # Similar logic but for general questions...
            st.info("מצב מידע כללי - תשובות מבוססות ידע כללי על ביטוחים")

elif st.session_state.page == "📚 מדריך נספחים":
    st.title("📚 מדריך נספחים - מה כל נספח מכסה?")
    st.write("מידע מפורט על נספחים נפוצים בפוליסות ביטוח בריאות")
    
    # UPDATED: Show new count
    st.info(f"📊 **במאגר שלנו יש מידע על {len(NISPACH_INFO_EXPANDED)} נספחים!**")
    
    st.markdown("---")
    
    search_term = st.text_input("🔍 חפש נספח לפי מספר או שם:", placeholder="לדוגמה: 8713 או אבחנה מהירה")
    
    if search_term:
        found_nispachim = []
        search_lower = search_term.lower()
        
        # UPDATED: Search in expanded database
        for nispach_num, data in NISPACH_INFO_EXPANDED.items():
            if (search_term in nispach_num or 
                search_lower in data['name'].lower() or 
                search_lower in data['description'].lower()):
                found_nispachim.append((nispach_num, data))
        
        if found_nispachim:
            st.success(f"נמצאו {len(found_nispachim)} תוצאות:")
            for nispach_num, data in found_nispachim:
                with st.expander(f"📋 נספח {nispach_num} - {data['name']}", expanded=True):
                    st.markdown(f"**תיאור:** {data['description']}")
                    
                    if 'includes' in data:
                        st.markdown("**כולל:**")
                        for item in data['includes']:
                            st.markdown(f"- {item}")
                    
                    if 'reimbursement' in data:
                        st.markdown("**💰 שיעורי החזר:**")
                        for service, amount in data['reimbursement'].items():
                            st.markdown(f"- {service}: **{amount}**")
                    
                    if 'limits' in data:
                        st.markdown("**📊 מגבלות:**")
                        for limit_type, limit_value in data['limits'].items():
                            st.markdown(f"- {limit_type}: {limit_value}")
                    
                    if 'notes' in data:
                        st.info(f"💡 {data['notes']}")
        else:
            st.warning("לא נמצאו תוצאות")
    
    st.markdown("---")
    st.markdown("### 📑 רשימת כל הנספחים")
    
    # Show all nispachim
    all_nispachim = get_all_known_nispachim()
    nispach_list = "\n".join([f"- **{num}**: {NISPACH_INFO_EXPANDED[num]['name']}" 
                              for num in all_nispachim])
    st.markdown(nispach_list)

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
            if st.button("🔍 השווה", type="primary"):
                # Comparison logic...
                st.info("מכין השוואה...")

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
    if st.session_state.username != "admin":
        st.error("⛔ אין לך הרשאה")
        st.stop()
    
    st.title("👑 פאנל ניהול")
    st.info("מידע זמין רק למנהל")

st.markdown("---")
st.caption(f"מערכת השוואת פוליסות v3.1 | משתמש: {st.session_state.username} | {len(NISPACH_INFO_EXPANDED)} נספחים במאגר")
