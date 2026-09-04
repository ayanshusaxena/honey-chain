"""Shared test configuration."""

import os

# This is a test-only signing value, set before application settings are imported.
os.environ.setdefault("HONEY_CHAIN_JWT_SECRET", "test-only-jwt-secret-not-for-production")
