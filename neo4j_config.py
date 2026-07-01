# neo4j_config.py

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
            "neo4j+s://4795b127.databases.neo4j.io",
            "4795b127",
            "ZyqVhHGNyhr9_m8zrrfcM9nEdm-YQsIIMtF-PTpvLks",
            "4795b127",
        )


NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE = get_neo4j_config()