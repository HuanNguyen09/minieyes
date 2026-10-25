import pytest
from conftest import sha256
from pydantic import ValidationError

from minieyes_api.auth import KeyRing
from minieyes_api.settings import Settings


def test_api_keys_are_read_from_env_as_json_site_to_digest(monkeypatch):
    digest = sha256("secret")
    monkeypatch.setenv("MINIEYES_API_KEYS", f'{{"site-01": "{digest}"}}')
    monkeypatch.setenv("MINIEYES_DATABASE_URL", "sqlite://")

    settings = Settings()

    assert settings.api_keys == {"site-01": digest}
    assert settings.database_url == "sqlite://"


@pytest.mark.parametrize("digest", ["secret", "ab" * 31, "zz" * 32])
def test_api_key_entry_that_is_not_a_sha256_hex_digest_fails_fast(digest):
    with pytest.raises(ValidationError, match="SHA-256"):
        Settings(api_keys={"site-01": digest})


def test_uppercase_digest_is_accepted():
    settings = Settings(api_keys={"site-01": sha256("secret").upper()})

    assert KeyRing(settings.api_keys).site_for("secret") == "site-01"
