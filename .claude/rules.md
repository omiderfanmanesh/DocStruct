# DocStruct Rules

- Prefer changes under `src/docstruct/` with clear layer boundaries.
- Keep domain code free of provider SDK imports.
- Preserve CLI behavior for `python -m docstruct extract` and `python -m docstruct fix`.
- Update tests alongside refactors and keep them runnable from repo root.

