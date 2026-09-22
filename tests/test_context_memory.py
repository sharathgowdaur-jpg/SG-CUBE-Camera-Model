import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistive.memory_manager import (
    MemoryManager,
    MemoryCategory,
    classify_memory_category
)
from assistive.command_router import CommandRouter
from assistive.security_manager import SecurityManager, SecurityLevel, SecurityState
from assistive.memory_store import MemoryStore
from assistive.vision_engine import VisionEngine

class TestContextMemory(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sgcube_ctx_mem_test_")
        self.mem_dir = os.path.join(self.test_dir, "memory")
        self.pref_dir = os.path.join(self.test_dir, "user_preferences")
        os.makedirs(self.mem_dir, exist_ok=True)
        os.makedirs(self.pref_dir, exist_ok=True)

        self.memory = MemoryManager(db_dir=self.mem_dir)
        self.router = CommandRouter()
        self.store = MemoryStore(base_dir=self.test_dir)
        self.security = SecurityManager(pref_dir=self.pref_dir, store=self.store)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    # 1. Category Taxonomy & Auto-Classification Tests
    # ----------------------------------------------------------------------
    def test_01_category_taxonomy_completeness(self):
        """ Verify all 10 structured categories exist in MemoryCategory enum """
        expected = {
            "personal", "preference", "location", "object", "task",
            "routine", "contact", "project", "device", "other"
        }
        actual = {c.value for c in MemoryCategory}
        self.assertEqual(expected, actual)

    def test_02_auto_classification_location(self):
        """ Location classification based on prepositions and places """
        cat1 = classify_memory_category("laptop location", "My laptop is on the study table")
        self.assertEqual(cat1, MemoryCategory.LOCATION)

        cat2 = classify_memory_category("keys", "Keys are kept inside the kitchen drawer")
        self.assertEqual(cat2, MemoryCategory.LOCATION)

        cat3 = classify_memory_category("wallet location", "Wallet is placed on my bedroom desk")
        self.assertEqual(cat3, MemoryCategory.LOCATION)

    def test_03_auto_classification_preference(self):
        """ Preference classification based on favorites, likes, tastes """
        cat1 = classify_memory_category("favorite color", "My favorite color is navy blue")
        self.assertEqual(cat1, MemoryCategory.PREFERENCE)

        cat2 = classify_memory_category("coffee preference", "I prefer hot black coffee with no sugar")
        self.assertEqual(cat2, MemoryCategory.PREFERENCE)

    def test_04_auto_classification_project(self):
        """ Project classification based on app, codebase, repository, system name """
        cat1 = classify_memory_category("project name", "My current project is named SG CUBE")
        self.assertEqual(cat1, MemoryCategory.PROJECT)

        cat2 = classify_memory_category("codebase", "The repository is called VisionClaw")
        self.assertEqual(cat2, MemoryCategory.PROJECT)

    def test_05_auto_classification_contact(self):
        """ Contact classification for phone numbers and email addresses """
        cat1 = classify_memory_category("doctor phone", "Doctor's phone number is 987-654-3210")
        self.assertEqual(cat1, MemoryCategory.CONTACT)

        cat2 = classify_memory_category("alex email", "Alex email is alex@example.com")
        self.assertEqual(cat2, MemoryCategory.CONTACT)

    def test_06_auto_classification_task(self):
        """ Task classification for reminders, appointments, todos """
        cat1 = classify_memory_category("reminder", "Remind me to buy groceries tomorrow at 5pm")
        self.assertEqual(cat1, MemoryCategory.TASK)

        cat2 = classify_memory_category("appointment", "Doctor appointment on Friday morning")
        self.assertEqual(cat2, MemoryCategory.TASK)

    def test_07_auto_classification_routine(self):
        """ Routine classification for habits and daily schedules """
        cat = classify_memory_category("daily routine", "I go for a walk every morning at 7am")
        self.assertEqual(cat, MemoryCategory.ROUTINE)

    def test_08_auto_classification_device_and_object(self):
        """ Device and object classification when not purely a location fact """
        cat_dev = classify_memory_category("headphone model", "Headphones are Sony WH1000XM4")
        self.assertEqual(cat_dev, MemoryCategory.DEVICE)

        cat_obj = classify_memory_category("car details", "My car is a blue Honda Civic")
        self.assertEqual(cat_obj, MemoryCategory.OBJECT)

    # ----------------------------------------------------------------------
    # 2. Explicit Save & Retrieval
    # ----------------------------------------------------------------------
    def test_09_explicit_save_and_exact_recall(self):
        """ Test direct save and exact recall across categories """
        saved = self.memory.save_memory("preference", "favorite color", "My favorite color is dark green.")
        self.assertTrue(saved)

        recalled = self.memory.recall_memory("favorite color")
        self.assertIsNotNone(recalled)
        self.assertIn("dark green", recalled)

        rec = self.memory.get_memory_record("favorite color")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["category"], "preference")
        self.assertEqual(rec["key_phrase"], "favorite color")
        self.assertIn("dark green", rec["fact_value"])

    # ----------------------------------------------------------------------
    # 3. Duplicate Prevention & Conflict Resolution
    # ----------------------------------------------------------------------
    def test_10_duplicate_prevention_same_fact(self):
        """ Saving identical key and fact should refresh timestamp without creating duplicate rows """
        ok1 = self.memory.save_memory("location", "laptop location", "My laptop is on the study table.")
        self.assertTrue(ok1)
        self.assertEqual(len(self.memory.list_all_memories()), 1)

        # Save exact same fact again
        ok2 = self.memory.save_memory("location", "laptop location", "My laptop is on the study table.")
        self.assertTrue(ok2)
        mems = self.memory.list_all_memories()
        self.assertEqual(len(mems), 1)

    def test_11_conflict_resolution_updates_in_place(self):
        """ Saving a new fact for an existing key updates the fact in place (study table -> bedroom) """
        self.memory.save_memory("location", "laptop location", "My laptop is on the study table.")
        self.assertIn("study table", self.memory.recall_memory("where is my laptop"))

        # User updates location to bedroom
        self.memory.save_memory("location", "laptop location", "My laptop is in the bedroom.")
        mems = self.memory.list_all_memories()
        self.assertEqual(len(mems), 1)

        updated_recall = self.memory.recall_memory("where is my laptop")
        self.assertIsNotNone(updated_recall)
        self.assertIn("bedroom", updated_recall)
        self.assertNotIn("study table", updated_recall)

    # ----------------------------------------------------------------------
    # 4. Contextual Natural Language Recall Queries
    # ----------------------------------------------------------------------
    def test_12_contextual_location_queries(self):
        """ Test location questions: 'Where is my X?' and 'Where did I say my X is?' """
        self.memory.save_memory("location", "laptop location", "My laptop is on the study table.")
        self.memory.save_memory("location", "keys location", "My keys are in the wooden drawer.")

        # Where is my laptop?
        res1 = self.memory.recall_memory("where is my laptop")
        self.assertIsNotNone(res1)
        self.assertIn("study table", res1)

        # Where did I say my laptop is?
        res2 = self.memory.recall_memory("where did I say my laptop is")
        self.assertIsNotNone(res2)
        self.assertIn("study table", res2)

        # Where are my keys?
        res3 = self.memory.recall_memory("where are my keys")
        self.assertIsNotNone(res3)
        self.assertIn("wooden drawer", res3)

    def test_13_contextual_project_and_preference_queries(self):
        """ Test project and preference natural queries """
        self.memory.save_memory("project", "project name", "My project is named SG CUBE.")
        self.memory.save_memory("preference", "favorite beverage", "My favorite drink is iced matcha latte.")

        res_proj = self.memory.recall_memory("what is my project called")
        self.assertIsNotNone(res_proj)
        self.assertIn("SG CUBE", res_proj)

        res_fav = self.memory.recall_memory("what is my favorite drink")
        self.assertIsNotNone(res_fav)
        self.assertIn("iced matcha latte", res_fav)

    # ----------------------------------------------------------------------
    # 5. Missing Memory Handling (Zero Hallucination)
    # ----------------------------------------------------------------------
    def test_14_missing_memory_returns_none(self):
        """ Recall for unsaved item returns None without inventing facts """
        self.memory.save_memory("personal", "favorite color", "My favorite color is blue.")
        res = self.memory.recall_memory("what is my favorite food")
        self.assertIsNone(res)

    # ----------------------------------------------------------------------
    # 6. Forget, Category Delete, and Clear All
    # ----------------------------------------------------------------------
    def test_15_forget_single_memory(self):
        """ forget_memory removes the target key cleanly """
        self.memory.save_memory("location", "laptop location", "Laptop is on table.")
        self.memory.save_memory("preference", "favorite color", "Color is purple.")
        self.assertEqual(len(self.memory.list_all_memories()), 2)

        ok = self.memory.forget_memory("laptop location")
        self.assertTrue(ok)
        self.assertEqual(len(self.memory.list_all_memories()), 1)
        self.assertIsNone(self.memory.recall_memory("laptop location"))
        self.assertIsNotNone(self.memory.recall_memory("favorite color"))

    def test_16_delete_category(self):
        """ delete_category clears only the specified category """
        self.memory.save_memory("location", "laptop location", "Laptop on table.")
        self.memory.save_memory("location", "keys location", "Keys in drawer.")
        self.memory.save_memory("preference", "favorite fruit", "Apples.")
        self.assertEqual(len(self.memory.list_all_memories()), 3)

        del_cnt = self.memory.delete_category("location")
        self.assertEqual(del_cnt, 2)
        mems = self.memory.list_all_memories()
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0]["category"], "preference")

    def test_17_clear_all_memories(self):
        """ clear_all_memories purges entire database and cache """
        self.memory.save_memory("location", "loc1", "Val 1")
        self.memory.save_memory("preference", "pref1", "Val 2")
        self.memory.save_memory("project", "proj1", "Val 3")
        self.assertEqual(len(self.memory.list_all_memories()), 3)

        cleared = self.memory.clear_all_memories()
        self.assertEqual(cleared, 3)
        self.assertEqual(len(self.memory.list_all_memories()), 0)
        self.assertEqual(len(self.memory._ram_cache), 0)

    # ----------------------------------------------------------------------
    # 7. Persistence & Cold Restart
    # ----------------------------------------------------------------------
    def test_18_persistence_across_cold_restart(self):
        """ Verify database and FTS index persist across fresh MemoryManager instances """
        self.memory.save_memory("location", "laptop location", "My laptop is on the study desk.", source="voice_explicit")
        self.memory.save_memory("preference", "favorite movie", "Interstellar.", source="voice_explicit")

        # Instantiate fresh instance simulating app restart
        fresh_mem = MemoryManager(db_dir=self.mem_dir)
        mems = fresh_mem.list_all_memories()
        self.assertEqual(len(mems), 2)

        res = fresh_mem.recall_memory("where is my laptop")
        self.assertIsNotNone(res)
        self.assertIn("study desk", res)

        search_res = fresh_mem.search_memories("Interstellar")
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0]["key_phrase"], "favorite movie")

    # ----------------------------------------------------------------------
    # 8. Privacy & Sensitive Credential Filtering
    # ----------------------------------------------------------------------
    def test_19_sensitive_credential_blocking(self):
        """ Ensure passwords, recovery codes, and API keys are strictly rejected """
        self.assertFalse(self.memory.save_memory("personal", "password", "my password is secret123"))
        self.assertFalse(self.memory.save_memory("personal", "api key", "AIzaSyD-1234567890"))
        self.assertFalse(self.memory.save_memory("personal", "recovery code", "RC-A7F2-9K4B"))
        self.assertFalse(self.memory.save_memory("personal", "credit card", "4111 2222 3333 4444"))
        self.assertFalse(self.memory.save_memory("personal", "pin number", "PIN is 1234"))

        # Database must remain empty
        self.assertEqual(len(self.memory.list_all_memories()), 0)

    # ----------------------------------------------------------------------
    # 9. Command Router Extraction & Intent Mapping
    # ----------------------------------------------------------------------
    def test_20_router_intent_routing(self):
        """ Verify CommandRouter maps memory phrases to correct intents """
        # Save intent
        r_save = self.router.route_command("remember that my laptop is on the study table")
        self.assertEqual(r_save["intent"], "MEMORY_SAVE")

        # Location recall intent
        r_rec1 = self.router.route_command("where did I say my laptop is")
        self.assertEqual(r_rec1["intent"], "MEMORY_RECALL")

        r_rec2 = self.router.route_command("where did I put my keys")
        self.assertEqual(r_rec2["intent"], "MEMORY_RECALL")

        # Preference recall intent
        r_rec3 = self.router.route_command("what is my favorite color")
        self.assertEqual(r_rec3["intent"], "MEMORY_RECALL")

        # Project recall intent
        r_rec4 = self.router.route_command("what is my project called")
        self.assertEqual(r_rec4["intent"], "MEMORY_RECALL")

        # List memories intent
        r_list = self.router.route_command("what do you remember about me")
        self.assertEqual(r_list["intent"], "MEMORY_LIST")

        # Forget intent
        r_fgt = self.router.route_command("forget where my laptop is")
        self.assertEqual(r_fgt["intent"], "MEMORY_FORGET")

        # Delete category intent
        r_del_cat = self.router.route_command("delete all location memories")
        self.assertEqual(r_del_cat["intent"], "MEMORY_DELETE_CATEGORY")

        # Clear intent
        r_clr = self.router.route_command("clear all my memories")
        self.assertEqual(r_clr["intent"], "MEMORY_CLEAR")

    def test_21_router_key_and_fact_extraction(self):
        """ Test linguistic key/fact extraction from diverse spoken sentences """
        k1, f1 = self.router.extract_memory_key_and_fact("remember that my laptop is on the study table")
        self.assertEqual(k1, "laptop location")
        self.assertIn("laptop is on the study table", f1.lower())

        k2, f2 = self.router.extract_memory_key_and_fact("remember that my favorite color is navy blue")
        self.assertEqual(k2, "favorite color")
        self.assertIn("navy blue", f2.lower())

        k3, f3 = self.router.extract_memory_key_and_fact("remember that my project name is SG CUBE")
        self.assertEqual(k3, "project name")
        self.assertIn("sg cube", f3.lower())

    # ----------------------------------------------------------------------
    # 10. SecurityManager Integration & Policy Evaluation
    # ----------------------------------------------------------------------
    def test_22_security_level_policy_mapping(self):
        """ Verify memory operations have appropriate SecurityLevels """
        self.assertEqual(self.security.get_security_level("MEMORY_SAVE"), SecurityLevel.SAFE)
        self.assertEqual(self.security.get_security_level("MEMORY_RECALL"), SecurityLevel.PROTECTED)
        self.assertEqual(self.security.get_security_level("MEMORY_LIST"), SecurityLevel.PROTECTED)
        self.assertEqual(self.security.get_security_level("MEMORY_FORGET"), SecurityLevel.PROTECTED)
        self.assertEqual(self.security.get_security_level("MEMORY_DELETE_CATEGORY"), SecurityLevel.PROTECTED)
        self.assertEqual(self.security.get_security_level("MEMORY_CLEAR"), SecurityLevel.HIGH_RISK)

    def test_23_security_authorization_gates(self):
        """ Test authorization check and access granting on valid passphrase """
        self.security.set_password("solar river mountain")

        # Lock session
        self.security.lock_session()
        self.assertFalse(self.security.is_session_authorized())

        # Authorize session with password
        ok, msg = self.security.verify_password("solar river mountain")
        self.assertTrue(ok)
        self.assertTrue(self.security.is_session_authorized())

    def test_24_high_risk_2fa_live_face_gate_for_memory_clear(self):
        """ Test HIGH_RISK 2FA Live Face evaluation """
        # When no faces detected
        ok_no_face, msg_no, _ = self.security.evaluate_live_face_2fa([])
        self.assertFalse(ok_no_face)

        # When known face is confirmed with liveness and quality
        face_known = [{
            "name": "Sharath",
            "match_state": "KNOWN",
            "is_confirmed": True,
            "liveness_ok": True,
            "quality_ok": True
        }]
        ok_face, msg_f, name_f = self.security.evaluate_live_face_2fa(face_known)
        self.assertTrue(ok_face)
        self.assertEqual(name_f, "Sharath")

    # ----------------------------------------------------------------------
    # 11. Transaction Safety & VisionEngine Execution
    # ----------------------------------------------------------------------
    def test_25_engine_memory_save_and_recall_flow(self):
        """ Test full VisionEngine flow with commit check and response generation """
        engine = VisionEngine()
        engine.memory = self.memory
        engine.security = self.security

        # 1. Save memory via engine intent
        t_save = "remember that my laptop is on the study table"
        r_save = engine.router.route_intent(t_save)
        res_save = engine._execute_intent(r_save["intent"], r_save, t_save)
        self.assertIn("Got it. I will remember that", res_save)
        self.assertIn("study table", res_save)

        # 2. Recall memory via engine intent
        t_rec = "where is my laptop"
        r_rec = engine.router.route_intent(t_rec)
        res_recall = engine._execute_intent(r_rec["intent"], r_rec, t_rec)
        self.assertIn("laptop is on the study table", res_recall)

        # 3. Unsaved memory recall returns "I don't have a specific memory saved for that."
        t_miss = "what is my favorite food"
        r_miss = engine.router.route_intent(t_miss)
        res_missing = engine._execute_intent(r_miss["intent"], r_miss, t_miss)
        self.assertEqual(res_missing, "I don't have a specific memory saved for that.")

    def test_26_engine_transaction_failure_safety(self):
        """ Critical Rule: Engine must NOT say 'I'll remember that' if DB save fails """
        engine = VisionEngine()
        mock_mem = MagicMock()
        mock_mem.save_memory.return_value = False
        mock_mem.is_sensitive_info.return_value = False
        engine.memory = mock_mem
        engine.security = self.security

        t_fail = "remember that my laptop is on the table"
        r_fail = engine.router.route_intent(t_fail)
        res = engine._execute_intent(r_fail["intent"], r_fail, t_fail)
        self.assertIn("I couldn't save that", res)
        self.assertNotIn("I'll remember that", res)

    # ----------------------------------------------------------------------
    # 12. Memory Statistics Aggregation
    # ----------------------------------------------------------------------
    def test_27_memory_stats_aggregation(self):
        """ Verify get_memory_stats returns accurate category counts """
        self.memory.save_memory("location", "laptop location", "Table.")
        self.memory.save_memory("location", "keys location", "Drawer.")
        self.memory.save_memory("preference", "favorite color", "Blue.")
        self.memory.save_memory("project", "project name", "SG CUBE.")

        stats = self.memory.get_memory_stats()
        self.assertEqual(stats["total_count"], 4)
        self.assertEqual(stats["categories"]["location"], 2)
        self.assertEqual(stats["categories"]["preference"], 1)
        self.assertEqual(stats["categories"]["project"], 1)

if __name__ == "__main__":
    unittest.main()
