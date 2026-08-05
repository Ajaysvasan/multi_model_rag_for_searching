import pytest
import sys
import os

# Add backend to path to allow importing modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

def test_generation_layer_imports():
    """Verify that generation_layer module imports correctly."""
    try:
        from generation_layer import generator
        assert True
    except ImportError:
        pytest.fail("Failed to import generation_layer")

def test_generation_fallback_model():
    """Test that the generation layer config fallback is configured properly."""
    from config import Config
    assert Config.GENERATION_MODEL == "TheBloke/stablelm-zephyr-3b-GGUF"
