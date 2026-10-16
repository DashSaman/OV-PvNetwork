"""Render the same inert-input regression fixture for an owned browser test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_subscription_qr_context import render_fixture

Path(sys.argv[1]).write_text(render_fixture(),encoding='utf-8')
