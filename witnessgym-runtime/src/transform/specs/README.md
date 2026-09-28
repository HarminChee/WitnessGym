Authoritative transform spec directory for WITNESSGYM.

Each JSON file defines one transform spec loaded by:
  src/transform/registry.py -> TransformRegistry.load(specs_dir)

Do not create duplicate transform specs elsewhere.
If experimenting, place temporary variants under:
  attic/transforms_unused/
