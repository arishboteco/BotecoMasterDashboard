"""Tests for environment configuration loading."""

import config


def test_load_local_env_reads_dotenv_without_overriding_existing_env(monkeypatch, tmp_path):
    """Local .env values should be available unless the OS env already set them."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SUPABASE_URL=https://example.supabase.co\n"
        "SUPABASE_KEY=from-dotenv\n"
        "USE_SUPABASE=1\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_KEY", "from-shell")
    monkeypatch.delenv("USE_SUPABASE", raising=False)

    assert config._load_local_env(env_file) is True

    assert config.os.environ["SUPABASE_URL"] == "https://example.supabase.co"
    assert config.os.environ["SUPABASE_KEY"] == "from-shell"
    assert config.os.environ["USE_SUPABASE"] == "1"
