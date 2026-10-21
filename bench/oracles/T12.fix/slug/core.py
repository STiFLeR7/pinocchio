import unicodedata

def slugify(s):
    """Make a slug."""
    out = []
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    for ch in s.lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch.isalpha():
            continue
        else:
            out.append("-")
    return "".join(out)
