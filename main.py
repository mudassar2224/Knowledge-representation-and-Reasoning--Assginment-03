# main.py — Assignment 3
# Only change: load_graph() instead of load_kb()

from aiml_bot import load_aiml
from chatbot import handle_input
from neo4j_engine import load_graph          # ← CHANGED (was prolog_engine)


BANNER = """
============================================================
 FAMILY KNOWLEDGE BASE CHATBOT  —  Assignment 3
 Powered by Neo4j Graph DB + AIML
 Type 'add person' to add family members
 Type 'help' for query examples | Type 'quit' to exit
============================================================
"""

SAMPLE_QUERIES = [
    "add person",
    "hi",
    "list all members",
    "who is Ali's father?",
    "what is Ali's dob?",
    "show siblings of Zain",
    "is Shakeel an ancestor of Zain?",
    "who lives in Lahore?",
    "tell me about Ali",
]


def init_bot():
    load_graph()                              # ← CHANGED (was load_kb())
    load_aiml()


def main():
    print(BANNER)
    print("Initialising...")
    init_bot()
    print("\nReady! Graph starts empty — add members with 'add person'.\n")
    print("Sample queries:")
    for q in SAMPLE_QUERIES:
        print(f"  > {q}")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBot: Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit"}:
            print("Bot: Goodbye! Have a nice day.")
            break

        response = handle_input(user_input)
        print(f"\nBot: {response}\n")
        print("-" * 60)


if __name__ == "__main__":
    main()