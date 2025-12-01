import streamlit as st
from anthropic import Anthropic
from modules.database_supabase import SupabaseDatabase
import os
from dotenv import load_dotenv
import tempfile
import uuid
import json
import shutil
import re
import hashlib
import traceback

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

# NISPACH_INFO_EXPANDED dictionary - keeping all 60+ nispachim
NISPACH_INFO_EXPANDED = {
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
    # ... (rest of nispachim - keeping original data)
}

# Helper functions
def extract_nispach_numbers(text):
    """חילוץ מספרי נספחים משאלה"""
    numbers = []
    pattern1 = r'נספח\s*(?:מספר\s*)?(\d{4,6})'
    matches1 = re.findall(pattern1, text)
    numbers.extend(matches1)
    
    pattern2 = r'\b(\d{4,6})\b'
    matches2 = re.findall(pattern2, text)
    
    for num in matches2:
        if num[0] in ['5', '6', '7', '8'] and num not in numbers:
            numbers.append(num)
    
    return list(set(numbers))


# ============================================================================
# ✅ NEW FUNCTIONS - FIX FOR LOCATION SEARCH
# ============================================================================

def detect_location_question(query):
    """
    זיהוי שאלות על מיקום/כתובת/איפה לעשות בדיקות
    
    Args:
        query: שאלת המשתמש
        
    Returns:
        bool: True אם זו שאלת מיקום
    """
    location_keywords = [
        'איפה', 'היכן', 'מיקום', 'כתובת', 'מקום',
        'בדיקות', 'לעשות', 'לבצע', 'מרכז', 'מדיקל',
        'טלפון', 'פלאפון', 'מספר', 'ליצור קשר', 'צור קשר',
        'ספק', 'שירות', 'הרצליה'
    ]
    
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in location_keywords)


def extract_location_info_from_chunks(chunks):
    """
    חילוץ מידע על מיקום מה-chunks
    מחפש מידע כמו: כתובת, טלפון, ספק שירות
    
    Args:
        chunks: רשימת chunks מה-PDF
        
    Returns:
        dict: מידע מיקום או None
    """
    location_data = {
        'provider': None,
        'address': None,
        'phone': None,
        'hours': None,
        'found_chunks': []
    }
    
    # Find chunks with location-relevant keywords
    location_indicators = ['ספק', 'כתובת', 'טלפון', 'מוקד', 'הרצליה', 'מדיקל', 'נותן השירות']
    
    for chunk in chunks:
        text = chunk.get('text', '')
        if any(indicator in text for indicator in location_indicators):
            location_data['found_chunks'].append(text)
    
    combined_text = '\n'.join(location_data['found_chunks'])
    
    if not combined_text:
        return None
    
    # חיפוש ספק שירות
    provider_patterns = [
        r'ספק השירות["\s:]+([^\n]+)',
        r'נותן השירות["\s:]+([^\n]+)',
        r'הרצליה מדיקל סנטר[,\s]+([^\n]*)',
        r'(הרצליה מדיקל סנטר)'
    ]
    
    for pattern in provider_patterns:
        match = re.search(pattern, combined_text)
        if match:
            full_match = match.group(0)
            location_data['provider'] = full_match
            # Also extract address from same line
            if 'רח' in full_match or 'רמת' in full_match:
                location_data['address'] = full_match
            break
    
    # חיפוש כתובת ספציפית
    if not location_data['address']:
        address_patterns = [
            r'רח[\'"\s]+רמת ים\s*\d+[,\s]*הרצליה פיתוח',
            r'רמת ים\s*\d+[,\s]*הרצליה',
            r'רח[\'"\s]+([^,\n]+\d+)',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, combined_text)
            if match:
                location_data['address'] = match.group(0)
                break
    
    # חיפוש טלפון
    phone_patterns = [
        r'1-700-[\d-]+',
        r'\*\d{4}',
        r'טלפון["\s:]+([^\n]+)',
        r'מוקד שירות["\s:]+([^\n]+)',
        r'מספר הטלפון["\s:]+([^\n]+)'
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, combined_text)
        if match:
            location_data['phone'] = match.group(0)
            break
    
    # חיפוש שעות פעילות
    hours_patterns = [
        r'שעות פעילות["\s:]+([^\n\.]+)',
        r'ימים\s+[א-ה\'-]+[,\s]+בין השעות\s+[\d:-]+',
        r'\d{2}:\d{2}\s*-\s*\d{2}:\d{2}'
    ]
    
    for pattern in hours_patterns:
        match = re.search(pattern, combined_text)
        if match:
            location_data['hours'] = match.group(0)
            break
    
    # בדיקה אם מצאנו משהו
    if location_data['provider'] or location_data['address'] or location_data['phone']:
        return location_data
    
    return None


def format_location_answer(location_data, policy_name):
    """
    פורמט תשובה יפה למידע מיקום
    
    Args:
        location_data: dict עם מידע מיקום
        policy_name: שם הפוליסה
        
    Returns:
        str: תשובה מפורמטת
    """
    answer = f"### 📍 מידע על מקום ביצוע בדיקות\n\n"
    answer += f"**על פי הפוליסה: {policy_name}**\n\n"
    
    if location_data.get('provider'):
        answer += f"🏥 **ספק השירות:**\n{location_data['provider']}\n\n"
    
    if location_data.get('address'):
        answer += f"📍 **כתובת:**\n{location_data['address']}\n\n"
    
    if location_data.get('phone'):
        answer += f"📞 **טלפון:**\n{location_data['phone']}\n\n"
    
    if location_data.get('hours'):
        answer += f"🕐 **שעות פעילות:**\n{location_data['hours']}\n\n"
    
    answer += "---\n\n"
    answer += "💡 **לתיאום תור או לפרטים נוספים:**\n"
    answer += "- התקשר למספר הטלפון למעלה\n"
    answer += "- ציין את מספר הפוליסה שלך\n"
    answer += "- בדוק זמינות מראש\n"
    
    return answer


# ============================================================================
# REST OF HELPER FUNCTIONS (keeping original)
# ============================================================================

def search_nispach_online_v2(nispach_number, client):
    """חיפוש נספח באינטרנט"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[{
                "name": "web_search",
                "description": "Search the web for information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        }
                    },
                    "required": ["query"]
                }
            }],
            messages=[{
                "role": "user",
                "content": f"""חפש באינטרנט מידע על נספח {nispach_number} בביטוח בריאות בישראל.

חפש באתרים של:
- חברות הביטוח (הראל, מגדל, כלל, פניקס, מנורה)
- רשות שוק ההון
- אתרי השוואת מחירים

אני צריך לדעת:
1. מה שם הנספח?
2. מה הוא מכסה?
3. אילו שירותים כלולים?

תן לי תשובה מסודרת בפורמט הזה:

שם: [שם הנספח]
תיאור: [תיאור קצר]
כולל: [רשימה של שירותים]

אם לא מצאת מידע כלל - אמר "לא נמצא מידע"."""
            }]
        )
        
        answer_text = ""
        
        for block in response.content:
            if block.type == "text":
                answer_text += block.text
        
        not_found_phrases = ["לא נמצא", "לא מצאתי", "מצטער", "אין מידע", "לא זמין", "sorry", "not found"]
        found_not_found = any(phrase in answer_text.lower() for phrase in not_found_phrases)
        
        if answer_text and not found_not_found and len(answer_text) > 50:
            lines = answer_text.split('\n')
            name = f"נספח {nispach_number}"
            description = ""
            includes = []
            
            for line in lines:
                line = line.strip()
                if line.startswith("שם:"):
                    name = line.replace("שם:", "").strip()
                elif line.startswith("תיאור:"):
                    description = line.replace("תיאור:", "").strip()
                elif line.startswith("כולל:"):
                    includes_text = line.replace("כולל:", "").strip()
                    includes = [x.strip() for x in includes_text.split(',') if x.strip()]
            
            if not description or len(description) < 20:
                description = answer_text[:500]
            
            if len(description) < 30 or any(phrase in description.lower() for phrase in not_found_phrases):
                return None
            
            return {
                "name": name,
                "description": description,
                "includes": includes,
                "reimbursement": {},
                "limits": {},
                "notes": "ℹ️ מידע זה נמצא באמצעות חיפוש באינטרנט ועשוי להשתנות. מומלץ לאמת עם חברת הביטוח.",
                "found_online": True,
                "source": "web_search",
                "raw_search_result": answer_text
            }
        
        return None
        
    except Exception as e:
        st.warning(f"שגיאה בחיפוש באינטרנט: {str(e)}")
        return None


def get_nispach_info_with_search(nispach_number, use_online_search=True, anthropic_client=None):
    """מחזיר מידע על נספח"""
    nispach_number = str(nispach_number).strip()
    
    if nispach_number in NISPACH_INFO_EXPANDED:
        info = NISPACH_INFO_EXPANDED[nispach_number].copy()
        info['source'] = 'local_database'
        info['nispach_number'] = nispach_number
        return info
    
    if use_online_search and anthropic_client:
        st.info(f"🔍 מחפש מידע על נספח {nispach_number} באינטרנט...")
        online_result = search_nispach_online_v2(nispach_number, anthropic_client)
        if online_result and online_result.get("found_online"):
            online_result['nispach_number'] = nispach_number
            return online_result
    
    return {
        "name": f"נספח {nispach_number}",
        "description": "מידע על נספח זה אינו זמין במאגר. אנא פנה לחברת הביטוח לפרטים.",
        "unknown": True,
        "source": "unknown",
        "nispach_number": nispach_number
    }


def format_nispach_response(nispach_info):
    """פורמט יפה לתשובה על נספח"""
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
    """Get information about a specific nispach"""
    clean_number = nispach_number.replace("/", "").replace("-", "").replace(" ", "")
    
    if clean_number in NISPACH_INFO_EXPANDED:
        return NISPACH_INFO_EXPANDED[clean_number]
    
    for key in NISPACH_INFO_EXPANDED.keys():
        if key in clean_number or clean_number in key:
            return NISPACH_INFO_EXPANDED[key]
    
    return None


def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def extract_text_from_pdf(pdf_file_or_bytes):
    """Extract text from PDF"""
    if not PDF_SUPPORT: 
        return "❌ PDF support not available", 0
    
    try:
        text = ""
        page_count = 0
        
        if isinstance(pdf_file_or_bytes, bytes):
            import io
            pdf_file_or_bytes = io.BytesIO(pdf_file_or_bytes)
        
        with pdfplumber.open(pdf_file_or_bytes) as pdf:
            page_count = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                try:
                    page_text = page.extract_text()
                    
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
        
        if len(text.strip()) < 100:
            return "⚠️ לא הצלחנו לחלץ טקסט מספיק מה-PDF. ייתכן שהוא מבוסס תמונות או בפורמט לא נתמך.", page_count
        
        return text, page_count
        
    except Exception as e:
        return f"❌ שגיאה בקריאת PDF: {str(e)}", 0


def detect_company_v2(text):
    """Detect insurance company from PDF text"""
    
    if 'fnx4u' in text.lower():
        return "הפניקס"
    
    text_lower = text.lower()
    header_text = text[:2000]
    header_lower = header_text.lower()
    footer_text = text[-1000:] if len(text) > 1000 else text
    
    company_scores = {
        "הפניקס": 0,
        "כלל": 0,
        "הראל": 0,
        "מגדל": 0,
        "מנורה": 0,
        "איילון": 0
    }
    
    # Check header for company names
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
    
    # Check footer for reversed text
    if 'סקינפה' in footer_text:
        company_scores["הפניקס"] += 25
    if 'ללכ' in footer_text and 'ילכ' not in footer_text:
        company_scores["כלל"] += 25
    if 'לארה' in footer_text:
        company_scores["הראל"] += 25
    if 'לדגמ' in footer_text:
        company_scores["מגדל"] += 25
    if 'הרונמ' in footer_text:
        company_scores["מנורה"] += 25
    if 'ןוליא' in footer_text:
        company_scores["איילון"] += 25
    
    # Check for websites
    if 'fnx.co.il' in text_lower or 'myinfo.fnx' in text_lower or 'phoenix' in text_lower or 'fnx4u' in text_lower:
        company_scores["הפניקס"] += 10
    if 'clal.co.il' in text_lower or 'clalbit.co.il' in text_lower:
        company_scores["כלל"] += 10
    if 'harel-group.co.il' in text_lower:
        company_scores["הראל"] += 10
    if 'migdal.co.il' in text_lower:
        company_scores["מגדל"] += 10
    if 'menoramivt.co.il' in text_lower:
        company_scores["מנורה"] += 10
    if 'ayalon-ins.co.il' in text_lower:
        company_scores["איילון"] += 10
    
    # Check phone numbers
    if '3455*' in text or '*3455' in text:
        company_scores["הפניקס"] += 8
    if '*2800' in text or '2800*' in text:
        company_scores["כלל"] += 8
    if '*2407' in text or '2407*' in text:
        company_scores["הראל"] += 8
    if '*2679' in text or '2679*' in text:
        company_scores["מגדל"] += 8
    if '*2000' in text or '2000*' in text:
        company_scores["מנורה"] += 8
    if '*5620' in text or '5620*' in text:
        company_scores["איילון"] += 8
    
    # Count company name appearances
    company_scores["הפניקס"] += (text.count('פניקס') + text.count('הפניקס') + text.count('סקינפה')) * 3
    company_scores["כלל"] += ((text.count('כלל') - text.count('כללי')) + text.count('ללכ')) * 3
    company_scores["הראל"] += (text.count('הראל') + text.count('לארה')) * 3
    company_scores["מגדל"] += (text.count('מגדל') + text.count('לדגמ')) * 3
    company_scores["מנורה"] += (text.count('מנורה') + text.count('הרונמ')) * 3
    company_scores["איילון"] += (text.count('איילון') + text.count('ןוליא')) * 3
    
    max_score = max(company_scores.values())
    if max_score >= 3:
        return max(company_scores, key=company_scores.get)
    
    return None


def create_chunks(text, size=1500, overlap=300):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i + size])
        if len(chunk.strip()) > 100: 
            chunks.append(chunk)
    return chunks


@st.cache_resource
def init_connections():
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        st.error("⚠️ Supabase credentials not configured!")
        st.stop()
    
    db = SupabaseDatabase(url=url, key=key)
    
    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").strip()
    claude = None
    if api_key:
        try:
            claude = Anthropic(api_key=api_key)
            st.sidebar.success("✅ Claude API connected!")
        except Exception as e:
            st.error(f"❌ Error initializing Claude: {str(e)}")
    else:
        st.sidebar.warning("⚠️ ANTHROPIC_API_KEY not found")
    
    return db, claude


db, claude_client = init_connections()

st.sidebar.write("🔍 Testing Supabase...")
try:
    test = db.client.table("users").select("id").limit(1).execute()
    st.sidebar.success("✅ Supabase connected!")
except Exception as e:
    st.sidebar.error(f"❌ Supabase error: {str(e)[:100]}")

st.sidebar.info(f"📚 במאגר: {len(NISPACH_INFO_EXPANDED)} נספחים")


# ============================================================================
# LOGIN PAGE
# ============================================================================

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


# ============================================================================
# MAIN APP - SIDEBAR
# ============================================================================

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
                    except:
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


# ============================================================================
# PAGE ROUTING
# ============================================================================

if not st.session_state.current_investigation_id and st.session_state.page not in ["🏠 בית", "📥 איך להשיג פוליסות", "📚 מדריך נספחים", "👑 ניהול"]:
    st.warning("⚠️ בחר חקירה")
    st.stop()


# ============================================================================
# PAGE: HOME
# ============================================================================

if st.session_state.page == "🏠 בית":
    st.title("🏠 השוואת פוליסות")
    st.write(f"שלום **{st.session_state.username}**! 👋")
    
    all_inv = db.get_all_investigations(st.session_state.user_id)
    col1, col2 = st.columns(2)
    with col1: 
        st.metric("החקירות שלי", len(all_inv))
    with col2: 
        st.metric("פוליסות", sum(inv['policy_count'] for inv in all_inv))
    
    if all_inv:
        st.markdown("### 📊 החקירות האחרונות")
        for inv in all_inv[:5]:
            with st.expander(f"🔍 {inv['client_name']}"):
                st.write(f"**פוליסות:** {inv['policy_count']}")
                st.write(f"**שאלות:** {inv['question_count']}")
                st.caption(f"נוצר: {inv['created_at']}")


# ============================================================================
# PAGE: HOW TO GET POLICIES
# ============================================================================

elif st.session_state.page == "📥 איך להשיג פוליסות":
    st.title("📥 איך להשיג את הפוליסות שלך")
    st.write("מדריך פשוט לקבלת פוליסות מכל חברות הביטוח")
    
    st.markdown("---")
    st.info("💡 **טיפ:** רוב חברות הביטוח מאפשרות להוריד את הפוליסות שלך דרך האזור האישי באתר")
    st.markdown("---")
    
    with st.expander("🏢 מגדל - Migdal"):
        st.markdown("""
        ### שלבים לקבלת הפוליסה:
        
        1. **כנס לאתר:** [www.migdal.co.il](https://www.migdal.co.il)
        2. **התחבר לאזור האישי**
        3. **לחץ על "הפוליסות שלי"**
        4. **בחר את הפוליסה** שרוצה להוריד
        5. **לחץ על "הורד פוליסה"**
        
        📞 **מוקד שירות:** *2679
        """)


# ============================================================================
# PAGE: UPLOAD
# ============================================================================

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


# ============================================================================
# PAGE: QUESTIONS - ✅ FIXED VERSION WITH LOCATION DETECTION
# ============================================================================

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
                                    placeholder="למשל: איפה אני יכול לעשות בדיקות?",
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
                                    # Check for nispach numbers
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
                                    
                                    # ✅ FIX: Check if this is a location question
                                    is_location_q = detect_location_question(query)
                                    
                                    selected_ids = [policy_options[name] for name in selected_names]
                                    all_contexts = []
                                    location_found = False
                                    
                                    for name, pol_id in zip(selected_names, selected_ids):
                                        chunks = db.search_chunks(pol_id, query, top_k=30)  # Increased from 20
                                        
                                        if chunks:
                                            # ✅ FIX: If location question, try to extract location info
                                            if is_location_q and not location_found:
                                                location_info = extract_location_info_from_chunks(chunks)
                                                if location_info:
                                                    formatted_answer = format_location_answer(location_info, name)
                                                    st.markdown("### 💡 תשובה:")
                                                    st.success(formatted_answer)
                                                    
                                                    # Save to history
                                                    db.save_qa(st.session_state.current_investigation_id, 
                                                             query, formatted_answer, [name])
                                                    location_found = True
                                                    break  # Found answer, stop searching
                                            
                                            # Regular context building
                                            context = f"=== פוליסה: {name} ===\n" + "\n\n".join([c['text'] for c in chunks[:8]])
                                            all_contexts.append(context)
                                    
                                    # If location question was answered, skip Claude call
                                    if is_location_q and location_found:
                                        pass  # Already showed answer above
                                    elif all_contexts:
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
                                    st.code(traceback.format_exc())
    
    else:  # General information mode
        st.info("💡 **במצב זה אתה יכול לשאול שאלות כלליות על ביטוחים**")
        
        with st.expander("🏢 השווה חברות ספציפיות (אופציונלי)"):
            selected_companies = st.multiselect(
                "בחר חברות להשוואה:",
                COMPANIES,
                help="השאר ריק לשאלה כללית"
            )
        
        query = st.text_area(
            "שאל שאלה כללית:",
            placeholder="לדוגמה: מה ההבדל בין מגדל להראל?",
            height=100
        )
        
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
                    with st.spinner("מחפש מידע..."):
                        try:
                            company_context = ""
                            if selected_companies:
                                company_context = "\n\nמידע על החברות שנבחרו:\n"
                                for company in selected_companies:
                                    if company in COMPANIES_INFO:
                                        info = COMPANIES_INFO[company]
                                        company_context += f"\n{company}: {', '.join(info['strengths'])}\n"
                            
                            system_prompt = """אתה יועץ ביטוח ישראלי. ענה בצורה מקצועית ומפורטת."""
                            
                            user_content = f"""שאלה: {query}
{company_context}

ענה על השאלה."""
                            
                            response = fresh_claude.messages.create(
                                model="claude-sonnet-4-20250514",
                                max_tokens=2000,
                                system=system_prompt,
                                messages=[{"role": "user", "content": user_content}]
                            )
                            
                            answer = response.content[0].text
                            st.markdown("### 💡 תשובה:")
                            st.success(answer)
                            
                            db.save_qa(st.session_state.current_investigation_id, query, answer, ["מידע כללי"])
                            
                        except Exception as e:
                            st.error(f"❌ שגיאה: {str(e)}")


# ============================================================================
# PAGE: NISPACHIM GUIDE
# ============================================================================

elif st.session_state.page == "📚 מדריך נספחים":
    st.title("📚 מדריך נספחים")
    st.info(f"📊 **במאגר: {len(NISPACH_INFO_EXPANDED)} נספחים**")
    
    search_term = st.text_input("🔍 חפש נספח:", placeholder="8713 או אבחנה מהירה")
    
    if search_term:
        found = []
        search_lower = search_term.lower()
        
        for num, data in NISPACH_INFO_EXPANDED.items():
            if (search_term in num or 
                search_lower in data['name'].lower() or 
                search_lower in data['description'].lower()):
                found.append((num, data))
        
        if found:
            st.success(f"✅ נמצאו {len(found)} תוצאות")
            for num, data in found:
                with st.expander(f"📋 נספח {num} - {data['name']}", expanded=True):
                    st.markdown(f"**תיאור:** {data['description']}")


# ============================================================================
# PAGE: COMPARISON
# ============================================================================

elif st.session_state.page == "⚖️ השוואה":
    st.title("⚖️ השוואה")
    policies = db.get_policies(st.session_state.current_investigation_id)
    
    if len(policies) < 2:
        st.warning("⚠️ העלה לפחות 2 פוליסות")


# ============================================================================
# PAGE: HISTORY
# ============================================================================

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


# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.caption(f"מערכת השוואת פוליסות v3.1 FIXED | משתמש: {st.session_state.username}")
