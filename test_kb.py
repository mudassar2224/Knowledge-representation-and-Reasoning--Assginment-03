import importlib.util
import unittest

from aiml_bot import load_aiml
from chatbot import handle_input
from prolog_engine import load_kb, query, query_yes_no


class FamilyChatbotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_kb()
        load_aiml()

    def assertAnswerContains(self, prompt, *parts):
        answer = handle_input(prompt)
        for part in parts:
            self.assertIn(part, answer, msg=f"Prompt: {prompt}\nAnswer: {answer}")
        return answer

    def test_raw_kb_queries(self):
        self.assertEqual(query("father", ["X", "ali"]), [{"X": "shakeel"}])
        self.assertTrue(query_yes_no("ancestor", ["shakeel", "zain"]))
        self.assertFalse(query_yes_no("father", ["zain", "ali"]))

    def test_properties(self):
        self.assertAnswerContains("what is Ali dob", "Ali's date of birth is 2000-05-12")
        self.assertAnswerContains("where does Ali live?", "Ali's city is Lahore")
        self.assertAnswerContains("what is Ali occupation?", "Ali's occupation is Engineer")
        self.assertAnswerContains("what is Ali religion?", "Ali's religion is Islam")

    def test_relationship_variants(self):
        self.assertAnswerContains("who is Ali's father?", "Ali's father is Shakeel")
        self.assertAnswerContains("father of Ali", "Ali's father is Shakeel")
        self.assertAnswerContains("list children of Ali", "Zain", "Zaini")
        self.assertAnswerContains("who are Ali's children?", "Ali's children are", "Zain", "Zaini")
        self.assertAnswerContains("show siblings of Zain", "Zaini")
        self.assertAnswerContains("who is Zain dada", "Zain's dada is Shakeel")
        self.assertAnswerContains("who is Laiba maamu", "Laiba's maamu is Usman")
        self.assertAnswerContains("who is Ali father in law", "Ali's father-in-law is Tariq")
        self.assertAnswerContains("who is Ali married to?", "Ali's spouse is Alia")
        self.assertAnswerContains("who is Ali's chacha?", "could not find any chacha for Ali")
        self.assertAnswerContains("re Ali and Asad related?", "Yes, Ali and Asad are blood relatives")
        self.assertAnswerContains("Who is Ali related to?", "Ali's blood relatives are", "Asad", "Nadia")

    def test_unary_and_member_lists(self):
        self.assertAnswerContains("who are the female members?", "Female family members", "Hina", "Shakeela")
        self.assertAnswerContains("who are the male members?", "Male family members", "Ali", "Shakeel")
        self.assertAnswerContains("which members are in the family KB?", "All family members", "Ali", "Hina")
        self.assertAnswerContains("is Ali male?", "Yes, Ali is male")

    def test_group_and_list_queries(self):
        self.assertAnswerContains("who lives in Lahore?", "Family members in Lahore", "Ali", "Nadia")
        self.assertAnswerContains("who is a doctor?", "Shakeel")
        self.assertAnswerContains("which family members are doctors?", "Family members who are doctors", "Shakeel")
        self.assertAnswerContains("same city as Ali", "Alia", "Zain")
        self.assertAnswerContains("list all members", "All family members", "Ali", "Hina")

    def test_yes_no_queries(self):
        self.assertAnswerContains("is Shakeel an ancestor of Zain?", "Yes")
        self.assertAnswerContains("are Ali and Asad related?", "Yes")
        self.assertAnswerContains("does Ali live in Lahore?", "Yes, Ali lives in Lahore")
        self.assertAnswerContains("is Ali a doctor?", "No, Ali is not a doctor")
        self.assertAnswerContains("is Ali married?", "Yes, Ali is married")

    def test_profile_greeting_and_fallback(self):
        self.assertAnswerContains("tell me about Ali", "Here is what I know about Ali", "Date of birth")
        self.assertTrue(handle_input("hi").strip())
        self.assertAnswerContains("what is quantum physics?", "family knowledge-base questions")
        self.assertAnswerContains(
            "Tell me about someone who is not in the family",
            "only describe family members that exist in the knowledge base",
        )
        self.assertAnswerContains("Who is John's father?", "Sorry, I do not have John in this family KB")

    @unittest.skipIf(importlib.util.find_spec("streamlit") is None, "streamlit is not installed")
    def test_streamlit_module_imports(self):
        __import__("streamlit_app")


if __name__ == "__main__":
    unittest.main()
