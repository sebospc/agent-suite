def short_title(text: str, limit: int = 70) -> str:
    """Cut a long bead title at a word boundary so a sentence around it stays readable."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:(")
    return cut + "..."
