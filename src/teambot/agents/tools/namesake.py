from __future__ import annotations

VALID_NAMESAKE_STRATEGIES = {"skip", "override", "raise", "rename"}


def normalize_namesake_strategy(strategy: str | None) -> str:
    raw = (strategy or "").strip().lower()
    if raw in VALID_NAMESAKE_STRATEGIES:
        return raw
    return "skip"


def rename_for_namesake(
    *,
    existing: set[str],
    incoming_name: str,
    namespace: str,
) -> str:
    suffix = (namespace or "alias").strip().lower().replace(" ", "_")
    if not suffix:
        suffix = "alias"

    index = 1
    while True:
        candidate = f"{incoming_name}__{suffix}_{index}"
        if candidate not in existing:
            return candidate
        index += 1


def apply_namesake_strategy(
    *,
    existing: set[str],
    incoming_name: str,
    strategy: str,
    namespace: str = "alias",
) -> str | None:
    mode = normalize_namesake_strategy(strategy)
    if incoming_name not in existing:
        return incoming_name

    if mode == "skip":
        return None
    if mode == "override":
        return incoming_name
    if mode == "raise":
        raise ValueError(f"namesake conflict: {incoming_name}")
    return rename_for_namesake(
        existing=existing,
        incoming_name=incoming_name,
        namespace=namespace,
    )
