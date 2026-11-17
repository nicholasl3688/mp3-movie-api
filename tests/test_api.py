import pytest
import pandas as pd

from src import MovieStorage
import main

def test_movies_persist(client, test_storage, uploaded_movies):
    # TODO: create another MovieStorage pointing to test_storage.db_path.
    # Use that object to get the movies and count them.
    # Check 20 rows, all four DataFrame columns, and the original title order.
    # Compare IDs from that object's select_columns() with GET /movies?limit=100.
    # Both should return IDs 1 through 20 in row order.
    reopened = MovieStorage(test_storage.db_path)

    df = reopened.get()
    assert reopened.count_movies() == 20
    assert len(df) == 20
    assert list(df.columns) == ["title", "release_year", "rating", "genre"]

    original_titles = pd.read_csv("fixtures/sample_movies.csv")["title"].tolist()
    assert df["title"].tolist() == original_titles

    stored_ids = [row["id"] for row in reopened.select_columns(["title"], limit=100)]
    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    api_ids = [movie["id"] for movie in response.json()["data"]]

    assert stored_ids == list(range(1, 21))
    assert api_ids == stored_ids


def test_cache_and_processing(client, uploaded_movies, processing_body):
    # TODO 1: GET /movies with limits 100 and 1.
    # Check 200 and that main.cache.get(limit) equals each response body.
    first_100 = client.get("/movies", params={"limit": 100})
    first_1 = client.get("/movies", params={"limit": 1})
    assert first_100.status_code == 200
    assert first_1.status_code == 200
    assert main.cache.get(100) == first_100.json()
    assert main.cache.get(1) == first_1.json()  


    # TODO 2: repeat limit=100 and check the same response.
    again_100 = client.get("/movies", params={"limit": 100})
    assert again_100.json() == first_100.json()


    # TODO 3: POST /movies/process using json=processing_body.
    # Check 200, zero validation removals, and the 20 -> 16 cleaning report.
    # Confirm both old cache entries are None.
    process = client.post("/movies/process", json=processing_body)
    assert process.status_code == 200
    body = process.json()
    assert body["validation_rows_removed"] == 0
    assert body["cleaning_report"]["rows_before"] == 20
    assert body["cleaning_report"]["rows_after"] == 16
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None 


    # TODO 4: retrieve again; check total_rows=16 and titles Movie A through Movie P, in order.
    # Check IDs 1 through 16 in the retrieved records.
    # Check that the new response is cached.
    after = client.get("/movies", params={"limit": 100})
    data = after.json()
    assert data["total_rows"] == 16
    assert [movie["title"] for movie in data["data"]] == [f"Movie {letter}" for letter in "ABCDEFGHIJKLMNOP"]
    assert [movie["id"] for movie in data["data"]] == [i for i in range(1, 17)]
    assert main.cache.get(100) == after.json()


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    # TODO 1: GET /movies with limit=100 to populate the cache.
    # Assert 200 and keep the response for comparison.
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200

    # TODO 2: Use monkeypatch to replace main.storage.select_columns()
    # and main.storage.count_movies() with a function that fails the test
    # if either method is called. 
    def fail_if_called(*args, **kwargs):
        pytest.fail("A cache hit should not query the database")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)



    # TODO 3: Repeat the same GET request.
    # Assert 200 and the same response body as the first request.
    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first.json()
