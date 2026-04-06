"""Load Coffee Quality Institute (CQI) cupping data from CSV files."""


def load_cqi_data(db_path: str) -> int:
    """Parse CQI arabica/robusta CSVs and populate coffee samples, origins, processing methods.

    Expected source files:
        data/raw/cqi_arabica.csv
        data/raw/cqi_robusta.csv

    Returns the number of records loaded.
    """
    # TODO: Implement CSV parsing, cleaning, normalization, and DuckDB insertion
    raise NotImplementedError("CQI data loader not yet implemented")
