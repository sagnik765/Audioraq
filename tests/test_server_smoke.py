"""Import-level and routing smoke tests for the backend application.

These guard two failure modes that unit tests on individual modules miss:
a dependency that is imported by server.py but absent from the deployed
requirements, and API routes silently failing to register on the app.
"""
from fastapi.testclient import TestClient

import backend.server as server


def _client() -> TestClient:
    # Instantiated without a `with` block so the lifespan (and its MongoDB
    # index creation) does not run; these tests only exercise routing.
    return TestClient(server.app)


def test_health_endpoint_is_registered_and_responds():
    response = _client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_routes_are_mounted_under_the_api_prefix():
    response = _client().get("/api/interests/options")
    assert response.status_code == 200
    assert "interests" in response.json()


def test_app_uses_lifespan_instead_of_deprecated_on_event():
    router = server.app.router
    assert not router.on_startup, "startup should be handled by the lifespan context"
    assert not router.on_shutdown, "shutdown should be handled by the lifespan context"
