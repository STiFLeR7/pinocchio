def slugify(s):
    """Turn text into a URL slug.

    Lowercases the text, keeps ASCII letters and digits, and replaces every other
    non-letter character (spaces, punctuation) with a dash. Accented letters are dropped.
    """
    out = []
    for ch in s.lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch.isalpha():
            continue
        else:
            out.append("-")
    return "".join(out)
