from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def app_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_DB_PATH", str(data_dir / "test.db"))
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name, None)

    db_module = importlib.import_module("app.db")
    main_module = importlib.import_module("app.main")
    models_module = importlib.import_module("app.models")
    extraction_module = importlib.import_module("app.services.extraction")
    retrieval_module = importlib.import_module("app.services.retrieval")
    storage_module = importlib.import_module("app.services.storage")

    db_module.init_db()

    return {
        "app": main_module.app,
        "db_module": db_module,
        "models_module": models_module,
        "extraction_module": extraction_module,
        "retrieval_module": retrieval_module,
        "storage_module": storage_module,
        "data_dir": data_dir,
    }
