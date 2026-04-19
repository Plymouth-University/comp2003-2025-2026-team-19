from functools import lru_cache
from pathlib import Path

from pydantic_extra_types import Color

# Resolve path relative to this file
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"


@lru_cache(maxsize=32)
def get_icon_template(filename: str) -> str:
    path = ASSETS_DIR / "icons" / filename
    if not path.exists():
        raise FileNotFoundError(f"Template {filename} not found")
    return path.read_text()


def colour_svg(
    template_name: str, colour_map: dict[str, Color], *, refresh: bool = False
) -> str:
    """
    Replaces {{key}} in the SVG with hex values from colour_map.
    Example: colour_map = {"hull": "#FF0000"}
    """
    if refresh:
        svg_text = get_icon_template.__wrapped__(f"{template_name}.svg")
    else:
        svg_text = get_icon_template(f"{template_name}.svg")

    for key, value in colour_map.items():
        print(repr(key), repr(value))
        svg_text = svg_text.replace(f"{{{{{key}}}}}", value.as_hex())
    return svg_text
