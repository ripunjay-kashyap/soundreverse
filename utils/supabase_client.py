import os
from supabase import create_client, Client

_supabase_client = None

def get_supabase() -> Client:
    """Returns a module-level lazy singleton Supabase client.
    Fails fast with a clear RuntimeError if environment variables are not set.
    """
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "Missing Supabase configuration! Please check that SUPABASE_URL "
                "and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) are set in your environment variables / .env file."
            )
        _supabase_client = create_client(url, key)
    return _supabase_client

