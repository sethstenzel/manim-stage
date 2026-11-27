"""Token diff between two versions of source code (spec F05, backlog 2.6; ADR-0008).

Pure Python, no Manim. Given the tokens of the old and the new code, decide which
token *is the same token* in both (it will slide to its new place), which disappear
(fade out) and which are new (fade in). Motion Canvas does this with a token-level
patience diff; we do:

1. **Patience diff on lines.** Lines that occur exactly once on each side anchor the
   alignment; between anchors we recurse, then fall back to an LCS (``difflib``).
   Patience keeps unrelated blocks from being matched through common lines like ``}``.
2. **Equal lines** keep all their tokens.
3. **Moved lines.** A non-blank line deleted in one place and inserted elsewhere with
   identical text is a *move*: its tokens slide.
4. **Changed blocks.** Between the remaining deleted and inserted lines, tokens are
   matched by an LCS on token text, so ``a = 1`` → ``a = 2`` keeps ``a`` and ``=``.
5. **Overrides.** ``mapping={old_index: new_index}`` pins pairs first (e.g. to say
   which of two identical ``x`` tokens moved). ``None`` as the new index forces a
   fade-out.

Repeated identical tokens are ambiguous; the result lists them in ``warnings`` (with
the line numbers) so you can add an override when the default isn't what you mean.
Whitespace never matters: tokens carry their own positions.

"""

from __future__ import annotations

import difflib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


class TokenLike(Protocol):
    line: int
    col: int
    text: str


@dataclass
class CodeDiff:
    matches: list[tuple[int, int]] = field(default_factory=list)  # (old, new) token index
    deleted: list[int] = field(default_factory=list)
    inserted: list[int] = field(default_factory=list)
    moved_lines: list[tuple[int, int]] = field(default_factory=list)  # (old line, new line)
    warnings: list[str] = field(default_factory=list)

    def new_for_old(self) -> dict[int, int]:
        return dict(self.matches)


def _lines(tokens: Sequence[TokenLike]) -> dict[int, list[int]]:
    by: dict[int, list[int]] = {}
    for i, t in enumerate(tokens):
        by.setdefault(t.line, []).append(i)
    return by


def _line_keys(tokens: Sequence[TokenLike], n_lines: int) -> list[str]:
    """Each line as a whitespace-insensitive key (tokens joined by a separator)."""
    by = _lines(tokens)
    return ["\x00".join(tokens[i].text for i in by.get(ln, [])) for ln in range(1, n_lines + 1)]


def patience(a: Sequence[str], b: Sequence[str]) -> list[tuple[int, int]]:
    """Matching index pairs of two sequences (patience diff, LCS fallback)."""
    out: list[tuple[int, int]] = []

    def rec(a0: int, a1: int, b0: int, b1: int) -> None:
        # trim equal prefix/suffix
        while a0 < a1 and b0 < b1 and a[a0] == b[b0]:
            out.append((a0, b0))
            a0, b0 = a0 + 1, b0 + 1
        tail = []
        while a0 < a1 and b0 < b1 and a[a1 - 1] == b[b1 - 1]:
            a1, b1 = a1 - 1, b1 - 1
            tail.append((a1, b1))
        if a0 < a1 and b0 < b1:
            ca, cb = Counter(a[a0:a1]), Counter(b[b0:b1])
            pos_b = {b[j]: j for j in range(b0, b1) if cb[b[j]] == 1}
            uniq = [(i, pos_b[a[i]]) for i in range(a0, a1) if ca[a[i]] == 1 and a[i] in pos_b]
            anchors = _lis(uniq)
            if anchors:
                pa, pb = a0, b0
                for i, j in anchors:
                    rec(pa, i, pb, j)
                    out.append((i, j))
                    pa, pb = i + 1, j + 1
                rec(pa, a1, pb, b1)
            else:
                sm = difflib.SequenceMatcher(None, list(a[a0:a1]), list(b[b0:b1]), autojunk=False)
                for blk in sm.get_matching_blocks():
                    for k in range(blk.size):
                        out.append((a0 + blk.a + k, b0 + blk.b + k))
        out.extend(reversed(tail))

    rec(0, len(a), 0, len(b))
    return sorted(out)


def _lis(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Longest increasing subsequence by the second element (patience sorting)."""
    import bisect

    tails: list[int] = []
    tails_idx: list[int] = []
    prev = [-1] * len(pairs)
    for k, (_i, j) in enumerate(pairs):
        p = bisect.bisect_left(tails, j)
        if p == len(tails):
            tails.append(j)
            tails_idx.append(k)
        else:
            tails[p] = j
            tails_idx[p] = k
        prev[k] = tails_idx[p - 1] if p else -1
    seq, k = [], tails_idx[-1] if tails_idx else -1
    while k >= 0:
        seq.append(pairs[k])
        k = prev[k]
    return seq[::-1]


def diff_tokens(
    old: Sequence[TokenLike],
    new: Sequence[TokenLike],
    *,
    mapping: dict[int, int | None] | None = None,
) -> CodeDiff:
    result = CodeDiff()
    pinned_old: set[int] = set()
    pinned_new: set[int] = set()
    for o, n in (mapping or {}).items():
        if not 0 <= o < len(old):
            raise IndexError(f"mapping: no old token {o}")
        pinned_old.add(o)
        if n is None:
            result.deleted.append(o)
            continue
        if not 0 <= n < len(new):
            raise IndexError(f"mapping: no new token {n}")
        if n in pinned_new:
            raise ValueError(f"mapping: new token {n} is the target of two old tokens")
        pinned_new.add(n)
        result.matches.append((o, n))

    n_old = max((t.line for t in old), default=0)
    n_new = max((t.line for t in new), default=0)
    keys_a, keys_b = _line_keys(old, n_old), _line_keys(new, n_new)
    lines_a, lines_b = _lines(old), _lines(new)
    line_pairs = patience(keys_a, keys_b)
    matched_a = {i for i, _ in line_pairs}
    matched_b = {j for _, j in line_pairs}

    def pair_line(la: int, lb: int) -> None:  # 0-based line indices with equal text
        for o, n in zip(lines_a.get(la + 1, []), lines_b.get(lb + 1, []), strict=False):
            if o not in pinned_old and n not in pinned_new:
                result.matches.append((o, n))
                pinned_old.add(o)
                pinned_new.add(n)

    for la, lb in line_pairs:
        pair_line(la, lb)

    # moved lines: identical, non-blank, unmatched lines on both sides
    free_a = [i for i in range(n_old) if i not in matched_a and keys_a[i]]
    free_b = [j for j in range(n_new) if j not in matched_b and keys_b[j]]
    by_key_b: dict[str, list[int]] = {}
    for j in free_b:
        by_key_b.setdefault(keys_b[j], []).append(j)
    for i in free_a:
        cands = by_key_b.get(keys_a[i])
        if cands:
            j = cands.pop(0)
            pair_line(i, j)
            result.moved_lines.append((i + 1, j + 1))
            matched_a.add(i)
            matched_b.add(j)

    # changed blocks: token LCS over the remaining tokens, block by block in order
    rest_a = [k for k in range(len(old)) if k not in pinned_old]
    rest_b = [k for k in range(len(new)) if k not in pinned_new]
    sm = difflib.SequenceMatcher(
        None, [old[k].text for k in rest_a], [new[k].text for k in rest_b], autojunk=False
    )
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            o, n = rest_a[blk.a + k], rest_b[blk.b + k]
            result.matches.append((o, n))
            pinned_old.add(o)
            pinned_new.add(n)

    result.deleted = sorted(
        set(result.deleted) | {k for k in range(len(old)) if k not in pinned_old}
    )
    result.inserted = sorted(k for k in range(len(new)) if k not in pinned_new)
    result.matches.sort()
    result.warnings = _ambiguities(old, new, result)
    return result


def _ambiguities(old: Sequence[TokenLike], new: Sequence[TokenLike], d: CodeDiff) -> list[str]:
    """Matched tokens whose text repeats among the changed tokens on both sides."""
    changed_old = Counter(
        old[o].text for o, n in d.matches if old[o].line != new[n].line or old[o].col != new[n].col
    )
    changed_old.update(old[o].text for o in d.deleted)
    changed_new = Counter(new[n].text for n in d.inserted)
    changed_new.update(
        new[n].text for o, n in d.matches if old[o].line != new[n].line or old[o].col != new[n].col
    )
    out = []
    for text, count in sorted(changed_old.items()):
        if count > 1 and changed_new.get(text, 0) > 1 and text.strip(",;:()[]{}"):
            lines = sorted({old[o].line for o in range(len(old)) if old[o].text == text})
            out.append(
                f"token {text!r} repeats ({count}x) where code changed (old lines "
                f"{lines[:6]}); pass mapping= if the wrong copy moves"
            )
    return out
