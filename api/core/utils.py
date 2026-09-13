def per_user_cache_key(base, user):
    """Returns a cache key built from a base name and user (or 'anon')."""
    user_part = getattr(user, "id", None) or "anon"
    return f"{base}:{user_part}"
