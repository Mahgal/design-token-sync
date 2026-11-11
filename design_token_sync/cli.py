"""Command-line interface for design-token-sync.

Usage::

    python -m design_token_sync tokens.json --css tokens.css --tailwind theme.css
    python -m design_token_sync tokens.json --check

Exit codes: 0 = success / no errors, 1 = validation errors (or bad usage),
2 = argparse usage error.
"""

from __future__ import annotations

import argparse
import json
import sys

from .tokens import load_tokens, render_css, render_tailwind

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="design-token-sync",
        description="Turn a design-tokens JSON file into CSS custom "
        "properties and a Tailwind v4 @theme block.",
    )
    parser.add_argument("input", help="design-tokens JSON file")
    parser.add_argument("--css", metavar="FILE",
                        help="write :root custom properties to FILE")
    parser.add_argument("--tailwind", metavar="FILE",
                        help="write Tailwind v4 @theme block to FILE")
    parser.add_argument("--check", action="store_true",
                        help="validate only: print a report, exit 1 on any error")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        tokens, report = load_tokens(args.input)
    except FileNotFoundError:
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {args.input}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr)
        return 1

    if args.check:
        sys.stdout.write(report.render(len(tokens)))
        return 0 if report.ok else 1

    if not args.css and not args.tailwind:
        print("error: nothing to do: pass --css FILE and/or --tailwind FILE "
              "(or --check to validate only)", file=sys.stderr)
        return 1

    if args.css:
        try:
            with open(args.css, "w", encoding="utf-8") as fh:
                fh.write(render_css(tokens))
        except OSError as exc:
            print(f"error: cannot write {args.css}: {exc}", file=sys.stderr)
            return 1

    if args.tailwind:
        try:
            with open(args.tailwind, "w", encoding="utf-8") as fh:
                fh.write(render_tailwind(tokens))
        except OSError as exc:
            print(f"error: cannot write {args.tailwind}: {exc}", file=sys.stderr)
            return 1

    sys.stdout.write(report.render(len(tokens)))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
