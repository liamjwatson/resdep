import os
import pytest

# Force Qt to use the offscreen platform across all tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

@pytest.fixture(scope="session", autouse=True)
def qapp_setup():
    """Ensures a clean QApplication lifecycle for headless tests."""
    from PySide6.QtWidgets import QApplication
    
    # Check if an instance already exists, create one if not
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

