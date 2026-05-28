import base64
import json
from pathlib import Path

import streamlit as st
import requests

API_BASE = "http://localhost:8000"

MODES = ["vector", "hybrid", "graph"]
SUGGESTIONS = [
    ("ما هي شروط إلغاء ترخيص البنك؟", "Licensing"),
    ("متى يجب إخطار البنك المركزي بتغيير ملكية البنك؟", "Ownership"),
    ("ما هي إجراءات وقف العمليات المصرفية جزئياً؟", "Operations"),
]

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --brand: #062F62;
    --brand-deep: #022048;
    --brand-tint: #1E548F;
    --adib: #009CDA;
    --adib-soft: #4DBAE7;
    --adib-deep: #0078A8;
    --adib-glow: #9DDBF0;
    --gold: #C9A961;
    --cream: #F8FBFE;
    --cream-soft: #FFFFFF;
    --cream-deeper: #E8F2FA;
    --cream-frame: #F1F6FB;
    --cream-border: #D8E5EE;
    --cream-edge: #BFD3E2;
    --ink: #0F1B2D;
    --ink-muted: #5A6776;
    --ink-faint: #94A2B0;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
    background: var(--cream);
    color: var(--ink);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

[data-testid="stSidebar"] {
    background: var(--cream-frame);
    border-right: 1px solid var(--cream-border);
}

[data-testid="stSidebar"] [data-testid="stMarkdown"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdown"] h3 {
    color: var(--brand);
}

.sidebar-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0 12px;
}
.sidebar-logo {
    width: 44px;
    height: 44px;
    border-radius: 999px;
    background: var(--cream-soft);
    box-shadow: 0 6px 16px rgba(6, 47, 98, 0.15);
    border: 1px solid rgba(0, 156, 218, 0.2);
    overflow: hidden;
}
.sidebar-logo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transform: scale(1.15);
}
.sidebar-title {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 18px;
    color: var(--brand);
    line-height: 1;
}
.sidebar-subtitle {
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--adib-deep);
    margin-top: 4px;
}

.section-label {
    font-size: 10px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--ink-faint);
    font-weight: 600;
    margin: 10px 0 6px;
}

.stButton > button {
    border-radius: 12px;
    border: 1px solid var(--cream-border);
    background: var(--cream-soft);
    color: var(--ink);
    font-weight: 500;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    border-color: var(--adib-soft);
    color: var(--brand);
    background: var(--cream-deeper);
}

.primary-button > button {
    background: linear-gradient(135deg, var(--adib), var(--adib-deep));
    color: white;
    border: none;
    box-shadow: 0 10px 18px rgba(0, 120, 168, 0.2);
}
.primary-button > button:hover {
    background: linear-gradient(135deg, var(--adib-deep), var(--brand));
}

.chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid var(--cream-border);
    background: var(--cream-frame);
    font-size: 11px;
    color: var(--ink-muted);
}

.chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    border-bottom: 1px solid var(--cream-border);
    background: rgba(248, 251, 254, 0.9);
    backdrop-filter: blur(6px);
}

.chat-header-title {
    font-size: 13px;
    color: var(--ink-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.chat-header-badge {
    font-size: 10px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--ink-faint);
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: var(--adib);
    display: inline-block;
}

.login-card {
    background: var(--cream-soft);
    border: 1px solid var(--cream-border);
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 14px 28px rgba(15, 27, 45, 0.08);
}

.mock-card {
    background: var(--cream-frame);
    border: 1px solid var(--cream-border);
    border-radius: 14px;
    padding: 16px;
}

.suggestion-card button {
    text-align: left;
    padding: 14px;
    border-radius: 16px;
    border: 1px solid var(--cream-border);
    background: var(--cream-soft);
    height: 100%;
    white-space: pre-wrap;
}

.suggestion-tag {
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--adib-deep);
    font-weight: 600;
}

[data-testid="stChatMessageContent"] p {
    direction: auto;
    text-align: start;
}

div[data-testid="stChatMessage"][data-author="user"] [data-testid="stMarkdown"] {
    background: var(--cream-deeper);
    border: 1px solid rgba(0, 156, 218, 0.25);
    border-radius: 18px;
    padding: 12px 16px;
    max-width: 78%;
    margin-left: auto;
    color: var(--brand);
}

div[data-testid="stChatMessage"][data-author="assistant"] [data-testid="stMarkdown"] {
    background: transparent;
    color: var(--ink);
}

.citation-text {
    direction: auto;
    text-align: start;
    font-size: 0.88rem;
    white-space: pre-wrap;
}

code, kbd {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
}

div[data-testid="stChatInput"] {
    border-top: 1px solid var(--cream-border);
    background: rgba(248, 251, 254, 0.9);
    backdrop-filter: blur(6px);
}

textarea[data-testid="stChatInputTextArea"] {
    border: 1px solid var(--cream-border);
    border-radius: 16px;
    padding: 12px 14px;
    background: var(--cream-soft);
    font-size: 15px;
    color: var(--ink);
    caret-color: var(--adib);
}

textarea[data-testid="stChatInputTextArea"]::placeholder {
    color: var(--ink-faint);
}

input, textarea {
    color: var(--ink);
}

input::placeholder {
    color: var(--ink-faint);
}

textarea[data-testid="stChatInputTextArea"]:focus {
    border-color: var(--adib);
    box-shadow: 0 0 0 1px var(--adib);
}

details {
    border-radius: 12px;
    border: 1px solid var(--cream-border);
    background: var(--cream-soft);
}
details[open] {
    border-color: var(--adib-soft);
}
summary {
    font-size: 12px;
    color: var(--ink);
}

.footer-hint {
    font-size: 10.5px;
    color: var(--ink-faint);
    text-align: center;
    margin-top: 8px;
    letter-spacing: 0.04em;
}
</style>
"""


def authHeaders():
    return {"Authorization": f"Bearer {st.session_state.token}"}


def apiLogin(username, password):
    r = requests.post(f"{API_BASE}/api/login", json={"username": username, "password": password})
    return r.json()


def apiInfo():
    r = requests.get(f"{API_BASE}/api/info", headers=authHeaders())
    return r.json()


def apiListChats():
    r = requests.get(f"{API_BASE}/api/chats", headers=authHeaders())
    return r.json().get("chats", [])


def apiGetChat(chatId):
    r = requests.get(f"{API_BASE}/api/chats/{chatId}", headers=authHeaders())
    return r.json().get("chat")


def apiCreateChat(title):
    r = requests.post(
        f"{API_BASE}/api/chats",
        json={"title": title},
        headers={**authHeaders(), "Content-Type": "application/json"},
    )
    return r.json().get("chat")


def apiDeleteChat(chatId):
    requests.delete(f"{API_BASE}/api/chats/{chatId}", headers=authHeaders())


@st.cache_data
def logoDataUrl():
    data = Path("frontend/public/logo.jpeg").read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("utf-8")


def streamResponse(query, chatId, mode, k, hops, provider):
    headers = {**authHeaders(), "Content-Type": "application/json"}
    body = {
        "query": query,
        "chatId": chatId,
        "mode": mode,
        "k": k,
        "hops": hops,
        "provider": provider,
    }
    with requests.post(f"{API_BASE}/api/chat", headers=headers, json=body, stream=True) as resp:
        resp.raise_for_status()
        buf = ""
        for raw in resp.iter_content(chunk_size=None, decode_unicode=True):
            buf += raw
            parts = buf.split("\n\n")
            buf = parts.pop()
            for part in parts:
                line = part.strip()
                if not line.startswith("data: "):
                    continue
                evt = json.loads(line[6:])
                if evt.get("type") == "citations":
                    st.session_state["_citations"] = evt["citations"]
                elif evt.get("type") == "token":
                    yield evt.get("text", "")
                elif evt.get("type") == "done" and evt.get("chatId"):
                    st.session_state["_returnedChatId"] = evt["chatId"]


def initState():
    defaults = {
        "token": None,
        "user": None,
        "chatId": None,
        "chatTitle": None,
        "messages": [],
        "providers": None,
        "settings": {"mode": "vector", "k": 5, "hops": 1, "provider": "ollama"},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def loadChat(chatId):
    chat = apiGetChat(chatId)
    if not chat:
        return
    st.session_state.chatId = chatId
    st.session_state.chatTitle = chat.get("title")
    st.session_state.messages = [
        {"role": m["role"], "text": m["text"], "citations": [], "mode": "vector"}
        for m in chat.get("messages", [])
    ]


def renderLogin():
    col = st.columns([1, 2, 1])[1]
    with col:
        logoUrl = logoDataUrl()
        st.markdown(
            f"""
            <div class="text-center" style="margin-bottom: 24px;">
              <div class="sidebar-logo" style="margin: 0 auto 16px;">
                <img src="{logoUrl}" alt="Gazelle" />
              </div>
              <div class="sidebar-title">Gazelle</div>
              <div class="sidebar-subtitle">ADIB · Compliance Assistant</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if "_prefill_user" in st.session_state:
            st.session_state["login_username"] = st.session_state.pop("_prefill_user")
        if "_prefill_pass" in st.session_state:
            st.session_state["login_password"] = st.session_state.pop("_prefill_pass")

        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Sign in", use_container_width=True, type="primary"):
                result = apiLogin(username, password)
                if result.get("ok"):
                    st.session_state.token = result["token"]
                    st.session_state.user = result["user"]
                    st.rerun()
                else:
                    st.error(result.get("error", "Login failed"))
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="mock-card" style="margin-top: 18px;">
              <div class="section-label">Mock users</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        mock_users = [
            ("omar", "Admin · restricted", "admin123"),
            ("sara", "Senior Compliance · confidential", "compliance123"),
            ("ahmed", "Compliance Analyst · internal", "staff123"),
            ("guest", "External · public", "guest"),
        ]
        for name, label, hint in mock_users:
            if st.button(f"{name} · {label}", key=f"mock_{name}", use_container_width=True):
                st.session_state["_prefill_user"] = name
                st.session_state["_prefill_pass"] = hint
                st.rerun()


def renderSidebar():
    with st.sidebar:
        user = st.session_state.user
        logoUrl = logoDataUrl()
        st.markdown(
            f"""
            <div class="sidebar-header">
              <div class="sidebar-logo">
                <img src="{logoUrl}" alt="Gazelle" />
              </div>
              <div>
                <div class="sidebar-title">Gazelle</div>
                <div class="sidebar-subtitle">ADIB · Compliance</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"**{user['username']}**")
        st.caption(f"role: {user.get('role', '—')} · clearance: {user.get('clearance', '—')}")

        if st.button("Sign out", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        st.divider()

        if st.button("＋ New chat", use_container_width=True):
            st.session_state.chatId = None
            st.session_state.chatTitle = None
            st.session_state.messages = []
            st.rerun()

        chats = apiListChats()
        for chat in chats:
            label = (chat.get("title") or "Untitled")[:42]
            active = st.session_state.chatId == chat["id"]
            btn_type = "primary" if active else "secondary"
            col1, col2 = st.columns([5, 1])
            if col1.button(label, key=f"chat_{chat['id']}", use_container_width=True, type=btn_type):
                loadChat(chat["id"])
                st.rerun()
            if col2.button("×", key=f"del_{chat['id']}"):
                apiDeleteChat(chat["id"])
                if st.session_state.chatId == chat["id"]:
                    st.session_state.chatId = None
                    st.session_state.chatTitle = None
                    st.session_state.messages = []
                st.rerun()

        st.divider()
        st.markdown("**Settings**")
        s = st.session_state.settings

        providers = st.session_state.providers
        if providers:
            available = [p for p, info in providers.items() if info.get("available", True)]
            providerOptions = available if available else list(providers.keys())
        else:
            providerOptions = ["ollama", "groq"]

        idx = providerOptions.index(s["provider"]) if s["provider"] in providerOptions else 0
        s["provider"] = st.selectbox("Provider", providerOptions, index=idx)

        if providers and s["provider"] in providers:
            st.caption(f"model: `{providers[s['provider']].get('model', '—')}`")

        s["mode"] = st.selectbox("Mode", MODES, index=MODES.index(s["mode"]))
        s["k"] = st.slider("Top K", 1, 15, s["k"])
        if s["mode"] == "graph":
            s["hops"] = st.select_slider("Graph hops", options=[1, 2], value=s["hops"])

        st.session_state.settings = s


def renderCitations(citations, mode):
    if not citations:
        return
    st.caption(f"Citations · {len(citations)} · {mode}")
    for i, c in enumerate(citations):
        source = c.get("source", "")
        chunkId = c.get("chunkId", "")
        label = f"[{i + 1}] {chunkId}"
        with st.expander(label):
            meta_cols = st.columns(3)
            meta_cols[0].caption(f"source: {source}")
            pages = c.get("pages") or []
            meta_cols[1].caption(f"pages: {', '.join(str(p) for p in pages) or '—'}")
            score = c.get("score")
            meta_cols[2].caption(f"score: {score:.4f}" if isinstance(score, float) else "score: —")
            path = c.get("sectionPath") or []
            if path:
                st.caption(" › ".join(path))
            st.markdown(
                f'<div class="citation-text">{c.get("text", "")}</div>',
                unsafe_allow_html=True,
            )


def renderChat():
    if st.session_state.providers is None:
        st.session_state.providers = apiInfo().get("providers")

    provider = st.session_state.settings.get("provider")
    provider_info = st.session_state.providers.get(provider, {}) if st.session_state.providers else {}
    model_label = provider_info.get("model", "—")
    header_title = st.session_state.chatTitle or "New conversation"
    st.markdown(
        f"""
        <div class="chat-header">
          <div class="chat-header-title">{header_title}</div>
          <div class="chat-header-badge">
            <span class="dot"></span>
            <span>Gazelle</span>
            <span style="color: var(--cream-edge);">·</span>
            <span style="font-family: 'JetBrains Mono', monospace; text-transform: none;">{provider}</span>
            <span style="color: var(--cream-edge);">/</span>
            <span style="font-family: 'JetBrains Mono', monospace; text-transform: none;">{model_label}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Consume pending query from suggestion button (set before rerun)
    pending = st.session_state.pop("_pendingQuery") if "_pendingQuery" in st.session_state else None

    if not st.session_state.messages and not pending:
        logoUrl = logoDataUrl()
        user_name = (st.session_state.user or {}).get("name") or (st.session_state.user or {}).get("username") or ""
        st.markdown(
            f"""
            <div style="text-align:center; margin-top: 40px;">
              <div class="sidebar-logo" style="margin: 0 auto 18px;">
                <img src="{logoUrl}" alt="Gazelle" />
              </div>
              <div style="font-family: 'Fraunces', Georgia, serif; font-size: 36px; color: var(--brand);">
                Welcome back, <span style="color: var(--adib-deep); font-style: italic;">{user_name}</span>.
              </div>
              <div style="font-size: 14px; color: var(--ink-muted); margin-top: 6px;">
                Gazelle is ready. Ask about ADIB. Answers are grounded in cited regulatory documents.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
        cols = st.columns(len(SUGGESTIONS))
        for i, (text, tag) in enumerate(SUGGESTIONS):
            with cols[i]:
                st.markdown("<div class='suggestion-card'>", unsafe_allow_html=True)
                if st.button(tag, key=f"suggestion_{i}", use_container_width=True):
                    st.session_state["_pendingQuery"] = text
                    st.rerun()
                st.markdown(f"<div class='suggestion-tag'>{tag}</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div dir='auto' style='font-size: 13px; color: var(--ink); line-height: 1.5;'>{text}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["text"])
            if msg["role"] == "assistant" and msg.get("citations"):
                renderCitations(msg["citations"], msg.get("mode", "vector"))

    typed = st.chat_input("Ask Gazelle about ADIB compliance…")
    query = pending or typed

    if not query:
        return

    s = st.session_state.settings

    # Show and store user message
    st.session_state.messages.append({"role": "user", "text": query, "citations": [], "mode": s["mode"]})
    with st.chat_message("user"):
        st.write(query)

    # Determine or create chat
    chatId = st.session_state.chatId
    if not chatId:
        chat = apiCreateChat(query[:60])
        if chat:
            chatId = chat["id"]
            st.session_state.chatId = chatId
            st.session_state.chatTitle = chat.get("title")

    # Stream and display assistant response
    st.session_state["_citations"] = []
    st.session_state["_returnedChatId"] = None

    with st.chat_message("assistant"):
        text = st.write_stream(
            streamResponse(query, chatId, s["mode"], s["k"], s["hops"], s["provider"])
        )
        citations = st.session_state.get("_citations", [])
        renderCitations(citations, s["mode"])

    st.session_state.messages.append({
        "role": "assistant",
        "text": text,
        "citations": citations,
        "mode": s["mode"],
    })

    if st.session_state.get("_returnedChatId"):
        st.session_state.chatId = st.session_state["_returnedChatId"]


def main():
    st.set_page_config(page_title="Gazelle", layout="wide", initial_sidebar_state="expanded")
    st.markdown(APP_CSS, unsafe_allow_html=True)
    initState()

    if not st.session_state.token:
        renderLogin()
        return

    renderSidebar()
    renderChat()


main()
import base64
import json
import uuid
from pathlib import Path

import streamlit as st
import requests
from pyvis.network import Network
from streamlit.components.v1 import html as components_html

API_BASE = "http://localhost:8000"

MODES = ["vector", "hybrid", "graph"]
VIEWS = ["chat", "graph"]
SUGGESTIONS = [
    ("ما هي شروط إلغاء ترخيص البنك؟", "Licensing"),
    ("متى يجب إخطار البنك المركزي بتغيير ملكية البنك؟", "Ownership"),
    ("ما هي إجراءات وقف العمليات المصرفية جزئياً؟", "Operations"),
]
MOCK_USERS = [
    ("omar", "Omar · Admin · restricted", "admin123"),
    ("sara", "Sara · Senior Compliance · confidential", "compliance123"),
    ("ahmed", "Ahmed · Compliance Analyst · internal", "staff123"),
    ("guest", "Guest · External · public", "guest"),
]

ENTITY_COLORS = {
    "Person": "#7A6FB5",
    "BankingInstitution": "#062F62",
    "RegulatoryBody": "#009CDA",
    "Law": "#0078A8",
    "Article": "#5A6776",
    "License": "#C9A961",
    "Document": "#A88840",
    "FinancialInstrument": "#0E4282",
    "RegulatoryRequirement": "#A8628F",
    "MonetaryAmount": "#7D8B5C",
    "Date": "#94A2B0",
}

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --brand: #062F62;
    --brand-deep: #022048;
    --brand-tint: #1E548F;
    --adib: #009CDA;
    --adib-soft: #4DBAE7;
    --adib-deep: #0078A8;
    --adib-glow: #9DDBF0;
    --gold: #C9A961;
    --cream: #F8FBFE;
    --cream-soft: #FFFFFF;
    --cream-deeper: #E8F2FA;
    --cream-frame: #F1F6FB;
    --cream-border: #D8E5EE;
    --cream-edge: #BFD3E2;
    --ink: #0F1B2D;
    --ink-muted: #5A6776;
    --ink-faint: #94A2B0;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
    background: var(--cream);
    color: var(--ink);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

[data-testid="stSidebar"] {
    background: var(--cream-frame);
    border-right: 1px solid var(--cream-border);
}

[data-testid="stSidebar"] [data-testid="stMarkdown"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdown"] h3 {
    color: var(--brand);
}

.sidebar-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0 12px;
}
.sidebar-logo {
    width: 44px;
    height: 44px;
    border-radius: 999px;
    background: var(--cream-soft);
    box-shadow: 0 6px 16px rgba(6, 47, 98, 0.15);
    border: 1px solid rgba(0, 156, 218, 0.2);
    overflow: hidden;
}
.sidebar-logo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transform: scale(1.15);
}
.sidebar-title {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 18px;
    color: var(--brand);
    line-height: 1;
}
.sidebar-subtitle {
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--adib-deep);
    margin-top: 4px;
}

.section-label {
    font-size: 10px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--ink-faint);
    font-weight: 600;
    margin: 10px 0 6px;
}

.stButton > button {
    border-radius: 12px;
    border: 1px solid var(--cream-border);
    background: var(--cream-soft);
    color: var(--ink);
    font-weight: 500;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    border-color: var(--adib-soft);
    color: var(--brand);
    background: var(--cream-deeper);
}

.primary-button > button {
    background: linear-gradient(135deg, var(--adib), var(--adib-deep));
    color: white;
    border: none;
    box-shadow: 0 10px 18px rgba(0, 120, 168, 0.2);
}
.primary-button > button:hover {
    background: linear-gradient(135deg, var(--adib-deep), var(--brand));
}

.chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid var(--cream-border);
    background: var(--cream-frame);
    font-size: 11px;
    color: var(--ink-muted);
}

.chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    border-bottom: 1px solid var(--cream-border);
    background: rgba(248, 251, 254, 0.9);
    backdrop-filter: blur(6px);
}

.chat-header-title {
    font-size: 13px;
    color: var(--ink-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.chat-header-badge {
    font-size: 10px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--ink-faint);
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: var(--adib);
    display: inline-block;
}

.login-card {
    background: var(--cream-soft);
    border: 1px solid var(--cream-border);
    border-radius: 18px;
    padding: 24px;
    box-shadow: 0 14px 28px rgba(15, 27, 45, 0.08);
}

.mock-card {
    background: var(--cream-frame);
    border: 1px solid var(--cream-border);
    border-radius: 14px;
    padding: 16px;
}

.suggestion-card button {
    text-align: left;
    padding: 14px;
    border-radius: 16px;
    border: 1px solid var(--cream-border);
    background: var(--cream-soft);
    height: 100%;
    white-space: pre-wrap;
}

.suggestion-tag {
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--adib-deep);
    font-weight: 600;
}

[data-testid="stChatMessageContent"] p {
    direction: auto;
    text-align: start;
}

div[data-testid="stChatMessage"][data-author="user"] [data-testid="stMarkdown"] {
    background: var(--cream-deeper);
    border: 1px solid rgba(0, 156, 218, 0.25);
    border-radius: 18px;
    padding: 12px 16px;
    max-width: 78%;
    margin-left: auto;
    color: var(--brand);
}

div[data-testid="stChatMessage"][data-author="assistant"] [data-testid="stMarkdown"] {
    background: transparent;
    color: var(--ink);
}

.citation-text {
    direction: auto;
    text-align: start;
    font-size: 0.88rem;
    white-space: pre-wrap;
}

code, kbd {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
}

div[data-testid="stChatInput"] {
    border-top: 1px solid var(--cream-border);
    background: rgba(248, 251, 254, 0.9);
    backdrop-filter: blur(6px);
}

textarea[data-testid="stChatInputTextArea"] {
    border: 1px solid var(--cream-border);
    border-radius: 16px;
    padding: 12px 14px;
    background: var(--cream-soft);
    font-size: 15px;
    color: var(--ink);
    caret-color: var(--adib);
}

textarea[data-testid="stChatInputTextArea"]::placeholder {
    color: var(--ink-faint);
}

input, textarea {
    color: var(--ink);
}

input::placeholder {
    color: var(--ink-faint);
}

textarea[data-testid="stChatInputTextArea"]:focus {
    border-color: var(--adib);
    box-shadow: 0 0 0 1px var(--adib);
}

details {
    border-radius: 12px;
    border: 1px solid var(--cream-border);
    background: var(--cream-soft);
}
details[open] {
    border-color: var(--adib-soft);
}
summary {
    font-size: 12px;
    color: var(--ink);
}

.footer-hint {
    font-size: 10.5px;
    color: var(--ink-faint);
    text-align: center;
    margin-top: 8px;
    letter-spacing: 0.04em;
}

.view-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 999px;
    border: 1px solid var(--cream-border);
    background: var(--cream-soft);
    color: var(--ink-muted);
    font-size: 11px;
}

.graph-panel {
    border: 1px solid var(--cream-border);
    border-radius: 18px;
    background: var(--cream-soft);
    box-shadow: 0 10px 22px rgba(15, 27, 45, 0.06);
    overflow: hidden;
}

.graph-panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 16px;
    border-bottom: 1px solid var(--cream-border);
    background: rgba(248, 251, 254, 0.8);
}

.graph-panel-title {
    font-size: 13px;
    color: var(--brand);
    font-weight: 600;
}

.graph-panel-subtitle {
    font-size: 11px;
    color: var(--ink-faint);
}
</style>
"""


def authHeaders():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def apiLogin(username, password):
    r = requests.post(f"{API_BASE}/api/login", json={"username": username, "password": password})
    return r.json()


def apiLogout():
    requests.post(f"{API_BASE}/api/logout", headers=authHeaders())


def apiMe():
    r = requests.get(f"{API_BASE}/api/me", headers=authHeaders())
    return r.json()


def apiInfo():
    r = requests.get(f"{API_BASE}/api/info", headers=authHeaders())
    return r.json()


def apiGraph(search="", entityType="", seed="", hops=1, limit=300):
    params = {"limit": limit}
    if search:
        params["search"] = search
    if entityType:
        params["type"] = entityType
    if seed:
        params = {"seed": seed, "hops": hops, "limit": limit}
    r = requests.get(f"{API_BASE}/api/graph", headers=authHeaders(), params=params)
    r.raise_for_status()
    return r.json()


@st.cache_data
def logoDataUrl():
    data = (Path(__file__).resolve().parent / "frontend/public/logo.jpeg").read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("utf-8")


def streamResponse(query, chatId, mode, k, hops, provider):
    headers = {**authHeaders(), "Content-Type": "application/json"}
    body = {
        "query": query,
        "chatId": chatId,
        "mode": mode,
        "k": k,
        "hops": hops,
        "provider": provider,
    }
    with requests.post(f"{API_BASE}/api/chat", headers=headers, json=body, stream=True) as resp:
        resp.raise_for_status()
        buf = ""
        for raw in resp.iter_content(chunk_size=None, decode_unicode=True):
            buf += raw
            parts = buf.split("\n\n")
            buf = parts.pop()
            for part in parts:
                line = part.strip()
                if not line.startswith("data: "):
                    continue
                evt = json.loads(line[6:])
                if evt.get("type") == "citations":
                    st.session_state["_citations"] = evt["citations"]
                elif evt.get("type") == "token":
                    yield evt.get("text", "")
                elif evt.get("type") == "done" and evt.get("chatId"):
                    st.session_state["_returnedChatId"] = evt["chatId"]


def initState():
    defaults = {
        "token": None,
        "user": None,
        "providers": None,
        "view": "chat",
        "sidebarOpen": True,
        "settings": {"mode": "vector", "k": 5, "hops": 1, "provider": "ollama"},
        "chats": [],
        "currentChatId": None,
        "graphSearch": "",
        "graphSeed": "",
        "graphTypes": [],
        "graphSelectedId": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def verifyAuth():
    if not st.session_state.get("token"):
        return
    response = apiMe()
    if not response.get("user"):
        clearAuth()


def clearAuth():
    st.session_state.token = None
    st.session_state.user = None


def saveAuth(token, user):
    st.session_state.token = token
    st.session_state.user = user


def currentChat():
    currentId = st.session_state.get("currentChatId")
    return next((chat for chat in st.session_state.chats if chat["id"] == currentId), None)


def createChat(title="New conversation"):
    chat = {
        "id": str(uuid.uuid4()),
        "title": title,
        "messages": [],
        "createdAt": 0,
        "updatedAt": 0,
    }
    st.session_state.chats = [chat, *st.session_state.chats]
    st.session_state.currentChatId = chat["id"]
    return chat


def updateChat(chatId, patch):
    chats = []
    for chat in st.session_state.chats:
        if chat["id"] == chatId:
            chats.append({**chat, **patch, "updatedAt": 0})
        else:
            chats.append(chat)
    st.session_state.chats = chats


def deleteChat(chatId):
    remaining = [chat for chat in st.session_state.chats if chat["id"] != chatId]
    st.session_state.chats = remaining
    if st.session_state.currentChatId == chatId:
        st.session_state.currentChatId = remaining[0]["id"] if remaining else None


def renderLogin():
    col = st.columns([1, 2, 1])[1]
    with col:
        logoUrl = logoDataUrl()
        st.markdown(
            f"""
            <div class="text-center" style="margin-bottom: 24px;">
              <div class="sidebar-logo" style="margin: 0 auto 16px;">
                <img src="{logoUrl}" alt="Gazelle" />
              </div>
              <div class="sidebar-title">Gazelle</div>
              <div class="sidebar-subtitle">ADIB · Compliance Assistant</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username", value=st.session_state.get("_prefill_username", ""))
            password = st.text_input("Password", type="password", value=st.session_state.get("_prefill_password", ""))
            if st.form_submit_button("Sign in", use_container_width=True, type="primary"):
                result = apiLogin(username, password)
                if result.get("ok"):
                    saveAuth(result["token"], result["user"])
                    if "_prefill_username" in st.session_state:
                        del st.session_state["_prefill_username"]
                    if "_prefill_password" in st.session_state:
                        del st.session_state["_prefill_password"]
                    st.rerun()
                else:
                    st.error(result.get("error", "Login failed"))
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(
            """
            <div class="mock-card" style="margin-top: 18px;">
              <div class="section-label">Mock users</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for name, label, hint in MOCK_USERS:
            if st.button(f"{label}", key=f"mock_{name}", use_container_width=True):
                st.session_state["_prefill_username"] = name
                st.session_state["_prefill_password"] = hint
                st.rerun()


def renderSidebar():
    with st.sidebar:
        user = st.session_state.user or {}
        logoUrl = logoDataUrl()
        st.markdown(
            f"""
            <div class="sidebar-header">
              <div class="sidebar-logo">
                <img src="{logoUrl}" alt="Gazelle" />
              </div>
              <div>
                <div class="sidebar-title">Gazelle</div>
                <div class="sidebar-subtitle">ADIB · Compliance</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.session_state.sidebarOpen:
            st.markdown(f"**{user.get('username', '—')}**")
            st.caption(f"role: {user.get('role', '—')} · clearance: {user.get('clearance', '—')}")
            if st.button("Collapse sidebar", use_container_width=True):
                st.session_state.sidebarOpen = False
                st.rerun()
        else:
            if st.button("Expand sidebar", use_container_width=True):
                st.session_state.sidebarOpen = True
                st.rerun()

        st.divider()

        if st.button("＋ New chat", use_container_width=True):
            createChat()
            st.session_state.view = "chat"
            st.rerun()

        st.markdown("**Tools**")
        if st.button("Chat", use_container_width=True, type="primary" if st.session_state.view == "chat" else "secondary"):
            st.session_state.view = "chat"
            st.rerun()
        if st.button("Graph Explorer", use_container_width=True, type="primary" if st.session_state.view == "graph" else "secondary"):
            st.session_state.view = "graph"
            st.rerun()

        st.divider()
        st.markdown("**Recent**")
        chats = st.session_state.chats
        if not chats:
            st.caption("Conversations will appear here")
        for chat in chats:
            label = (chat.get("title") or "Untitled")[:42]
            active = st.session_state.currentChatId == chat["id"] and st.session_state.view == "chat"
            btn_type = "primary" if active else "secondary"
            col1, col2 = st.columns([5, 1])
            if col1.button(label, key=f"chat_{chat['id']}", use_container_width=True, type=btn_type):
                st.session_state.currentChatId = chat["id"]
                st.session_state.view = "chat"
                st.rerun()
            if col2.button("×", key=f"del_{chat['id']}"):
                deleteChat(chat["id"])
                st.rerun()

        st.divider()
        st.markdown("**Settings**")
        s = st.session_state.settings

        providers = st.session_state.providers
        if providers:
            available = [p for p, info in providers.items() if info.get("available", True)]
            providerOptions = available if available else list(providers.keys())
        else:
            providerOptions = ["ollama", "groq"]

        idx = providerOptions.index(s["provider"]) if s["provider"] in providerOptions else 0
        s["provider"] = st.selectbox("Provider", providerOptions, index=idx)

        if providers and s["provider"] in providers:
            st.caption(f"model: `{providers[s['provider']].get('model', '—')}`")

        s["mode"] = st.selectbox("Mode", MODES, index=MODES.index(s["mode"]))
        s["k"] = st.slider("Top K", 1, 15, s["k"])
        if s["mode"] == "graph":
            s["hops"] = st.select_slider("Graph hops", options=[1, 2], value=s["hops"])

        st.session_state.settings = s

        if st.button("Sign out", use_container_width=True):
            apiLogout()
            clearAuth()
            st.rerun()


def renderWelcome(user):
    logoUrl = logoDataUrl()
    userName = user.get("name") or user.get("username") or "there"
    st.markdown(
        f"""
        <div style="text-align:center; margin-top: 40px;">
          <div class="sidebar-logo" style="margin: 0 auto 18px;">
            <img src="{logoUrl}" alt="Gazelle" />
          </div>
          <div style="font-family: 'Fraunces', Georgia, serif; font-size: 36px; color: var(--brand);">
            Welcome back, <span style="color: var(--adib-deep); font-style: italic;">{userName}</span>.
          </div>
          <div style="font-size: 14px; color: var(--ink-muted); margin-top: 6px;">
            Gazelle is ready. Ask about ADIB. Answers are grounded in cited regulatory documents.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderCitations(citations, mode):
    if not citations:
        return
    st.caption(f"Citations · {len(citations)} · {mode}")
    for i, c in enumerate(citations):
        source = c.get("source", "")
        chunkId = c.get("chunkId", "")
        label = f"[{i + 1}] {chunkId}"
        with st.expander(label):
            meta_cols = st.columns(3)
            meta_cols[0].caption(f"source: {source}")
            pages = c.get("pages") or []
            meta_cols[1].caption(f"pages: {', '.join(str(p) for p in pages) or '—'}")
            score = c.get("score")
            meta_cols[2].caption(f"score: {score:.4f}" if isinstance(score, float) else "score: —")
            path = c.get("sectionPath") or []
            if path:
                st.caption(" › ".join(path))
            st.markdown(
                f'<div class="citation-text">{c.get("text", "")}</div>',
                unsafe_allow_html=True,
            )


def renderChat():
    if st.session_state.providers is None:
        st.session_state.providers = apiInfo().get("providers")

    provider = st.session_state.settings.get("provider")
    provider_info = st.session_state.providers.get(provider, {}) if st.session_state.providers else {}
    model_label = provider_info.get("model", "—")
    header_title = (currentChat() or {}).get("title") or "New conversation"
    st.markdown(
        f"""
        <div class="chat-header">
          <div class="chat-header-title">{header_title}</div>
          <div class="chat-header-badge">
            <span class="dot"></span>
            <span>Gazelle</span>
            <span style="color: var(--cream-edge);">·</span>
            <span style="font-family: 'JetBrains Mono', monospace; text-transform: none;">{provider}</span>
            <span style="color: var(--cream-edge);">/</span>
            <span style="font-family: 'JetBrains Mono', monospace; text-transform: none;">{model_label}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pending = st.session_state.pop("_pendingQuery") if "_pendingQuery" in st.session_state else None
    chat = currentChat()
    messages = chat.get("messages", []) if chat else []

    if not messages and not pending:
        renderWelcome(st.session_state.user or {})
        st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
        cols = st.columns(len(SUGGESTIONS))
        for i, (text, tag) in enumerate(SUGGESTIONS):
            with cols[i]:
                st.markdown("<div class='suggestion-card'>", unsafe_allow_html=True)
                if st.button(tag, key=f"suggestion_{i}", use_container_width=True):
                    st.session_state["_pendingQuery"] = text
                    st.rerun()
                st.markdown(f"<div class='suggestion-tag'>{tag}</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div dir='auto' style='font-size: 13px; color: var(--ink); line-height: 1.5;'>{text}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["text"])
            if msg["role"] == "assistant" and msg.get("citations"):
                renderCitations(msg["citations"], msg.get("mode", "vector"))

    typed = st.chat_input("Ask Gazelle about ADIB compliance…")
    query = pending or typed

    if not query:
        return

    s = st.session_state.settings
    if not chat:
        chat = createChat(query[:60])

    userMessage = {"role": "user", "text": query, "citations": [], "mode": s["mode"]}
    assistantMessage = {"role": "assistant", "text": "", "citations": [], "mode": s["mode"]}
    nextMessages = [*chat.get("messages", []), userMessage, assistantMessage]
    updateChat(chat["id"], {"title": query[:60], "messages": nextMessages} if not chat.get("messages") else {"messages": nextMessages})

    with st.chat_message("user"):
        st.markdown(query)

    st.session_state["_citations"] = []
    st.session_state["_returnedChatId"] = None

    with st.chat_message("assistant"):
        text = st.write_stream(streamResponse(query, chat["id"], s["mode"], s["k"], s["hops"], s["provider"]))
        citations = st.session_state.get("_citations", [])
        renderCitations(citations, s["mode"])

    updateChat(
        chat["id"],
        {
            "messages": [
                *chat.get("messages", []),
                userMessage,
                {"role": "assistant", "text": text, "citations": citations, "mode": s["mode"]},
            ]
        },
    )

    if st.session_state.get("_returnedChatId"):
        st.session_state.currentChatId = st.session_state["_returnedChatId"]


def graphNodeLabel(node):
    data = node.get("data", {})
    return data.get("name") or data.get("label") or data.get("id")


def renderGraphNetwork(graph, activeTypes):
    net = Network(height="640px", width="100%", bgcolor="#F8FBFE", font_color="#0F1B2D", directed=True)
    net.barnes_hut(gravity=-30000, central_gravity=0.2, spring_length=130, spring_strength=0.04, damping=0.09)
    net.set_options(
        """
        {
          "nodes": {
            "shape": "dot",
            "size": 18,
            "borderWidth": 2,
            "font": {"face": "Inter", "size": 13, "color": "#0F1B2D"}
          },
          "edges": {
            "arrows": {"to": {"enabled": true, "scaleFactor": 0.7}},
            "color": {"color": "#5BB8E8", "highlight": "#062F62"},
            "smooth": {"type": "dynamic"}
          },
          "physics": {"enabled": true},
          "interaction": {"hover": true, "multiselect": true}
        }
        """
    )

    visible = []
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        if activeTypes and data.get("type") not in activeTypes:
            continue
        visible.append(data.get("id"))
        net.add_node(
            data.get("id"),
            label=graphNodeLabel(node),
            title=f"{data.get('type', 'Entity')}\n{data.get('id', '')}\nchunks: {data.get('chunkCount', 0)}",
            color=ENTITY_COLORS.get(data.get("type"), "#9C968E"),
        )

    visibleSet = set(visible)
    for edge in graph.get("edges", []):
        data = edge.get("data", {})
        if data.get("source") in visibleSet and data.get("target") in visibleSet:
            net.add_edge(data.get("source"), data.get("target"), label=data.get("label", ""))

    return net.generate_html()


def renderGraphExplorer():
    if st.session_state.providers is None:
        st.session_state.providers = apiInfo().get("providers")

    st.markdown(
        """
        <div class="graph-panel">
          <div class="graph-panel-header">
            <div>
              <div class="graph-panel-title">Graph Explorer</div>
              <div class="graph-panel-subtitle">Search entities, inspect relations, and expand neighbors.</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    topCols = st.columns([3, 1, 1])
    with topCols[0]:
        st.session_state.graphSearch = st.text_input("Search entity name…", value=st.session_state.graphSearch)
    with topCols[1]:
        refresh = st.button("Refresh", use_container_width=True)
    with topCols[2]:
        clear = st.button("Clear", use_container_width=True)

    if clear:
        st.session_state.graphSearch = ""
        st.session_state.graphSeed = ""
        st.session_state.graphSelectedId = None
        st.rerun()

    graph = {"nodes": [], "edges": []}
    graphError = None
    try:
        graph = apiGraph(search=st.session_state.graphSearch, seed=st.session_state.graphSeed, hops=1, limit=300)
    except Exception as err:
        graphError = str(err)

    if graphError:
        st.error(f"Could not load graph: {graphError}")
        return

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    byType = {}
    for node in nodes:
        nodeType = node.get("data", {}).get("type")
        byType[nodeType] = byType.get(nodeType, 0) + 1

    allTypes = [nodeType for nodeType, count in byType.items() if count > 0]
    defaultTypes = st.session_state.graphTypes if st.session_state.graphTypes else allTypes
    selectedTypes = st.multiselect("Entity types", allTypes, default=[t for t in defaultTypes if t in allTypes])
    st.session_state.graphTypes = selectedTypes

    st.caption(f"{len(nodes)} nodes · {len(edges)} edges")

    if not nodes:
        st.info("No graph data. Try clearing the search or expanding a seed node.")
        return

    activeTypes = set(selectedTypes or allTypes)
    components_html(renderGraphNetwork(graph, activeTypes), height=660, scrolling=True)

    visibleNodes = [node for node in nodes if not activeTypes or node.get("data", {}).get("type") in activeTypes]
    nodeOptions = {node.get("data", {}).get("id"): graphNodeLabel(node) for node in visibleNodes}
    if not nodeOptions:
        st.info("No nodes match the selected types.")
        return

    optionIds = list(nodeOptions.keys())
    selectedDefault = st.session_state.graphSelectedId if st.session_state.graphSelectedId in nodeOptions else optionIds[0]
    selectedIndex = optionIds.index(selectedDefault)
    selectedId = st.selectbox("Inspect node", options=optionIds, format_func=lambda nodeId: nodeOptions[nodeId], index=selectedIndex)
    st.session_state.graphSelectedId = selectedId

    selectedNode = next(node for node in visibleNodes if node.get("data", {}).get("id") == selectedId)
    related = []
    for edge in edges:
        data = edge.get("data", {})
        if data.get("source") == selectedId or data.get("target") == selectedId:
            related.append(data)

    detailCols = st.columns([2, 1])
    with detailCols[0]:
        st.markdown(f"**{selectedNode.get('data', {}).get('name') or selectedId}**")
        st.caption(f"type: {selectedNode.get('data', {}).get('type', '—')} · chunks: {selectedNode.get('data', {}).get('chunkCount', 0)}")
        if st.button("Expand neighbors", use_container_width=True):
            st.session_state.graphSeed = selectedId
            st.session_state.graphSearch = ""
            st.session_state.graphSelectedId = selectedId
            st.rerun()
    with detailCols[1]:
        st.markdown("**Related edges**")
        if not related:
            st.caption("No visible connections.")
        for edge in related[:8]:
            st.caption(f"{edge.get('source')} → {edge.get('target')} · {edge.get('label', '')}")


def main():
    st.set_page_config(page_title="Gazelle", layout="wide", initial_sidebar_state="expanded")
    st.markdown(APP_CSS, unsafe_allow_html=True)
    initState()

    verifyAuth()

    if not st.session_state.token:
        renderLogin()
        return

    renderSidebar()
    if st.session_state.view == "graph":
        renderGraphExplorer()
    else:
        renderChat()


main()
