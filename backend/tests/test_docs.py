from fastapi.testclient import TestClient


def test_openapi_schema(client: TestClient) -> None:
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert {tag["name"] for tag in schema["tags"]} == {"Health", "Auth", "Orders", "GraphQL"}
    assert "/api/health" in schema["paths"]


def test_swagger_ui(client: TestClient) -> None:
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text


def test_root_redirects_to_docs(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/api/docs"
