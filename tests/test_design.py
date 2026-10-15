#!/usr/bin/env python3
"""Tests for the P5 pre-registration log and gate. Stdlib only, offline.

Run from the kit root:  python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import design_gate  # noqa: E402
import design_log  # noqa: E402

GATE = ROOT / "scripts" / "design_gate.py"
LOGCLI = ROOT / "scripts" / "design_log.py"
FIX = ROOT / "tests" / "fixtures" / "design"
LOG, RETRO, ORACLE, DATASET = FIX / "design_log.jsonl", FIX / "design_log_retro.jsonl", FIX / "oracle.jsonl", FIX / "DATASET.md"
MCP_KEY = "request.conditions"


def gate(log, source, dataset=None, *extra):
    args = [sys.executable, str(GATE), str(log), "--source", str(source)]
    if dataset:
        args += ["--dataset", str(dataset)]
    r = subprocess.run(args + list(extra), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def rules(out):
    return {ln[1:3] for ln in out.splitlines() if ln.startswith("[D")}


class Scratch(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def put(self, name, text):
        p = self.td / name
        p.write_text(text, encoding="utf-8")
        return p

    def log_lines(self):
        return LOG.read_text(encoding="utf-8").splitlines()

    def rechain(self, entries):
        """Entries (dicts) re-serialised with a valid seq / prev chain, as a tidy rewrite would."""
        lines = []
        for e in entries:
            lines.append(design_log.make_entry(lines, e["batch"], e["phase"], e["points"], None,
                                               e["design_method"], written_at=e["written_at"]))
        return "\n".join(lines) + "\n"


class TestHonest(Scratch):
    def test_fixture_passes(self):
        code, out = gate(LOG, ORACLE, DATASET)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "PASS")

    def test_csv_source_passes(self):
        rows = ["time,call,name,A,B,E,temperature"]
        for i, ln in enumerate(ORACLE.read_text().splitlines()):
            d = json.loads(ln)
            for name, c in d["points"].items():
                rows.append(f"{d['time']},{i},{name},{c['A']},{c['B']},{c['E']},{c['temperature']}")
        code, out = gate(LOG, self.put("oracle.csv", "\n".join(rows) + "\n"), DATASET)
        self.assertEqual(code, 0, out)

    def test_unrun_point_is_a_note_not_a_failure(self):
        src = ORACLE.read_text().splitlines()
        last = json.loads(src[-1])
        del last["points"]["e7"]
        src[-1] = json.dumps(last)
        code, out = gate(LOG, self.put("o.jsonl", "\n".join(src) + "\n"), DATASET)
        self.assertEqual(code, 0, out)
        self.assertIn("note: batch 3 (line 3): 1 registered point(s) never ran", out)


class TestRetroactive(Scratch):
    def test_no_log_fails_d1(self):
        code, out = gate(self.td / "design_log.jsonl", ORACLE, DATASET)
        self.assertEqual(code, 1, out)
        self.assertIn("[D1] design log", out)
        self.assertIn("7 executed experiment(s) in 4 call(s) have no pre-registration", out)
        self.assertIn("[D5]", out)

    def test_log_written_after_all_batches_fails_d3(self):
        code, out = gate(RETRO, ORACLE, DATASET)
        self.assertEqual(code, 1, out)
        self.assertEqual(rules(out), {"D3"})
        self.assertEqual(out.count("[D3]"), 4)
        self.assertIn("before any design-log entry was written", out)
        self.assertIn("registered later, line 1 (batch 1) written_at 2026-10-01T12:30:00", out)

    def test_entry_written_after_its_batch_fails_d3(self):
        entries = [json.loads(ln) for ln in self.log_lines()]
        entries[2]["written_at"] = "2026-10-01T11:30:00+00:00"   # batch 3 ran at 11:01
        code, out = gate(self.put("log.jsonl", self.rechain(entries)), ORACLE, DATASET)
        self.assertEqual(code, 1, out)
        self.assertIn("[D3]", out)
        self.assertIn("ran at 2026-10-01T11:01:00+00:00 but was registered later, line 3", out)


class TestConditions(Scratch):
    def test_executed_point_differs_fails_d4(self):
        src = ORACLE.read_text().replace('"A": 10.0', '"A": 12.0')
        code, out = gate(LOG, self.put("o.jsonl", src), DATASET)
        self.assertEqual(code, 1, out)
        self.assertEqual(rules(out), {"D4"})
        self.assertIn('{"A": 12.0, "B": 1.0, "E": 0.01, "temperature": 25} matches no point of the open entry', out)

    def test_within_tolerance_passes(self):
        src = ORACLE.read_text().replace('"A": 10.0', '"A": 10.0000000001')
        self.assertEqual(gate(LOG, self.put("o.jsonl", src), DATASET)[0], 0)

    def test_extra_condition_key_fails_d4(self):
        src = ORACLE.read_text().replace('"temperature": 45', '"temperature": 45, "pH": 7')
        self.assertIn("D4", rules(gate(LOG, self.put("o.jsonl", src), DATASET)[1]))

    def test_point_from_a_closed_batch_fails_d4(self):
        extra = json.dumps({"time": "2026-10-01T11:05:00+00:00",
                            "points": {"again": {"A": 1.0, "B": 1.0, "E": 0.01, "temperature": 25}}})
        code, out = gate(LOG, self.put("o.jsonl", ORACLE.read_text() + extra + "\n"), DATASET)
        self.assertEqual(code, 1, out)
        self.assertIn("matches batch 1, which was closed by line 3", out)

    def test_point_run_twice_fails_d4(self):
        extra = json.dumps({"time": "2026-10-01T11:05:00+00:00",
                            "points": {"again": {"A": 5.0, "B": 1.0, "E": 0.01, "temperature": 45}}})
        code, out = gate(LOG, self.put("o.jsonl", ORACLE.read_text() + extra + "\n"), DATASET)
        self.assertIn("ran more times than batch 3 registered it", out)


class TestAppendOnly(Scratch):
    def test_edited_line_fails_d2(self):
        lines = self.log_lines()
        lines[0] = lines[0].replace('"A": 10.0', '"A": 12.0')
        src = ORACLE.read_text().replace('"A": 10.0', '"A": 12.0')
        code, out = gate(self.put("log.jsonl", "\n".join(lines) + "\n"), self.put("o.jsonl", src), DATASET)
        self.assertEqual(code, 1, out)
        self.assertEqual(rules(out), {"D2"})
        self.assertIn("line 2: prev does not match the sha256 of line 1", out)

    def test_removed_line_fails(self):
        lines = self.log_lines()
        del lines[1]
        out = gate(self.put("log.jsonl", "\n".join(lines) + "\n"), ORACLE, DATASET)[1]
        self.assertTrue({"D1", "D2"} <= rules(out), out)

    def test_non_monotonic_time_fails_d2(self):
        entries = [json.loads(ln) for ln in self.log_lines()]
        entries[1]["written_at"] = "2026-10-01T08:00:00+00:00"
        out = gate(self.put("log.jsonl", self.rechain(entries)), ORACLE, DATASET)[1]
        self.assertIn("[D2] line 2: written_at 2026-10-01T08:00:00+00:00 is earlier than the line before it", out)

    def test_bad_justification_type_fails_d1(self):
        lines = self.log_lines()
        e = json.loads(lines[0])
        e["points"][0]["justification"] = {"type": "explore", "target": "the space"}
        lines[0] = json.dumps(e)
        out = gate(self.put("log.jsonl", "\n".join(lines) + "\n"), ORACLE)[1]
        self.assertIn("[D1] line 1: point e1 needs exactly one justification", out)

    def test_point_without_justification_fails_d1(self):
        lines = self.log_lines()
        e = json.loads(lines[0])
        del e["points"][1]["justification"]
        lines[0] = json.dumps(e)
        self.assertIn("point e2 needs exactly one justification", gate(self.put("log.jsonl", "\n".join(lines) + "\n"), ORACLE)[1])

    def test_duplicate_point_name_fails_d1(self):
        lines = self.log_lines()
        e = json.loads(lines[0])
        e["points"][1]["name"] = "e1"
        lines[0] = json.dumps(e)
        self.assertIn("point name e1 is used twice", gate(self.put("log.jsonl", "\n".join(lines) + "\n"), ORACLE)[1])


class TestDataset(Scratch):
    def test_justification_reconstructed_fails_d5(self):
        ds = DATASET.read_text().replace("`variance → Km_A`", "`variance → Vmax`")
        code, out = gate(LOG, ORACLE, self.put("D.md", ds))
        self.assertEqual(code, 1, out)
        self.assertEqual(rules(out), {"D5"})
        self.assertIn("DATASET batch 1: one justification `variance → Vmax` for the whole batch, but the design log "
                      "line 1 justifies e1 as `variance → Km_A`", out)

    def test_missing_experiment_fails_d5(self):
        ds = DATASET.read_text().replace("; e5: `variance → Km_B`", "")
        self.assertIn("DATASET batch 2: experiment e5 ran and has no justification in the cell",
                      gate(LOG, ORACLE, self.put("D.md", ds))[1])

    def test_swapped_experiment_justification_fails_d5(self):
        ds = DATASET.read_text().replace("e5: `variance → Km_B`", "e5: `variance → Km_A`")
        self.assertIn("experiment e5 is justified as `variance → Km_A`, the design log line 2 says `variance → Km_B`",
                      gate(LOG, ORACLE, self.put("D.md", ds))[1])

    def test_one_shared_justification_for_a_mixed_batch_fails_d5(self):
        ds = DATASET.read_text().replace("e4: `information → cpt-enz-comparison-c1 pair H1/H2`; e5: `variance → Km_B`",
                                         "`variance → Km_B`")
        out = gate(LOG, ORACLE, self.put("D.md", ds))[1]
        self.assertIn("justifies e4 as `information → cpt-enz-comparison-c1 pair H1/H2`", out)

    def test_unknown_experiment_name_fails_d5(self):
        ds = DATASET.read_text().replace("e5: `variance → Km_B`", "e5, e9: `variance → Km_B`")
        self.assertIn("experiment e9 is not a point of the design log line 2", gate(LOG, ORACLE, self.put("D.md", ds))[1])

    def test_named_grouping_passes(self):
        ds = DATASET.read_text().replace("| `variance → Km_A` |", "| e1, e2: `variance → Km_A`; e3: `variance → Km_A` |")
        code, out = gate(LOG, ORACLE, self.put("D.md", ds))
        self.assertEqual(code, 0, out)

    def test_design_method_differs_fails_d5(self):
        ds = DATASET.read_text().replace("D-optimal, seed 1", "D-optimal, seed 7")
        self.assertIn("DATASET batch 1: design method", gate(LOG, ORACLE, self.put("D.md", ds))[1])

    def test_missing_row_fails_d5(self):
        ds = "\n".join(ln for ln in DATASET.read_text().splitlines() if not ln.startswith("| 2 "))
        self.assertIn("batch 2 (line 2) ran 2 experiment(s) and has no DATASET section 6 row",
                      gate(LOG, ORACLE, self.put("D.md", ds))[1])

    def test_unknown_batch_fails_d5(self):
        ds = DATASET.read_text().replace("| 3 | CYCLE-2", "| 4 | CYCLE-2")
        out = gate(LOG, ORACLE, self.put("D.md", ds))[1]
        self.assertIn("DATASET batch 4: no design-log entry", out)

    def test_cell_without_type_fails_d5(self):
        ds = DATASET.read_text().replace("`variance → Km_A`", "explore the A axis")
        self.assertIn("is not `<variance|information|boundary> → <target>`", gate(LOG, ORACLE, self.put("D.md", ds))[1])


class TestSemicolonTargets(Scratch):
    """Targets with `;`: the separator of the cell's parts only counts outside backticks."""
    LOG, ORACLE, DATASET = FIX / "design_log_semicolon.jsonl", FIX / "oracle_semicolon.jsonl", FIX / "DATASET_semicolon.md"
    E9 = "`information → C_A shape at the hot end of the T range; with e8 it also gives the slope of log r0 in 1/T`"

    def run_gate(self, ds):
        return gate(self.LOG, self.ORACLE, self.put("D.md", ds))

    def test_verbatim_copy_passes(self):
        code, out = gate(self.LOG, self.ORACLE, self.DATASET)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "PASS")

    def test_truncated_target_fails_d5(self):
        ds = self.DATASET.read_text().replace(self.E9, "`information → C_A shape at the hot end of the T range`")
        code, out = self.run_gate(ds)
        self.assertEqual(code, 1, out)
        self.assertEqual(rules(out), {"D5"})
        self.assertIn("experiment e9 is justified as `information → C_A shape at the hot end of the T range`, the "
                      "design log line 1 says `information → C_A shape at the hot end of the T range; with e8", out)
        self.assertIn("copy it, do not reconstruct it", out)
        self.assertNotIn("is not `<names>:", out)

    def test_paraphrased_target_fails_d5(self):
        ds = self.DATASET.read_text().replace(self.E9, "`information → hot end of T; with e8, slope of log r0 vs 1/T`")
        code, out = self.run_gate(ds)
        self.assertEqual(code, 1, out)
        self.assertIn("experiment e9 is justified as `information → hot end of T; with e8, slope of log r0 vs 1/T`", out)

    def test_shared_target_truncated_fails_d5(self):
        ds = self.DATASET.read_text().replace("`variance → k1 at 25 °C; k2 held at its PRE-1 estimate`",
                                              "`variance → k1 at 25 °C`")
        out = self.run_gate(ds)[1]
        self.assertIn("one justification `variance → k1 at 25 °C` for the whole batch, but the design log line 2 "
                      "justifies e10 as `variance → k1 at 25 °C; k2 held at its PRE-1 estimate`", out)

    def test_names_grouped_with_semicolon_targets_passes(self):
        shared = "`variance → k1 at 25 °C; k2 held at its PRE-1 estimate`"
        ds = self.DATASET.read_text().replace(f"| {shared} |", f"| e10: {shared}; e11: {shared} |")
        code, out = self.run_gate(ds)
        self.assertEqual(code, 0, out)

    def test_br_separates_parts_outside_backticks(self):
        ds = self.DATASET.read_text().replace(f"; e9: {self.E9}", f"<br>e9: {self.E9}")
        code, out = self.run_gate(ds)
        self.assertEqual(code, 0, out)

    def test_unclosed_backtick_fails_d5(self):
        ds = self.DATASET.read_text().replace(f"e9: {self.E9}", f"e9: {self.E9[:-1]}")
        code, out = self.run_gate(ds)
        self.assertEqual(code, 1, out)
        self.assertIn("DATASET batch 1: Justification has an unclosed backtick", out)

    def test_missing_names_prefix_is_not_hidden_by_backticks(self):
        ds = self.DATASET.read_text().replace(f"; e9: {self.E9}", f"; {self.E9}")
        out = self.run_gate(ds)[1]
        self.assertIn("is not `<names>: <variance|information|boundary> → <target>`", out)
        self.assertIn("experiment e9 ran and has no justification in the cell", out)

    def test_cell_parts(self):
        self.assertEqual(design_gate.cell_parts("e1: `variance → a; b`; e2, e3: `boundary → c`<br/>e4: `x → y`"),
                         ["e1: `variance → a; b`", " e2, e3: `boundary → c`", "e4: `x → y`"])
        self.assertEqual(design_gate.cell_parts("explore; the A axis"), ["explore", " the A axis"])
        self.assertEqual(design_gate.cell_parts("`variance → k <br> 1`"), ["`variance → k <br> 1`"])


class TestPipeTargets(Scratch):
    """A `|` would split the table cell: it is written `\\|` in the log and in the cell."""

    def one_batch(self, target):
        log = self.td / "design_log.jsonl"      # written directly: append would refuse a bare `|`
        log.write_text(json.dumps({"seq": 1, "prev": None, "written_at": "2026-10-01T09:00:00+00:00", "batch": "1",
                                   "phase": "PRE-1", "points": [{"name": "x1", "conditions": {"A": 1.0}, "justification":
                                                                 {"type": "information", "target": target}}],
                                   "design_method": "manual: test"}) + "\n")
        src = self.put("o.jsonl", json.dumps({"time": "2026-10-01T09:05:00+00:00", "points": {"x1": {"A": 1.0}}}) + "\n")
        return log, src

    def dataset(self, cell):
        return self.put("D.md", "## 6. Acquisition\n\n| Batch | Justification | Design method |\n|---|---|---|\n"
                                f"| 1 | {cell} | manual: test |\n")

    def test_escaped_pipe_copied_verbatim_passes(self):
        log, src = self.one_batch(r"sign of k1 \| k2")
        code, out = gate(log, src, self.dataset(r"`information → sign of k1 \| k2`"))
        self.assertEqual(code, 0, out)

    def test_legacy_bare_pipe_in_log_matches_escaped_cell(self):
        log, src = self.one_batch("sign of k1 | k2")      # an old log, written before append refused a bare `|`
        code, out = gate(log, src, self.dataset(r"`information → sign of k1 \| k2`"))
        self.assertEqual(code, 0, out)

    def test_pipe_paraphrase_fails_d5(self):
        log, src = self.one_batch(r"sign of k1 \| k2")
        out = gate(log, src, self.dataset(r"`information → sign of k1 \| k3`"))[1]
        self.assertIn("[D5]", out)


class TestVectorConditions(Scratch):
    """Conditions that are lists and objects: same structure, numbers within tolerance element by element."""
    LOG, ORACLE, DATASET = FIX / "design_log_vector.jsonl", FIX / "oracle_vector.jsonl", FIX / "DATASET_vector.md"
    P = {"p1": 2, "p2": 1, "pos2": [3, 0], "velocity2": [0, 0.5], "measurement_times": [0, 5, 10], "duration": 10}
    PROBES = {"probes": [{"pos": [1, 0], "vel": [0, 1]}, {"pos": [-1, 0], "vel": [0, -1]}], "duration": 20}

    def oracle_with(self, old, new):
        src = self.ORACLE.read_text()
        self.assertIn(old, src)
        return self.put("o.jsonl", src.replace(old, new, 1))

    def test_honest_run_passes(self):
        code, out = gate(self.LOG, self.ORACLE, self.DATASET)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "PASS")

    def test_changed_vector_element_fails_d4(self):
        code, out = gate(self.LOG, self.oracle_with('"pos2": [3.0, 0.0]', '"pos2": [3.0, 0.1]'), self.DATASET)
        self.assertEqual(code, 1, out)
        self.assertEqual(rules(out), {"D4"})
        self.assertIn('"pos2": [3.0, 0.1]', out)
        self.assertIn("matches no point of the open entry, line 1 (batch 1)", out)

    def test_other_list_length_fails_d4(self):
        out = gate(self.LOG, self.oracle_with('"measurement_times": [0.0, 5.0, 10.0]',
                                              '"measurement_times": [0.0, 5.0, 10.0, 15.0]'), self.DATASET)[1]
        self.assertEqual(rules(out), {"D4"})

    def test_changed_nested_object_fails_d4(self):
        out = gate(self.LOG, self.oracle_with('"vel": [0.0, -1.0]', '"vel": [0.0, -1.5]'), self.DATASET)[1]
        self.assertEqual(rules(out), {"D4"})
        self.assertIn("line 2 (batch 2)", out)

    def test_same_value(self):
        same = design_log.same_value
        self.assertTrue(same([3, 0], [3.0, 0.0]))
        self.assertFalse(same([3, 0], [3, 0.1]))
        self.assertFalse(same([3, 0], [3, 0, 0]))
        self.assertFalse(same([3, 0], [0, 3]))                              # list order counts
        self.assertTrue(same({"a": 1, "b": [1, 2]}, {"b": [1.0, 2.0], "a": 1.0}))   # key order does not
        self.assertFalse(same({"a": 1}, {"a": 1, "b": 2}))
        self.assertFalse(same([1], 1))
        self.assertFalse(same({"a": 1}, [1]))
        self.assertTrue(same([], []))
        self.assertTrue(same(10.0, 10.0000000001))
        self.assertTrue(same("H2O", " H2O "))

    def test_append_accepts_vectors_and_refuses_null_and_bool(self):
        log = self.td / "design_log.jsonl"
        design_log.append_entry(log, "1", "PRE-1", {"a": self.P, "b": self.PROBES}, "variance → p2", "manual: t")
        _, entries, probs = design_log.load_log(log)
        self.assertEqual(probs, [])
        self.assertEqual(entries[0]["points"][0]["conditions"]["pos2"], [3, 0])
        for bad, where in (({**self.P, "pos2": [3, None]}, "pos2[1]"), ({**self.P, "on": True}, "on"),
                           ({"probes": [{"pos": [1, float("nan")]}]}, "probes[0].pos[1]")):
            with self.assertRaises(ValueError) as cm:
                design_log.append_entry(log, "2", "PRE-1", {"c": bad}, "variance → p2", "manual: t")
            self.assertIn(f"condition {where}=", str(cm.exception))
        self.assertEqual(len(design_log.raw_lines(log)), 1)

    def test_append_cli_takes_the_example_point(self):
        log = self.td / "design_log.jsonl"
        r = subprocess.run([sys.executable, str(LOGCLI), "append", "--log", str(log), "--batch", "1", "--phase", "PRE-1",
                            "--points", json.dumps({"x1": self.P}), "--justification", "variance → p2",
                            "--design-method", "manual: t"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class TestUsage(Scratch):
    def test_usage_errors_exit_2(self):
        self.assertEqual(subprocess.run([sys.executable, str(GATE), str(LOG)], capture_output=True).returncode, 2)
        self.assertEqual(gate(LOG, self.td / "nope.jsonl")[0], 2)
        self.assertEqual(gate(LOG, ORACLE, self.td / "nope.md")[0], 2)
        self.assertEqual(gate(LOG, ORACLE, None, "--bogus")[0], 2)

    def test_unreadable_source_exits_2(self):
        code, out = gate(LOG, self.put("o.jsonl", "{not json\n"))
        self.assertEqual(code, 2)
        self.assertIn("not JSON", out)


class TestAppendCli(Scratch):
    def run_append(self, log, batch, just, points='{"x1": {"A": 1, "B": 2}}'):
        return subprocess.run([sys.executable, str(LOGCLI), "append", "--log", str(log), "--batch", batch,
                               "--phase", "PRE-1", "--points", points, "--justification", just,
                               "--design-method", "manual: test"], capture_output=True, text=True)

    def test_append_builds_a_valid_chain(self):
        log = self.td / "design_log.jsonl"
        self.assertEqual(self.run_append(log, "1", "variance → k1").returncode, 0)
        self.assertEqual(self.run_append(log, "2", "boundary -> T range").returncode, 0)
        lines, entries, probs = design_log.load_log(log)
        self.assertEqual(probs, [])
        self.assertEqual([e["seq"] for e in entries], [1, 2])
        self.assertEqual(entries[1]["points"][0]["just"], ("boundary", "T range"))

    def test_per_point_justifications(self):
        log = self.td / "design_log.jsonl"
        pts = json.dumps({"x1": {"conditions": {"A": 1}, "justification": "variance → k1"},
                          "x2": {"conditions": {"A": 2}, "justification": {"type": "boundary", "target": "A range"}}})
        r = subprocess.run([sys.executable, str(LOGCLI), "append", "--log", str(log), "--batch", "1", "--phase", "P",
                            "--points", pts, "--design-method", "manual: t"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        _, entries, probs = design_log.load_log(log)
        self.assertEqual(probs, [])
        self.assertEqual([q["just"] for q in entries[0]["points"]], [("variance", "k1"), ("boundary", "A range")])

    def test_append_refuses_a_point_without_justification(self):
        log = self.td / "design_log.jsonl"
        r = subprocess.run([sys.executable, str(LOGCLI), "append", "--log", str(log), "--batch", "1", "--phase", "P",
                            "--points", '{"x1": {"A": 1}}', "--design-method", "manual: t"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("point x1 has no justification", r.stderr)
        r = subprocess.run([sys.executable, str(LOGCLI), "append", "--log", str(log), "--batch", "1", "--phase", "P",
                            "--points", '{"x1": {"A": 1}}', "--justification", "variance → a", "--justification",
                            "variance → b", "--design-method", "manual: t"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("one default justification at most", r.stderr)
        self.assertFalse(log.exists())

    def test_append_refuses_explore_and_duplicate_batch(self):
        log = self.td / "design_log.jsonl"
        r = self.run_append(log, "1", "explore → everything")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(log.exists())
        self.run_append(log, "1", "variance → k1")
        self.run_append(log, "1", "variance → k2")
        self.assertIn("batch 1 already registered", " ".join(m for _, m in design_log.load_log(log)[2]))

    def test_append_accepts_semicolon_in_target(self):
        log = self.td / "design_log.jsonl"
        r = self.run_append(log, "1", "information → C_A shape at the low end; with e8 it also gives the slope")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(design_log.load_log(log)[1][0]["points"][0]["just"],
                         ("information", "C_A shape at the low end; with e8 it also gives the slope"))

    def test_append_refuses_characters_that_break_the_cell(self):
        log = self.td / "design_log.jsonl"
        for target, why in ((r"uses `k1` only", "a backtick"), ("k1 | k2", "a `|`"), ("k1\nk2", "a line break")):
            pts = json.dumps({"x1": {"conditions": {"A": 1}, "justification": {"type": "variance", "target": target}}})
            r = subprocess.run([sys.executable, str(LOGCLI), "append", "--log", str(log), "--batch", "1", "--phase", "P",
                                "--points", pts, "--design-method", "manual: t"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, target)
            self.assertIn(f"point x1: target {target!r} has {why}", r.stderr)
        r = self.run_append(log, "1", "boundary → T range\nand pH")
        self.assertEqual(r.returncode, 1)
        self.assertIn("a line break", r.stderr)
        self.assertFalse(log.exists())
        self.assertEqual(self.run_append(log, "1", r"variance → sign of k1 \| k2").returncode, 0)

    def test_append_refuses_a_pipe_in_the_design_method(self):
        log = self.td / "design_log.jsonl"
        r = subprocess.run([sys.executable, str(LOGCLI), "append", "--log", str(log), "--batch", "1", "--phase", "P",
                            "--points", '{"x1": {"A": 1}}', "--justification", "variance → k1",
                            "--design-method", "tool | criterion"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("design method 'tool | criterion' has a `|`", r.stderr)
        self.assertFalse(log.exists())


class TestHook(Scratch):
    """The PreToolUse hook as wired for mcp__enzyme_simulation__simulate_enzyme_dynamics."""

    def hook(self, conditions):
        payload = {"tool_name": "mcp__enzyme_simulation__simulate_enzyme_dynamics",
                   "tool_input": {"request": {"conditions": conditions}}}
        err = io.StringIO()
        old, sys.stderr = sys.stderr, err
        try:
            code = design_log.main(["hook", "--log", str(self.log), "--witness", str(self.wit),
                                    "--points-key", MCP_KEY], stdin=io.StringIO(json.dumps(payload)))
        finally:
            sys.stderr = old
        return code, err.getvalue()

    def setUp(self):
        super().setUp()
        self.log, self.wit = self.td / "design_log.jsonl", self.td / "design_witness.jsonl"
        self.p1 = {"A": 1.0, "B": 1.0, "E": 0.01, "temperature": 25}
        self.p2 = {"A": 5.0, "B": 1.0, "E": 0.01, "temperature": 25}

    def register(self, batch, *pts):
        design_log.append_entry(self.log, batch, "PRE-1", {f"x{i}": p for i, p in enumerate(pts)},
                                ["variance → Km_A"], "manual: test")

    def test_blocks_without_log(self):
        code, err = self.hook({"x": self.p1})
        self.assertEqual(code, 2)
        self.assertIn("no design log", err)
        self.assertFalse(self.wit.exists())

    def test_admits_registered_points_and_blocks_others(self):
        self.register("1", self.p1, self.p2)
        self.assertEqual(self.hook({"a": self.p1})[0], 0)
        self.assertEqual(self.hook({"b": self.p2})[0], 0)
        code, err = self.hook({"c": self.p2})                 # already used
        self.assertEqual(code, 2)
        self.assertIn("not an unused point of the latest design-log entry", err)
        code, _ = self.hook({"d": {**self.p1, "A": 2.0}})     # never registered
        self.assertEqual(code, 2)
        self.assertEqual(len(self.wit.read_text().splitlines()), 2)

    def test_new_entry_closes_the_previous_one(self):
        self.register("1", self.p1, self.p2)
        self.register("2", {**self.p1, "temperature": 45})
        self.assertEqual(self.hook({"a": self.p1})[0], 2)

    def test_witness_is_a_gate_source_with_commitments(self):
        self.register("1", self.p1)
        self.hook({"a": self.p1})
        self.register("2", self.p2)
        self.hook({"b": self.p2})
        code, out = gate(self.log, self.wit, None, "--require-commit")
        self.assertEqual(code, 0, out)

    def test_rewrite_after_the_call_is_caught_by_the_commitment(self):
        self.register("1", self.p1)
        self.hook({"a": self.p1})
        e = json.loads(self.log.read_text())
        e["points"][0]["justification"] = {"type": "variance", "target": "Vmax"}   # last line: the chain alone cannot see it
        self.log.write_text(json.dumps(e) + "\n")
        code, out = gate(self.log, self.wit)
        self.assertEqual(code, 1, out)
        self.assertIn("[D2]", out)
        self.assertIn("rewritten after the call", out)

    def test_backdated_entry_is_caught_by_the_commitment(self):
        self.register("1", self.p1)
        self.hook({"a": self.p1})
        w = json.loads(self.wit.read_text())
        # A batch run without registration, then a backdated entry appended for it.
        w2 = {**w, "time": "2099-01-01T00:00:00+00:00", "points": [{"name": "b", "conditions": self.p2}]}
        with open(self.wit, "a") as f:
            f.write(json.dumps(w2) + "\n")
        lines = design_log.raw_lines(self.log)
        with open(self.log, "a") as f:
            f.write(design_log.make_entry(lines, "2", "PRE-1", {"b": self.p2}, ["variance → Km_B"], "manual: t",
                                          written_at="2026-01-01T00:00:00+00:00") + "\n")
        code, out = gate(self.log, self.wit)
        self.assertEqual(code, 1, out)
        self.assertIn("written_at was backdated", out)
        self.assertIn("registered later, line 2", out)

    def test_require_commit_on_a_plain_oracle_log_fails_d3(self):
        code, out = gate(LOG, ORACLE, DATASET, "--require-commit")
        self.assertEqual(code, 1)
        self.assertIn("no design_head / design_lines recorded", out)

    def test_points_option_for_a_cli_wrapper(self):
        self.register("1", self.p1)
        args = ["hook", "--log", str(self.log), "--witness", str(self.wit), "--points", json.dumps([self.p1]),
                "--tool", "oracle-cli"]
        self.assertEqual(design_log.main(args), 0)
        self.assertEqual(json.loads(self.wit.read_text())["tool"], "oracle-cli")

    def test_vector_point_admitted_as_floats(self):
        P, PROBES = TestVectorConditions.P, TestVectorConditions.PROBES
        self.register("1", P, PROBES)
        as_floats = {"duration": 10.0, "measurement_times": [0.0, 5.0, 10.0], "velocity2": [0.0, 0.5],
                     "pos2": [3.0, 0.0], "p2": 1.0, "p1": 2.0}
        self.assertEqual(self.hook({"a": as_floats})[0], 0)
        self.assertEqual(self.hook({"b": {"duration": 20.0, "probes": [{"vel": [0, 1], "pos": [1, 0]},
                                                                       {"vel": [0, -1], "pos": [-1, 0]}]}})[0], 0)
        code, err = self.hook({"c": P})                       # already used
        self.assertEqual(code, 2)
        self.assertIn("not an unused point of the latest design-log entry", err)
        code, out = gate(self.log, self.wit, None, "--require-commit")
        self.assertEqual(code, 0, out)

    def test_vector_element_or_length_change_is_blocked(self):
        P = TestVectorConditions.P
        self.register("1", P)
        for changed in ({**P, "pos2": [3, 0.1]}, {**P, "measurement_times": [0, 5]},
                        {**P, "pos2": [0, 3]}, {**P, "pos2": 3}):
            code, err = self.hook({"x": changed})
            self.assertEqual(code, 2, changed)
            self.assertIn("design_log hook: call blocked", err)
        self.assertFalse(self.wit.exists())


class TestModule(unittest.TestCase):
    def test_check_returns_notes_separately(self):
        fails, notes = design_gate.check(LOG, ORACLE, DATASET)
        self.assertEqual((fails, notes), ([], []))


if __name__ == "__main__":
    unittest.main()
