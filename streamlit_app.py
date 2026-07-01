# streamlit_app.py — Assignment 3 Complete
# All priorities: Graph Analysis + Inference + Hybrid Reasoning

from pathlib import Path
from functools import lru_cache

import streamlit as st

from aiml_bot import load_aiml
from chatbot import handle_input
from neo4j_engine import load_graph, query
from utils import PROPERTY_RELATIONS, RELATION_NAMES


APP_TITLE    = "Family Knowledge Base Chatbot — A3"
APP_SUBTITLE = (
    "Neo4j Graph DB + AIML brain. Type 'add person' to add family members, "
    "then query relationships, run graph analysis, and perform inference."
)
WELCOME_MESSAGE = (
    "Hello! I'm your family knowledge-base chatbot.\n\n"
    "The graph starts **empty**. "
    "Type **add person** to add the first family member, "
    "then ask questions about them!\n\n"
    "**New features:**\n"
    "- `show graph statistics` — analyze the graph structure\n"
    "- `what do Ali and Asad have in common` — inference\n"
    "- `run hybrid reasoning` — Neo4j + Prolog hybrid (bonus)"
)

ASSET_DIR = Path(__file__).resolve().parent / "assets"
PROFILE_IMAGE_CANDIDATES = (
    ASSET_DIR / "profile.png",
    ASSET_DIR / "profile.jpg",
    ASSET_DIR / "profile.jpeg",
    ASSET_DIR / "profile.webp",
)


def _find_profile_image():
    for candidate in PROFILE_IMAGE_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


def _extract_values(raw, var="X"):
    values = []
    for item in raw or []:
        if isinstance(item, dict):
            value = item.get(var, "")
            if value:
                values.append(str(value))
        elif isinstance(item, str) and item.lower() not in {"yes", "no", "false"}:
            values.append(item)
    seen, unique = set(), []
    for v in values:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _family_members():
    members = (
        _extract_values(query("male",   ["X"])) +
        _extract_values(query("female", ["X"]))
    )
    return sorted(set(members))


def _family_cities():
    return sorted(set(_extract_values(query("lives_in", ["X", "Y"]), var="Y")))


def _family_occupations():
    return sorted(set(_extract_values(query("occupation", ["X", "Y"]), var="Y")))


def _family_religions():
    return sorted(set(_extract_values(query("religion", ["X", "Y"]), var="Y")))


@lru_cache(maxsize=1)
def init_bot():
    load_graph()
    load_aiml()
    return True


@lru_cache(maxsize=1)
def kb_overview():
    return {
        "people_count":     len(_family_members()),
        "city_count":       len(_family_cities()),
        "occupation_count": len(_family_occupations()),
        "religion_count":   len(_family_religions()),
        "relation_count":   len(RELATION_NAMES),
        "property_count":   len(PROPERTY_RELATIONS),
    }


def build_suggested_queries():
    if st.session_state.get("_collecting", False):
        return []
    members = _family_members()
    cities  = _family_cities()
    if not members:
        return ["add person", "list all members", "show graph statistics", "hi"]
    focus = members[0]
    city  = cities[0] if cities else "lahore"
    return [
        "add person",
        f"tell me about {focus.title()}",
        "show graph statistics",
        f"who lives in {city.title()}?",
    ]


def reset_chat():
    st.session_state.messages    = [{"role": "assistant", "content": WELCOME_MESSAGE}]
    st.session_state._collecting = False
    st.session_state._stage      = 0
    st.session_state._data       = {}


def add_message(role, content):
    st.session_state.messages.append({"role": role, "content": content})


def ask_bot(prompt: str):
    import chatbot as _chatbot

    # Restore collection state
    _chatbot._collecting = st.session_state.get("_collecting", False)
    _chatbot._stage      = st.session_state.get("_stage",      0)
    _chatbot._data       = st.session_state.get("_data",       {}).copy()

    add_message("user", prompt)
    response = handle_input(prompt)
    add_message("assistant", response)

    # Save collection state
    st.session_state["_collecting"] = _chatbot._collecting
    st.session_state["_stage"]      = _chatbot._stage
    st.session_state["_data"]       = _chatbot._data.copy()

    # Clear KB stats cache when a person is added
    if "Successfully added" in response:
        kb_overview.cache_clear()


def apply_styles():
    st.markdown("""
    <style>
    .stApp {
        background:
            radial-gradient(circle at 12% 8%,  rgba(255,155,112,0.30), transparent 22%),
            radial-gradient(circle at 88% 10%, rgba(124,139,255,0.22), transparent 24%),
            radial-gradient(circle at 18% 82%, rgba(85,212,182,0.18),  transparent 24%),
            radial-gradient(circle at 84% 78%, rgba(255,117,165,0.18), transparent 22%),
            linear-gradient(135deg, #fff7ef 0%, #f6fff8 33%, #f3f6ff 66%, #fff2fa 100%);
        background-attachment: fixed;
    }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg,
            rgba(255,250,245,0.92) 0%, rgba(242,251,255,0.90) 48%,
            rgba(251,244,255,0.90) 100%);
        border-right: 1px solid rgba(255,157,115,0.22);
        backdrop-filter: blur(18px);
    }
    section[data-testid="stSidebar"] > div { background: transparent; }
    .hero-card {
        position: relative; overflow: hidden; padding: 1.25rem 1.45rem;
        border-radius: 24px; border: 1px solid rgba(255,255,255,0.88);
        background: linear-gradient(135deg, rgba(255,255,255,0.80),
            rgba(255,246,236,0.58), rgba(243,248,255,0.78));
        box-shadow: 0 18px 45px rgba(51,65,85,0.10),
                    inset 0 1px 0 rgba(255,255,255,0.78);
        margin-bottom: 1rem;
    }
    .hero-card::before {
        content: ""; position: absolute; inset: 0 auto auto 0;
        width: 100%; height: 6px;
        background: linear-gradient(90deg,
            #ff8a5b 0%, #ffd166 28%, #59c3c3 58%, #7c8bff 80%, #ff6aa2 100%);
    }
    .hero-title { font-size:2.15rem; font-weight:800; line-height:1.1;
                  margin-bottom:.35rem; color:#1f2937; }
    .hero-subtitle { font-size:1rem; color:#52606d; margin-bottom:.85rem; }
    .pill {
        display:inline-block; padding:.38rem .78rem; margin:.15rem .28rem 0 0;
        border-radius:999px;
        background:linear-gradient(135deg,rgba(255,255,255,0.92),rgba(245,249,255,0.80));
        border:1px solid rgba(255,255,255,0.96); color:#405066;
        font-size:.82rem; font-weight:600; box-shadow:0 8px 20px rgba(15,23,42,0.06);
    }
    .section-label { font-size:.82rem; text-transform:uppercase; letter-spacing:.12em;
                     color:#64748b; margin-bottom:.5rem; font-weight:700; }
    .collecting-banner {
        background:linear-gradient(135deg,#fff3cd,#fff8e1);
        border:1px solid #ffc107; border-radius:12px;
        padding:.6rem 1rem; margin-bottom:.8rem;
        font-size:.88rem; color:#856404;
    }
    .stButton > button {
        background:linear-gradient(135deg,#ff8a5b 0%,#ff72a0 55%,#7c8bff 100%);
        color:white!important; border:none!important; border-radius:999px!important;
        padding:.7rem 1rem!important; box-shadow:0 12px 28px rgba(255,122,98,0.22);
        transition:transform .18s ease,box-shadow .18s ease,filter .18s ease;
    }
    .stButton > button:hover { transform:translateY(-1px); filter:saturate(1.05); }
    div[data-testid="stChatInput"] {
        background:linear-gradient(135deg,rgba(255,255,255,0.88),rgba(247,250,255,0.95));
        border:1px solid rgba(126,151,255,0.30); border-radius:20px;
        box-shadow:0 14px 32px rgba(15,23,42,0.08); backdrop-filter:blur(18px);
    }
    div[data-testid="stMetric"] {
        background:linear-gradient(135deg,rgba(255,255,255,0.82),rgba(245,250,255,0.72));
        border:1px solid rgba(255,255,255,0.9); border-radius:18px;
        padding:.25rem .65rem; box-shadow:0 10px 24px rgba(15,23,42,0.05);
    }
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
        background:rgba(255,255,255,0.72); border:1px solid rgba(255,255,255,0.9);
        border-radius:18px; padding:.7rem .9rem;
        box-shadow:0 12px 24px rgba(15,23,42,0.05);
    }
    </style>
    """, unsafe_allow_html=True)


def render_sidebar(assistant_avatar, overview):
    with st.sidebar:
        st.markdown("## Family Knowledge Base")

        if assistant_avatar:
            st.image(assistant_avatar, width=92)
        else:
            st.markdown("<div style='font-size:3rem;text-align:center;'>💬</div>",
                        unsafe_allow_html=True)

        st.caption("Neo4j Graph DB + AIML + Hybrid Prolog Reasoning.")

        # Live status
        st.markdown("<div class='section-label'>Live status</div>",
                    unsafe_allow_html=True)
        st.success("Neo4j graph connected")
        st.success("AIML loaded (family + collect + analysis)")

        is_collecting = st.session_state.get("_collecting", False)
        stage         = st.session_state.get("_stage", 0)

        if is_collecting and stage > 0:
            st.warning(f"⏳ Collecting — Step {stage}/9 in progress")

        # Stats
        r1 = st.columns(2)
        r1[0].metric("People",     overview["people_count"])
        r1[1].metric("Cities",     overview["city_count"])
        r2 = st.columns(2)
        r2[0].metric("Relations",  overview["relation_count"])
        r2[1].metric("Properties", overview["property_count"])

        st.markdown("---")

        # Add member
        st.markdown("<div class='section-label'>Add to Graph</div>",
                    unsafe_allow_html=True)
        if not is_collecting:
            if st.button("➕ Add family member", use_container_width=True):
                ask_bot("add person")
                st.rerun()
        else:
            st.info("✍️ Complete the form in the chat to finish adding.")

        if is_collecting:
            if st.button("❌ Cancel collection", use_container_width=True):
                ask_bot("cancel")
                st.rerun()

        st.markdown("---")

        # Graph analysis quick buttons
        st.markdown("<div class='section-label'>Graph Analysis</div>",
                    unsafe_allow_html=True)
        if st.button("📊 Graph statistics", use_container_width=True):
            ask_bot("show graph statistics")
            st.rerun()
        if st.button("🔗 Relationship breakdown", use_container_width=True):
            ask_bot("what relationship types exist")
            st.rerun()
        if st.button("⭐ Most connected person", use_container_width=True):
            ask_bot("who has the most connections")
            st.rerun()
        if st.button("✅ Data completeness", use_container_width=True):
            ask_bot("show data completeness")
            st.rerun()

        st.markdown("---")

        # Hybrid reasoning bonus button
        st.markdown("<div class='section-label'>Hybrid Reasoning (Bonus)</div>",
                    unsafe_allow_html=True)
        if st.button("🧠 Run Prolog inference on graph", use_container_width=True):
            ask_bot("run hybrid reasoning")
            st.rerun()

        st.markdown("---")

        # Manage chat
        st.markdown("<div class='section-label'>Manage chat</div>",
                    unsafe_allow_html=True)
        if st.button("Clear chat", use_container_width=True):
            reset_chat()
            st.rerun()

        with st.expander("What this bot can do"):
            st.markdown(
                "**Add data:**\n"
                "- `add person` → guided 9-step data entry\n"
                "- Data stored as Person nodes + edges in Neo4j\n\n"
                "**Query family:**\n"
                "- Relationships: father, mother, sibling, uncle, cousin\n"
                "- Urdu: chacha, phoophi, maamu, khala, dada, nani\n"
                "- Recursive: ancestor, descendant, blood_relative\n"
                "- Properties: dob, occupation, city, religion\n\n"
                "**Graph analysis:**\n"
                "- `show graph statistics`\n"
                "- `what relationship types exist`\n"
                "- `who has the most connections`\n"
                "- `show data completeness`\n\n"
                "**Inference & discovery:**\n"
                "- `what do Ali and Asad have in common`\n"
                "- `discover hidden relationships of Ali`\n"
                "- `recommend connections for Ali`\n"
                "- `how are Ali and Asad connected`\n\n"
                "**Hybrid reasoning (bonus):**\n"
                "- `run hybrid reasoning`\n"
                "  Exports Neo4j → Prolog facts → runs inference → "
                "writes INFERRED_* relationships back to Neo4j"
            )
        st.caption("Add your photo as assets/profile.png and push to GitHub.")


def render_header(assistant_avatar, suggested_queries):
    left_col, right_col = st.columns([0.84, 0.16])
    with left_col:
        st.markdown(f"""
        <div class="hero-card">
            <div class="hero-title">Hi, I'm Family Chatbot 👋</div>
            <div class="hero-subtitle">{APP_SUBTITLE}</div>
            <div>
                <span class="pill">add person</span>
                <span class="pill">father</span>
                <span class="pill">ancestor</span>
                <span class="pill">graph stats</span>
                <span class="pill">inference</span>
                <span class="pill">hybrid</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with right_col:
        if assistant_avatar:
            st.image(assistant_avatar, width=96)
        else:
            st.markdown(
                "<div class='hero-card' style='text-align:center;font-size:3rem;'>💬</div>",
                unsafe_allow_html=True)

    if st.session_state.get("_collecting", False):
        stage = st.session_state.get("_stage", 0)
        data  = st.session_state.get("_data",  {})
        name  = data.get("name", "").title() or "new person"
        st.markdown(
            f"<div class='collecting-banner'>"
            f"⏳ <strong>Adding {name}</strong> — Step {stage} of 9. "
            f"Type your answer below and press Enter, or type <code>cancel</code> to stop."
            f"</div>",
            unsafe_allow_html=True)
        return

    if suggested_queries:
        st.markdown("<div class='section-label'>Suggested questions</div>",
                    unsafe_allow_html=True)
        cols = st.columns(2)
        for i, sample in enumerate(suggested_queries):
            with cols[i % 2]:
                if st.button(sample, key=f"sample_{i}", use_container_width=True):
                    ask_bot(sample)
                    st.rerun()


def render_conversation(assistant_avatar):
    st.markdown("<div class='section-label'>Conversation</div>",
                unsafe_allow_html=True)
    for msg in st.session_state.messages:
        avatar = (assistant_avatar if assistant_avatar else "💬") \
                 if msg["role"] == "assistant" else "🧑‍💻"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])


def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=_find_profile_image() or "💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_bot()

    if "messages" not in st.session_state:
        reset_chat()

    assistant_avatar  = _find_profile_image()
    overview          = kb_overview()
    suggested_queries = build_suggested_queries()

    apply_styles()
    render_sidebar(assistant_avatar, overview)

    if st.session_state.get("_collecting", False):
        placeholder = "Type your answer and press Enter ↵"
    else:
        placeholder = "Ask a question or type 'add person' to start adding..."

    prompt = st.chat_input(placeholder)
    if prompt:
        ask_bot(prompt)
        st.rerun()

    render_header(assistant_avatar, suggested_queries)
    render_conversation(assistant_avatar)


if __name__ == "__main__":
    main()