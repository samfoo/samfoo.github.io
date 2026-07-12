#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "garminconnect>=0.3.6",
# ]
# ///
"""Diagnostic: attempt a Garmin login with full debug logging.

Run WITHOUT the token cache interfering:
    GARMIN_EMAIL=you@example.com GARMIN_PASSWORD='...' ./scripts/garmin_debug.py

If your account has MFA enabled you'll be prompted for the code.
"""
import logging
import os
import sys

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr,
                    format="%(levelname)s %(name)s: %(message)s")

from garminconnect import Garmin

email = os.environ["GARMIN_EMAIL"]
password = os.environ["GARMIN_PASSWORD"]

def prompt_mfa():
    return input("MFA code: ").strip()

api = Garmin(email, password, prompt_mfa=prompt_mfa)
try:
    api.login()   # NOTE: no tokenstore -> ignore stale ~/.garth cache
    print("\n=== LOGIN OK ===")
    print("display_name:", api.display_name)
    print("full_name:", api.full_name)
except Exception as e:
    print("\n=== LOGIN FAILED ===")
    print(type(e).__name__, e)
    # unwrap the underlying cause chain
    cur = e.__cause__
    while cur:
        print("  caused by:", type(cur).__name__, cur)
        cur = cur.__cause__
    sys.exit(1)
