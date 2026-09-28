# Install the WitnessGym skill

Run `python3 scripts/install_skill.py --destination /absolute/path/to/skills` from this code checkout. The destination receives `witnessgym/SKILL.md`, interface metadata, and a self-contained `runtime/` code tree. Existing installations are never overwritten.

Reload the host's skills and invoke `$witnessgym`. The portable command can be installed with `python3 -m pip install /path/to/skills/witnessgym/runtime`, preferably in a dedicated virtual environment. Alternatively, the skill can run it with `PYTHONPATH=/path/to/skills/witnessgym/runtime/src python3 -m witnessgym`.

The original four Java/Maven skills remain in the checkout for compatibility. Their wrapper scripts assume sibling `witnessgym-runtime/`; do not install these directories in isolation. The unified skill routes to them only when the requested project needs that workflow.
