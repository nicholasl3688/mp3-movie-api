import io
import json
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import HealthResponse, setup_logging, ProcessConfig, log_requests
from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src import (
    MovieStorage,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
    MovieCache
)
from src.storage import MOVIE_COLUMNS

# URL http://127.0.0.1:8000/docs

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
storage = MovieStorage()
cache = MovieCache()
app.middleware("http")(log_requests)




@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    # TODO 1: Keep MP2's .csv check, await file.read(), and CSV parsing.
    # Raise HTTPException with status 400 for an unsupported extension or an expected parsing failure.
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".csv":
        logger.warning(f"Unsupported file format: {suffix}")
        raise HTTPException( status_code=400, detail="Unsupported file type")

    contents =  await file.read()   
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as error:
        logger.warning(f"Parsing errors. Errors: {error}")
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {error}")
    
    # TODO 2: Quick validation before saving:
    # Require exactly MOVIE_COLUMNS
    # Require at least one data row (hint: Use if df.empty: to check for an empty DataFrame).
    # Raise HTTPException with status 400 if these checks fail.
    # Reorder the columns to match MOVIE_COLUMNS.
    
    if df.empty: 
        logger.warning(f"DF has no columns")
        raise HTTPException(status_code=400, detail=f"DF has no rows")
    if set(df.columns) != set(MOVIE_COLUMNS):
        logger.warning(f"Wrong columns: {list(df.columns)}")
        raise HTTPException(status_code=400, detail=f"Columns must be exactly {MOVIE_COLUMNS}")

    df = df[MOVIE_COLUMNS]

    # TODO 3: Call storage.save(df) to replace the current collection.
    # Log the filename and saved row count at INFO.
    # Return filename, rows, columns, and column_names for this upload.
    pass
    storage.save(df)
    cache.invalidate()
    logger.info(f"Uploaded movies: filename={file.filename}, rows={len(df)}")
    return {"filename": file.filename, "rows": len(df), "columns": df.shape[1],
    "column_names": list(df.columns)}


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    # TODO 1: Look up the response using cache.get(limit).
    # If it is not None, log the cache hit at INFO and return it.
    value = cache.get(limit)
    if value is not None:
        logger.info(f"Retrieved movies from cache: limit={limit}, returned_rows={len(value['data'])}")
        return value 
    # Keep Part 1's SQL retrieval, total count, and response construction here.
    data = storage.select_columns(MOVIE_COLUMNS, limit)
    total_rows = storage.count_movies()
    
    # TODO 2: Before the existing return, cache the complete response
    # using cache.set(limit, response).
    # Keep the existing row-count log and return.
    response = {"data": data, "total_rows": total_rows}
    cache.set(limit, response)
    logger.info(f"Retrieved movies: returned_rows={len(data)}")
    return response


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1)
):
    # TODO: Call storage.query_movies(columns, min_rating, limit).
    # Catch ValueError and raise HTTPException with status 400.
    # Return id plus the selected fields, or [] if there are no matches.
    # Log the selected columns and returned row count at INFO.
    try:
        data = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    logger.info(f"Queried movies: columns={columns}, min_rating={min_rating}, returned_rows={len(data)}")
    return data



@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    # TODO 1: Retrieve data using storage.get().
    # Raise HTTPException with status 400 if empty.
    df = storage.get()
    if df.empty: 
            raise HTTPException(status_code=400, detail=f"DF is empty")

    # TODO 2: Reuse MP2's configuration, validation, processing,
    # cleaning report, logging, and ValueError handling.

    conf = config.model_dump()

    for col in conf["validation"]["numeric_columns"]:
        if col not in df.columns:
            raise HTTPException( status_code=400, detail=f"Missing column: {col}")
    
    try:
        validated_df = validate_dataframe(df, conf["validation"]["required_columns"], conf["validation"]["numeric_columns"])
        rows_removed = len(df) - len(validated_df) 
        validated_copy = validated_df.copy()
        processed_df = process_data(validated_copy, conf)
    except ValueError as error:
        raise HTTPException( status_code=400, detail=str(error))

    report = create_cleaning_report(validated_copy, processed_df)

    # TODO 3: Save the processed DataFrame using storage.save().
    # Return validation_rows_removed and cleaning_report without a dataset ID.
    storage.save(processed_df)
    cache.invalidate()
    logger.info(f"Processed movies: validation_removed={rows_removed}, rows_before={len(validated_copy)}, rows_after={len(processed_df)}")
    return {"validation_rows_removed": rows_removed, "cleaning_report": report}

# class MovieProcessingReport(BaseModel):
#     validation_rows_removed: int

#     cleaning_report: dict
