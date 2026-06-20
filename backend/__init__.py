"""Coffee Atlas backend package.

``__version__`` is sourced from the installed distribution metadata, which is
built from ``[project].version`` in ``pyproject.toml`` — the single source of
truth. All deploy images run ``uv pip install .``, so the metadata is always
present there; the fallback only matters when running from a bare source tree.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("coffee-atlas-backend")
except PackageNotFoundError:  # running from source without an install
    __version__ = "0.0.0"

__all__ = ["__version__"]
