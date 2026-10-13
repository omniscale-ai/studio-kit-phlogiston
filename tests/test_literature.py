#!/usr/bin/env python3
"""Tests for the literature block. Stdlib only, offline by default.

Run from the kit root:  python3 -m unittest discover -s tests -v

Network tests (real lit_run retrieval) run only with LIT_ONLINE=1.
"""
from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lit_common  # noqa: E402
import lit_gate  # noqa: E402
import lit_run  # noqa: E402

GATE = ROOT / "scripts" / "lit_gate.py"
RUN = ROOT / "scripts" / "lit_run.py"
EXAMPLE = ROOT / "artifacts" / "LITERATURE" / "examples" / "example-related-three-benchmarks.md"
FIX = ROOT / "tests" / "fixtures"
ALLOWED, BLIND, NONE = FIX / "plan-allowed.md", FIX / "plan-blind.md", FIX / "plan-none.md"

ONLINE = ("Gate, online: `python3 scripts/lit_gate.py x.md --plan PLAN.md --resolve`, "
          "run 2026-10-14: PASS; 32 DOIs looked up.")


def gate(path, plan=None, resolve=False):
    args = [sys.executable, str(GATE), str(path)]
    if plan:
        args += ["--plan", str(plan)]
    if resolve:
        args.append("--resolve")
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def example_text():
    return EXAMPLE.read_text(encoding="utf-8")


def blind_text(n=3):
    """The example turned into a blind-mode LITERATURE with n exclusions checked."""
    t = example_text()
    t = t.replace("- Literature mode: `allowed`, copied", "- Literature mode: `blind`, copied")
    t = t.replace("- Exclusions checked: not applicable.", f"- Exclusions checked: {n}")
    t = t.replace("- Removed by exclusion: not applicable.", "- Removed by exclusion: 0")
    return t


def plan_text(mode="blind", rows=(("Zyxwvut Quillfeather", "author"),), pid="cpt-ctank-plan-example"):
    body = "".join(f"| {i} | {t} | r |\n" for i, t in rows)
    table = "\n\n| Excluded item | Type | Reason |\n|---|---|---|\n" + body if rows else "none"
    return (f"# PLAN\n\n**ID**: `{pid}`\n\n## 2. Prior Knowledge\n\n**Literature mode**: `{mode}`\n\n"
            f"**Excluded**:{(' ' if not rows else '')}{table}\n\n**LITERATURE drawn on**: none\n")


class Scratch(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def lit(self, text, name="lit.md"):
        p = self.td / name
        p.write_text(text, encoding="utf-8")
        return p

    def plan(self, **kw):
        p = self.td / "plan.md"
        p.write_text(plan_text(**kw), encoding="utf-8")
        return p

    def assertFires(self, out, *rules):
        got = {r for r in ("L%d" % i for i in range(1, 12)) if f"[{r}]" in out}
        self.assertEqual(got, set(rules), out)


class TestShippedExample(unittest.TestCase):
    def test_example_passes_offline_with_plan(self):
        rc, out = gate(EXAMPLE, ALLOWED)
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.strip().endswith("PASS"))

    def test_example_passes_offline_without_plan(self):
        rc, out = gate(EXAMPLE)
        self.assertEqual(rc, 0, out)

    def test_example_is_draft_without_online_line(self):
        t = example_text()
        self.assertIn("status: draft", t)
        self.assertNotIn("Gate, online:", t)

    def test_example_vs_blind_plan_fails_only_on_mode(self):
        rc, out = gate(EXAMPLE, BLIND)
        self.assertEqual(rc, 1)
        self.assertNotIn("excluded hit", out)
        self.assertIn("Literature mode is 'allowed'", out)

    def test_example_vs_none_plan_fails(self):
        rc, out = gate(EXAMPLE, NONE)
        self.assertEqual(rc, 1)
        self.assertIn("`none`", out)

    def test_usage_exit_2(self):
        self.assertEqual(gate(ROOT / "nope.md")[0], 2)
        r = subprocess.run([sys.executable, str(GATE)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class TestPlantedErrors(Scratch):
    def test_planted_errors_fire_exactly_l4_l5_l6(self):
        t = example_text()
        t = t.replace("| 8 | — | — | assumed |", "| 8 | — | — | verified |")          # L4
        t = t.replace("[10]", "[99]")                                                 # L5
        t = t.replace("none — the Set is consistent on the anchor's question.",
                      "| candidate | claims | proposed diagnostic condition | status |\n"
                      "|-----------|--------|-------------------------------|--------|\n"
                      "| an extra mechanism | — | some condition | NOT YET TESTED |")  # L6
        rc, out = gate(self.lit(t))
        self.assertEqual(rc, 1)
        self.assertFires(out, "L4", "L5", "L6")

    def test_low_collection_coverage_fails_l7(self):
        t = example_text().replace("## 4. Collection\n\nnot used",
                                   "## 4. Collection\n\nCollection `c-1` holds 5 of 36 approved papers.")
        rc, out = gate(self.lit(t))
        self.assertEqual(rc, 1)
        self.assertFires(out, "L7")

    def test_half_coverage_passes_l7(self):
        t = example_text().replace("## 4. Collection\n\nnot used",
                                   "## 4. Collection\n\nCollection `c-1` holds 18 of 36 approved papers.")
        self.assertEqual(gate(self.lit(t))[0], 0)

    def test_unapproved_set_fails_l2(self):
        t = example_text().replace("- Approved by: A. Shumilov, 2026-10-12", "- Approved by: {person, YYYY-MM-DD}")
        self.assertFires(gate(self.lit(t))[1], "L2")

    def test_two_strategies_fail_l1(self):
        t = example_text().replace("- Strategy: `related`", "- Strategy: `related` `review`")
        self.assertFires(gate(self.lit(t))[1], "L1")

    def test_bad_resolved_vocabulary_fails_l3(self):
        t = example_text().replace("| reference | 2674 | yes |", "| reference | 2674 | maybe |")
        self.assertFires(gate(self.lit(t))[1], "L3")

    def test_no_doi_without_mark_fails_l3(self):
        t = example_text().replace("| reference | 1096 | no DOI |", "| reference | 1096 | yes |")
        self.assertIn("[L3]", gate(self.lit(t))[1])

    def test_ran_without_query_fails_l8(self):
        t = example_text()
        t = t.replace("| OpenAlex | yes | https://api.openalex.org/works/https://doi.org/10.1016/j.ifacol.2017.08.071?select=",
                      "| OpenAlex | yes | — | x | y | ?select=", 1)
        self.assertIn("[L8]", gate(self.lit(t))[1])

    def test_unresolved_row_with_verified_claim_fails_l4(self):
        t = example_text().replace("| reference | 743 | yes |", "| reference | 743 | unresolved |")
        rc, out = gate(self.lit(t))
        self.assertEqual(rc, 1)
        self.assertFires(out, "L4")

    def test_unresolved_row_with_assumed_claim_passes(self):
        t = example_text().replace("| reference | 279 | yes |", "| reference | 279 | unresolved |")
        self.assertEqual(gate(self.lit(t))[0], 0)

    def test_no_doi_row_with_verified_claim_fails_l4(self):
        t = example_text().replace("| 3 | 10.1007/s11831-009-9031-8 | 2009 |", "| 3 | — | 2009 |") \
                          .replace("| reference | 743 | yes |", "| reference | 743 | no DOI |")
        self.assertFires(gate(self.lit(t))[1], "L4")

    def test_scout_value_without_passage_fails_l10(self):
        t = example_text().replace("- Strategy: `related`", "- Strategy: `scout`")
        p = self.lit(t, "scout.md")
        (self.td / "scout.csv").write_text("set_no,paper,doi,link,what_measured,how_measured,constraints,value,unit,passage\n"
                                           "1,P,10.1/x,,k,m,c,3.2,s,\n", encoding="utf-8")
        self.assertIn("[L10]", gate(p)[1])
        (self.td / "scout.csv").write_text("set_no,paper,doi,link,what_measured,how_measured,constraints,value,unit,passage\n"
                                           "1,P,10.1/x,,k,m,c,3.2,s,\"it was 3.2 s\"\n", encoding="utf-8")
        self.assertNotIn("[L10]", gate(p)[1])


class TestL9(Scratch):
    def verified(self, online=True):
        t = example_text().replace("status: draft", "status: verified")
        if online:
            t = t.rstrip("\n") + "\n- " + ONLINE + "\n"
        return t

    def test_verified_with_online_attestation_passes(self):
        rc, out = gate(self.lit(self.verified()), ALLOWED)
        self.assertEqual(rc, 0, out)

    def test_verified_without_online_attestation_fails_l9(self):
        rc, out = gate(self.lit(self.verified(online=False)), ALLOWED)
        self.assertEqual(rc, 1)
        self.assertFires(out, "L9")

    def test_verified_with_offline_only_line_fails_l9(self):
        t = self.verified(online=False)
        rc, out = gate(self.lit(t), ALLOWED)
        self.assertIn("Gate, offline:", t)
        self.assertFires(out, "L9")

    def test_online_line_missing_plan_flag_fails_l9(self):
        t = self.verified(online=False).rstrip("\n") + "\n- Gate, online: `python3 scripts/lit_gate.py x.md --resolve`, run 2026-10-14: PASS\n"
        self.assertFires(gate(self.lit(t), ALLOWED)[1], "L9")

    def test_online_line_with_fail_result_fails_l9(self):
        t = self.verified(online=False).rstrip("\n") + "\n- Gate, online: `python3 scripts/lit_gate.py x.md --plan P.md --resolve`, run 2026-10-14: FAIL\n"
        self.assertFires(gate(self.lit(t), ALLOWED)[1], "L9")

    def test_verified_with_other_failure_fails_l9_too(self):
        t = self.verified().replace("[10]", "[99]")
        rc, out = gate(self.lit(t), ALLOWED)
        self.assertEqual(rc, 1)
        self.assertFires(out, "L5", "L9")


class TestL11(Scratch):
    def test_blind_clean_passes(self):
        rc, out = gate(self.lit(blind_text()), BLIND)
        self.assertEqual(rc, 0, out)

    def test_blind_count_mismatch_fails(self):
        for n in (2, 4):
            rc, out = gate(self.lit(blind_text(n)), BLIND)
            self.assertEqual(rc, 1)
            self.assertFires(out, "L11")
            self.assertIn("Exclusions checked", out)

    def test_blind_without_plan_fails(self):
        rc, out = gate(self.lit(blind_text()))
        self.assertEqual(rc, 1)
        self.assertFires(out, "L11")

    def test_plan_mode_none_fails(self):
        rc, out = gate(self.lit(example_text()), NONE)
        self.assertEqual(rc, 1)
        self.assertFires(out, "L11")

    def test_plan_id_mismatch_fails(self):
        rc, out = gate(self.lit(example_text()), self.plan(mode="allowed", rows=(), pid="cpt-other-plan-x"))
        self.assertEqual(rc, 1)
        self.assertFires(out, "L11")
        self.assertIn("ID", out)

    def test_plan_mode_mismatch_fails(self):
        rc, out = gate(self.lit(example_text()), BLIND)
        self.assertEqual(rc, 1)
        self.assertFires(out, "L11")

    def test_blind_with_empty_excluded_fails(self):
        rc, out = gate(self.lit(blind_text(0)), self.plan(rows=()))
        self.assertEqual(rc, 1)
        self.assertFires(out, "L11")

    def hit(self, item, typ, count=1):
        return gate(self.lit(blind_text(count)), self.plan(rows=((item, typ),)))

    def test_hit_in_set_title_fails_without_naming_text(self):
        rc, out = self.hit("Bouc-Wen Model, a Survey", "title")
        self.assertEqual(rc, 1)
        self.assertFires(out, "L11")
        self.assertIn("Set row 3", out)
        self.assertNotIn("Bouc-Wen Model", out)

    def test_hit_case_insensitive_term(self):
        rc, out = self.hit("HAMMERSTEIN", "term")
        self.assertEqual(rc, 1)
        self.assertIn("[L11]", out)

    def test_hit_doi_cell_with_prefix_and_case(self):
        rc, out = self.hit("https://doi.org/10.1007/S11831-009-9031-8", "doi")
        self.assertEqual(rc, 1)
        self.assertIn("Set row 3", out)

    def test_doi_is_exact_not_substring(self):
        rc, out = self.hit("10.1007/s11831", "doi")
        self.assertEqual(rc, 0, out)

    def test_hit_oa_link(self):
        rc, out = self.hit("eprints.lancs.ac.uk", "benchmark")
        self.assertEqual(rc, 1)
        self.assertIn("Set row 34", out)

    def test_hit_in_analysis_only(self):
        # present in Analysis, absent from every Set cell: row 1 title carries "random vibration"; use a Request-free phrase
        t = blind_text(1).replace("What the anchor adds is not a method", "A Zyxwvut Quillfeather note: what the anchor adds is not a method")
        rc, out = gate(self.lit(t), self.plan())
        self.assertEqual(rc, 1)
        self.assertIn("Analysis", out)

    def test_hit_in_claims(self):
        t = blind_text(1).replace("\"The Hysteresis Bouc-Wen Model, a Survey\"", "\"Zyxwvut Quillfeather survey\"")
        rc, out = gate(self.lit(t), self.plan())
        self.assertEqual(rc, 1)
        self.assertIn("Claims", out)

    def test_hit_in_request(self):
        t = blind_text(1).replace("- Output shape: reading list.", "- Output shape: reading list on Zyxwvut Quillfeather.")
        rc, out = gate(self.lit(t), self.plan())
        self.assertEqual(rc, 1)
        self.assertIn("Request", out)

    def test_hit_in_sources_query_decoded(self):
        t = blind_text(1)
        t = t.replace("?select=id%2Cdoi", "?search=Zyxwvut%20Quillfeather&select=id%2Cdoi", 1)
        rc, out = gate(self.lit(t), self.plan())
        self.assertEqual(rc, 1)
        self.assertIn("Sources query", out)

    def test_doi_item_in_query_substring(self):
        rc, out = self.hit("10.1016/j.ifacol.2017.08.071", "doi")
        self.assertEqual(rc, 1)   # the anchor DOI is in the Request and in the query

    def test_offline_does_not_clear_author_items(self):
        rc, out = self.hit("Ljung", "author")
        self.assertEqual(rc, 0, out)

    def test_three_rows_none_hit_passes(self):
        rows = (("Zyxwvut Quillfeather", "author"), ("zeolite", "term"), ("10.9999/x", "doi"))
        rc, out = gate(self.lit(blind_text(3)), self.plan(rows=rows))
        self.assertEqual(rc, 0, out)


class TestResolve(Scratch):
    def run_gate(self, text, plan, resolver):
        p = self.lit(text)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        args = [str(p), "--resolve"] + (["--plan", str(plan)] if plan else [])
        with redirect_stdout(buf):
            rc = lit_gate.main(args, resolver=resolver)
        return rc, buf.getvalue()

    def test_all_resolve_passes_and_counts_lookups(self):
        calls = []

        def ok(doi):
            calls.append(doi)
            return {"authors": ["A. Person"], "venue": "Some Journal"}
        rc, out = self.run_gate(example_text(), ALLOWED, ok)
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(calls), 32)

    def test_unresolvable_doi_fails_l3(self):
        rc, out = self.run_gate(example_text(), ALLOWED,
                                lambda d: None if d == "10.1007/s11831-009-9031-8" else {"authors": [], "venue": ""})
        self.assertEqual(rc, 1)
        self.assertIn("[L3]", out)
        self.assertIn("rows 3", out)

    def test_unresolvable_but_marked_unresolved_passes(self):
        t = example_text().replace("| reference | 279 | yes |", "| reference | 279 | unresolved |")
        rc, out = self.run_gate(t, ALLOWED, lambda d: None if d == "10.1016/j.automatica.2010.01.001" else {"authors": [], "venue": ""})
        self.assertEqual(rc, 0, out)

    def test_blind_author_hit_only_with_resolve(self):
        plan = self.plan(rows=(("Zyxwvut Quillfeather", "author"),))
        rec = lambda d: {"authors": ["Dr. Zyxwvut Quillfeather"] if d.endswith("s11831-009-9031-8") else ["X"], "venue": "V"}
        rc, out = self.run_gate(blind_text(1), plan, rec)
        self.assertEqual(rc, 1)
        self.assertIn("authors or venue of Set row 3", out)
        self.assertNotIn("Quillfeather", out)
        self.assertEqual(gate(self.lit(blind_text(1)), plan)[0], 0)   # offline: not seen

    def test_blind_venue_hit(self):
        plan = self.plan(rows=(("Secret Journal", "term"),))
        rec = lambda d: {"authors": [], "venue": "The Secret Journal of X" if d.endswith("0002106") else ""}
        rc, out = self.run_gate(blind_text(1), plan, rec)
        self.assertEqual(rc, 1)
        self.assertIn("Set row 1", out)

    def test_blind_clean_resolve_passes(self):
        rc, out = self.run_gate(blind_text(3), BLIND, lambda d: {"authors": ["A"], "venue": "V"})
        self.assertEqual(rc, 0, out)


class TestLitRunOffline(Scratch):
    def run_cli(self, *args):
        r = subprocess.run([sys.executable, str(RUN), *args], capture_output=True, text=True, cwd=self.td)
        return r.returncode, r.stdout + r.stderr

    def test_plan_mode_none_exits_2_and_writes_nothing(self):
        out_dir = self.td / "out"
        rc, out = self.run_cli("scout", "fake subject", "--system", "t", "--plan", str(NONE), "--out", str(out_dir))
        self.assertEqual(rc, 2, out)
        self.assertIn("none", out)
        self.assertFalse(out_dir.exists())

    def test_check_plan_function(self):
        plan, err = lit_run.check_plan(NONE, "x")
        self.assertIsNone(plan)
        self.assertIn("none", err)
        plan, err = lit_run.check_plan(ALLOWED, "x")
        self.assertIsNone(err)
        self.assertEqual(plan["mode"], "allowed")

    def test_anchor_matching_exclusion_refused(self):
        plan = self.plan(rows=(("10.9999/target.paper.2099", "doi"),))
        out_dir = self.td / "out"
        rc, out = self.run_cli("related", "https://doi.org/10.9999/TARGET.paper.2099", "--system", "t",
                               "--plan", str(plan), "--out", str(out_dir))
        self.assertEqual(rc, 2, out)
        self.assertIn("refused", out)
        self.assertFalse(out_dir.exists())

    def test_subject_matching_exclusion_refused(self):
        plan = self.plan(rows=(("tennessee eastman", "benchmark"),))
        rc, out = self.run_cli("review", "Tennessee Eastman process control", "--system", "t", "--plan", str(plan))
        self.assertEqual(rc, 2, out)

    def test_blind_plan_with_empty_excluded_refused(self):
        rc, out = self.run_cli("review", "anything", "--system", "t", "--plan", str(self.plan(rows=())))
        self.assertEqual(rc, 2, out)

    def test_missing_plan_file_exits_2(self):
        self.assertEqual(self.run_cli("review", "x", "--system", "t", "--plan", str(self.td / "none.md"))[0], 2)

    def fake_works(self):
        def w(i, doi, title, auth="Someone", venue="Jrnl"):
            return {"id": f"https://openalex.org/W{i}", "doi": f"https://doi.org/{doi}" if doi else None, "title": title,
                    "publication_year": 2020, "cited_by_count": i,
                    "authorships": [{"author": {"display_name": auth}}],
                    "primary_location": {"source": {"display_name": venue}}, "best_oa_location": None}
        return [(w(1, "10.1/a", "Plain paper"), "reference"),
                (w(2, "10.9999/target.paper.2099", "Other title"), "reference"),
                (w(3, "10.1/c", "Tennessee Eastman revisited"), "citer"),
                (w(4, "10.1/d", "Fine paper", auth="Zyxwvut Quillfeather"), "related"),
                (w(5, None, "Fine no-doi paper", venue="Fine"), "related")]

    def test_apply_exclusion_drops_and_counts(self):
        plan = lit_common.load_plan(BLIND)
        kept, removed = lit_run.apply_exclusion(self.fake_works(), plan["excluded"])
        self.assertEqual(removed, 3)
        self.assertEqual([w["id"][-1] for w, _ in kept], ["1", "5"])

    def test_written_blind_artifact_passes_gate_up_to_approval(self):
        plan = lit_common.load_plan(BLIND)
        rows, removed = lit_run.apply_exclusion(self.fake_works(), plan["excluded"])
        lit_run.budget["queries"] = ["https://api.openalex.org/works?search=fake"]
        import argparse
        a = argparse.Namespace(since=None, quantity="", unit="", depth="quick", output="reading list", n=20)
        path = lit_run.write_artifact("review", "fake subject", "ctank", rows, {"n_total": 5, "counts": {}, "groups": []},
                                      a, self.td / "out", plan, removed, argv=["lit_run.py", "review", "fake subject"])
        text = path.read_text(encoding="utf-8")
        self.assertIn("- Removed by exclusion: 3", text)
        self.assertIn("- Exclusions checked: 3", text)
        self.assertIn("- PLAN: `cpt-ctank-plan-example`", text)
        self.assertNotIn("Tennessee", text)
        rc, out = gate(path, BLIND)
        self.assertEqual(rc, 1)
        self.assertFires(out, "L2", "L6")    # the approval and the agent's section 7 are still open
        self.assertFalse(list(path.parent.glob("*.csv")))

    def test_written_artifact_without_plan_leaves_agent_lines_open(self):
        import argparse
        a = argparse.Namespace(since=None, quantity="", unit="", depth="quick", output="reading list", n=20)
        path = lit_run.write_artifact("review", "fake subject", "ctank", self.fake_works(),
                                      {"n_total": 5, "counts": {}, "groups": []}, a, self.td / "out", None, 0)
        text = path.read_text(encoding="utf-8")
        self.assertIn("- Literature mode: {", text)
        self.assertIn("- Removed by exclusion: {", text)

    def test_scout_writes_csv_beside_artifact_only(self):
        import argparse
        a = argparse.Namespace(since=None, quantity="q", unit="s", depth="quick", output="table", n=20)
        out = self.td / "out"
        path = lit_run.write_artifact("scout", "fake subject", "ctank", self.fake_works(), {}, a, out, lit_common.load_plan(ALLOWED), 0)
        self.assertEqual(sorted(p.name for p in out.iterdir()), sorted([path.name, path.with_suffix(".csv").name]))
        self.assertFalse(any("DATASET" in p.name for p in self.td.rglob("*")))

    def assertFires(self, out, *rules):
        got = {r for r in ("L%d" % i for i in range(1, 12)) if f"[{r}]" in out}
        self.assertEqual(got, set(rules), out)


class TestCommon(unittest.TestCase):
    def test_norm_doi(self):
        self.assertEqual(lit_common.norm_doi("https://doi.org/10.1/ABC"), "10.1/abc")
        self.assertEqual(lit_common.norm_doi(" 10.1/abc "), "10.1/abc")

    def test_hit_index_types(self):
        ex = [("10.1/abc", "doi", ""), ("Foo Bar", "title", "")]
        self.assertEqual(lit_common.hit_index(ex, dois=["https://doi.org/10.1/ABC"]), 0)
        self.assertIsNone(lit_common.hit_index(ex, dois=["10.1/abcd"]))
        self.assertEqual(lit_common.hit_index(ex, texts=["a foo bar baz"]), 1)
        self.assertIsNone(lit_common.hit_index(ex, texts=["10.1/abc"]))
        self.assertEqual(lit_common.hit_index(ex, texts=["10.1/abc"], doi_in_text=True), 0)

    def test_parse_plan_fixtures(self):
        p = lit_common.load_plan(BLIND)
        self.assertEqual((p["id"], p["mode"], len(p["excluded"]), p["problems"]),
                         ("cpt-ctank-plan-example", "blind", 3, []))
        self.assertEqual({t for _, t, _ in p["excluded"]}, {"doi", "benchmark", "author"})
        self.assertEqual(lit_common.load_plan(ALLOWED)["excluded"], [])
        self.assertEqual(lit_common.load_plan(NONE)["mode"], "none")

    def test_shipped_template_placeholder_row_is_skipped(self):
        t = (ROOT / "artifacts" / "PLAN" / "template.md").read_text(encoding="utf-8")
        self.assertEqual(lit_common.parse_plan(t)["excluded"], [])


def chk(text, plan=None, resolve=False, resolver=None, td=None):
    """In-process gate on a text; returns the violation lines joined."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "lit.md"
        p.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        return "\n".join(lit_gate.check(p, plan, resolve, resolver))


class FakeGet:
    """Stub for lit_run.get: records every call, serves canned OpenAlex answers."""

    def __init__(self, works=(), anchor=None, fail=False):
        self.calls, self.works, self.anchor, self.fail = [], list(works), anchor, fail

    def __call__(self, path, **params):
        self.calls.append((path, params))
        if self.fail:
            raise RuntimeError("boom")
        lit_run.budget["queries"].append(f"https://api.openalex.org{path}?{sorted(params.items())}")
        if path.startswith("/works/"):
            return self.anchor
        if "group_by" in params:
            return {"group_by": [{"key": "k", "key_display_name": "Zyxwvut Quillfeather Institute", "count": 9}]}
        if params.get("per_page") == 1:
            return {"meta": {"count": 999}, "results": []}
        return {"results": self.works, "meta": {"count": len(self.works)}}


def fake_work(i, doi, title, authors=("Someone",), venue="Jrnl", year=2020):
    return {"id": f"https://openalex.org/W{i}", "doi": f"https://doi.org/{doi}" if doi else None, "title": title,
            "publication_year": year, "cited_by_count": i,
            "authorships": [{"author": {"id": f"A{a}", "display_name": a}, "institutions": [{"display_name": "Some Inst"}]}
                            for a in authors],
            "primary_location": {"source": {"display_name": venue}}, "best_oa_location": None,
            "referenced_works": [], "related_works": []}


def run_main(argv, fake):
    err, out = io.StringIO(), io.StringIO()
    with mock.patch.object(lit_run, "get", fake), redirect_stderr(err), redirect_stdout(out):
        rc = lit_run.main(argv)
    return rc, out.getvalue() + err.getvalue()


class TestFindingsGate(Scratch):
    # ---- C-001
    def test_c001_status_parse(self):
        ex = example_text()
        self.assertEqual(chk(ex.encode("utf-8")), "")
        self.assertEqual(chk(b"\xef\xbb\xbf" + ex.encode("utf-8")), "")          # BOM
        self.assertEqual(chk(ex.replace("status: draft", 'status: "Draft" ')), "")
        for bad in ("status: published", "status:", "status: draft-ish"):
            self.assertIn("[L9]", chk(ex.replace("status: draft", bad)), bad)
        self.assertIn("[L9]", chk(ex.replace("status: draft\n", "")))
        self.assertIn("[L9]", chk(ex.split("---\n", 2)[2]))                       # no frontmatter
        self.assertIn("[L9]", chk(ex.replace("status: draft", "status: 'verified'")))   # verified, no online line

    # ---- C-002 (gate side)
    def test_c002_scan_covers_every_table_of_section_3(self):
        t = blind_text(1).replace("- Approved by: A. Shumilov",
                                  "**Groups**:\n\n| author | works |\n|---|---|\n| Zyxwvut Quillfeather | 3 |\n\n- Approved by: A. Shumilov")
        out = chk(t, self.plan())
        self.assertIn("section 3 outside the Set table", out)
        self.assertNotIn("Quillfeather", out)
        t = blind_text(1).replace("- Approved by: A. Shumilov", "Landscape: Zyxwvut Quillfeather works.\n\n- Approved by: A. Shumilov")
        self.assertIn("section 3 outside", chk(t, self.plan()))

    # ---- C-004
    def test_c004_section7(self):
        ex = example_text()
        head = "| candidate | claims | proposed diagnostic condition | status |\n|---|---|---|---|\n"
        old = "none — the Set is consistent on the anchor's question."
        self.assertEqual(chk(ex), "")
        row = lambda c: ex.replace(old, "none\n\n" + head + f"| mech | {c} | cond | NOT YET TESTED |")
        self.assertIn("[L6]", chk(row("—")))                   # `none` does not excuse a row without claim
        self.assertIn("[L6]", chk(row("claim 99")))
        self.assertIn("[L6]", chk(row("claim 0")))
        self.assertEqual(chk(row("`LIT`, claim 1; claim 2")), "")
        self.assertEqual(chk(ex.replace(old, head + "| mech | claim 1 | cond | NOT YET TESTED |")), "")
        self.assertIn("[L6]", chk(ex.replace(old, "{one candidate per contradiction, or `none`}")))   # unfilled placeholder
        self.assertIn("[L6]", chk(ex.replace(old, "<!-- none -->")))
        self.assertIn("[L6]", chk(ex.replace(old, "there is none of it")))

    # ---- C-005
    def test_c005_short_set_row_fails_l3_and_is_still_scanned(self):
        t = blind_text(1)
        short = [ln for ln in t.splitlines() if ln.startswith("| 5 |")][0]
        cut = short.rsplit("|", 3)[0] + "|"                     # 7 cells
        t7 = t.replace(short, cut)
        self.assertIn("[L3]", chk(t7))
        t7 = t7.replace("System identification of nonlinear state-space models", "Zyxwvut Quillfeather note")
        out = chk(t7, self.plan())
        self.assertIn("Set row 5", out)

    # ---- C-007
    def test_c007_normalisation(self):
        def hit(item, typ, mutate=lambda t: t):
            return "excluded hit" in chk(mutate(blind_text(1)), self.plan(rows=((item, typ),)))
        ana = lambda w: (lambda t: t.replace("What the anchor adds is not a method", f"{w} What the anchor adds is not a method"))
        self.assertTrue(hit("Zyxwvut Quillfeather", "author", ana("_Zyxwvut Quillfeather_")))
        self.assertTrue(hit("**Zyxwvut** `Quillfeather`", "author", ana("zyxwvut   quillfeather")))
        self.assertTrue(hit("Zyxwvut Quillfeather", "author", ana("[Zyxwvut Quillfeather](http://x.org)")))
        self.assertTrue(hit("Zyxwvut", "term", ana("[text](http://x.org/Zyxwvut)")))
        self.assertTrue(hit("zyxwvut quillfeather", "term", ana("Zyxwvut%20Quillfeather")))
        for form in ("https://www.doi.org/10.1007/S11831-009-9031-8.", "doi:10.1007/s11831-009-9031-8",
                     "http://dx.doi.org/10.1007/s11831-009-9031-8>", "**10.1007/s11831-009-9031-8**", "`10.1007/s11831-009-9031-8`;"):
            self.assertTrue(hit(form, "doi"), form)
        self.assertTrue(hit("10.1007/s11831-009-9031-8", "doi",
                            lambda t: t.replace("| 3 | 10.1007/s11831-009-9031-8 |", "| 3 | [10.1007/S11831-009-9031-8](https://doi.org/10.1007/S11831-009-9031-8) |")))
        self.assertTrue(hit("10.1007/s11831-009-9031-8", "doi",
                            lambda t: t.replace("| 3 | 10.1007/s11831-009-9031-8 |", "| 3 | 10.1007%2FS11831-009-9031-8 |")))
        # doi item against a DOI embedded in an OA link cell
        self.assertTrue(hit("10.9999/target.2099", "doi",
                            lambda t: t.replace("https://eprints.lancs.ac.uk/id/eprint/124945/1/BookOfAbstracts2018_30.pdf",
                                                "https://doi.org/10.9999/TARGET.2099?x=1")))
        self.assertFalse(hit("10.9999/target", "doi",
                             lambda t: t.replace("https://eprints.lancs.ac.uk/id/eprint/124945/1/BookOfAbstracts2018_30.pdf",
                                                 "https://doi.org/10.9999/TARGET.2099")))

    # ---- C-008
    def test_c008_approval_line(self):
        ex = example_text()
        for bad in ("- Approved by: 2026-10-12", "- Approved by: A, 2026-10-12", "- Approved by: A. Shumilov",
                    "- Approved by: A. Shumilov, 2026-13-45", "- Approved by: A. Shumilov, 26-10-12"):
            self.assertIn("[L2]", chk(ex.replace("- Approved by: A. Shumilov, 2026-10-12", bad)), bad)
        t = ex.replace("- Approved by: A. Shumilov, 2026-10-12",
                       "Reviewer note (Approved by: Bob Jones 2026-01-01).\n\n- Approved by: {person, YYYY-MM-DD}")
        self.assertIn("[L2]", chk(t))                              # only the line starting `- Approved by:` counts
        self.assertEqual(chk(ex.replace("A. Shumilov, 2026-10-12", "Al, 2026-10-12")), "")

    # ---- C-009
    def test_c009_collection(self):
        ex = example_text()
        col = lambda c: ex.replace("## 4. Collection\n\nnot used", f"## 4. Collection\n\n{c}")
        hyp = "| Hypothesis | not configured | — | — | set HYPOTHESIS_MCP_KEY and build a collection of the approved set |"
        ran = ex.replace(hyp, "| Hypothesis | **yes** | collection c-1 | — | x |")
        self.assertNotEqual(ran, ex)
        self.assertIn("[L7]", chk(ran))                                           # ran, but `not used`
        self.assertEqual(chk(ran.replace("not used", "Collection holds 30 of 36 approved papers.")), "")
        self.assertIn("[L7]", chk(col("not used (5 of 36)")))
        self.assertIn("[L7]", chk(col("40 of 36 papers")))
        self.assertIn("[L7]", chk(col("0 of 0 papers")))
        self.assertIn("[L7]", chk(col("The collection was not used, it said.")))
        self.assertIn("[L7]", chk(col("<!-- not used -->")))
        self.assertIn("[L7]", chk(col("{k of N}")))
        self.assertEqual(chk(col("<!-- c -->\n**not used**")), "")

    # ---- C-010
    def test_c010_online_line_form(self):
        t = example_text().replace("status: draft", "status: verified")
        good = "- Gate, online: `python3 scripts/lit_gate.py x.md --plan P.md --resolve`, run 2026-10-14: PASS; 32 DOIs."
        self.assertEqual(chk(t.rstrip("\n") + "\n" + good + "\n", ALLOWED), "")
        for bad in ("- Gate, online: `python3 other.py --plan P.md --resolve`, run 2026-10-14: PASS",
                    "- Gate, online: `python3 scripts/lit_gate.py x.md --plan P.md --resolve`, run 2026-10-14: note PASS",
                    "- Gate, online: `python3 scripts/lit_gate.py x.md --plan P.md --resolve`, run 2026-10-14: FAIL",
                    "- Gate, online: python3 scripts/lit_gate.py x.md --plan P.md --resolve, run 2026-10-14: PASS",
                    "- Gate, online: `python3 scripts/lit_gate.py x.md --plan P.md --resolve`, run 2026-99-14: PASS",
                    "- Gate, online: `python3 scripts/lit_gate.py x.md --plan P.md`, run 2026-10-14: PASS; --resolve"):
            self.assertIn("[L9]", chk(t.rstrip("\n") + "\n" + bad + "\n", ALLOWED), bad)

    # ---- C-011
    def test_c011_analysis_citations(self):
        ex = example_text()
        mk = lambda c: ex.replace("What the anchor adds is not a method", f"See {c}. What the anchor adds is not a method")
        self.assertEqual(chk(mk("[1-3]")), "")
        self.assertEqual(chk(mk("[1, 3–5]")), "")
        self.assertIn("[L5]", chk(mk("[1, 99]")))
        self.assertIn("[L5]", chk(mk("[30–40]")))
        self.assertIn("[L5]", chk(mk("[0]")))
        self.assertIn("[L5]", chk(mk("[5-3]")))
        ph = ex.split("## 5. Analysis\n")[0] + "## 5. Analysis\n\n{Path 1: placeholder [99]}\n\n## 6." + ex.split("## 6.", 1)[1]
        self.assertIn("[L5]", chk(ph))                                           # drafts are range-checked too
        self.assertNotIn("[L5]", chk(ph.replace("[99]", "")))

    # ---- C-012
    def test_c012_tables_and_noncontent(self):
        self.assertEqual(lit_common.split_row(r"| a \| b | c |"), ["a | b", "c"])
        self.assertEqual(lit_common.split_row("| a | b \\|"), ["a", "b |"])
        ex = example_text()
        self.assertEqual(chk(ex.replace("Hysteresis Bouc-Wen Model, a Survey | reference", r"Hysteresis \| Bouc-Wen Model | reference")), "")
        # comments and fenced code are not parsed as content, but the blind scan reads them raw (N-002)
        t = blind_text(1).replace("## 4. Collection", "<!-- Zyxwvut Quillfeather -->\n\n```\n| 1 | Zyxwvut Quillfeather | x |\n```\n\n## 4. Collection")
        self.assertIn("excluded hit", chk(t, self.plan()))
        self.assertEqual(chk(t.replace("`blind`", "`allowed`").replace("Exclusions checked: 1", "Exclusions checked: not applicable")), "")
        t = ex.replace("## 7. Candidate", "```\n| c | 1 | q |\n```\n\n## 7. Candidate")
        self.assertEqual(chk(t), "")
        t = ex.replace("| PNLSS models are initialised", "<!-- | a | 1 | — | — | verified | -->\n| PNLSS models are initialised")
        self.assertEqual(chk(t), "")

    # ---- C-016
    def test_c016_ran_cell_markdown_and_all_queries(self):
        ex = example_text()
        t = ex.replace("| Consensus | not configured | — |", "| Consensus | **yes** | — |")
        self.assertIn("[L8]", chk(t))
        two = blind_text(1).replace("| Consensus | not configured | — | 0 |",
                                    "| OpenAlex | yes | https://api.openalex.org/works?search=Zyxwvut%20Quillfeather | — | request 2 |\n| Consensus | not configured | — | 0 |")
        self.assertIn("Sources query", chk(two, self.plan()))
        br = blind_text(1).replace("| Consensus | not configured | — | 0 |",
                                   "| OpenAlex | yes | https://a.org/x<br>https://a.org/Zyxwvut+Quillfeather | — | y |\n| Consensus | not configured | — | 0 |")
        self.assertIn("Sources query", chk(br, self.plan()))

    # ---- C-017
    def test_c017_csv(self):
        t = example_text().replace("- Strategy: `related`", "- Strategy: `scout`")
        p = self.lit(t, "scout.md")
        csvp = self.td / "scout.csv"
        hdr = "set_no,paper,value,passage\n"
        csvp.write_text("set_no,paper,value\n1,P,3.2\n", encoding="utf-8")
        self.assertIn("[L10]", gate(p)[1])                                       # no passage column
        csvp.write_text("set_no,paper,passage\n1,P,x\n", encoding="utf-8")
        self.assertIn("[L10]", gate(p)[1])
        csvp.write_text("Set_No,Paper,Value,Passage\n1,P,3.2,\"it was 3.2\"\n", encoding="utf-8")
        self.assertNotIn("[L10]", gate(p)[1])
        for empty in ("—", "–", "-", "n/a", "N/A"):
            csvp.write_text(hdr + f"1,P,3.2,{empty}\n", encoding="utf-8")
            self.assertIn("[L10]", gate(p)[1], empty)
        csvp.write_bytes(b"\xef\xbb\xbf" + (hdr + "1,P,3.2,ok\n").encode())
        self.assertNotIn("[L10]", gate(p)[1])

    # ---- C-018
    def test_c018_mode_without_plan(self):
        ex = example_text()
        mode = "- Literature mode: `allowed`, copied from the PLAN's section 2."
        self.assertEqual(chk(ex.replace(mode, "- **Literature mode**: allowed")), "")
        for bad in ("- Literature mode: `blind`, copied", "- Literature mode: {`allowed` | `blind`}", "- Literature mode: allowed or blind",
                    "- Literature mode: `none`", ""):
            self.assertIn("[L11]", chk(ex.replace(mode, bad)), bad)

    def test_c018_blind_scan_extended(self):
        def hit(mutate, where):
            out = chk(mutate(blind_text(1)), self.plan())
            self.assertIn(f"excluded hit in {where}", out)
            self.assertNotIn("Quillfeather", out)
        hit(lambda t: t.replace("none — the Set is consistent", "none, but Zyxwvut Quillfeather disagrees; the Set is consistent"), "Candidate Hypotheses")
        hit(lambda t: t.replace("# LITERATURE — related:", "# LITERATURE — Zyxwvut Quillfeather related:"), "the title")
        hit(lambda t: t.replace("description: ", "description: Zyxwvut Quillfeather ", 1), "the frontmatter description")


class TestRound2(Scratch):
    X = "Zyxwvut Quillfeather"

    def blind(self, mutate):
        return chk(mutate(blind_text(1)), self.plan())

    # ---- N-001
    def test_n001_empty_plan_arg_exit_2_zero_calls(self):
        f = FakeGet()
        rc, out = run_main(["scout", "q", "--system", "t", "--plan", "", "--out", str(self.td / "o")], f)
        self.assertEqual(rc, 2, out)
        self.assertEqual(f.calls, [])

    # ---- N-002
    def test_n002_whole_raw_text_scanned_under_blind(self):
        X = self.X
        cases = {
            "frontmatter": lambda t: t.replace("status: draft", f"status: draft\nnote: {X}", 1),
            "the title block": lambda t: t.replace("**ID**:", f"{X} **ID**:", 1),
            "preamble": lambda t: t.replace("\n---\n\n# LITERATURE", f"\n---\n{X}\n\n# LITERATURE", 1),
            "section 'Sources'": lambda t: t.replace("set CONSENSUS_API_KEY to enable", f"{X} note", 1),
            "section 'Collection'": lambda t: t.replace("## 4. Collection\n\nnot used", f"## 4. Collection\n\nnot used, {X}"),
            "section 'Attestation'": lambda t: t.rstrip("\n") + f"\n- {X}\n",
            "section 'Sources' (removed line)": lambda t: t.replace("- Removed by exclusion: 0", f"- Removed by exclusion: 0 ({X})"),
            "comment": lambda t: t.replace("## 4. Collection", f"<!-- {X} -->\n\n## 4. Collection"),
            "fence": lambda t: t.replace("## 4. Collection", f"```\n{X}\n```\n\n## 4. Collection"),
        }
        for name, mut in cases.items():
            out = self.blind(mut)
            self.assertIn("excluded hit in", out, name)
            self.assertNotIn("Quillfeather", out, name)
        self.assertIn("frontmatter", self.blind(cases["frontmatter"]))
        self.assertIn("preamble", self.blind(cases["preamble"]))
        self.assertIn("'Collection'", self.blind(cases["section 'Collection'"]))
        self.assertIn("'Attestation'", self.blind(cases["section 'Attestation'"]))
        self.assertIn("'Sources'", self.blind(cases["section 'Sources'"]))
        self.assertEqual(chk(blind_text(1), self.plan()), "")

    # ---- N-003
    def test_n003_normalisation_forms(self):
        c = lit_common
        self.assertEqual(c.norm_text("Caf\u00e9"), "cafe")
        self.assertEqual(c.norm_text("Cafe\u0301"), "cafe")
        self.assertEqual(c.norm_text("a&amp;b"), "a&b")
        self.assertEqual(c.norm_text("a<br/>b"), "a b")
        self.assertEqual(c.norm_text("a<BR>b"), "a b")
        self.assertEqual(c.norm_text("a\u200bb\u00adc"), "abc")

    def test_n003_hits_through_obfuscation_and_every_set_cell(self):
        for form in ("Zyxwvut\u200b Quillfeather", "Zyxwvut<br>Quillfeather", "Zyxwv&#117;t Quillfeather", "Zyxwv\u00fct Quillfeather"):
            out = self.blind(lambda t: t.replace("What the anchor adds is not a method", f"{form} What the anchor adds is not a method"))
            self.assertIn("excluded hit in Analysis", out, form)
        t = blind_text(1)
        line = [ln for ln in t.splitlines() if ln.startswith("| 3 |")][0]
        for i in (3, 5, 6):          # year, role, cited by (0-based cells after the leading pipe)
            cells = line.split("|")
            cells[i] = f" {self.X} "
            out = chk(t.replace(line, "|".join(cells)), self.plan())
            self.assertIn("Set row 3", out, i)

    def test_n003_doi_item_in_prose(self):
        pl = self.plan(rows=(("10.9999/target.1", "doi"),))
        t = blind_text(1).replace("What the anchor adds is not a method", "See 10.9999/TARGET.1 What the anchor adds is not a method")
        self.assertIn("excluded hit in Analysis", chk(t, pl))
        t = blind_text(1).replace("none — the Set is consistent", "none (10.9999/target.1); the Set is consistent")
        self.assertIn("excluded hit in Candidate Hypotheses", chk(t, pl))

    # ---- N-004
    def test_n004_collection_n_equals_set_rows(self):
        t = example_text().replace("## 4. Collection\n\nnot used", "## 4. Collection\n\nCollection `c-1` holds 30 of 40 approved papers.")
        self.assertIn("[L7]", chk(t))
        t = example_text().replace("## 4. Collection\n\nnot used", "## 4. Collection\n\nCollection `c-1` holds 36 of 36 approved papers.")
        self.assertNotIn("[L7]", chk(t))

    # ---- N-005
    def test_n005_citation_forms(self):
        ex = example_text()
        ana = "What the anchor adds is not a method"
        def with_(c):
            return chk(ex.replace(ana, f"Claim {c} {ana}"))
        self.assertNotIn("[L5]", with_("[1; 2]"))
        self.assertNotIn("[L5]", with_("[1, 3-4]"))
        for bad_c in ("[99a]", "[1 99]", "[2015-2020]", "[1; 99]"):
            self.assertIn("[L5]", with_(bad_c), bad_c)
        self.assertIn("unparseable citation", with_("[99a]"))
        self.assertIn("0 to 1", with_("[99a]"))

    # ---- N-006
    def test_n006_online_invocation(self):
        ex = example_text().replace("status: draft", "status: verified")
        att = lambda inv: ex.rstrip("\n") + f"\n- Set approved by Mark Z, 2026-10-14.\n- Gate, online: `{inv}`, run 2026-10-14: PASS\n"
        good = "python3 scripts/lit_gate.py x.md --plan PLAN.md --resolve"
        def l9(inv):
            return "no `Gate, online" in chk(att(inv))
        self.assertFalse(l9(good))
        for bad_inv in ("echo lit_gate.py --resolve --plan", "python3 scripts/lit_gate.py x.md --plan --resolve",
                        "python3 scripts/lit_gate.py x.md --plan=PLAN.md --resolve", "python3 scripts/lit_gate.py x.md --plan PLAN.md --resolved",
                        "python3 scripts/lit_gate.py x.md --plan PLAN.md", "python3 scripts/lit_gate.py x.md --plan 'PLAN.md --resolve"):
            self.assertTrue(l9(bad_inv), bad_inv)

    # ---- N-007
    def test_n007_non_dict_json_is_resolver_error(self):
        for body in (b"[]", b"null", b'"x"', b"3"):
            resp = mock.MagicMock()
            resp.__enter__.return_value = io.BytesIO(body)
            with mock.patch.object(lit_gate.urllib.request, "urlopen", return_value=resp):
                with self.assertRaises(lit_gate.ResolverError):
                    lit_gate.openalex_resolver("10.1/x")

    # ---- N-008
    def test_n008_empty_passage_forms(self):
        t = example_text().replace("- Strategy: `related`", "- Strategy: `scout`")
        p = self.lit(t, "scout.md")
        csvp = self.td / "scout.csv"
        for empty in ("\u200b", "...", "?", "None", "TBD", "null", "N/A", "\u00ad", "-"):
            csvp.write_text(f"set_no,paper,value,passage\n1,P,3.2,{empty}\n", encoding="utf-8")
            self.assertIn("[L10]", gate(p)[1], repr(empty))
        csvp.write_text("set_no,paper,value,passage\n1,P,3.2,it was 3.2\n", encoding="utf-8")
        self.assertNotIn("[L10]", gate(p)[1])

    # ---- N-009
    def test_n009_mode_line(self):
        ex = example_text()
        mode = "- Literature mode: `allowed`, copied from the PLAN's section 2."
        self.assertEqual(chk(ex.replace(mode, "- Literature mode: allowed")), "")
        for bad_m in ("- Literature mode: allowed, but really blind", "- Literature mode: allowed. blind", "- Literature mode: allowed (blind)",
                      mode + "\n" + mode, mode + "\n- Literature mode: `blind`"):
            self.assertIn("[L11]", chk(ex.replace(mode, bad_m)), bad_m)
        self.assertIn("more than one", chk(ex.replace(mode, mode + "\n" + mode)))

    # ---- N-010
    def test_n010_description_quoted(self):
        out = self.td / "o"
        f = FakeGet(works=[fake_work(1, "10.1/a", "A title: with colon")])
        rc, msg = run_main(["metareview", 'sub "q": x', "--system", "t", "--out", str(out)], f)
        self.assertEqual(rc, 0, msg)
        md = next(out.glob("*.md")).read_text(encoding="utf-8")
        line = [ln for ln in md.splitlines() if ln.startswith("description:")][0]
        import json
        self.assertIsInstance(json.loads(line[len("description:"):]), str)
        self.assertTrue(example_text().split("\n")[1].startswith('description: "'))

    # ---- N-011
    def test_n011_oserror_exit_1(self):
        f = FakeGet(works=[fake_work(1, "10.1/a", "T")])
        with mock.patch.object(lit_run, "write_artifact", side_effect=OSError("disk full")):
            rc, msg = run_main(["metareview", "q", "--system", "t", "--out", str(self.td / "o")], f)
        self.assertEqual(rc, 1)
        self.assertIn("disk full", msg)
        blocker = self.td / "afile"
        blocker.write_text("x")
        rc, msg = run_main(["metareview", "q", "--system", "t", "--out", str(blocker / "sub")], FakeGet(works=[fake_work(1, "10.1/a", "T")]))
        self.assertEqual(rc, 1, msg)

    def test_n011_stray_csv_blocks_only_scout(self):
        out = self.td / "o"
        out.mkdir()
        (out / (lit_run.artifact_slug("metareview", "q") + ".csv")).write_text("x")
        rc, msg = run_main(["metareview", "q", "--system", "t", "--out", str(out)], FakeGet(works=[fake_work(1, "10.1/a", "T")]))
        self.assertEqual(rc, 0, msg)
        (out / (lit_run.artifact_slug("scout", "q") + ".csv")).write_text("x")
        rc, msg = run_main(["scout", "q", "--system", "t", "--out", str(out)], FakeGet(works=[fake_work(1, "10.1/a", "T")]))
        self.assertEqual(rc, 2, msg)

    def test_n011_ran_vocabulary(self):
        ex = example_text()
        for ok in ("not configured", "no", "skipped", "skipped (no key)", "No", "**not configured**"):
            self.assertNotIn("[L8]", chk(ex.replace("| Consensus | not configured |", f"| Consensus | {ok} |")), ok)
        for bad_c in ("maybe", "n/a", "yes-ish", "—", "not  configured now"):
            self.assertIn("[L8]", chk(ex.replace("| Consensus | not configured |", f"| Consensus | {bad_c} |")), bad_c)


class TestResolverErrors(Scratch):
    def http(self, code):
        return urllib.error.HTTPError("u", code, "m", {}, None)

    def test_c013_404_is_none_and_errors_abort(self):
        with mock.patch("urllib.request.urlopen", side_effect=self.http(404)):
            self.assertIsNone(lit_gate.openalex_resolver("10.1/x"))
        for exc in (self.http(503), self.http(429), urllib.error.URLError("down"), TimeoutError("t")):
            m = mock.Mock(side_effect=exc)
            with mock.patch("urllib.request.urlopen", m), mock.patch("time.sleep") as sl:
                with self.assertRaises(lit_gate.ResolverError):
                    lit_gate.openalex_resolver("10.1/x")
            self.assertEqual(m.call_count, 3)                                   # first try plus 2 retries
            self.assertEqual(sl.call_count, 2)
        with mock.patch("urllib.request.urlopen", side_effect=self.http(403)), mock.patch("time.sleep"):
            with self.assertRaises(lit_gate.ResolverError):
                lit_gate.openalex_resolver("10.1/x")

    def test_c013_gate_exit_2_with_distinct_message(self):
        def boom(doi):
            raise lit_gate.ResolverError("OpenAlex answered HTTP 503")
        p = self.lit(example_text())
        err = io.StringIO()
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(err):
            rc = lit_gate.main([str(p), "--resolve"], resolver=boom)
        self.assertEqual(rc, 2)
        self.assertNotIn("unresolved", out.getvalue() + err.getvalue())
        self.assertIn("503", err.getvalue())

    def test_c013_resolver_gets_normalised_doi(self):
        seen = []
        t = example_text().replace("| 3 | 10.1007/s11831-009-9031-8 |", "| 3 | **https://doi.org/10.1007/S11831-009-9031-8.** |")
        chk(t, resolve=True, resolver=lambda d: seen.append(d) or {"authors": [], "venue": ""})
        self.assertIn("10.1007/s11831-009-9031-8", seen)
        self.assertTrue(all(d == d.lower() and not d.startswith("http") for d in seen))

    def test_c014_usage_and_unreadable(self):
        p = self.lit(example_text())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(lit_gate.main([str(p), "--plan", ""]), 2)
        bad = self.td / "bad.md"
        bad.write_bytes(b"---\nstatus: draft\n---\n\xff\xfe\x80")
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            self.assertEqual(lit_gate.main([str(bad)]), 2)
        self.assertIn("lit_gate", err.getvalue())
        self.assertEqual(subprocess.run([sys.executable, str(GATE), str(p), "--plan", ""], capture_output=True).returncode, 2)


class TestPlanParsing(unittest.TestCase):
    def test_c006_placeholders(self):
        def parse(rows):
            return lit_common.parse_plan(plan_text(rows=()).replace("**Excluded**: none",
                "**Excluded**:\n\n| Excluded item | Type | Reason |\n|---|---|---|\n" + rows + "\n"))
        p = parse("| {…} | {doi / title} | {what it could reveal} |")
        self.assertEqual((p["excluded"], p["problems"]), ([], []))
        p = parse("| Foo | {...} | r |")
        self.assertEqual(p["excluded"], [])
        self.assertTrue(p["problems"])
        p = parse("| Foo | term | {why} |")                 # half-filled row: fail closed
        self.assertEqual(p["excluded"], [])
        self.assertTrue(p["problems"])
        p = parse("| f{x} and {y} | term | r |")
        self.assertEqual([i for i, _, _ in p["excluded"]], ["f{x} and {y}"])
        self.assertEqual(p["problems"], [])
        p = parse("| a \\| b | term | r |")
        self.assertEqual(p["excluded"][0][0], "a | b")

    def test_c006_blind_fails_closed_through_lit_run(self):
        t = plan_text(rows=()).replace("**Excluded**: none", "**Excluded**:\n\n| i | t | r |\n|--|--|--|\n| Foo | term | {…} |\n")
        with tempfile.TemporaryDirectory() as d:
            pl = Path(d) / "p.md"
            pl.write_text(t, encoding="utf-8")
            plan, err = lit_run.check_plan(pl, "x")
            self.assertIsNone(plan)
            self.assertIn("placeholder", err)


class TestLitRunFindings(Scratch):
    base = ("--system", "t")

    def test_zero_calls_none_empty_blind_intake_overwrite(self):
        out = self.td / "out"
        f = FakeGet()
        self.assertEqual(run_main(["scout", "q", *self.base, "--plan", str(NONE), "--out", str(out)], f)[0], 2)
        self.assertEqual(run_main(["scout", "q", *self.base, "--plan", str(self.plan(rows=())), "--out", str(out)], f)[0], 2)
        pl = self.plan(rows=(("tennessee eastman", "benchmark"),))
        self.assertEqual(run_main(["review", "Tennessee Eastman process", *self.base, "--plan", str(pl), "--out", str(out)], f)[0], 2)
        self.assertEqual(run_main(["related", "10.9999/x", *self.base, "--plan", str(self.plan(rows=(("10.9999/X", "doi"),))),
                                   "--out", str(out)], f)[0], 2)
        self.assertEqual(f.calls, [])
        self.assertFalse(out.exists())

    def test_c003_overwrite_refused_before_network_and_force(self):
        out = self.td / "out"
        f = FakeGet(works=[fake_work(1, "10.1/a", "Plain")])
        rc, _ = run_main(["scout", "some subject", *self.base, "--out", str(out)], f)
        self.assertEqual(rc, 0)
        files = sorted(out.iterdir())
        self.assertEqual({p.suffix for p in files}, {".md", ".csv"})
        before = {p: p.read_bytes() for p in files}
        f2 = FakeGet(works=[fake_work(2, "10.1/b", "Other")])
        rc, msg = run_main(["scout", "some subject", *self.base, "--out", str(out)], f2)
        self.assertEqual((rc, f2.calls), (2, []))
        self.assertIn("--force", msg)
        self.assertEqual(before, {p: p.read_bytes() for p in files})
        # only the CSV exists
        files[0].unlink() if files[0].suffix == ".md" else files[1].unlink()
        rc, _ = run_main(["scout", "some subject", *self.base, "--out", str(out)], FakeGet())
        self.assertEqual(rc, 2)
        rc, _ = run_main(["scout", "some subject", *self.base, "--out", str(out), "--force"], f2)
        self.assertEqual(rc, 0)
        self.assertIn("Other", next(out.glob("*.md")).read_text(encoding="utf-8"))

    def test_c003_slug_has_hash_of_full_query(self):
        a = lit_run.artifact_slug("review", "x" * 80 + " alpha")
        b = lit_run.artifact_slug("review", "x" * 80 + " beta")
        self.assertNotEqual(a, b)
        self.assertEqual(a, lit_run.artifact_slug("review", "x" * 80 + " alpha"))

    def test_c019_retrieval_failure_exit_1_writes_nothing(self):
        out = self.td / "out"
        for strat in ("review", "scout", "metareview", "related"):
            rc, msg = run_main([strat, "q", *self.base, "--out", str(out)], FakeGet(fail=True))
            self.assertEqual(rc, 1, msg)
            self.assertIn("retrieval failed", msg)
        self.assertFalse(out.exists())

    def test_c002_blind_review_uses_kept_rows_only(self):
        out = self.td / "out"
        works = [fake_work(1, "10.1/a", "Plain paper", authors=("Fine Person",)),
                 fake_work(2, "10.1/b", "Second", authors=("Zyxwvut Quillfeather", "Fine Person")),
                 fake_work(3, "10.1/c", "Third", authors=("Other Person",), year=2019)]
        f = FakeGet(works=works)
        rc, msg = run_main(["review", "subject words", *self.base, "--plan", str(BLIND), "--out", str(out)], f)
        self.assertEqual(rc, 0, msg)
        self.assertFalse(any("group_by" in kw for _, kw in f.calls))
        self.assertEqual(sum(1 for _, kw in f.calls if kw.get("per_page") == 1), 0)
        text = next(out.glob("*.md")).read_text(encoding="utf-8")
        self.assertNotIn("Quillfeather", text)
        self.assertNotIn("999", text)
        self.assertNotIn("Second", text)
        self.assertIn("- Removed by exclusion: 1", text)
        self.assertIn("Fine Person | 1 |", text)              # 2 works by him in the Set would show 2: the dropped one is not counted
        self.assertIn("computed from the 2 works", text)
        rc, out_g = gate(next(out.glob("*.md")), BLIND)
        self.assertNotIn("excluded hit", out_g)

    def test_c002_allowed_review_keeps_server_counts(self):
        out = self.td / "out"
        f = FakeGet(works=[fake_work(1, "10.1/a", "Plain")])
        rc, msg = run_main(["review", "subject", *self.base, "--plan", str(ALLOWED), "--out", str(out)], f)
        self.assertEqual(rc, 0, msg)
        self.assertIn("999 works match", next(out.glob("*.md")).read_text(encoding="utf-8"))

    def test_c015_related_anchor_checked_after_fetch_before_more_calls(self):
        anchor = fake_work(100, "10.5/anchor", "Neutral anchor title", authors=("Zyxwvut Quillfeather",))
        out = self.td / "out"
        f = FakeGet(works=[fake_work(1, "10.1/a", "Plain")], anchor=anchor)
        rc, msg = run_main(["related", "10.5/anchor", *self.base, "--plan", str(BLIND), "--out", str(out)], f)
        self.assertEqual(rc, 2, msg)
        self.assertIn("refused", msg)
        self.assertEqual(len(f.calls), 1)                      # only work(); the title is never searched
        self.assertTrue(f.calls[0][0].startswith("/works/"))
        self.assertFalse(out.exists())
        # title and venue of the anchor are compared too
        for item, typ, kw in (("Neutral anchor", "title", {}), ("Secret Jrnl", "term", {"venue": "Secret Jrnl"})):
            a2 = fake_work(100, "10.5/anchor", "Neutral anchor title", **kw)
            f = FakeGet(anchor=a2)
            rc, _ = run_main(["related", "10.5/anchor", *self.base, "--plan", str(self.plan(rows=((item, typ),))), "--out", str(out)], f)
            self.assertEqual((rc, len(f.calls)), (2, 1), item)

    def test_c015_related_clean_anchor_proceeds(self):
        anchor = fake_work(100, "10.5/anchor", "Neutral anchor title")
        out = self.td / "out"
        f = FakeGet(works=[fake_work(1, "10.1/a", "Plain")], anchor=anchor)
        rc, msg = run_main(["related", "10.5/anchor", *self.base, "--plan", str(BLIND), "--out", str(out)], f)
        self.assertEqual(rc, 0, msg)
        self.assertGreater(len(f.calls), 1)

    def test_c016_every_distinct_query_recorded(self):
        import argparse
        lit_run.budget.update(credits=3, remaining="9", queries=["https://api.openalex.org/works?a=1", "https://api.openalex.org/works?b=2",
                                                                 "https://api.openalex.org/works?a=1"])
        a = argparse.Namespace(since=None, quantity="", unit="", depth="quick", output="reading list", n=20)
        path = lit_run.write_artifact("metareview", "subj", "t", [], {}, a, self.td / "o", None, 0)
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("| OpenAlex | yes |"), 2)
        self.assertIn("works?a=1", text)
        self.assertIn("works?b=2", text)
        lit_run.budget["queries"] = []

    def test_pipes_in_titles_are_escaped(self):
        import argparse
        lit_run.budget["queries"] = ["https://api.openalex.org/works?x=1"]
        a = argparse.Namespace(since=None, quantity="", unit="", depth="quick", output="reading list", n=20)
        w = fake_work(1, "10.1/a", "A | B")
        path = lit_run.write_artifact("metareview", "subj", "t", [(w, "review")], {}, a, self.td / "o", None, 0)
        rows = lit_common.table_rows(lit_common.section(path.read_text(encoding="utf-8"), "Set"), first_only=True)
        self.assertEqual((len(rows[0]), rows[0][3]), (8, "A | B"))
        lit_run.budget["queries"] = []


class TestWorkingTree(Scratch):
    def test_gate_runs_do_not_modify_shipped_files(self):
        def h():
            d = hashlib.sha256()
            for p in sorted((ROOT / "artifacts").rglob("*.md")) + sorted(FIX.glob("*.md")):
                d.update(p.read_bytes())
            return d.hexdigest()
        before = h()
        gate(EXAMPLE, ALLOWED)
        gate(EXAMPLE, BLIND)
        self.assertEqual(before, h())


@unittest.skipUnless(os.environ.get("LIT_ONLINE") == "1", "network test: set LIT_ONLINE=1")
class TestOnline(Scratch):
    def test_related_strategy_real_retrieval(self):
        r = subprocess.run([sys.executable, str(RUN), "related", "10.1016/j.ifacol.2017.08.071", "--system", "ctank",
                            "--plan", str(ALLOWED), "--out", str(self.td), "-n", "6"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        f = next(self.td.glob("related-*.md"))
        rc, out = gate(f, ALLOWED)
        self.assertIn("[L2]", out)

    def test_gate_resolve_real(self):
        rc, out = gate(EXAMPLE, ALLOWED, resolve=True)
        self.assertIn(rc, (0, 1))


if __name__ == "__main__":
    unittest.main()
