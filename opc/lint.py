"""Deterministic checks for the landing page. Used by the developer, the reviewer and compare.py."""
from __future__ import annotations

import html as htmllib
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict]] = []
        self.text: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k: (v or "") for k, v in attrs}))
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


def _norm(s: str) -> str:
    s = htmllib.unescape(s).lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def primary_tagline(copy_text: str) -> Optional[str]:
    m = re.search(r"\*\*Primary tagline:?\*\*:?\s*(.+)", copy_text, re.I)
    return re.sub(r"[*_\"“”]", "", m.group(1)).strip() if m else None


def lint_html(path: Path, copy_path: Optional[Path] = None) -> list[tuple[str, bool, str]]:
    raw = Path(path).read_text(errors="replace")
    c = _Collector()
    c.feed(raw)
    tags = c.tags
    visible = " ".join(c.text)
    res: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        res.append((name, bool(ok), detail))

    check("doctype present", re.match(r"\s*<!doctype html", raw, re.I))
    check("<html lang=...>", any(t == "html" and a.get("lang") for t, a in tags))
    title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    check("non-empty <title>", title and title.group(1).strip())
    check("responsive viewport meta", any(t == "meta" and a.get("name") == "viewport" for t, a in tags))
    h1s = sum(t == "h1" for t, _ in tags)
    check("exactly one <h1>", h1s == 1, f"found {h1s}")
    bad_imgs = [a for t, a in tags if t == "img" and "alt" not in a]
    check("all <img> have alt", not bad_imgs, f"{len(bad_imgs)} missing")
    ext = [a.get("src") or a.get("href") for t, a in tags
           if (t in ("script", "img", "iframe", "source") and (a.get("src", "").startswith(("http", "//"))))
           or (t == "link" and a.get("href", "").startswith(("http", "//")))]
    check("self-contained (no external assets)", not ext, ", ".join(filter(None, ext))[:80])
    check("size <= 60 KB", len(raw.encode()) <= 60_000, f"{len(raw.encode()) // 1024} KB")
    has_cta = any(t == "button" or (t == "input" and a.get("type") == "submit") or
                  (t == "a" and "cta" in a.get("class", "").lower()) for t, a in tags)
    check("has a call-to-action", has_cta)
    labels_for = {a.get("for") for t, a in tags if t == "label"}
    unlabeled = [a for t, a in tags if t == "input" and a.get("type", "text") not in ("hidden", "submit", "button")
                 and not (a.get("id") in labels_for or a.get("aria-label"))]
    check("form inputs are labelled", not unlabeled, f"{len(unlabeled)} unlabelled")
    check("has @media / responsive CSS", "@media" in raw)
    check("no lorem ipsum", "lorem ipsum" not in visible.lower())
    check("no raw [PLACEHOLDER] markers visible", "[placeholder" not in visible.lower())
    if copy_path and Path(copy_path).exists():
        tag = primary_tagline(Path(copy_path).read_text(errors="replace"))
        if tag:
            check("primary tagline from copy pack appears on page", _norm(tag) in _norm(visible), tag[:60])
        else:
            check("copy pack has '**Primary tagline:**' line", False, "cannot verify consistency")
    return res


def format_results(res: list[tuple[str, bool, str]]) -> str:
    lines = [f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else "")
             for name, ok, detail in res]
    passed = sum(ok for _, ok, _ in res)
    return "\n".join(lines) + f"\n\n{passed}/{len(res)} checks passed"
