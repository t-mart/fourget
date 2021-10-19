"""fourget."""
from importlib.metadata import PackageNotFoundError, version

__title__ = "fourget"

try:
    __version__ = version(__title__)
except PackageNotFoundError:
    # package is not installed
    __version__ = "dev"
