from __future__ import annotations

import os
from typing import Optional

from supabase import Client, create_client


def get_supabase_client(
    url: Optional[str] = None,
    service_role_key: Optional[str] = None,
) -> Client:
    """
      Docstring for get_supabase_client
    Create and return a Supabase client using environment variables by default.

      Environment variables:
          SUPABASE_URL
          SUPABASE_SERVICE_ROLE_KEY

      Args:
          url: Optional override for the Supabase URL.
          service_role_key: Optional override for the service role key.

      Returns:
          Supabase Client instance.

      Raises:
          RuntimeError: If URL or key are missing.
    """
    supabase_url = url or os.getenv("SUPABASE_URL")
    supabase_key = service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Supabase URL or SERVICE_ROLE_KEY not set. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your environment."
        )

    return create_client(supabase_url, supabase_key)
