PASSWORD = "correct horse battery staple"


def register(client, email="Alice@Example.com", password=PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email="alice@example.com", password=PASSWORD):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_register_lowercases_email_and_hides_password(client):
    response = register(client)
    assert response.status_code == 201
    assert response.json() == {"id": 1, "email": "alice@example.com"}


def test_duplicate_email_is_409_case_insensitive(client):
    register(client)
    assert register(client, email="ALICE@example.com").status_code == 409


def test_short_and_context_passwords_are_422(client):
    assert register(client, password="short").status_code == 422
    assert register(client, password="vacation planner").status_code == 422
    assert (
        register(
            client, email="vacationplanner@example.com", password="vacationplanner"
        ).status_code
        == 422
    )


def test_login_and_me(client):
    register(client)
    response = login(client, email="ALICE@example.com")
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_login_failures_are_indistinguishable(client):
    register(client)
    wrong = login(client, password="wrong password entirely")
    unknown = login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_rejects_oversized_password(client):
    register(client)
    assert login(client, password="a" * 5000).status_code == 401


def test_me_requires_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    bad = client.get("/auth/me", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    assert bad.headers["www-authenticate"] == "Bearer"


def test_token_for_deleted_user_is_rejected(client, db_session):
    from app.models import User

    register(client)
    token = login(client).json()["access_token"]
    db_session.delete(db_session.get(User, 1))
    db_session.commit()
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
