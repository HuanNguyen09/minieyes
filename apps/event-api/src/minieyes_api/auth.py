"""API keys: one per site, configured as SHA-256 digests so plaintext keys never sit in config."""

import hashlib
import hmac


class KeyRing:
    def __init__(self, digests_by_site: dict[str, str]):
        self._digests = {site: digest.lower() for site, digest in digests_by_site.items()}

    def site_for(self, key: str | None) -> str | None:
        """The site that owns this key, or None. Compares every digest in constant time."""
        if not key:
            return None
        digest = hashlib.sha256(key.encode()).hexdigest()
        owner = None
        for site, expected in self._digests.items():
            if hmac.compare_digest(digest, expected):
                owner = site
        return owner
