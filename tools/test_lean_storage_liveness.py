"""Certificate pruning must remove dead copies without losing live guard facts."""
import unittest

import check_lean_boundary as bridge
import check_lean_storage as storage


class CertificateLivenessTests(unittest.TestCase):
    def test_batches_cover_every_obligation_and_reject_last_broken_guard(self):
        nodes = []
        for j in range(129):
            nodes.append({"op": "guard", "value": f"x{j}", "tags": ["fit"], "yes": 2 * j + 1, "no": 258})
            nodes.append({"op": "payload", "value": f"x{j}", "tags": ["fit"], "next": 2 * j + 2})
        nodes.append({"op": "stop"})
        candidate = {"schema_version": 2, "program": {"entry": 0, "nodes": nodes}, "certificate": []}
        batches = list(storage.proof_batches(candidate))
        covered = [site for _, sites in batches for site in sites]
        self.assertEqual(sorted(covered), list(range(1, 258, 2)))
        self.assertEqual(len(covered), len(set(covered)))
        for batch, sites in batches:
            for index, node in enumerate(nodes):
                expected = node if node["op"] != "payload" or index in sites else {"op": "jump", "next": node["next"]}
                self.assertEqual(batch["program"]["nodes"][index], expected)
        if bridge.DEFAULT_CHECKER.is_file():
            for batch, sites in batches:
                self.assertTrue(bridge.run_checker(bridge.DEFAULT_CHECKER, bridge.encode(batch),
                                                  {"nodes": len(nodes), "payloads": len(sites)}))
            nodes[256]["value"] = "wrong"
            results = [bridge.run_checker(bridge.DEFAULT_CHECKER, bridge.encode(batch),
                                          {"nodes": len(nodes), "payloads": len(sites)})
                       for batch, sites in storage.proof_batches(candidate)]
            self.assertFalse(all(results))

    def test_guards_without_payload_demands_need_no_stored_facts(self):
        nodes = [{"op": "guard", "value": "x", "tags": ["fit"], "yes": 1, "no": 2},
                 {"op": "guard", "value": "y", "tags": ["fit"], "yes": 2, "no": 2},
                 {"op": "stop"}]
        self.assertEqual(bridge.live_locations(nodes), [set(), set(), set()])
        self.assertEqual(bridge.infer_certificate(nodes), [[], [], []])

    def test_dead_copy_cycle_has_no_guard_requirements(self):
        nodes = [{"op": "copy", "dst": "a", "src": "b", "next": 1},
                 {"op": "copy", "dst": "b", "src": "a", "next": 0}]
        self.assertEqual(bridge.live_locations(nodes), [set(), set()])
        self.assertEqual(bridge.infer_certificate(nodes), [[], []])

    def test_live_copy_chain_keeps_required_source_guard(self):
        nodes = [{"op": "guard", "value": "x", "tags": ["fit"], "yes": 1, "no": 4},
                 {"op": "copy", "dst": "y", "src": "x", "next": 2},
                 {"op": "copy", "dst": "z", "src": "y", "next": 3},
                 {"op": "payload", "value": "z", "tags": ["fit"], "next": 4},
                 {"op": "stop"}]
        facts = bridge.infer_certificate(nodes)
        self.assertIn(["x", ["fit"]], facts[1])
        self.assertIn(["z", ["fit"]], facts[3])
        if bridge.DEFAULT_CHECKER.is_file():
            candidate = {"schema_version": 2, "program": {"entry": 0, "nodes": nodes}, "certificate": facts}
            self.assertTrue(bridge.run_checker(bridge.DEFAULT_CHECKER, bridge.encode(candidate),
                                              {"nodes": len(nodes), "payloads": 1}))


if __name__ == "__main__":
    unittest.main()
