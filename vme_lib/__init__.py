"""Compatibility package to hold the project's internal helper modules.

This mirrors the original `lib/` package but uses a different top-level
name to avoid packaging/ignore issues on some PaaS platforms.
"""

__all__ = ["supabase_client"]
