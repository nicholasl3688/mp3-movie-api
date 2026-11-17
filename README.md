# MP3 Movie API

This is a FastAPI app that stores one movie collection in a SQLite database and cleans it with the MP1 data pipeline. POST /upload accepts a CSV with exactly the columns title, release_year, rating, and genre, and each successful upload replaces the whole collection in a single transaction. GET /movies returns up to `limit` movies plus the total count, and GET /movies/search uses SQL to filter by a minimum rating, sort by rating, and return only the requested columns. POST /movies/process loads the stored movies, validates and cleans them using settings from a JSON body, saves the cleaned rows back to SQLite, and returns a cleaning report. Responses from GET /movies are cached in fakeredis for 90 seconds under a key based on `limit`, so repeated requests skip the database. Every successful upload or processing run clears the cache, so the next request reads fresh data from SQLite. The code is split into src/database.py (connections and table setup), src/storage.py (SQL queries), src/cache.py (caching), src/models.py (Pydantic models), data_pipeline/ (MP1 modules), and tests/ (pytest tests).

## Run

python -m pip install -r requirements.txt
python -m uvicorn main:app --reload

Then open http://127.0.0.1:8000/docs.

## Test


python -m pytest tests -v


## Sample Processing Request

After uploading `fixtures/sample_movies.csv`, send this body to POST /movies/process:

{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {"enabled": true, "axis": "rows"},
    "outliers": {"enabled": true, "columns": ["rating"], "method": "iqr", "threshold": 1.5}
  }
}


Expected result:

{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}

The 4 removed rows are 2 duplicates (Movie B and Movie D) and 2 low-rating outliers (Movie Q and Movie R).