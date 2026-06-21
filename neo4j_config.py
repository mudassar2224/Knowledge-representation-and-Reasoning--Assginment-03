# neo4j_config.py
# Reads from Streamlit secrets on cloud.
# Falls back to Aura credentials locally.

def get_neo4j_config():
    """Return (uri, username, password, database) from the right source."""
    try:
        import streamlit as st
        cfg = st.secrets["neo4j"]
        return (
            cfg["uri"],
            cfg["username"],
            cfg["password"],
            cfg.get("database", "neo4j"),
        )
    except Exception:
        # Local fallback
        return (
            "neo4j+s://d23b33f1.databases.neo4j.io",
            "d23b33f1",
            "3_k7cisfzjZ--Pw6qd5cBGyCpRSUZWWYUQPag51419o",
            "d23b33f1",
        )


NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE = get_neo4j_config()