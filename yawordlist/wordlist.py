from dataclasses import dataclass, field
from pathlib import Path
import random
from typing import List, Optional

import typer

# -----------------------------
# Data structures
# -----------------------------

@dataclass
class WordRecord:
    index: int
    word: str
    attempts: List[str] = field(default_factory=list)
    attempted: bool = False
    result: Optional[str] = None  # "correct" | "passed" | "stopped"

@dataclass
class SessionState:
    words: List[WordRecord]

    def get_pending_words(self) -> List[WordRecord]:
        return [w for w in self.words if not w.attempted]

    def get_attempted_words(self) -> List[WordRecord]:
        return [w for w in self.words if w.attempted]

# -----------------------------
# Utility functions
# -----------------------------

def _count_correct_attempts(record: WordRecord) -> int:
    return sum(1 for a in record.attempts if a.strip().lower() == record.word.lower())

def _count_incorrect_attempts(record: WordRecord, skip_command: str) -> int:
    skip_norm = skip_command.strip().lower()
    return sum(
        1
        for a in record.attempts
        if a.strip().lower() not in (record.word.lower(), skip_norm)
    )

def _attempt_bits(record: WordRecord, skip_command: str) -> List[int]:
    """Ordered correctness for spelling attempts: 1=correct, 0=incorrect.

    Skip token attempts are excluded.
    """
    skip_norm = skip_command.strip().lower()
    bits: List[int] = []
    for a in record.attempts:
        norm = a.strip().lower()
        if norm == skip_norm:
            continue
        bits.append(1 if norm == record.word.lower() else 0)
    return bits

def _attempt_marks(record: WordRecord, skip_command: str) -> str:
    marks = []
    for bit in _attempt_bits(record, skip_command=skip_command):
        marks.append("✔️" if bit == 1 else "❌")
    return " ".join(marks)

def _recompute_record_result(record: WordRecord, skip_command: str) -> None:
    """Recompute record.attempted and record.result from record.attempts.

    Note: "stopped" is a session-level state and should be set only when ending the session.
    """
    if not record.attempts:
        record.attempted = False
        record.result = None
        return

    record.attempted = True
    word_norm = record.word.lower()
    skip_norm = skip_command.strip().lower()
    attempt_norms = [a.strip().lower() for a in record.attempts]
    if any(a == word_norm for a in attempt_norms):
        record.result = "correct"
    elif any(a == skip_norm for a in attempt_norms):
        record.result = "passed"
    else:
        record.result = None

def _attempt_status_line(record: WordRecord, attempt: str, skip_command: str) -> str:
    attempt_stripped = attempt.strip()
    attempt_norm = attempt_stripped.lower()
    word = record.word
    word_norm = word.lower()
    skip_norm = skip_command.strip().lower()

    if attempt_norm == skip_norm:
        return f"Last: {attempt_stripped} -> PASS"

    if attempt_norm == word_norm:
        return f"Last: {attempt_stripped} -> CORRECT"

    # INCORRECT: find first mismatch (or early/extra termination)
    limit = min(len(attempt_stripped), len(word))
    for i in range(limit):
        got = attempt_stripped[i]
        expected = word[i]
        if got.lower() != expected.lower():
            return f"Last: {attempt_stripped} -> INCORRECT at pos {i + 1} (got '{got}', expected '{expected}')"

    if len(attempt_stripped) < len(word):
        expected = word[len(attempt_stripped)]
        return f"Last: {attempt_stripped} -> INCORRECT at pos {len(attempt_stripped) + 1} (got <end>, expected '{expected}')"

    # attempt longer than word
    got = attempt_stripped[len(word)] if len(attempt_stripped) > len(word) else ""
    return f"Last: {attempt_stripped} -> INCORRECT at pos {len(word) + 1} (got '{got}', expected <end>)"

def _print_word_context(record: WordRecord, skip_command: str, *, show_last: bool = False) -> None:
    """Print current word info.

    Always prints the word header with the current attempt number. When show_last=True,
    also prints the status of the most recent recorded attempt (if any).
    """
    print(f"\nWord #{record.index}: {record.word} (#{len(record.attempts) + 1})")
    if not show_last:
        return
    if not record.attempts:
        print("Last: (none)")
        return
    print(_attempt_status_line(record, record.attempts[-1], skip_command=skip_command))

def print_progress_table(state: SessionState, skip_command: str) -> None:
    print("\nProgress table:")
    print("-" * 120)
    header = f"{'#':<3} {'Word':<15} {'Attempts':<8} {'Correct':<8} {'Incorrect':<10} {'State':<6} {'Result'}"
    print(header)
    print("-" * 120)
    for w in state.words:
        attempts_count = len(w.attempts)
        correct_count = _count_correct_attempts(w)
        incorrect_count = _count_incorrect_attempts(w, skip_command=skip_command)
        state_icon = "⏳" if not w.attempted else "✅"
        if w.result == "correct":
            result = "✔️"
        elif w.result == "passed":
            result = "PASS"
        elif w.result == "stopped":
            result = "STOP"
        else:
            result = ""
        row = f"{w.index:<3} {w.word:<15} {attempts_count:<8} {correct_count:<8} {incorrect_count:<10} {state_icon:<6} {result}"
        print(row)
    print("-" * 120)

def prompt_yes_no(prompt: str, default: Optional[bool] = None) -> bool:
    while True:
        if default is True:
            suffix = "[Y/n]"
        elif default is False:
            suffix = "[y/N]"
        else:
            suffix = "[y/n]"

        ans = input(f"{prompt} {suffix}: ").strip().lower()
        if ans == "" and default is not None:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Enter y or n.\n")

def choose_skip_command(words: List[str], base: str = "/pass") -> str:
    words_lower = {w.strip().lower() for w in words}
    cmd = base
    while cmd.strip().lower() in words_lower:
        cmd += "!"
    return cmd

def _get_key_event() -> Optional[str]:
    """Read a single key event (Windows only).

    Returns:
      - Regular characters as a 1-length string
      - "<UP>", "<DOWN>", "<LEFT>", "<RIGHT>" for arrow keys
      - None for ignored keys
    """
    import msvcrt

    ch = msvcrt.getwch()
    # Ignore special keys (arrows/function keys) which come as a two-character sequence.
    if ch in ("\x00", "\xe0"):
        code = msvcrt.getwch()
        return {
            "H": "<UP>",
            "P": "<DOWN>",
            "K": "<LEFT>",
            "M": "<RIGHT>",
        }.get(code)
    return ch

# -----------------------------
# Core game logic
# -----------------------------

def run_spelling_session(words: List[str], skip_command: str) -> SessionState:
    # Create session state
    state = SessionState(
        words=[WordRecord(index=i + 1, word=w) for i, w in enumerate(words)]
    )

    word_index = 0
    undo_command = "/undo"
    show_last_on_entry = False

    while 0 <= word_index < len(state.words):
        record = state.words[word_index]
        current = ""
        position = 0

        def print_input_prompt() -> None:
            print("> ", end="", flush=True)

        print_progress_table(state, skip_command=skip_command)
        _print_word_context(record, skip_command=skip_command, show_last=show_last_on_entry)
        show_last_on_entry = False

        print_input_prompt()

        while True:
            ev = _get_key_event()
            if ev is None:
                continue

            # Navigation does not record or alter attempts.
            if ev == "<UP>":
                if word_index > 0:
                    print()
                    word_index -= 1
                    show_last_on_entry = True
                    break
                continue

            if ev == "<DOWN>":
                if word_index < len(state.words) - 1:
                    print()
                    word_index += 1
                    show_last_on_entry = True
                    break
                continue

            # Ctrl+C ends session (summary).
            if ev == "\x03":
                print()
                record.attempted = True
                record.result = "stopped"
                return state

            # Ctrl+Z undoes the last recorded attempt for this word.
            if ev == "\x1a":
                if not record.attempts:
                    continue
                record.attempts.pop()
                _recompute_record_result(record, skip_command=skip_command)
                print("\nUNDO\n")
                _print_word_context(record, skip_command=skip_command, show_last=True)
                current = ""
                position = 0
                print_input_prompt()
                continue

            # Enter submits the current attempt if non-empty; if empty, advances (or ends if last word).
            if ev in ("\r", "\n"):
                print()
                if current:
                    record.attempts.append(current)
                    record.attempted = True
                    if current.strip().lower() == record.word.lower():
                        record.result = "correct"
                    current = ""
                    position = 0
                    _print_word_context(record, skip_command=skip_command)
                    print_input_prompt()
                    continue

                # Empty enter: proceed to next word, or finish if last.
                if word_index == len(state.words) - 1:
                    record.attempted = True
                    record.result = "stopped"
                    return state
                word_index += 1
                break

            # Backspace
            if ev in ("\b", "\x7f"):
                if current:
                    current = current[:-1]
                    if current.startswith("/"):
                        position = 0
                    else:
                        position = len(current)
                    print("\b \b", end="", flush=True)
                continue

            # Start / command mode (can be entered even mid-typing).
            if ev == "/":
                if current:
                    print()
                    print_input_prompt()
                current = "/"
                position = 0
                print("/", end="", flush=True)
                continue

            # Command mode for skip/undo tokens
            if current.startswith("/"):
                # Ignore non-printing events.
                if len(ev) != 1:
                    continue
                current += ev
                print(ev, end="", flush=True)

                cur_norm = current.strip().lower()
                skip_norm = skip_command.strip().lower()
                undo_norm = undo_command.strip().lower()

                if cur_norm == undo_norm:
                    if record.attempts:
                        record.attempts.pop()
                        _recompute_record_result(record, skip_command=skip_command)
                    print("\nUNDO\n")

                    _print_word_context(record, skip_command=skip_command, show_last=True)
                    current = ""
                    position = 0
                    print_input_prompt()
                    continue

                if cur_norm == skip_norm:
                    print("\nPASS\n")
                    record.attempts.append(skip_command)
                    record.attempted = True
                    if record.result != "correct":
                        record.result = "passed"
                    if word_index < len(state.words) - 1:
                        word_index += 1
                        break
                    return state

                if not (skip_norm.startswith(cur_norm) or undo_norm.startswith(cur_norm)):
                    print("\nInvalid command.\n")
                    current = ""
                    position = 0
                    print_input_prompt()
                continue

            # Letter mode
            if len(ev) != 1 or not ev.isprintable() or ev.isspace():
                continue

            expected = record.word[position]
            if ev.lower() != expected.lower():
                attempt = f"{current}{ev}"
                print(f"\nIncorrect letter '{ev}' at position {position + 1} (expected '{expected}').\n")
                record.attempts.append(attempt)
                record.attempted = True
                current = ""
                position = 0
                _print_word_context(record, skip_command=skip_command)
                print_input_prompt()
                continue

            current += ev
            position += 1
            print(ev, end="", flush=True)

            if position == len(record.word):
                print("\nCORRECT\n")
                record.attempts.append(current)
                record.attempted = True
                record.result = "correct"
                current = ""
                position = 0
                _print_word_context(record, skip_command=skip_command)
                print_input_prompt()

    return state

# -----------------------------
# Summary
# -----------------------------

def print_session_summary(state: SessionState, skip_command: str) -> None:
    attempted = state.get_attempted_words()
    total_words = len(state.words)
    total_attempted = len(attempted)
    total_correct = sum(1 for w in attempted if w.result == "correct")
    total_passed = sum(1 for w in attempted if w.result == "passed")
    total_stopped = sum(1 for w in attempted if w.result == "stopped")
    total_attempts = sum(len(w.attempts) for w in attempted)
    spelling_attempts = sum(
        1
        for w in attempted
        for a in w.attempts
        if a.strip().lower() != skip_command.strip().lower()
    )
    attempts_per_word = (spelling_attempts / total_attempted) if total_attempted else 0.0
    correct_per_attempt = (total_correct / spelling_attempts * 100) if spelling_attempts else 0.0
    attempts_per_correct = (spelling_attempts / total_correct) if total_correct else None

    print("\nSESSION SUMMARY")
    print("=" * 40)
    print(f"Total words:       {total_words}")
    print(f"Attempted:         {total_attempted}")
    print(f"Correct:           {total_correct}")
    print(f"Passed:            {total_passed}")
    print(f"Stopped early:     {total_stopped}")
    print(f"Total attempts:    {total_attempts}")
    print(f"Spelling attempts: {spelling_attempts}")
    print(f"Attempts/word:     {attempts_per_word:.2f}")
    if attempts_per_correct is None:
        print("Attempts/correct:  n/a")
    else:
        print(f"Attempts/correct:  {attempts_per_correct:.2f}")
    print(f"Correct/attempt:   {correct_per_attempt:.1f}%")

    print("\nAttempts by word:")
    for w in attempted:
        attempts_str = ", ".join(w.attempts) if w.attempts else "(none)"
        result = w.result or ""
        correct_count = _count_correct_attempts(w)
        incorrect_count = _count_incorrect_attempts(w, skip_command=skip_command)
        marks = _attempt_marks(w, skip_command=skip_command)
        if marks:
            print(
                f"  Word #{w.index} ({w.word}) {result} | correct={correct_count} incorrect={incorrect_count} | {marks}: {attempts_str}"
            )
        else:
            print(
                f"  Word #{w.index} ({w.word}) {result} | correct={correct_count} incorrect={incorrect_count} | {attempts_str}"
            )

    print("\nSummary complete.\n")

# -----------------------------
# Entry point
# -----------------------------

def _default_words_dir() -> Path:
    # Project layout:
    #   <repo-root>/words/*.txt
    #   <repo-root>/yawordlist/wordlist.py
    return Path(__file__).resolve().parents[1] / "words"


def load_word_modules(words_dir: Optional[Path] = None) -> List[List[str]]:
    """Load words from all .txt files in a directory.

    Returns a list of "modules", one per file, where each module is the list of
    words (lowercased, preserving duplicates).
    """
    base_dir = words_dir if words_dir is not None else _default_words_dir()

    if base_dir.exists() and base_dir.is_file():
        raise ValueError(f"Expected a directory, but got a file path: {base_dir}")

    if not base_dir.exists():
        raise FileNotFoundError(
            f"Required directory not found: {base_dir}\n"
            "Create a 'words' folder in the project root and add one or more .txt files.\n"
            "Each .txt file should contain one word per line.\n"
            "Example file: words/words_wk1.txt\n"
            "  because\n"
            "  friend\n"
            "  beautiful\n"
        )

    txt_files = sorted(base_dir.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(
            f"No .txt files found in: {base_dir}\n"
            "Add one or more files like 'words/words_wk1.txt' with one word per line.\n"
        )

    modules: List[List[str]] = []
    for path in txt_files:
        text = path.read_text(encoding="utf-8")
        words = [line.strip().lower() for line in text.splitlines() if line.strip()]
        if words:
            modules.append(words)

    if not modules:
        raise ValueError(f"No words found in any .txt files under: {base_dir}")

    return modules


def load_words(*, level: int = 1, words_dir: Optional[Path] = None) -> List[str]:
    """Load words using module-based shuffling.

    level=1 (default): shuffle within each file/module, but never mix words between files.
    level=2: mix all words from all files, then shuffle together.
    """
    modules = load_word_modules(words_dir=words_dir)

    if level == 1:
        out: List[str] = []
        for module_words in modules:
            random.shuffle(module_words)
            out.extend(module_words)
        return out

    if level == 2:
        out = [w for module_words in modules for w in module_words]
        random.shuffle(out)
        return out

    raise ValueError("level must be 1 or 2")

app = typer.Typer(add_completion=False)


@app.command()
def main(
    level: int = typer.Option(
        1,
        "--level",
        "-l",
        min=1,
        max=2,
        help="1 = shuffle within each file; 2 = mix all files then shuffle",
    ),
):
    try:
        words = load_words(level=level)
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        raise typer.Exit(code=1)

    skip_command = choose_skip_command(words, base="/pass")

    print("Structured Spelling Game (letter-by-letter mode)\n")

    # Confirm list with user
    print("Loaded word list:")
    for i, w in enumerate(words, start=1):
        print(f"{i:2d}. {w}")
    print()

    if not prompt_yes_no("Confirm this is the list you want to use?", default=True):
        print("\nExiting. Update input list to continue.")
        raise typer.Exit(code=0)

    print(f"\nSkip token: {skip_command}\n")

    state = run_spelling_session(words, skip_command=skip_command)
    print_session_summary(state, skip_command=skip_command)


if __name__ == "__main__":
    app()