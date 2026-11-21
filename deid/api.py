"""Shared interfaces for the de-identification pipeline.

Every format handler lives in deid/handlers/<name>.py and exposes a module-level
`HANDLER = <Handler subclass instance>`. Handlers never invent pseudonyms: all
replacement goes through the `Replacer` passed in.

All pseudonyms are LENGTH-PRESERVING (same number of characters, same character
classes), so `Replacer.data()` returns bytes of exactly the same length as its
input. That lets handlers patch binary containers in place.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

# Candidate kinds reported by harvest().
KINDS = (
    "PERSON",    # a human name: "John Smith", "J. Smith"
    "ORG",       # company, university, lab, team
    "ACCOUNT",   # login / handle / OS user name: "jsmith", "BCN3D"
    "EMAIL",
    "DOMAIN",    # host or domain: "acme.com", "www.acme.de"
    "URL",
    "PHONE",
    "ADDRESS",   # street / postal address
    "PROJECT",   # project, product or repo name
    "PARTNO",    # company-specific part or drawing number
    "HOST",      # machine / workstation name
    "PATH",      # a filesystem path as stored in a file (may contain user names): r"C:\Users\jsmith\Desktop\x.sldprt"
    "FREETEXT",  # free text that probably contains identifiers (title block line, comment, description)
)


@dataclass
class Cand:
    """One candidate identifier found by a handler during harvest."""

    kind: str            # one of KINDS
    value: str           # the string exactly as found (decoded to str)
    field: str           # where: "step.header.author", "pdf.info.Author", "ole.summary.last_saved_by", ...
    conf: float = 1.0    # 1.0 = this field is an identity field by definition; lower = heuristic guess


class Replacer:
    """Interface of the global replacer (implemented in deid/identity.py).

    Guarantees: deterministic, context-free, length-preserving.
    """

    def text(self, s: str) -> str:
        """Replace every known identifier inside a unicode string. len(result) == len(s)."""
        raise NotImplementedError

    def data(self, b: bytes) -> bytes:
        """Replace identifiers inside raw bytes, wherever they occur encoded as ASCII/UTF-8,
        UTF-16LE (and common legacy code pages for non-ASCII names). len(result) == len(b).
        Safe to call on arbitrary binary data; returns `b` itself (same object) when nothing matched."""
        raise NotImplementedError

    def field(self, kind: str, value: str) -> str:
        """Pseudonym for a WHOLE identity-field value (author, company, user name ...), even if this exact
        value was never harvested. Same length as `value`. Use for fields that are identity fields by
        definition (PDF /Author, OLE 'Last saved by', STEP author ...). Empty or placeholder values
        ('', 'unknown', 'none', '-') are returned unchanged."""
        raise NotImplementedError

    def name(self, component: str) -> str:
        """New name for one path component (file or folder name). Same as text() but never produces
        characters that are illegal in file names."""
        raise NotImplementedError

    def hits(self, s: str) -> list[tuple[int, int, str]]:
        """(start, end, replacement) for each match in `s`; for handlers that need positions."""
        raise NotImplementedError


class DictReplacer(Replacer):
    """Trivial stand-in for tests: literal, case-sensitive, same-length replacements from a dict.

    Use it in handler self-tests until deid/identity.py exists:
        R = DictReplacer({"John Smith": "Mark Jones", "acme": "bolt"})
    """

    def __init__(self, mapping: dict[str, str]):
        for k, v in mapping.items():
            if len(k) != len(v):
                raise ValueError(f"not length-preserving: {k!r} -> {v!r}")
        self.mapping = dict(sorted(mapping.items(), key=lambda kv: -len(kv[0])))
        self._rx = re.compile("|".join(re.escape(k) for k in self.mapping)) if self.mapping else None
        bm: dict[bytes, bytes] = {}
        for k, v in self.mapping.items():
            for enc in ("utf-8", "utf-16-le"):
                bm[k.encode(enc)] = v.encode(enc)
        self._bmap = bm
        self._brx = re.compile(b"|".join(re.escape(k) for k in sorted(bm, key=len, reverse=True))) if bm else None

    def text(self, s: str) -> str:
        return self._rx.sub(lambda m: self.mapping[m.group(0)], s) if self._rx else s

    def data(self, b: bytes) -> bytes:
        if not self._brx or not self._brx.search(b):
            return b
        return self._brx.sub(lambda m: self._bmap[m.group(0)], b)

    def field(self, kind: str, value: str) -> str:
        if value.strip().lower() in ("", "unknown", "none", "-", "n/a"):
            return value
        out = self.text(value)
        if out != value:
            return out
        # deterministic same-shape fallback so tests can see that the field was pseudonymized
        return "".join(
            "X" if c.isupper() else "x" if c.islower() else c for c in value
        )

    def name(self, component: str) -> str:
        return self.text(component)

    def hits(self, s: str) -> list[tuple[int, int, str]]:
        return [(m.start(), m.end(), self.mapping[m.group(0)]) for m in self._rx.finditer(s)] if self._rx else []


@dataclass
class Ctx:
    """Services the orchestrator gives to handlers (mainly for containers/archives)."""

    tmpdir: str = "/tmp"
    # Recursively harvest a member file that a container handler extracted to disk.
    # harvest_member(path_on_disk, member_name) -> list[Cand]
    harvest_member: Optional[Callable[[str, str], list]] = None
    # Recursively rewrite an extracted member. rewrite_member(path_on_disk, member_name) -> path of the
    # rewritten file, or None when the member needs no change. The member NAME is renamed by the
    # container handler itself with R.name() on each path component.
    rewrite_member: Optional[Callable[[str, str], Optional[str]]] = None
    notes: list = field(default_factory=list)   # handlers append human-readable problems here

    def note(self, msg: str) -> None:
        self.notes.append(msg)


class Handler:
    """Base class for format handlers."""

    name = "base"
    exts: tuple[str, ...] = ()        # lower-case extensions incl. dot, e.g. (".step", ".stp")

    def sniff(self, path: str, head: bytes) -> bool:
        """Optional content check on the first 4 KB; default: trust the extension."""
        return True

    def harvest(self, src: str, ctx: Ctx) -> Iterable[Cand]:
        """Report candidate identifiers found in the file at `src`. Must not modify anything."""
        return ()

    def rewrite(self, src: str, dst: str, R: Replacer, ctx: Ctx) -> bool:
        """Write a de-identified copy of `src` to `dst`.

        Return True if `dst` was written (content changed), False if the file needs no change
        (then `dst` must not exist). Never modify `src`. On any doubt about breaking the file,
        leave that part unchanged and ctx.note() it.
        """
        return False
