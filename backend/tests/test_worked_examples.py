import unittest
import pandas as pd
from backend.app.decision_engine import DecisionEngine
from backend.app.schemas import PRLineInput
from backend.app.config import SAMPLE_PR_BATCH_CSV

class TestWorkedExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = DecisionEngine()
        batch_df = pd.read_csv(SAMPLE_PR_BATCH_CSV)
        inputs = [PRLineInput(**row) for row in batch_df.to_dict(orient="records")]
        outputs = cls.engine.process_batch(inputs)
        cls.batch_results = { (o.pr_no, o.pr_line): o for o in outputs }

    def test_preferred_suppliers_ranking_itm_1048(self):
        # ITM-1048 Nitrile coated gloves as of 1 Nov 2026 (Page 5)
        pref = self.engine.get_preferred_suppliers("ITM-1048", pd.to_datetime("2026-11-01"))
        self.assertGreaterEqual(len(pref), 2)
        self.assertEqual(pref[0]['supplier_id'], "S029")  # SafeGuard Industrial
        self.assertEqual(pref[1]['supplier_id'], "S030")  # Karam Safety
        # Inactive S031 must NOT be in the list
        self.assertFalse(any(p['supplier_id'] == "S031" for p in pref))

    def test_preferred_suppliers_ranking_itm_1036(self):
        # ITM-1036 Pneumatic cylinder 50x100 as of 1 Nov 2026 (Page 5)
        pref = self.engine.get_preferred_suppliers("ITM-1036", pd.to_datetime("2026-11-01"))
        self.assertGreaterEqual(len(pref), 3)
        self.assertEqual(pref[0]['supplier_id'], "S023")  # Hydrax Hydraulics
        self.assertEqual(pref[1]['supplier_id'], "S022")  # Fluidline Hydraulics
        self.assertEqual(pref[2]['supplier_id'], "S024")  # Janatics Dealer Chakan

    def test_preferred_suppliers_ranking_itm_1016(self):
        # ITM-1016 MIG wire ER70S-6 1.2mm as of 1 Nov 2026 (Page 5)
        pref = self.engine.get_preferred_suppliers("ITM-1016", pd.to_datetime("2026-11-01"))
        self.assertGreaterEqual(len(pref), 2)
        self.assertEqual(pref[0]['supplier_id'], "S009")  # Weldtech Supplies
        self.assertEqual(pref[1]['supplier_id'], "S010")  # Inox Gases

    def test_example_1_contract_po(self):
        # Example 1: PR-26-00019/1 -> CONTRACT_PO, S001, PO-0011
        res = self.batch_results[("PR-26-00019", 1)]
        self.assertEqual(res.route, "CONTRACT_PO")
        self.assertEqual(res.decision, "PO")
        self.assertEqual(res.supplier_id, "S001")
        self.assertEqual(round(res.group_value_inr), 137531)
        self.assertEqual(res.po_id, "PO-0011")

    def test_example_2_contract_pdf(self):
        # Example 2: PR-26-00045/1 -> CONTRACT_PO, S021 (RC-2026-031 from PDF), PO-0072
        res = self.batch_results[("PR-26-00045", 1)]
        self.assertEqual(res.route, "CONTRACT_PO")
        self.assertEqual(res.decision, "PO")
        self.assertEqual(res.supplier_id, "S021")
        self.assertEqual(round(res.group_value_inr), 26829)
        self.assertEqual(res.po_id, "PO-0072")

    def test_example_3_contract_ceiling_exhausted(self):
        # Example 3: PR-26-00004/1 and PR-26-00026/1 clubbed, RC-2026-002 ceiling exceeded -> RFQ
        res1 = self.batch_results[("PR-26-00004", 1)]
        res2 = self.batch_results[("PR-26-00026", 1)]
        self.assertEqual(res1.group_id, res2.group_id)
        self.assertEqual(res1.route, "RFQ")
        self.assertEqual(res1.decision, "SOURCING_REQUEST")
        self.assertEqual(round(res1.group_value_inr), 220256)
        self.assertEqual(res1.suggested_supplier_ids.split(";"), ["S014", "S013", "S016"])

    def test_example_4_two_contracts_lowest_with_room(self):
        # Example 4: PR-26-00034/1 and PR-26-00032/1 clubbed -> CONTRACT_PO S007 PO-0003
        res1 = self.batch_results[("PR-26-00034", 1)]
        res2 = self.batch_results[("PR-26-00032", 1)]
        self.assertEqual(res1.group_id, res2.group_id)
        self.assertEqual(res1.route, "CONTRACT_PO")
        self.assertEqual(res1.decision, "PO")
        self.assertEqual(res1.supplier_id, "S007")
        self.assertEqual(round(res1.group_value_inr), 32547)
        self.assertEqual(res1.po_id, "PO-0003")

    def test_example_5_clubbed_split_prs(self):
        # Example 5: PR-26-00146/1, PR-26-00144/1, PR-26-00145/1 clubbed into SPOT_PO S024 PO-0001
        r1 = self.batch_results[("PR-26-00146", 1)]
        r2 = self.batch_results[("PR-26-00144", 1)]
        r3 = self.batch_results[("PR-26-00145", 1)]
        self.assertEqual(r1.group_id, r2.group_id)
        self.assertEqual(r2.group_id, r3.group_id)
        self.assertEqual(r1.route, "SPOT_PO")
        self.assertEqual(r1.decision, "PO")
        self.assertEqual(r1.supplier_id, "S024")
        self.assertEqual(round(r1.group_value_inr), 126472)
        self.assertEqual(r1.po_id, "PO-0001")

    def test_example_6_not_clubbed_different_plants(self):
        # Example 6: PR-26-00106 (PUN1) and PR-26-00103 (CHK1) separate
        r_pun = self.batch_results[("PR-26-00106", 1)]
        r_chk = self.batch_results[("PR-26-00103", 1)]
        self.assertNotEqual(r_pun.group_id, r_chk.group_id)
        self.assertEqual(r_pun.route, "SPOT_PO")
        self.assertEqual(r_pun.supplier_id, "S027")
        self.assertEqual(round(r_pun.group_value_inr), 156170)
        self.assertEqual(r_pun.po_id, "PO-0002")

    def test_example_7_freetext_matched(self):
        # Example 7: PR-26-00088/1 "hyd hose 1/2 inch 2 wire" -> SPOT_PO S023 PO-0023
        res = self.batch_results[("PR-26-00088", 1)]
        self.assertEqual(res.resolved_item_code, "ITM-1035")
        self.assertEqual(res.route, "SPOT_PO")
        self.assertEqual(res.decision, "PO")
        self.assertEqual(res.supplier_id, "S023")
        self.assertEqual(round(res.group_value_inr), 97955)
        self.assertEqual(res.po_id, "PO-0023")

    def test_example_8_emergency_po(self):
        # Example 8: PR-26-00059/1 Emergency -> EMERGENCY_PO S014 PO-0024
        res = self.batch_results[("PR-26-00059", 1)]
        self.assertEqual(res.route, "EMERGENCY_PO")
        self.assertEqual(res.decision, "PO")
        self.assertEqual(res.supplier_id, "S014")
        self.assertEqual(round(res.group_value_inr), 253184)
        self.assertEqual(res.po_id, "PO-0024")

    def test_example_9_rfq_above_limit(self):
        # Example 9: PR-26-00089/1 "CMM calibration service" -> RFQ suggested S043, S044, S042
        res = self.batch_results[("PR-26-00089", 1)]
        self.assertEqual(res.resolved_item_code, "ITM-1066")
        self.assertEqual(res.route, "RFQ")
        self.assertEqual(res.decision, "SOURCING_REQUEST")
        self.assertEqual(round(res.group_value_inr), 336562)
        self.assertEqual(res.suggested_supplier_ids.split(";"), ["S043", "S044", "S042"])

    def test_example_10_rfq_never_bought(self):
        # Example 10: PR-26-00050/1 ITM-1006 not bought in 365d from active -> RFQ suggested S003, S002, S005
        res = self.batch_results[("PR-26-00050", 1)]
        self.assertEqual(res.route, "RFQ")
        self.assertEqual(res.decision, "SOURCING_REQUEST")
        self.assertEqual(round(res.group_value_inr), 80300)
        self.assertEqual(res.suggested_supplier_ids.split(";"), ["S003", "S002", "S005"])

    def test_example_11_rfp(self):
        # Example 11: PR-26-00100/1 ITM-1034 >= 10L -> RFP suggested S020, S017, S019, S018
        res = self.batch_results[("PR-26-00100", 1)]
        self.assertEqual(res.route, "RFP")
        self.assertEqual(res.decision, "SOURCING_REQUEST")
        self.assertEqual(round(res.group_value_inr), 2070780)
        self.assertEqual(res.suggested_supplier_ids.split(";"), ["S020", "S017", "S019", "S018"])

    def test_example_12_capex(self):
        # Example 12: PR-26-00047/1 "eot crane 5 ton" Capex -> CAPEX_SOURCING suggested S045, S047, S020, S048, S046
        res = self.batch_results[("PR-26-00047", 1)]
        self.assertEqual(res.resolved_item_code, "ITM-1071")
        self.assertEqual(res.route, "CAPEX_SOURCING")
        self.assertEqual(res.decision, "SOURCING_REQUEST")
        self.assertEqual(round(res.group_value_inr), 6036704)
        self.assertEqual(res.suggested_supplier_ids.split(";"), ["S045", "S047", "S020", "S048", "S046"])

    def test_example_13_new_item(self):
        # Example 13: PR-26-00170/1 "Drinking water purifier 50 LPH" -> NEW_ITEM_SOURCING
        res = self.batch_results[("PR-26-00170", 1)]
        self.assertEqual(res.resolved_item_code, "NEW")
        self.assertEqual(res.route, "NEW_ITEM_SOURCING")
        self.assertEqual(res.decision, "SOURCING_REQUEST")
        self.assertEqual(round(res.group_value_inr), 141100)
        self.assertEqual(res.suggested_supplier_ids, "")

    def test_example_14_po_consolidation(self):
        # Example 14: Several requirements on one PO: PR-26-00034, 00032 and PR-26-00031, 00035 share PO-0003
        r34 = self.batch_results[("PR-26-00034", 1)]
        r32 = self.batch_results[("PR-26-00032", 1)]
        r31 = self.batch_results[("PR-26-00031", 1)]
        r35 = self.batch_results[("PR-26-00035", 1)]

        self.assertEqual(r34.group_id, r32.group_id)
        self.assertEqual(r31.group_id, r35.group_id)
        self.assertNotEqual(r34.group_id, r31.group_id)  # Two distinct requirements!
        self.assertEqual(r34.po_id, "PO-0003")
        self.assertEqual(r31.po_id, "PO-0003")  # Consolidated into PO-0003!

if __name__ == "__main__":
    unittest.main()
