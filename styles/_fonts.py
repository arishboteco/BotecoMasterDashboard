"""Google Fonts imports and Streamlit expander font override."""

FONTS = r"""    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..24,400,0,0&display=swap');

    /* Force system fonts for Streamlit expander icons */
    section[data-testid="stExpander"] * {
        font-family: inherit !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] button {
        font-family: inherit !important;
    }
    summary {
        font-family: inherit !important;
    }

"""
