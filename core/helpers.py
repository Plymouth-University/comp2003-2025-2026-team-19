from typing import Any
from uuid import UUID


def filter_uuids(v: Any) -> Any:
    """Filter out any list items that aren't valid UUID strings/objects."""
    if isinstance(v, list):
        cleaned = []
        for item in v:
            try:
                # Attempt to cast to UUID; if it fails, we just skip it
                if isinstance(item, UUID):
                    cleaned.append(item)
                else:
                    cleaned.append(UUID(str(item)))
            except (ValueError, TypeError):
                continue
        return cleaned
    return v
