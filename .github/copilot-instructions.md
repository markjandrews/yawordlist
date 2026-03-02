
# Workspace Copilot Instructions

1. For every request, explicitly say you have read this file.

2. Absolute minimal implementation only. Challenge any unnecessary engineering.

3. Comments: only brief notes when code paths are ambiguous or overly complicated.

4. Do not consider fallback, legacy, or compatibility options unless explicitly asked.

5. Inputs are trusted. Avoid defense-in-depth guards; add gates/guards only when necessary or explicitly requested.

6. When running Python commands, always check for an existing virtual environment first.
	- Prefer `.venv`/`venv` in the workspace root if present.
	- Never create a new virtual environment.
	- If you install dependencies into an existing venv, update `requirements.txt`.

