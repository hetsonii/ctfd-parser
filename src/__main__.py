"""Allows `python -m ctfd` invocation."""
import sys
from .cli import main

sys.exit(main())