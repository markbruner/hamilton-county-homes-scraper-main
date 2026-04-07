import os

import pytest

from hch_scraper.io import supabase_client


def test_get_supabase_client_uses_anon_key(monkeypatch):
    captured = {}

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")

    def fake_create_client(url, key):
        captured["url"] = url
        captured["key"] = key
        return "fake-client"

    monkeypatch.setattr(supabase_client, "create_client", fake_create_client)

    client = supabase_client.get_supabase_client(key_type="anon")

    assert client == "fake-client"
    assert captured == {
        "url": "https://example.supabase.co",
        "key": "anon-test-key",
    }


def test_get_supabase_client_requires_requested_key(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(RuntimeError):
        supabase_client.get_supabase_client(key_type="anon")
