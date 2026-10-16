#!/usr/bin/env python3
"""Tests for the final-result gate (R1-R6) and its hook. Stdlib only, offline.

Every test builds a small workspace in a temp dir (PLAN, DATASET, acquisitions
source, RUNs, COMPARISONs, submission) and changes one thing.

Run from the kit root:  python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import design_log  # noqa: E402
import result_gate  # noqa: E402

GATE = ROOT / "scripts" / "result_gate.py"
CRIT = ["cpt-t-criterion-units-match", "cpt-t-criterion-quality", "cpt-t-criterion-parsimony"]
DS = "cpt-t-dataset-x"
A, B, A0 = "cpt-t-run-a", "cpt-t-run-b", "cpt-t-run-a0"
SUBMISSION = "y = a * x\n"
SPEC_A = "y = a * x, one free parameter a in [0, 10]."
SPEC_B = "y = a * x + b * x^2, free parameters a in [0, 10], b in [-1, 1]."


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def plan_md() -> str:
    blocks = "".join(f"### C{k}\n\n**ID**: `{c}`\n\n**How measured**: mechanical\n\n" for k, c in enumerate(CRIT))
    return f"# PLAN — fixture\n\n**ID**: `cpt-t-plan-x`\n\n## 9. Verdict Criteria\n\n{blocks}"


def dataset_md(rows=None) -> str:
    rows = rows or [("1", "e1, e2", "`variance → a`"),
                    ("2", "e3, e4", f"`information → cpt-t-comparison-c1 pair {A0} vs alternative`")]
    body = "".join(f"| {b} | P | simulator | {e} | {j} | manual: test | n/a | 1 min | T, 2026-10-01 |\n" for b, e, j in rows)
    return ("---\ndescription: fixture\nstatus: draft\n---\n\n# DATASET — fixture\n\n"
            f"**ID**: `{DS}`\n\n## 6. Acquisition\n\n"
            "| Batch | Phase | Origin | Experiments | Justification (type → target) | Design method | Simulator preview "
            "| Actual duration | Approved by |\n|---|---|---|---|---|---|---|---|---|\n" + body)


def source_jsonl(calls=(("e1", "e2"), ("e3", "e4"))) -> str:
    return "".join(json.dumps({"time": f"2026-10-01T{9 + k:02d}:00:00+00:00",
                               "points": {n: {"x": float(i)} for i, n in enumerate(c)}}) + "\n"
                   for k, c in enumerate(calls))


def run_md(rid, exps="e1, e2, e3, e4", structure="single-site", spec=SPEC_A, verdict=("pass", "pass", "pass"),
           cand_sha=None, dataset=DS, drop=None, measured="mechanical") -> str:
    secs = {
        1: ("Unit", f"**Dataset**: `{dataset}`\n\n**Experiments**: {exps}\n\nSimulator data."),
        2: ("Procedure", "Least squares."),
        3: ("Candidate Spec", (f"**Structure**: {structure}\n\n" if structure else "")
            + f"**Candidate file**: `candidate.txt`\n\n**Candidate sha256**: `{cand_sha or sha(SUBMISSION)}`\n\n{spec}"),
        4: ("Procedure Settings", "Defaults written out."),
        5: ("Assumptions", "None."),
        6: ("Inputs", "All experiments."),
        7: ("Outputs", "a = 1."),
        8: ("Deviations", "None"),
        9: ("Verdict", "| Criterion ID | Measured | Threshold | Measured by | Result | Failure mode |\n"
                       "|---|---|---|---|---|---|\n"
            + "".join(f"| `{c}` | 0 | 0 | {measured} | {v} | none |\n" for c, v in zip(CRIT, verdict))),
        10: ("Reproduction", "request.json"),
    }
    out, n = [], 0
    for k in sorted(secs):
        if k == drop:
            continue
        n += 1
        out.append(f"## {n}. {secs[k][0]}\n\n{secs[k][1]}\n")
    return f"---\ndescription: fixture run\nstatus: draft\n---\n\n# RUN — {rid}\n\n**ID**: `{rid}`\n\n" + "\n".join(out)


def comp_md(cid, exps="e1, e2, e3, e4", cands=(A, B), rows=None, selected=A, pairs=((A, B, "closed by batch 2"),),
            columns=CRIT, supersedes="none", pairs_head="| Pair | Differing hypotheses (IDs) | Condition | Status |",
            dataset=DS) -> str:
    rows = rows if rows is not None else {A: ("pass", "pass", "pass"), B: ("pass", "pass", "fail")}
    cand = "".join(f"| `{r}` | {r} | 1 | starting candidate | — |\n" for r in cands)
    vec = "".join(f"| `{r}` | " + " | ".join(v) + " |\n" for r, v in rows.items())
    if pairs:
        sep = "|" + "---|" * (pairs_head.count("|") - 1)
        pair_rows = "".join(f"| `{a}` vs `{b}` | H | x > 5 | {s} |\n" if "Status" in pairs_head
                            else f"| `{a}` vs `{b}` | H | x > 5 |\n" for a, b, s in pairs)
        open_pairs = f"{pairs_head}\n{sep}\n{pair_rows}"
    else:
        open_pairs = "None"
    sel = f"**Selected**: `{selected}`" if selected and selected.startswith("cpt-") else f"**Selected**: {selected}"
    return ("---\ndescription: fixture comparison\nstatus: draft\n---\n\n"
            f"# COMPARISON — {cid}\n\n**ID**: `{cid}`\n\n"
            f"## 1. Snapshot\n\n**Dataset**: `{dataset}`\n\n**Experiments**: {exps}\n\n**Supersedes**: {supersedes}\n\n"
            "## 2. Candidates\n\n| RUN ID | Candidate | Free parameters | Extends (nested RUN) | Hypotheses it adds (IDs) |\n"
            f"|---|---|---|---|---|\n{cand}\n"
            "## 3. Criterion Vectors\n\n| RUN ID | " + " | ".join(f"`{c}`" for c in columns) + " |\n"
            "|---|" + "---|" * len(columns) + f"\n{vec}\n"
            "## 4. Pairwise Dominance\n\nA dominates B.\n\n"
            f"## 5. Selection\n\n{sel}\n\nFewer parameters.\n\n"
            f"## 6. Open Pairs\n\n{open_pairs}\n\n"
            "## 7. Hypothesis Status Updates\n\nunchanged\n\n## 8. Approval\n\nT, 2026-10-02\n")


class Workspace(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)
        (self.td / "runs").mkdir()
        (self.td / "comparisons").mkdir()
        self.put("PLAN.md", plan_md())
        self.put("DATASET.md", dataset_md())
        self.put("acquisitions.jsonl", source_jsonl())
        self.put("submission.txt", SUBMISSION)
        self.put("runs/a0.md", run_md(A0, exps="e1, e2"))
        self.put("runs/a.md", run_md(A))
        self.put("runs/b.md", run_md(B, structure="two-site", spec=SPEC_B, verdict=("pass", "pass", "fail")))
        self.put("comparisons/c1.md", comp_md("cpt-t-comparison-c1", exps="e1, e2", cands=(A0,),
                                              rows={A0: ("pass", "pass", "pass")}, selected=A0, pairs=()))
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2"))

    def tearDown(self):
        self._td.cleanup()

    def put(self, name, text):
        p = self.td / name
        p.write_text(text, encoding="utf-8")
        return p

    def args(self, budget="3", source=True, **over):
        o = {"--plan": "PLAN.md", "--dataset": "DATASET.md", "--runs": "runs", "--comparisons": "comparisons",
             "--submission": "submission.txt", "--source": "acquisitions.jsonl" if source else None,
             "--budget-left": budget, **over}
        out = []
        for k, v in o.items():
            if v is not None:
                out += [k, v if k == "--budget-left" else str(self.td / v)]
        return out

    def gate(self, *extra, **kw):
        r = subprocess.run([sys.executable, str(GATE)] + self.args(**kw) + list(extra), capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def rules(self, out):
        return {ln[1:3] for ln in out.splitlines() if ln.startswith("[R")}

    def assertFails(self, rule, needle=None, **kw):
        code, out = self.gate(**kw)
        self.assertEqual(code, 1, out)
        self.assertEqual(self.rules(out), {rule}, out)
        if needle:
            self.assertIn(needle, out)
        return out


class TestPass(Workspace):
    def test_honest_workspace_passes(self):
        code, out = self.gate()
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "PASS")

    def test_without_source_reads_dataset_experiments(self):
        code, out = self.gate(source=False)
        self.assertEqual(code, 0, out)

    def test_ranges_and_abbreviations(self):
        self.put("runs/a.md", run_md(A, exps="e1–e4", verdict=("p", "P", "pass")))
        self.put("runs/b.md", run_md(B, exps="e1..e4", structure="two-site", spec=SPEC_B, verdict=("p", "p", "F")))
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", exps="e1–e4",
                                              rows={A: ("p", "p", "p"), B: ("pass", "pass", "fail")}))
        code, out = self.gate()
        self.assertEqual(code, 0, out)

    def test_names(self):
        self.assertEqual(result_gate.names("`e1`, e2–e4; x07..x09, b-1"),
                         ["e1", "e2", "e3", "e4", "x07", "x08", "x09", "b-1"])


class TestR1Snapshot(Workspace):
    def test_only_an_older_snapshot_fails_r1(self):
        (self.td / "comparisons/c2.md").unlink()
        out = self.assertFails("R1", "no COMPARISON is on the final snapshot (4 experiments in --source acquisitions.jsonl)")
        self.assertIn("the closest, c1.md, misses e3, e4", out)
        self.assertIn("note: R2-R5 not evaluated", out)

    def test_new_batch_after_the_comparison_fails_r1(self):
        self.put("acquisitions.jsonl", source_jsonl((("e1", "e2"), ("e3", "e4"), ("e5",))))
        self.assertFails("R1", "the closest, c2.md, misses e5")

    def test_comparison_lists_an_experiment_never_acquired_fails_r1(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", exps="e1, e2, e3, e4, e9"))
        self.assertFails("R1", "lists e9, never acquired")

    def test_other_dataset_fails_r1(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", dataset="cpt-t-dataset-other"))
        self.assertFails("R1", "names DATASET cpt-t-dataset-other, not cpt-t-dataset-x")

    def test_no_comparison_at_all_fails_r1_not_usage(self):
        for f in (self.td / "comparisons").iterdir():
            f.unlink()
        out = self.assertFails("R1", "no COMPARISON in")
        self.assertIn("R2-R5 not evaluated", out)

    def test_no_runs_and_no_comparisons_directories_fail(self):
        code, out = self.gate(**{"--runs": "nope-runs", "--comparisons": "nope-comparisons"})
        self.assertEqual(code, 1, out)
        self.assertIn("[R1] no COMPARISON in", out)

    def test_two_comparisons_on_the_final_snapshot_fail_r1_unless_superseded(self):
        self.put("comparisons/c3.md", comp_md("cpt-t-comparison-c3"))
        self.assertFails("R1", "2 COMPARISONs on the final snapshot (c2.md, c3.md)")
        self.put("comparisons/c3.md", comp_md("cpt-t-comparison-c3", supersedes="`cpt-t-comparison-c2`"))
        self.assertEqual(self.gate()[0], 0)

    def test_missing_snapshot_lines_fail_r1(self):
        text = comp_md("cpt-t-comparison-c2").replace("**Experiments**: e1, e2, e3, e4\n", "")
        self.put("comparisons/c2.md", text)
        self.assertFails("R1", "c2.md: section 1 needs `**Dataset**:")


class TestR2Alternatives(Workspace):
    def test_single_candidate_fails_r2(self):
        (self.td / "runs/b.md").unlink()
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", cands=(A,), rows={A: ("pass",) * 3}, pairs=()))
        out = self.assertFails("R2", "1 candidate(s) in section 2")
        self.assertNotIn("[R5]", out)

    def test_parameter_variant_is_not_an_alternative(self):
        self.put("runs/b.md", run_md(B, structure="Single-site", spec=SPEC_A.replace("[0, 10]", "[0, 100]"),
                                     verdict=("pass", "pass", "fail")))
        self.assertFails("R2", "all 2 candidates have the structure `single-site`")

    def test_relabelled_identical_spec_fails_r2(self):
        self.put("runs/b.md", run_md(B, structure="two-site", spec=SPEC_A, verdict=("pass", "pass", "fail")))
        out = self.assertFails("R2", f"{B} and {A} declare different structures but have the same Candidate Spec")
        self.assertIn("all 2 candidates have the structure", out)

    def test_missing_structure_fails_r2(self):
        self.put("runs/b.md", run_md(B, structure=None, spec=SPEC_B, verdict=("pass", "pass", "fail")))
        self.assertFails("R2", "b.md: section 3 has no `**Structure**:` line")

    def test_unlisted_run_on_the_snapshot_fails_r2(self):
        self.put("runs/c.md", run_md("cpt-t-run-c", structure="three-site", spec="y = a x + b x^2 + c x^3"))
        self.assertFails("R2", "RUN cpt-t-run-c is on this snapshot and is not listed in section 2")

    def test_candidate_on_an_older_snapshot_fails_r2(self):
        self.put("runs/b.md", run_md(B, exps="e1, e2", structure="two-site", spec=SPEC_B, verdict=("pass", "pass", "fail")))
        self.assertFails("R2", f"candidate {B} is not on this snapshot (misses e3, e4)")

    def test_candidate_without_run_file_fails_r2(self):
        (self.td / "runs/b.md").unlink()
        out = self.gate()[1]
        self.assertIn(f"[R2] c2.md: candidate {B} has no RUN file", out)


class TestR3Vectors(Workspace):
    def test_vector_not_copied_fails_r3(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2",
                                              rows={A: ("pass",) * 3, B: ("pass", "pass", "pass")},
                                              pairs=((A, B, "closed by batch 2"),)))
        self.assertFails("R3", f"{B} × cpt-t-criterion-parsimony is `pass`, the RUN's Verdict says `fail`")

    def test_columns_out_of_plan_order_fail_r3(self):
        cols = [CRIT[1], CRIT[0], CRIT[2]]
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", columns=cols))
        self.assertFails("R3", "the PLAN's criteria in order are")

    def test_run_verdict_with_a_dropped_row_fails_r3(self):
        text = run_md(B, structure="two-site", spec=SPEC_B, verdict=("pass", "pass", "fail"))
        self.put("runs/b.md", text.replace(f"| `{CRIT[0]}` | 0 | 0 | mechanical | pass | none |\n", ""))
        self.assertIn("RUN rule 7", self.assertFails("R3"))

    def test_candidate_without_a_row_fails_r3(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", rows={A: ("pass",) * 3}))
        self.assertFails("R3", f"candidate {B} has no row in section 3")


class TestR4Submission(Workspace):
    def test_submission_is_not_the_selected_candidate(self):
        self.put("submission.txt", SUBMISSION + "edited after the RUN\n")
        self.assertFails("R4", "the submitted file is not the selected candidate")

    def test_nothing_selected_fails_r4(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", selected="none"))
        self.assertFails("R4", "nothing is selected (`none`)")

    def test_missing_selected_line_fails_r4(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2").replace(f"**Selected**: `{A}`", "A wins."))
        self.assertFails("R4", "section 5 has no `**Selected**:")

    def test_selected_candidate_that_fails_a_gate_and_is_dominated(self):
        self.put("runs/b.md", run_md(B, structure="two-site", spec=SPEC_B, verdict=("pass", "pass", "fail"),
                                     cand_sha=sha(SUBMISSION)))
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", selected=B))
        out = self.assertFails("R4", f"selected {B} fails mechanical rows (cpt-t-criterion-parsimony)")
        self.assertIn(f"selected {B} is dominated by {A}", out)

    def test_selected_with_not_evaluated_row_fails_r4(self):
        self.put("runs/a.md", run_md(A, verdict=("pass", "pass", "not evaluated"), measured="judged by: T"))
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2",
                                              rows={A: ("pass", "pass", "n/e"), B: ("pass", "pass", "fail")}))
        self.assertFails("R4", "has `not evaluated` rows (cpt-t-criterion-parsimony)")

    def test_missing_candidate_hash_fails_r4(self):
        self.put("runs/a.md", run_md(A).replace(f"**Candidate sha256**: `{sha(SUBMISSION)}`", "**Candidate sha256**: tbd"))
        self.assertFails("R4", "a.md: section 3 has no `**Candidate sha256**:` of 64 hex digits")


class TestR5Stopping(Workspace):
    """The stopping rule: an open pair blocks a result while budget remains."""

    def with_status(self, status):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", pairs=((A, B, status),)))

    def test_open_pair_with_budget_left_fails_r5(self):
        self.with_status("open")
        self.assertFails("R5", f"pair {A} vs {B} is open and 3 batch(es) remain: run the batch that separates it")

    def test_open_pair_with_budget_spent_passes_with_a_note(self):
        self.with_status("open")
        code, out = self.gate(budget="0")
        self.assertEqual(code, 0, out)
        self.assertIn(f"note: pair {A} vs {B} stays open; the budget is spent", out)

    def test_open_pair_without_budget_left_fails_closed(self):
        self.with_status("open")
        self.assertFails("R5", "the remaining budget is unknown; pass --budget-left", budget=None)

    def test_unresolvable_with_a_reason_passes_with_budget_left(self):
        self.with_status("unresolvable: the separating condition x > 50 lies outside the allowed range x ≤ 10")
        code, out = self.gate(budget="3")
        self.assertEqual(code, 0, out)

    def test_unresolvable_without_a_reason_fails_r5(self):
        self.with_status("unresolvable:")
        self.assertFails("R5", "is `unresolvable` without a reason")

    def test_fewer_experiments_is_not_a_reason(self):
        for why in ("finished with fewer experiments", "to save budget", "saving the remaining batches"):
            self.with_status(f"unresolvable: {why}")
            self.assertFails("R5", "is not a reason; fewer experiments is never a reason")

    def test_closed_by_a_batch_not_designed_to_separate_fails_r5(self):
        self.with_status("closed by batch 1")
        self.assertFails("R5", "closed by batch 1, whose Justification has no `information →` target")

    def test_closed_by_an_unknown_batch_fails_r5(self):
        self.with_status("closed by batch 9")
        self.assertFails("R5", "closed by batch 9, which is not a batch of DATASET section 6")

    def test_unknown_status_fails_r5(self):
        self.with_status("probably fine")
        self.assertFails("R5", "has status `probably fine`")

    def test_missing_status_column_fails_r5(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", pairs_head="| Pair | Differing hypotheses (IDs) | Condition |"))
        self.assertFails("R5", "section 6 table has no Status column")

    def test_rival_not_dominated_must_be_listed(self):
        self.put("runs/b.md", run_md(B, structure="two-site", spec=SPEC_B))
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", rows={A: ("pass",) * 3, B: ("pass",) * 3},
                                              pairs=()))
        self.assertFails("R5", f"{B} is not dominated by the selected {A} and the pair is not in section 6")

    def test_dominated_rival_needs_no_pair(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", pairs=()))
        self.assertEqual(self.gate()[0], 0)


class TestR6Structure(Workspace):
    def test_missing_section_fails_r6(self):
        self.put("runs/b.md", run_md(B, structure="two-site", spec=SPEC_B, verdict=("pass", "pass", "fail"), drop=8))
        self.assertFails("R6", "b.md: required section `Deviations` is missing")

    def test_duplicate_id_fails_r6(self):
        self.put("runs/a0.md", run_md(A, exps="e1, e2"))
        out = self.gate()[1]
        self.assertIn("[R6] a0.md: ID cpt-t-run-a is also the ID of", out)

    def test_old_files_are_checked_too(self):
        self.put("comparisons/c1.md", comp_md("cpt-t-comparison-c1", exps="e1, e2", cands=(A0,),
                                              rows={A0: ("pass",) * 3}, selected=A0, pairs=())
                 .replace("## 7. Hypothesis Status Updates", "## 8. Hypothesis Status Updates"))
        self.assertFails("R6", "c1.md: numbered sections are [1, 2, 3, 4, 5, 6, 8, 8]")

    def test_structure_matches_the_constraints(self):
        cons = result_gate.load_constraints()
        self.assertEqual([c["pattern"] for c in cons["RUN"] if "pattern" in c][:3],
                         ["Unit", "Procedure", "Candidate Spec"])
        self.assertIn("Open Pairs", [c.get("pattern") for c in cons["COMPARISON"]])


class TestUsage(Workspace):
    def test_usage_errors_exit_2(self):
        self.assertEqual(self.gate(**{"--submission": "nope.txt"})[0], 2)
        self.assertEqual(self.gate(budget="-1")[0], 2)
        self.assertEqual(self.gate(budget="two")[0], 2)
        self.assertEqual(self.gate("--bogus", "x")[0], 2)
        self.assertEqual(self.gate(**{"--plan": None})[0], 2)
        self.assertEqual(self.gate(**{"--source": "nope.jsonl"})[0], 2)

    def test_unnamed_source_points_exit_2(self):
        self.put("acquisitions.jsonl", json.dumps({"time": "2026-10-01T09:00:00+00:00", "points": [{"x": 1.0}]}) + "\n")
        code, out = self.gate()
        self.assertEqual(code, 2)
        self.assertIn("have no name", out)

    def test_missing_plan_and_dataset_are_violations(self):
        code, out = self.gate(**{"--plan": "nope-PLAN.md", "--dataset": "nope-DATASET.md"}, source=True)
        self.assertEqual(code, 1, out)
        self.assertIn("[R3] PLAN", out)
        self.assertIn("[R1] DATASET", out)


class TestHookWitnessAsSource(Workspace):
    """The full PASS workspace with the acquisitions source written by `design_log.py hook`
    from unnamed tool inputs, as a harness that follows the kit produces it."""
    BATCHES = (("1", {"e1": {"x": 0.0}, "e2": {"x": 1.0}}, "variance → a"),
               ("2", {"e3": {"x": 2.0}, "e4": {"x": 3.0}}, f"information → cpt-t-comparison-c1 pair {A0} vs alternative"))

    def setUp(self):
        super().setUp()
        self.log, self.wit = self.td / "design_log.jsonl", self.td / "design_witness.jsonl"
        for batch, pts, just in self.BATCHES:
            design_log.append_entry(self.log, batch, "P", pts, just, "manual: test")
            unnamed = [dict(c) for c in reversed(list(pts.values()))]          # a plain list, any order
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "design_log.py"), "hook", "--log",
                                str(self.log), "--witness", str(self.wit), "--points", json.dumps(unnamed),
                                "--tool", "simulate"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        (self.td / "acquisitions.jsonl").unlink()                              # only the witness remains

    def old_witness(self):
        """The same witness as written before kit 0.4.1: no names."""
        lines = []
        for ln in self.wit.read_text().splitlines():
            w = json.loads(ln)
            w["points"] = [{"name": None, "conditions": q["conditions"]} for q in w["points"]]
            lines.append(json.dumps(w))
        return self.put("old_witness.jsonl", "\n".join(lines) + "\n")

    def test_witness_names_the_registered_points(self):
        names = [q["name"] for ln in self.wit.read_text().splitlines() for q in json.loads(ln)["points"]]
        self.assertEqual(names, ["e2", "e1", "e4", "e3"])

    def test_result_gate_accepts_the_hook_witness(self):
        code, out = self.gate(**{"--source": "design_witness.jsonl"})
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "PASS")

    def test_hook_witness_still_catches_a_new_batch(self):
        design_log.append_entry(self.log, "3", "P", {"e5": {"x": 4.0}}, "boundary → x range", "manual: test")
        design_log.admit(self.log, self.wit, [{"x": 4.0}], "simulate")
        code, out = self.gate(**{"--source": "design_witness.jsonl"})
        self.assertEqual(code, 1, out)
        self.assertIn("the closest, c2.md, misses e5", out)

    def test_old_unnamed_witness_needs_the_design_log(self):
        self.old_witness()
        code, out = self.gate(**{"--source": "old_witness.jsonl"})
        self.assertEqual(code, 2)
        self.assertIn("pass --design-log", out)
        code, out = self.gate(**{"--source": "old_witness.jsonl", "--design-log": "design_log.jsonl"})
        self.assertEqual(code, 0, out)

    def test_old_witness_with_a_rewritten_log_is_refused(self):
        self.old_witness()
        lines = self.log.read_text().splitlines()
        e = json.loads(lines[0])
        e["points"][0]["name"] = "e9"
        lines[0] = json.dumps(e)
        self.log.write_text("\n".join(lines) + "\n")
        code, out = self.gate(**{"--source": "old_witness.jsonl", "--design-log": "design_log.jsonl"})
        self.assertEqual(code, 2)
        self.assertIn("not valid", out)

    def test_design_log_without_source_is_a_usage_error(self):
        self.assertEqual(self.gate(source=False, **{"--design-log": "design_log.jsonl"})[0], 2)


class TestHook(Workspace):
    def hook(self, **kw):
        wit = self.td / "result_witness.jsonl"
        err, out = io.StringIO(), io.StringIO()
        with redirect_stderr(err), redirect_stdout(out):
            code = result_gate.main(["hook", "--witness", str(wit)] + self.args(**kw))
        lines = wit.read_text().splitlines() if wit.exists() else []
        return code, out.getvalue(), err.getvalue(), [json.loads(x) for x in lines]

    def test_accepts_and_writes_a_pass_witness(self):
        code, out, err, wit = self.hook()
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), "PASS")
        self.assertEqual(len(wit), 1)
        w = wit[0]
        self.assertEqual((w["verdict"], w["violations"], w["gate"], w["version"]), ("PASS", [], "result_gate", "0.4.1"))
        self.assertEqual(w["submission_sha256"], sha(SUBMISSION))
        self.assertEqual((w["comparison"], w["selected"], w["budget_left"]), ("cpt-t-comparison-c2", A, 3))
        self.assertEqual(w["source_sha256"], hashlib.sha256((self.td / "acquisitions.jsonl").read_bytes()).hexdigest())
        self.assertEqual(w["gate_sha256"], hashlib.sha256(GATE.read_bytes()).hexdigest())
        self.assertTrue(w["time"].endswith("+00:00"))

    def test_refuses_an_open_pair_and_records_why(self):
        self.put("comparisons/c2.md", comp_md("cpt-t-comparison-c2", pairs=((A, B, "open"),)))
        code, out, err, wit = self.hook()
        self.assertEqual(code, 2)
        self.assertIn("result_gate hook: result refused: FAIL — 1 violation(s)", err)
        self.assertIn("[R5]", err)
        self.assertEqual(wit[0]["verdict"], "FAIL")
        self.assertEqual(len(wit[0]["violations"]), 1)
        self.assertTrue(wit[0]["violations"][0].startswith("[R5]"))

    def test_witness_is_appended_not_rewritten(self):
        self.hook()
        self.put("submission.txt", "something else\n")
        code, _, _, wit = self.hook()
        self.assertEqual(code, 2)
        self.assertEqual([w["verdict"] for w in wit], ["PASS", "FAIL"])
        self.assertEqual(wit[1]["submission_sha256"], sha("something else\n"))

    def test_unreadable_source_refuses_with_error(self):
        self.put("acquisitions.jsonl", "{not json\n")
        code, _, err, wit = self.hook()
        self.assertEqual(code, 2)
        self.assertEqual(wit[0]["verdict"], "ERROR")
        self.assertIn("not JSON", wit[0]["violations"][0])

    def test_usage_error_exits_1_and_writes_nothing(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(result_gate.main(["hook"] + self.args()), 1)               # no --witness
            self.assertEqual(result_gate.main(["hook", "--witness", str(self.td / "w.jsonl"), "--plan", "x"]), 1)
        self.assertFalse((self.td / "w.jsonl").exists())

    def test_hook_cli_exit_code(self):
        self.put("submission.txt", "not the candidate\n")
        r = subprocess.run([sys.executable, str(GATE), "hook", "--witness", str(self.td / "w.jsonl")] + self.args(),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("[R4]", r.stderr)


if __name__ == "__main__":
    unittest.main()
