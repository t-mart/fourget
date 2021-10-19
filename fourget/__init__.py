"""fourget."""
from importlib.metadata import version, PackageNotFoundError

__title__ = 'fourget'

try:
    __version__ = version(__title__)
except PackageNotFoundError:
    # package is not installed
    __version__ = "dev"
