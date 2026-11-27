import pytest


@pytest.fixture(autouse=True)
def isolated_user_profile(tmp_path_factory, monkeypatch):
    """Preferências locais (responsável, lotes recentes) nunca tocam no perfil real."""
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path_factory.mktemp('perfil')))
