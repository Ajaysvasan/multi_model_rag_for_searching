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
    # Model-agnostic: this test is about the fallback wiring, not about which
    # model is currently selected. Hardcoding a name here made it fail on every
    # model change for reasons unrelated to what it claims to check.
    assert Config.GENERATION_MODEL
    assert Config.DEFAULT_MODEL == Config.GENERATION_MODEL
    assert Config.GENERATION_MODEL_FILE.endswith(".gguf")
