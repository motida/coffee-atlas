"""Parse the WCR Sensory Lexicon 2.0 PDF into flavor attributes."""


def load_wcr_lexicon(db_path: str) -> int:
    """Parse the WCR Sensory Lexicon PDF and populate flav_attributes table.

    Expected source file: data/raw/wcr_sensory_lexicon.pdf
    Contains 110 flavor attributes in a 3-tier hierarchy.

    Returns the number of attributes loaded.
    """
    # TODO: Implement PDF parsing (e.g., with pdfplumber or PyMuPDF)
    raise NotImplementedError("WCR lexicon loader not yet implemented")
