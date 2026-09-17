import unittest

from app import Conversation, KnowledgeStore


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.conversation = Conversation(KnowledgeStore(":memory:"))

    def test_incomplete_request_asks_for_clarification(self):
        response = self.conversation.respond("Biodiversity is declining on my land")
        self.assertEqual(response["status"], "needs_clarification")
        self.assertIn("rainfall", response["question"])

    def test_structured_request_retrieves_evidence_and_multimetric_actions(self):
        response = self.conversation.respond("Please assess my farm", {"soil_organic_carbon": 0.3, "rainfall": "low", "land_use": "monoculture wheat", "region": "semi-arid"})
        self.assertEqual(response["status"], "complete")
        self.assertGreaterEqual(len(response["retrieved_evidence"]), 2)
        self.assertTrue({"soil organic carbon", "soil moisture"}.issubset(set(response["recommendations"][0]["impacted_metrics"])))
        self.assertTrue(response["recommendations"][0]["evidence_ids"])

    def test_context_persists_across_turns(self):
        self.conversation.respond("My soil organic carbon is 0.3% and rainfall is low")
        response = self.conversation.respond("The land use is monoculture wheat")
        self.assertEqual(response["status"], "complete")
        self.assertEqual(response["context"]["soil_organic_carbon"], "0.3")


if __name__ == "__main__":
    unittest.main()