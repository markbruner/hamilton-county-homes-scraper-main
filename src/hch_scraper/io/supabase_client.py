from __future__ import annotations

import os
from typing import Optional

from supabase import Client, create_client
from dotenv import load_dotenv


load_dotenv()


def get_supabase_client(
    url: Optional[str] = None,
    service_role_key: Optional[str] = None,
    *,
    key: Optional[str] = None,
    key_type: str = "service_role",
) -> Client:
    """
      Docstring for get_supabase_client
    Create and return a Supabase client using environment variables by default.

      Environment variables:
          SUPABASE_URL
          SUPABASE_SERVICE_ROLE_KEY
          SUPABASE_ANON_KEY

      Args:
          url: Optional override for the Supabase URL.
          service_role_key: Optional override for the service role key.
          key: Optional explicit key override.
          key_type: Either ``service_role`` or ``anon`` when ``key`` is not passed.

      Returns:
          Supabase Client instance.

      Raises:
          RuntimeError: If URL or key are missing.
    """
    supabase_url = url or os.getenv("SUPABASE_URL")
    if key is not None:
        supabase_key = key
    elif service_role_key is not None:
        supabase_key = service_role_key
    elif key_type == "anon":
        supabase_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv(
            "NEXT_PUBLIC_SUPABASE_ANON_KEY"
        )
    elif key_type == "service_role":
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    else:
        raise RuntimeError(
            f"Unsupported Supabase key type: {key_type}. Use 'service_role' or 'anon'."
        )

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Supabase URL or requested key not set. "
            "Set SUPABASE_URL and either SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY."
        )

    return create_client(supabase_url, supabase_key)


def get_supabase_anon_client(
    url: Optional[str] = None,
    anon_key: Optional[str] = None,
) -> Client:
    """Create a Supabase client configured to use the anonymous API key."""
    return get_supabase_client(url=url, key=anon_key, key_type="anon")
