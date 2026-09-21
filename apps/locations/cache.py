"""Caching for the locations list endpoint.

Strategy: a cache "version" counter. Every list-request cache key includes
the current version; bumping the version (on any location/review change)
makes all previously cached list pages unreachable without needing to
enumerate/delete every query-param combination that was ever cached.
"""
import hashlib

from django.core.cache import cache

VERSION_KEY = "locations:list:version"


def _current_version():
    version = cache.get(VERSION_KEY)
    if version is None:
        version = 1
        cache.set(VERSION_KEY, version, timeout=None)
    return version


def bump_locations_cache_version():
    try:
        cache.incr(VERSION_KEY)
    except ValueError:
        # Key expired/missing between get and incr — just (re)seed it.
        cache.set(VERSION_KEY, 1, timeout=None)


def build_locations_list_cache_key(query_params, user_id):
    version = _current_version()
    # Sort so ?a=1&b=2 and ?b=2&a=1 hit the same cache entry.
    normalized = "&".join(f"{k}={v}" for k, v in sorted(query_params.items()))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    # Namespaced by user because permissions/ownership never change what a
    # list *contains* here (read is public), but keeping this future-proof
    # is cheap and avoids a class of subtle cache-leak bugs.
    return f"locations:list:v{version}:u{user_id or 'anon'}:{digest}"
