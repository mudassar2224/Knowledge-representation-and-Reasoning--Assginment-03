# neo4j_config.py
# Automatically uses Streamlit secrets on cloud, file values locally.

try:
    import streamlit as st
    NEO4J_URI      = st.secrets["neo4j"]["uri"]
    NEO4J_USERNAME = st.secrets["neo4j"]["username"]
    NEO4J_PASSWORD = st.secrets["neo4j"]["password"]
    NEO4J_DATABASE = st.secrets["neo4j"]["database"]
except Exception:
    # Local fallback — used when running main.py from console
    NEO4J_URI      = "neo4j+s://d23b33f1.databases.neo4j.io"
    NEO4J_USERNAME = "d23b33f1"
    NEO4J_PASSWORD = "3_k7cisfzjZ--Pw6qd5cBGyCpRSUZWWYUQPag51419o"
    NEO4J_DATABASE = "d23b33f1"