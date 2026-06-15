# Console entry point - A2 adds 'add person' to sample queries

from aiml_bot import load_aiml
from chatbot import handle_input
from prolog_engine import load_kb


BANNER = """
============================================================
 FAMILY KNOWLEDGE BASE CHATBOT  -  Assignment 2
 Powered by Pytholog + AIML
 Type 'add person' to add family members
 Type 'help' for query examples | Type 'quit' to exit
============================================================
"""

SAMPLE_QUERIES = [
    "add person",                    # A2: collect new facts via AIML
    "hi",
    "list all members",
    "who is Ali's father?",          # works after adding Ali
    "what is Ali's dob?",
    "show siblings of Zain",
    "is Shakeel an ancestor of Zain?",
    "who lives in Lahore?",
    "tell me about Ali",
]


def init_bot():
    load_kb()
    load_aiml()


def main():
    print(BANNER)
    print("Initialising...")
    init_bot()
    print("\nReady!\n")
    print("The KB starts empty. Add members with 'add person', then query them.")
    print("\nSample queries:")
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