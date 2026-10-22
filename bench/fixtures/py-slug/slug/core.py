def slugify(s):
    """Make a slug."""
    out = []
    for ch in s.lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch.isalpha():
            continue
        else:
            out.append("-")
    return "".join(out)
