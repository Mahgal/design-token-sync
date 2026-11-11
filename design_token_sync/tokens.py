"""Core token parsing, flattening and validation.

Supports two input shapes:

(a) flat nested groups::

    {"color": {"primary": "#d4a017"}, "spacing": {"sm": "4px"}}

(b) W3C-ish tokens with ``$value`` / ``$type`` leaves::

    {"color": {"primary": {"$value": "#d4a017", "$type": "color"}}}

Nested groups flatten with ``-``: ``color.primary`` -> ``--color-primary``.

Standard library only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

__all__ = ["Token", "ValidationReport", "flatten_tokens", "load_tokens", "validate_tokens"]

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_RE = re.compile(
    r"^rgba?\(\s*\d{1,3}\s*(?:\s*,\s*\d{1,3}\s*){2}"
    r"(?:\s*,\s*(?:0|1|0?\.\d+)\s*)?\)$"
)
_HSL_RE = re.compile(
    r"^hsla?\(\s*\d{1,3}\s*(?:deg|turn|rad)?\s*(?:\s*,\s*\d{1,3}%\s*){2}"
    r"(?:\s*,\s*(?:0|1|0?\.\d+)\s*)?\)$"
)
# Looser fallback for functional colour notations with space / slash syntax,
# e.g. rgb(212 160 23 / 50%). The strict regexes above cover the common
# comma forms; this accepts the modern space-separated forms.
_FUNC_RE = re.compile(r"^(?:rgb|rgba|hsl|hsla)\([^)]+\)$")


@dataclass
class Token:
    """A single flattened design token."""

    name: str  # e.g. "color-primary"
    value: str
    type: str | None = None  # W3C $type, when present


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self, token_count: int) -> str:
        lines = [
            "design-token-sync check",
            f"tokens: {token_count}",
            f"errors: {self.error_count}",
            f"warnings: {self.warning_count}",
        ]
        for error in self.errors:
            lines.append(f"ERROR: {error}")
        for warning in self.warnings:
            lines.append(f"WARNING: {warning}")
        lines.append("result: OK" if self.ok else "result: FAILED")
        return "\n".join(lines) + "\n"


def is_valid_color(value: str) -> bool:
    """Return True for #rgb / #rrggbb / #rrggbbaa or rgb()/hsl() colours."""
    value = value.strip()
    if _HEX_RE.match(value):
        return True
    if _RGB_RE.match(value) or _HSL_RE.match(value):
        return True
    # Modern space-separated functional syntax, e.g. rgb(212 160 23).
    if _FUNC_RE.match(value):
        return True
    return False


def _is_w3c_leaf(node: object) -> bool:
    return isinstance(node, dict) and "$value" in node


def _flatten(node: object, prefix: str, tokens: dict[str, Token],
             types: dict[str, str | None], report: ValidationReport) -> None:
    """Recursively flatten *node* into ``tokens`` keyed by dashed name."""
    if _is_w3c_leaf(node):
        assert isinstance(node, dict)
        raw = node["$value"]
        token_type = node.get("$type")
        if not isinstance(token_type, str):
            token_type = None
        if not isinstance(raw, str):
            report.errors.append(
                f"non-string leaf value for --{prefix}: {raw!r}"
            )
            return
        tokens[prefix] = Token(name=prefix, value=raw, type=token_type)
        types[prefix] = token_type
        return

    if isinstance(node, dict):
        if not node:
            report.warnings.append(f"empty group: {prefix or '(root)'}")
            return
        for key in sorted(node):
            child = node[key]
            child_prefix = f"{prefix}-{key}" if prefix else str(key)
            _flatten(child, child_prefix, tokens, types, report)
        return

    # A non-dict, non-W3C leaf reached directly (top-level or nested value).
    if isinstance(node, str):
        tokens[prefix] = Token(name=prefix, value=node)
        types[prefix] = None
    else:
        report.errors.append(
            f"non-string leaf value for --{prefix}: {node!r}"
        )


def flatten_tokens(data: object) -> tuple[dict[str, Token], ValidationReport]:
    """Flatten parsed JSON into ``{dashed-name: Token}`` plus a report.

    Non-string leaves are errors; empty groups are warnings. Colour
    validation and duplicate detection happen in :func:`validate_tokens`.
    """
    report = ValidationReport()
    tokens: dict[str, Token] = {}
    types: dict[str, str | None] = {}
    if not isinstance(data, dict):
        report.errors.append(f"top-level value must be an object, got {type(data).__name__}")
        return tokens, report
    if not data:
        report.warnings.append("empty group: (root)")
        return tokens, report
    _flatten(data, "", tokens, types, report)
    return tokens, report


def _is_color_token(token: Token) -> bool:
    if token.type == "color":
        return True
    # Flat-shape tokens carry no $type; the top-level group decides.
    return token.name.startswith("color-")


def validate_tokens(tokens: dict[str, Token],
                    report: ValidationReport) -> ValidationReport:
    """Add colour and duplicate checks to *report* (mutated, returned)."""
    for name in sorted(tokens):
        token = tokens[name]
        if _is_color_token(token) and not is_valid_color(token.value):
            report.errors.append(
                f"invalid color value for --{name}: {token.value!r}"
            )

    by_value: dict[str, list[str]] = {}
    for name in sorted(tokens):
        by_value.setdefault(tokens[name].value, []).append(name)
    for value in sorted(by_value):
        names = by_value[value]
        if len(names) > 1:
            joined = ", ".join(f"--{n}" for n in names)
            report.warnings.append(
                f"duplicate value {value!r} used by {joined}"
            )
    return report


def load_tokens(path: str) -> tuple[dict[str, Token], ValidationReport]:
    """Load, flatten and validate a tokens JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    tokens, report = flatten_tokens(data)
    validate_tokens(tokens, report)
    return tokens, report


def render_css(tokens: dict[str, Token]) -> str:
    """Render tokens as a ``:root`` custom-properties block, sorted."""
    lines = [":root {"]
    for name in sorted(tokens):
        lines.append(f"  --{name}: {tokens[name].value};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_tailwind(tokens: dict[str, Token]) -> str:
    """Render tokens as a Tailwind v4 ``@theme`` block, sorted."""
    lines = ["@theme {"]
    for name in sorted(tokens):
        lines.append(f"  --{name}: {tokens[name].value};")
    lines.append("}")
    return "\n".join(lines) + "\n"
