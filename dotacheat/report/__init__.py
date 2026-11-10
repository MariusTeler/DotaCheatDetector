"""Report writers: HTML (for humans), JSON (raw detections), console summary."""

from .console import console_summary  # noqa: F401
from .html import write_html  # noqa: F401
from .json_export import to_json_dict, write_json  # noqa: F401
