"""Fixture source, inspected as an AST and never imported by the demo."""

import os

print(os.getenv("SERVICE_TOKEN", "demo"))
