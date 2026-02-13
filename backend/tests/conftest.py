import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session")
def app_module(tmp_path_factory):
    bootstrap_db_path = tmp_path_factory.mktemp("bootstrap_db") / "bootstrap.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{bootstrap_db_path}"
    sys.modules.pop("db", None)
    sys.modules.pop("main", None)

    import main  # pylint: disable=import-error,import-outside-toplevel

    return main


@pytest.fixture()
def client_and_db(app_module, tmp_path):
    from db import Base  # pylint: disable=import-error,import-outside-toplevel

    test_db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app_module.fastapi_app.dependency_overrides[app_module.get_db] = override_get_db

    with TestClient(app_module.fastapi_app) as client:
        yield client, TestingSessionLocal

    app_module.fastapi_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
