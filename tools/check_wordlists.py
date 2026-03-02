from __future__ import annotations

from collections import Counter
from pathlib import Path

from spellchecker import SpellChecker


def main() -> int:
    words_dir = Path(__file__).resolve().parents[1] / "words"
    files = sorted(words_dir.glob("*.txt"))

    entries: list[tuple[str, int, str]] = []
    for file_path in files:
        for line_num, raw in enumerate(
            file_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            word = raw.strip()
            if not word:
                continue
            entries.append((file_path.name, line_num, word))

    print(f"Files: {len(files)}")
    print(f"Total words (non-empty lines): {len(entries)}")
    print()

    if not entries:
        print("No words found.")
        return 1

    # Duplicates (case-insensitive)
    normalized = [w.lower() for _, _, w in entries]
    dup_counts = Counter(normalized)
    duplicates = {w: c for w, c in dup_counts.items() if c > 1}

    if duplicates:
        print("Duplicates (case-insensitive):")
        for word, count in sorted(duplicates.items(), key=lambda kv: (-kv[1], kv[0])):
            locs = [(f, ln) for f, ln, w in entries if w.lower() == word]
            loc_str = ", ".join([f"{f}:{ln}" for f, ln in locs])
            print(f"  {word} x{count} ({loc_str})")
        print()
    else:
        print("No duplicates found.")
        print()

    # Formatting/character sanity checks
    issues: list[tuple[str, int, str, str]] = []
    for fname, line, word in entries:
        if any(ch.isspace() for ch in word):
            issues.append((fname, line, word, "contains whitespace"))
        if not all(ch.isalpha() or ch in "'-" for ch in word):
            issues.append(
                (
                    fname,
                    line,
                    word,
                    "contains non-letter characters (besides apostrophe/hyphen)",
                )
            )

    if issues:
        print("Formatting/character issues:")
        for fname, line, word, reason in issues:
            print(f"  {fname}:{line}: {word!r} -> {reason}")
        print()
    else:
        print("No formatting/character issues found.")
        print()

    # Spellcheck: SpellChecker doesn't always include contractions, so treat
    # apostrophe/hyphenated words specially by also checking their parts.
    spell = SpellChecker()

    def tokens_for_check(word: str) -> list[str]:
        word = word.lower()
        if "'" in word:
            parts = [p for p in word.split("'") if p]
            return [word, *parts]
        if "-" in word:
            parts = [p for p in word.split("-") if p]
            return [word, *parts]
        return [word]

    suspicious: list[tuple[str, int, str, list[str]]] = []
    for fname, line, word in entries:
        tokens = tokens_for_check(word)
        # Flag only if ALL tokens are unknown.
        if all(spell.unknown([t]) for t in tokens):
            suggestions = sorted(spell.candidates(word.lower()))[:8]
            suspicious.append((fname, line, word, suggestions))

    if suspicious:
        print("Possibly misspelled (SpellChecker unknown):")
        for fname, line, word, suggestions in suspicious:
            print(f"  {fname}:{line}: {word} | suggestions: {suggestions}")
        print()
    else:
        print("No spelling issues flagged by SpellChecker.")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
