"""BituachBot design system: tokens, CSS and small HTML builders.

Direction: an insurance *document* feel. Ink navy on cool paper, one green for
actions/ready and amber for "waiting". Headings in Frank Ruhl Libre (the Hebrew
book serif), UI in IBM Plex Sans Hebrew. The signature element is the annex
"ledger": every נספח is a row with its code set like a printed schedule number.
No keyboard emojis in the chrome — icons are Material Symbols (bundled with Streamlit).
"""
from html import escape as _e

FONTS_URL = ("https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@500;700;900"
             "&family=IBM+Plex+Sans+Hebrew:wght@400;500;600;700&display=swap")

BASE_CSS = """
@import url('__FONTS__');
:root {
  --ink:#16233B; --ink-2:#55607A; --ink-3:#8B94A7;
  --paper:#F4F6F3; --surface:#FFFFFF; --line:#DCE1DA; --line-2:#ECEFEA;
  --green:#0B7A55; --green-d:#085F42; --green-t:#E3F3EC;
  --amber:#9A5B06; --amber-t:#FCF1DC; --blue:#2B4C9B; --blue-t:#E9EFFB;
  --red:#B3261E; --red-t:#FBE9E7;
  --serif:'Frank Ruhl Libre','David Libre','David','Times New Roman',serif;
  --sans:'IBM Plex Sans Hebrew','Arimo','Segoe UI','Arial Hebrew',Arial,sans-serif;
  --r:10px;
}
html, body { direction: rtl; }
.stApp { background: var(--paper); color: var(--ink); }
.stApp *:not([data-testid="stIconMaterial"]):not(.bb-ms),
[data-baseweb="popover"] *:not([data-testid="stIconMaterial"]):not(.bb-ms) { font-family: var(--sans) !important; }
.stApp .bb-serif.bb-serif.bb-serif.bb-serif, .stApp .bb-serif.bb-serif.bb-serif.bb-serif *,
[data-baseweb="popover"] .bb-serif.bb-serif.bb-serif.bb-serif { font-family: var(--serif) !important; }
.stApp [data-testid="stCode"][data-testid="stCode"][data-testid="stCode"] * {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace !important; }
.bb-ms { font-family: 'Material Symbols Rounded' !important; font-weight: 400; font-style: normal; font-size: 1.25em;
  line-height: 1; display: inline-block; vertical-align: -0.2em; direction: ltr; letter-spacing: normal;
  text-transform: none; white-space: nowrap; -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga'; }

/* Streamlit chrome */
#MainMenu, footer, [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stMainBlockContainer"] { padding: 24px 20px 96px !important; max-width: 920px !important; }
[data-testid="stCode"], [data-testid="stCode"] * { direction: ltr !important; text-align: left !important; }
[data-testid="stCode"] pre, [data-testid="stCode"] code { white-space: pre-wrap !important; word-break: break-all !important; }
[data-testid="stCode"] pre { background: var(--surface) !important; border: 1px solid var(--line); border-radius: 8px !important; }
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stCaptionContainer"],
[data-baseweb="popover"] [data-testid="stMarkdownContainer"] { text-align: right; }
[data-testid="stMarkdownContainer"] p { line-height: 1.6; }
[data-testid="stCaptionContainer"] p { color: var(--ink-2) !important; font-size: .85rem !important; }
hr { border-color: var(--line) !important; margin: 20px 0 !important; }

/* Buttons */
.stApp button[kind="primary"], .stApp button[kind="primaryFormSubmit"] {
  background: var(--green) !important; border: 1px solid var(--green) !important; color: #fff !important;
  border-radius: 8px !important; min-height: 44px !important; font-weight: 600 !important; box-shadow: none !important; }
.stApp button[kind="primary"]:hover, .stApp button[kind="primaryFormSubmit"]:hover {
  background: var(--green-d) !important; border-color: var(--green-d) !important; }
.stApp button[kind="primary"] p, .stApp button[kind="primaryFormSubmit"] p { color: #fff !important; font-weight: 600 !important; }
.stApp button[kind="secondary"], .stApp button[kind="secondaryFormSubmit"] {
  background: var(--surface) !important; border: 1px solid var(--line) !important; color: var(--ink) !important;
  border-radius: 8px !important; min-height: 40px !important; font-weight: 500 !important; box-shadow: none !important; }
.stApp button[kind="secondary"]:hover, .stApp button[kind="secondaryFormSubmit"]:hover {
  border-color: var(--ink-3) !important; color: var(--ink) !important; }
.stApp button[kind="tertiary"] { color: var(--green) !important; font-weight: 600 !important;
  padding: 2px 0 !important; min-height: 0 !important; border: 0 !important; background: transparent !important; }
.stApp button[kind="tertiary"]:hover p { text-decoration: underline; }
.stApp button:focus-visible { outline: 2px solid var(--green) !important; outline-offset: 2px !important; }
.stApp button:disabled { opacity: .5 !important; }

/* Inputs */
.stApp [data-baseweb="input"], .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="textarea"] {
  background: var(--surface) !important; border: 1px solid var(--line) !important; border-radius: 8px !important; }
.stApp [data-baseweb="base-input"] { background: transparent !important; }
.stApp [data-baseweb="input"]:focus-within, .stApp [data-baseweb="select"] > div:focus-within {
  border-color: var(--green) !important; box-shadow: 0 0 0 3px rgba(11,122,85,.16) !important; }
.stApp [data-testid="stTextInputRootElement"] { background: var(--surface) !important; border: 1px solid var(--line) !important;
  border-radius: 8px !important; }
.stApp [data-testid="stTextInputRootElement"]:focus-within { border-color: var(--green) !important;
  box-shadow: 0 0 0 3px rgba(11,122,85,.16) !important; }
.stApp [data-testid="stTextInputRootElement"] input { background: transparent !important; }
.stApp [data-testid="stChatInput"] > div { background: var(--surface) !important; border: 1px solid var(--line) !important;
  border-radius: 10px !important; }
.stApp [data-testid="stSelectbox"] .react-aria-ComboBox > div { background: var(--surface) !important;
  border: 1px solid var(--line) !important; border-radius: 8px !important; }
.stApp [data-testid="stSelectbox"] .react-aria-ComboBox > div:focus-within {
  border-color: var(--green) !important; box-shadow: 0 0 0 3px rgba(11,122,85,.16) !important; }
.stApp [data-testid="stSelectbox"] input { background: transparent !important; }
.stApp input { color: var(--ink) !important; min-height: 42px; }
.stApp input::placeholder { color: var(--ink-3) !important; }
[data-testid="stWidgetLabel"] p { font-size: .875rem !important; font-weight: 500 !important; color: var(--ink) !important; }
[data-testid="stCheckbox"] p { font-size: .88rem !important; color: var(--ink-2) !important; }

/* Expanders ("dropdowns") */
[data-testid="stExpander"] details { border: 1px solid var(--line) !important; border-radius: var(--r) !important;
  background: var(--surface) !important; }
[data-testid="stExpander"] summary { padding: 12px 16px !important; }
[data-testid="stExpander"] summary p { font-weight: 600 !important; color: var(--ink) !important; font-size: .95rem !important; }
[data-testid="stExpander"] summary:hover p { color: var(--green) !important; }
[data-testid="stExpander"] details:not([open]) summary [data-testid="stIconMaterial"] { transform: scaleX(-1); }

/* Popover menus */
[data-testid="stPopoverBody"] { border-radius: 12px !important; border: 1px solid var(--line) !important; direction: rtl; }

/* Alerts */
[data-testid="stAlertContainer"] { border-radius: 8px !important; }
[data-testid="stAlertContainer"] p { font-size: .92rem !important; }

/* File uploader, in Hebrew */
[data-testid="stFileUploaderDropzone"] { background: var(--surface) !important; border: 1.5px dashed #BFC8BE !important;
  border-radius: var(--r) !important; }
[data-testid="stFileUploaderDropzoneInstructions"] span, [data-testid="stFileUploaderDropzoneInstructions"] small { display: none !important; }
[data-testid="stFileUploaderDropzoneInstructions"]::after { content: "גררו לכאן קובצי PDF, או בחרו מהמכשיר";
  color: var(--ink-2); font-size: .9rem; }
[data-testid="stFileUploaderDropzone"] button p { font-size: 0 !important; line-height: 0 !important; }
[data-testid="stFileUploaderDropzone"] button p::after { content: "בחירת קבצים"; font-size: .9rem; line-height: 1.4; }
[data-testid="stFileUploaderFile"] { direction: ltr; }

/* Segmented control (section switch) */
[data-testid="stButtonGroup"] button { border-radius: 8px !important; min-height: 40px !important; font-weight: 500 !important; }
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"],
[data-testid="stButtonGroup"] button[aria-checked="true"] {
  background: var(--ink) !important; border-color: var(--ink) !important; color: #fff !important; }
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"] p,
[data-testid="stButtonGroup"] button[aria-checked="true"] p { color: #fff !important; }

/* ── BituachBot components ── */
.bb-titlerow { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; }
.bb-h1 { font-weight: 900; font-size: clamp(1.7rem, 5vw, 2.3rem); line-height: 1.15; margin: 6px 0 4px; color: var(--ink); }
.bb-h2 { font-weight: 700; font-size: 1.3rem; line-height: 1.25; margin: 26px 0 10px; color: var(--ink);
  display: flex; align-items: baseline; gap: 10px; }
.bb-h2 small { font-family: var(--sans) !important; font-size: .82rem; font-weight: 500; color: var(--ink-3); }
.bb-sub { color: var(--ink-2); font-size: .95rem; margin: 0 0 14px; }
.bb-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r); padding: 16px 18px; margin-bottom: 12px; }
.bb-card .bb-label { margin: 0 0 3px; font-size: .8rem; font-weight: 600; color: var(--ink-3); }
.bb-card .bb-big { font-size: 1.05rem; font-weight: 600; color: var(--ink); }
.bb-card .bb-meta { color: var(--ink-2); font-size: .86rem; }
.bb-kv { display: flex; flex-wrap: wrap; gap: 6px 22px; color: var(--ink-2); font-size: .9rem; }
.bb-kv b { color: var(--ink); font-weight: 600; }
.bb-ltr { direction: ltr; unicode-bidi: isolate; display: inline-block; }
.stApp a.bb-link { color: var(--green) !important; font-weight: 600; text-decoration: none !important; white-space: nowrap; }
.stApp a.bb-link:hover { text-decoration: underline !important; }
.stApp a.bb-btn { display: inline-flex; align-items: center; gap: 8px; background: var(--green); color: #fff !important;
  font-weight: 600; padding: 10px 18px; border-radius: 8px; text-decoration: none !important; }
.stApp a.bb-btn:hover { background: var(--green-d); }

.bb-pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px;
  font-size: .78rem; font-weight: 600; white-space: nowrap; }
.bb-pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.bb-pill.ok { background: var(--green-t); color: var(--green); }
.bb-pill.wait { background: var(--amber-t); color: var(--amber); }
.bb-pill.part { background: var(--blue-t); color: var(--blue); }
.bb-pill.none { background: #ECEEEB; color: var(--ink-2); }

/* The annex ledger */
.bb-ledger { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r); overflow: hidden; margin-bottom: 12px; }
.bb-row { display: grid; grid-template-columns: 78px minmax(0, 1fr) auto; align-items: center; gap: 14px;
  padding: 12px 14px; border-top: 1px solid var(--line-2); }
.bb-row:first-child { border-top: 0; }
.bb-code { font-weight: 700; font-size: 1.2rem; line-height: 1; text-align: center; direction: ltr;
  font-variant-numeric: tabular-nums; color: var(--ink); background: var(--paper); border: 1px solid var(--line);
  border-radius: 6px; padding: 8px 0 7px; }
.bb-row.wait .bb-code { background: var(--amber-t); border-color: #EBD3A1; color: var(--amber); }
.bb-row .bb-name { font-weight: 600; color: var(--ink); overflow-wrap: anywhere; }
.bb-row .bb-meta { color: var(--ink-2); font-size: .84rem; }
.bb-row.wait .bb-name { color: var(--ink-2); font-weight: 500; }

/* Portfolio status bar (agent) */
.bb-bar { display: flex; height: 10px; border-radius: 999px; overflow: hidden; background: #E6E9E4; margin: 4px 0 10px; }
.bb-bar i { display: block; height: 100%; }
.bb-bar .ok { background: var(--green); } .bb-bar .part { background: var(--blue); }
.bb-bar .wait { background: #D69A2D; } .bb-bar .none { background: #B9C0B8; }
.bb-legend { display: flex; flex-wrap: wrap; gap: 8px 18px; font-size: .88rem; color: var(--ink-2); margin-bottom: 6px; }
.bb-legend b { color: var(--ink); font-size: 1.05rem; font-weight: 700; margin-inline-end: 4px; }
.bb-legend span::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-inline-end: 6px; }
.bb-legend .ok::before { background: var(--green); } .bb-legend .part::before { background: var(--blue); }
.bb-legend .wait::before { background: #D69A2D; } .bb-legend .none::before { background: #B9C0B8; }

/* Client rows (agent list): each row is a keyed Streamlit container "row_<id>" */
[class*="st-key-row_"] { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r);
  padding: 12px 14px 14px !important; }
[class*="st-key-row_"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center !important; gap: 12px !important; }
[class*="st-key-row_"] [data-testid="stColumn"] { min-width: 0 !important; }
[class*="st-key-row_"] [data-testid="stColumn"]:last-child { flex: 0 0 auto !important; width: auto !important; }
.bb-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; }
.bb-top .bb-name { font-weight: 600; font-size: 1.02rem; color: var(--ink); }
.bb-meta { color: var(--ink-2); font-size: .84rem; }

/* Top bar */
.st-key-bb_topbar { background: var(--ink); border-radius: 12px; padding: 10px 16px !important; margin-bottom: 14px; }
.st-key-bb_topbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center !important; gap: 12px !important; }
.st-key-bb_topbar [data-testid="stColumn"] { min-width: 0 !important; }
.st-key-bb_topbar [data-testid="stColumn"]:last-child { flex: 0 0 auto !important; width: auto !important; }
.bb-brand { display: flex; align-items: center; gap: 10px; color: #fff; min-width: 0; }
.bb-brand svg { flex: 0 0 auto; }
.bb-brand .bb-word { font-weight: 900; font-size: 1.3rem; line-height: 1; color: #fff; }
.bb-brand .bb-who { color: #B9C2D6; font-size: .84rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.st-key-bb_topbar [data-testid="stPopover"] button { background: rgba(255,255,255,.08) !important;
  border: 1px solid rgba(255,255,255,.2) !important; color: #fff !important; min-height: 38px !important; }
.st-key-bb_topbar [data-testid="stPopover"] button p { color: #fff !important; }
.st-key-bb_topbar [data-testid="stPopover"] button:hover { background: rgba(255,255,255,.16) !important; }

/* Form brand head (auth pages) */
.bb-formhead { margin-bottom: 22px; }
.bb-formhead .bb-mark { display: flex; align-items: center; gap: 8px; color: var(--green); font-weight: 900; font-size: 1.2rem; margin-bottom: 18px; }
.bb-formhead .bb-title { font-weight: 900; font-size: 1.75rem; line-height: 1.2; color: var(--ink); margin: 0 0 6px; }
.bb-formhead .bb-desc { color: var(--ink-2); font-size: .95rem; margin: 0; }
.bb-choice { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r); padding: 16px 18px; margin-bottom: 10px; }
.bb-choice b { display: block; font-size: 1.02rem; color: var(--ink); }
.bb-choice span { color: var(--ink-2); font-size: .88rem; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
""".replace("__FONTS__", FONTS_URL)

# Auth pages: an ink side panel on wide screens, a plain centred form on phones.
AUTH_CSS = """
.stApp { background: var(--surface); }
[data-testid="stMainBlockContainer"] { max-width: 480px !important; padding-top: 40px !important; }
.bb-side { display: none; }
@media (min-width: 992px) {
  [data-testid="stMain"] { padding-left: 44vw; }
  [data-testid="stMainBlockContainer"] { padding-top: 72px !important; }
  .bb-side { display: flex; flex-direction: column; justify-content: center; position: fixed; top: 0; bottom: 0; left: 0;
    width: 44vw; background: var(--ink); padding: 56px clamp(32px, 4.5vw, 72px); z-index: 2; overflow: hidden; }
}
.bb-side .bb-eyebrow { color: #8FD3B8; font-weight: 600; font-size: .9rem; margin-bottom: 14px; }
.bb-side h1 { font-weight: 900; font-size: clamp(2rem, 3.1vw, 3rem); line-height: 1.15; color: #fff; margin: 0 0 16px; }
.bb-side .bb-lead { color: #C6CEDF; font-size: 1.02rem; line-height: 1.65; margin: 0 0 28px; max-width: 34em; }
.bb-side ul { list-style: none; padding: 0; margin: 28px 0 0; }
.bb-side li { color: #E6EAF2; font-size: .95rem; padding: 7px 0; display: flex; gap: 10px; align-items: flex-start; }
.bb-side li .bb-ms { color: #8FD3B8; }
.bb-side .bb-foot { color: #8B94A7; font-size: .8rem; margin-top: 28px; }
.bb-side .bb-ledger { border-color: rgba(255,255,255,.14); background: rgba(255,255,255,.04); max-width: 30em; }
.bb-side .bb-row { border-top-color: rgba(255,255,255,.1); grid-template-columns: 66px minmax(0, 1fr) auto; padding: 10px 12px; }
.bb-side .bb-code { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.16); color: #fff; font-size: 1.05rem; }
.bb-side .bb-row.wait .bb-code { background: rgba(214,154,45,.18); border-color: rgba(214,154,45,.4); color: #F2C879; }
.bb-side .bb-row .bb-name { color: #fff; } .bb-side .bb-row .bb-meta { color: #AEB8CC; }
.bb-side .bb-row.wait .bb-name { color: #C6CEDF; }
.bb-side .bb-pill.ok { background: rgba(143,211,184,.16); color: #8FD3B8; }
.bb-side .bb-pill.wait { background: rgba(214,154,45,.18); color: #F2C879; }
.bb-side .bb-pill.part { background: rgba(160,185,240,.16); color: #B6C8F3; }
.bb-side .bb-pill.none { background: rgba(255,255,255,.1); color: #C6CEDF; }
"""

SHIELD = ('<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
          '<path d="M12 2.5 4.5 5.4v6.1c0 4.6 3.1 8.4 7.5 10 4.4-1.6 7.5-5.4 7.5-10V5.4L12 2.5Z" fill="{c}"/>'
          '<path d="m8.6 12.1 2.4 2.4 4.5-4.9" stroke="{k}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def shield(size: int = 22, color: str = "#0B7A55", check: str = "#fff") -> str:
    return SHIELD.format(s=size, c=color, k=check)


def ms(name: str) -> str:
    """Material Symbols icon for use inside custom HTML."""
    return f'<span class="bb-ms" aria-hidden="true">{name}</span>'


def ltr(text) -> str:
    return f'<span class="bb-ltr">{_e(str(text))}</span>'


def pill(kind: str, label: str) -> str:
    return f'<span class="bb-pill {kind}">{_e(label)}</span>'


def h1(text: str) -> str:
    return f'<div class="bb-h1 bb-serif">{_e(text)}</div>'


def h2(text: str, note: str = "") -> str:
    return f'<div class="bb-h2 bb-serif">{_e(text)}' + (f"<small>{_e(note)}</small>" if note else "") + "</div>"


def ledger(rows: list[dict]) -> str:
    """rows: [{code, name, meta, ready(bool), pill(optional str)}]"""
    out = ['<div class="bb-ledger">']
    for r in rows:
        ready = r.get("ready", True)
        label = r.get("pill") or ("מוכן" if ready else "בעיבוד")
        meta = f'<div class="bb-meta">{_e(r["meta"])}</div>' if r.get("meta") else ""
        out.append(
            f'<div class="bb-row {"ok" if ready else "wait"}">'
            f'<div class="bb-code bb-serif{" bb-code-sm" if r.get("small") else ""}">{_e(str(r["code"]))}</div>'
            f'<div><div class="bb-name">{_e(r.get("name") or "")}</div>{meta}</div>'
            f'{pill("ok" if ready else "wait", label)}</div>')
    out.append("</div>")
    return "".join(out)


def status_bar(counts: dict, labels: dict) -> str:
    """counts/labels keyed by ok | part | wait | none."""
    total = sum(counts.values()) or 1
    bar = "".join(f'<i class="{k}" style="width:{counts.get(k, 0) / total * 100:.2f}%"></i>'
                  for k in ("ok", "part", "wait", "none") if counts.get(k))
    legend = "".join(f'<span class="{k}"><b>{counts.get(k, 0)}</b>{_e(labels[k])}</span>'
                     for k in ("ok", "part", "wait", "none"))
    return f'<div class="bb-bar">{bar}</div><div class="bb-legend">{legend}</div>'


def brand(who: str = "") -> str:
    who_html = f'<span class="bb-who">{_e(who)}</span>' if who else ""
    return (f'<div class="bb-brand">{shield(24, "#8FD3B8", "#16233B")}'
            f'<span class="bb-word bb-serif">BituachBot</span>{who_html}</div>')


def form_head(title: str, desc: str = "") -> str:
    d = f'<p class="bb-desc">{_e(desc)}</p>' if desc else ""
    return (f'<div class="bb-formhead"><div class="bb-mark bb-serif">{shield(24)}<span>BituachBot</span></div>'
            f'<div class="bb-title bb-serif">{_e(title)}</div>{d}</div>')


def choice(title: str, desc: str) -> str:
    return f'<div class="bb-choice"><b>{_e(title)}</b><span>{_e(desc)}</span></div>'


def side_panel(audience: str) -> str:
    """The ink panel of the auth pages. It shows the product itself: the annex ledger a client sees,
    or the client list an agent sees."""
    if audience == "agent":
        eyebrow = "כלי עבודה לסוכני ביטוח מורשים"
        title = "הלקוחות שואלים על הפוליסה. הבוט עונה בשמך."
        lead = ("עוזר דיגיטלי בוואטסאפ שמסביר לכל לקוח מה כתוב בנספחים שלו — "
                "ואתה רואה בפאנל מי מוכן, מה חסר ומה נשאל.")
        demo = ledger([
            {"code": "3/3", "name": "מיכל כהן", "meta": "כל הנספחים במאגר", "ready": True, "pill": "מוכן"},
            {"code": "0/2", "name": "יוסי לוי", "meta": "חסרים במאגר: 5404, 5406", "ready": False, "pill": "חסר נספח"},
            {"code": "—", "name": "רונית אברהם", "meta": "נרשמה דרך הקישור שלך", "ready": False, "pill": "בלי פוליסה"},
        ])
        points = ["לקוחות נרשמים רק דרך הקישור האישי שלך",
                  "הבוט מסביר את הפוליסה — בלי המלצות ובלי ייעוץ רפואי",
                  "התראה בוואטסאפ על כל לקוח חדש ועל כל נספח שחסר"]
    else:
        eyebrow = "העוזר הדיגיטלי של סוכן הביטוח שלך"
        title = "מה הביטוח שלך מכסה, בשפה פשוטה."
        lead = "שולחים שאלה בוואטסאפ ומקבלים הסבר לפי הנספחים שבפוליסה שלך — מטעם סוכן הביטוח שלך."
        demo = ledger([
            {"code": "6417", "name": "ניתוחים וטיפולים מחליפי ניתוח", "meta": "הפניקס", "ready": True},
            {"code": "2210", "name": "ייעוץ ובדיקות אבחנתיות", "meta": "מגדל · 12 טיפולי פיזיותרפיה בשנה", "ready": True},
            {"code": "5404", "name": "נספח 5404", "meta": "הסוכן שלך משלים אותו", "ready": False},
        ])
        points = ["תשובות לפי הפוליסה האישית שלך, עם הפניה לנספח",
                  "זמין בוואטסאפ בכל שעה",
                  "לכל החלטה — הסוכן שלך נשאר הכתובת"]
    lis = "".join(f"<li>{ms('check_circle')}<span>{_e(p)}</span></li>" for p in points)
    return (f'<aside class="bb-side"><div class="bb-eyebrow">{_e(eyebrow)}</div>'
            f'<h1 class="bb-serif">{_e(title)}</h1><p class="bb-lead">{_e(lead)}</p>{demo}'
            f'<ul>{lis}</ul><div class="bb-foot">המידע מאובטח ומעובד לפי חוק הגנת הפרטיות.</div></aside>')
