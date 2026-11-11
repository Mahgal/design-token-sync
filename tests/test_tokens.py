"""Tests for design-token-sync (stdlib unittest only)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design_token_sync.tokens import (  # noqa: E402
    flatten_tokens,
    render_css,
    render_tailwind,
    validate_tokens,
)

FLAT = {
    "color": {"primary": "#d4a017", "ink": "#111111"},
    "spacing": {"sm": "4px"},
}

W3C = {
    "color": {
        "primary": {"$value": "#d4a017", "$type": "color"},
        "ink": {"$value": "#111111", "$type": "color"},
    },
    "spacing": {"sm": {"$value": "4px", "$type": "dimension"}},
}

EXPECTED_CSS = (
    ":root {\n"
    "  --color-ink: #111111;\n"
    "  --color-primary: #d4a017;\n"
    "  --spacing-sm: 4px;\n"
    "}\n"
)


def _run_cli(args, cwd):
    import os
    env = dict(os.environ)
    repo_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "design_token_sync", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


class TestFlatShape(unittest.TestCase):
    def test_flat_shape_exact_css_lines(self):
        tokens, report = flatten_tokens(FLAT)
        validate_tokens(tokens, report)
        self.assertEqual(report.errors, [])
        self.assertEqual(render_css(tokens), EXPECTED_CSS)

    def test_w3c_shape_same_vars(self):
        tokens, report = flatten_tokens(W3C)
        validate_tokens(tokens, report)
        self.assertEqual(report.errors, [])
        self.assertEqual(render_css(tokens), EXPECTED_CSS)
        self.assertEqual(tokens["color-primary"].value, "#d4a017")
        self.assertEqual(tokens["color-primary"].type, "color")

    def test_tailwind_block(self):
        tokens, _ = flatten_tokens(FLAT)
        self.assertEqual(
            render_tailwind(tokens),
            "@theme {\n"
            "  --color-ink: #111111;\n"
            "  --color-primary: #d4a017;\n"
            "  --spacing-sm: 4px;\n"
            "}\n",
        )


class TestValidation(unittest.TestCase):
    def test_invalid_hex_is_error(self):
        tokens, report = flatten_tokens(
            {"color": {"primary": "#gggggg", "ink": "#111111"}})
        validate_tokens(tokens, report)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("--color-primary", report.errors[0])
        self.assertFalse(report.ok)

    def test_check_exits_1_on_invalid_hex(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokens.json"
            path.write_text(json.dumps(
                {"color": {"primary": "not-a-color"}}), encoding="utf-8")
            result = _run_cli([str(path), "--check"], cwd=tmp)
            self.assertEqual(result.returncode, 1)
            self.assertIn("errors: 1", result.stdout)
            self.assertIn("ERROR:", result.stdout)

    def test_duplicate_values_produce_warning(self):
        tokens, report = flatten_tokens(
            {"color": {"primary": "#d4a017", "gold": "#d4a017"}})
        validate_tokens(tokens, report)
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 1)
        self.assertIn("duplicate value", report.warnings[0])
        self.assertIn("--color-gold", report.warnings[0])
        self.assertIn("--color-primary", report.warnings[0])

    def test_non_string_leaf_is_error(self):
        tokens, report = flatten_tokens({"spacing": {"sm": 4}})
        validate_tokens(tokens, report)
        self.assertEqual(len(report.errors), 1)
        self.assertIn("non-string", report.errors[0])

    def test_empty_group_is_warning(self):
        tokens, report = flatten_tokens(
            {"color": {"primary": "#d4a017"}, "radius": {}})
        validate_tokens(tokens, report)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("empty group" in w for w in report.warnings))

    def test_spacing_and_size_pass_through_unchanged(self):
        tokens, report = flatten_tokens({
            "spacing": {"sm": "4px", "md": "0.5rem"},
            "size": {"icon": "24px", "max": "100%"},
            "color": {"primary": "rgb(212, 160, 23)"},
        })
        validate_tokens(tokens, report)
        self.assertEqual(report.errors, [])
        self.assertEqual(tokens["spacing-sm"].value, "4px")
        self.assertEqual(tokens["spacing-md"].value, "0.5rem")
        self.assertEqual(tokens["size-icon"].value, "24px")
        self.assertEqual(tokens["size-max"].value, "100%")
        self.assertIn("--spacing-sm: 4px;", render_css(tokens))

    def test_rgb_and_hsl_colours_are_valid(self):
        tokens, report = flatten_tokens({
            "color": {
                "a": "rgb(212, 160, 23)",
                "b": "hsl(45, 76%, 47%)",
                "c": "#abc",
                "d": "#d4a017ff",
            },
        })
        validate_tokens(tokens, report)
        self.assertEqual(report.errors, [])

    def test_check_exits_0_on_valid_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokens.json"
            path.write_text(json.dumps(FLAT), encoding="utf-8")
            result = _run_cli([str(path), "--check"], cwd=tmp)
            self.assertEqual(result.returncode, 0)
            self.assertIn("result: OK", result.stdout)


class TestCliOutputs(unittest.TestCase):
    def test_css_and_tailwind_files_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "tokens.json"
            src.write_text(json.dumps(FLAT), encoding="utf-8")
            css = Path(tmp) / "tokens.css"
            theme = Path(tmp) / "theme.css"
            result = _run_cli(
                [str(src), "--css", str(css), "--tailwind", str(theme)],
                cwd=tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(css.read_text(encoding="utf-8"), EXPECTED_CSS)
            self.assertTrue(theme.read_text(encoding="utf-8").startswith("@theme {"))


if __name__ == "__main__":
    unittest.main()
