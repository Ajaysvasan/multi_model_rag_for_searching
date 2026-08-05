import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

def test_project_main_imports():
    """Verify that the main application entry point can be imported."""
    import sys
    from unittest.mock import patch
    try:
        with patch.object(sys, 'argv', ['main.py', 'bot']):
            import main
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import main project entrypoint: {e}")

def test_project_configuration():
    """Verify that the global Config is correctly loaded across the project."""
    try:
        from config import Config
        assert Config.CHUNK_SIZE > 0
    except Exception as e:
        pytest.fail(f"Configuration failed to load: {e}")
