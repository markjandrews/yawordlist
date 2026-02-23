from dataclasses import dataclass, field
from pathlib import Path
import random
from typing import List, Optional
import textwrap

# -----------------------------
# Data structures
# -----------------------------

@dataclass
class WordRecord:
    index: int
    word: str
    attempts: List[str] = field(default_factory=list)
    attempt_notes: List[str] = field(default_factory=list)
    attempted: bool = False
    correct: Optional[bool] = None
    notes: str = ""

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

def print_progress_table(state: SessionState) -> None:
    print("\nProgress table:")
    print("-" * 120)
    header = f"{'#':<3} {'Word':<15} {'Attempts':<8} {'Attempted':<10} {'Correct':<8} {'Notes'}"
    print(header)
    print("-" * 120)
    for w in state.words:
        attempts_count = len(w.attempts)
        attempted = "⏳" if not w.attempted else "✅"
        correct = "" if w.correct is None else ("✔️" if w.correct else "❌")
        notes = w.notes
        row = f"{w.index:<3} {w.word:<15} {attempts_count:<8} {attempted:<10} {correct:<8} {notes}"
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

def wrap_input(prompt: str) -> str:
    return input(textwrap.fill(prompt, width=80) + "\n> ").strip()

def choose_skip_command(words: List[str], base: str = "/pass") -> str:
    words_lower = {w.strip().lower() for w in words}
    cmd = base
    while cmd.strip().lower() in words_lower:
        cmd += "!"
    return cmd

# -----------------------------
# Core game logic
# -----------------------------

def run_spelling_session(words: List[str], skip_command: str) -> SessionState:
    # Create session state
    state = SessionState(
        words=[WordRecord(index=i + 1, word=w) for i, w in enumerate(words)]
    )

    # Main loop over words
    for record in state.words:
        aggregated_attempt_notes: List[str] = []
        passed = False
        while True:
            print(f"Word #{record.index}: {record.word}")
            attempt = wrap_input(f"Attempt (blank to end, {skip_command} to skip):")
            if attempt == "":
                if record.attempts:
                    record.attempted = True
                    record.correct = any(a.strip().lower() == record.word.lower() for a in record.attempts)
                    record.notes = "\n".join(aggregated_attempt_notes)
                return state
            if attempt.strip().lower() == skip_command.strip().lower():
                record.attempts.append(skip_command)
                attempt_note = input("Notes: ").strip()
                record.attempt_notes.append(attempt_note)
                if attempt_note:
                    aggregated_attempt_notes.append(f"Attempt #{len(record.attempts)}: {attempt_note}")
                passed = True
                break
            record.attempts.append(attempt)

            is_correct = (attempt.strip().lower() == record.word.lower())

            print(f"Recorded attempt #{len(record.attempts)}: '{attempt}' -> {'CORRECT' if is_correct else 'INCORRECT'}")

            attempt_note = input("Notes: ").strip()
            record.attempt_notes.append(attempt_note)
            if attempt_note:
                aggregated_attempt_notes.append(f"Attempt #{len(record.attempts)}: {attempt_note}")

            if is_correct:
                break

        record.attempted = True
        if passed:
            record.correct = False
        else:
            record.correct = any(a.strip().lower() == record.word.lower() for a in record.attempts)

        record.notes = "\n".join(aggregated_attempt_notes)

        # Update progress table after each word
        print_progress_table(state)

    return state

# -----------------------------
# Summary
# -----------------------------

def print_session_summary(state: SessionState) -> None:
    attempted = state.get_attempted_words()
    total_words = len(state.words)
    total_attempted = len(attempted)
    total_correct = sum(1 for w in attempted if w.correct)
    total_attempts = sum(len(w.attempts) for w in attempted)
    attempts_per_word = (total_attempts / total_attempted) if total_attempted else 0.0
    correct_per_attempt = (total_correct / total_attempts * 100) if total_attempts else 0.0
    attempts_per_correct = (total_attempts / total_correct) if total_correct else None

    print("\nSESSION SUMMARY")
    print("=" * 40)
    print(f"Total words:       {total_words}")
    print(f"Attempted:         {total_attempted}")
    print(f"Correct:           {total_correct}")
    print(f"Total attempts:    {total_attempts}")
    print(f"Attempts/word:     {attempts_per_word:.2f}")
    if attempts_per_correct is None:
        print("Attempts/correct:  n/a")
    else:
        print(f"Attempts/correct:  {attempts_per_correct:.2f}")
    print(f"Correct/attempt:   {correct_per_attempt:.1f}%")

    # Notes
    print("\nNotes:")
    for w in attempted:
        if w.notes:
            print(f"  Word #{w.index} ({w.word}): {w.notes}")

    print("\nSummary complete.\n")

# -----------------------------
# Entry point
# -----------------------------

def load_words_from_file(words_path: Optional[Path] = None) -> List[str]:
    """Load a word list from a text file (one word per line)."""
    if words_path is None:
        # Project layout:
        #   <repo-root>/words.txt
        #   <repo-root>/yawordlist/wordlist.py
        words_path = Path(__file__).resolve().parents[1] / "words.txt"

    try:
        text = words_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Required file not found: {words_path}\n"
            "Create words.txt in the project root (same folder as setup files).\n"
            "Format: one word per line.\n"
            "Example:\n"
            "  because\n"
            "  friend\n"
            "  beautiful\n"
        ) from e

    words = [line.strip().lower() for line in text.splitlines() if line.strip()]
    if not words:
        raise ValueError(f"No words found in: {words_path}")
    return words

def main():
    try:
        words = load_words_from_file()
    except (FileNotFoundError, ValueError) as e:
        print(str(e))
        return

    random.shuffle(words)

    skip_command = choose_skip_command(words)

    print("Structured Spelling Game\n")

    # Confirm list with user
    print("Loaded word list:")
    for i, w in enumerate(words, start=1):
        print(f"{i:2d}. {w}")
    print()

    if not prompt_yes_no("Confirm this is the list you want to use?", default=True):
        print("\nExiting. Update input list to continue.")
        return

    state = run_spelling_session(words, skip_command=skip_command)
    print_session_summary(state)

if __name__ == "__main__":
    main()