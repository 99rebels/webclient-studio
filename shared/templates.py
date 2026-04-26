"""Minimal template renderer for Freelance Forge.

Two constructs only:
- {{var}}                         → context["var"] (or "" if missing)
- {{#section}} ... {{/section}}   → block rendered once per item if context["section"]
                                    is a list of dicts (each item becomes the inner context)
                                    or rendered once if it's truthy non-list / dict.
                                    Skipped entirely if missing or falsy.

No conditionals, no filters, no inheritance. Templates are starting points the
agent then adapts — overengineering the renderer would push too much logic into
markdown files.

Run as a module to render from the CLI (useful from SKILL.md):
    python -m templates render <path> --json '{"company": "Acme"}'
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


_SECTION_RE = re.compile(
    r"\{\{#(?P<name>[a-zA-Z_][\w\-.]*)\}\}(?P<body>.*?)\{\{/(?P=name)\}\}",
    re.DOTALL,
)
_VAR_RE = re.compile(r"\{\{(?P<name>[a-zA-Z_][\w\-.]*)\}\}")


def _resolve(name: str, context: dict[str, Any]) -> Any:
    """Dotted lookup. `client.name` walks context['client']['name']."""
    cursor: Any = context
    for part in name.split("."):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            return ""
    return cursor


def _render_sections(template: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        body = match.group("body")
        value = _resolve(name, context)
        if not value:
            return ""
        if isinstance(value, list):
            return "".join(render_string(body, {**context, **(item if isinstance(item, dict) else {"item": item})})
                           for item in value)
        if isinstance(value, dict):
            return render_string(body, {**context, **value})
        # Truthy scalar — render the body once with the value bound to "item"
        return render_string(body, {**context, "item": value})

    # Sections can nest — keep replacing until stable
    prev = None
    while prev != template:
        prev = template
        template = _SECTION_RE.sub(replace, template)
    return template


def _render_vars(template: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = _resolve(match.group("name"), context)
        return "" if value is None else str(value)
    return _VAR_RE.sub(replace, template)


def render_string(template: str, context: dict[str, Any]) -> str:
    """Render a template string against a context dict."""
    return _render_vars(_render_sections(template, context), context)


def _references_search_paths() -> list[Path]:
    """Where to look for templates when given a relative path.

    Order: env var > ~/.freelance-forge/references/ > sibling references/ > inside this module's dir.
    """
    paths: list[Path] = []
    env = os.environ.get("FREELANCE_FORGE_REFERENCES_DIR")
    if env:
        paths.append(Path(env).expanduser())
    # ~/.freelance-forge/references/ — the standard install location
    paths.append(Path.home() / ".freelance-forge" / "references")
    # Source-repo layout (for development)
    here = Path(__file__).resolve().parent
    paths.append(here.parent / "references")
    paths.append(here / "references")
    return paths


def render(template_path: str | Path, context: dict[str, Any]) -> str:
    """Render a template file against a context dict.

    Resolves relative paths via _references_search_paths().
    """
    p = Path(template_path)
    if not p.is_absolute():
        for base in _references_search_paths():
            candidate = base / p
            if candidate.exists():
                p = candidate
                break
    if not p.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    return render_string(p.read_text(), context)


# ---------------------------------------------------------------------------
# CLI shim
# ---------------------------------------------------------------------------

def _cmd_render(args: argparse.Namespace) -> None:
    if args.json:
        ctx = json.loads(args.json)
    elif args.json_file:
        ctx = json.loads(Path(args.json_file).read_text())
    else:
        ctx = json.loads(sys.stdin.read() or "{}")
    out = render(args.template, ctx)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out)
        print(args.out)
    else:
        print(out)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="templates")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("render")
    r.add_argument("template", help="Path to template (relative resolves under references/)")
    r.add_argument("--json", help="Inline JSON context")
    r.add_argument("--json-file", dest="json_file", help="Path to JSON context file")
    r.add_argument("--out", help="If given, write result here and print the path")
    r.set_defaults(func=_cmd_render)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
