def slugify(s, max_length=None):
    """Make a slug."""
    out = []
    for ch in s.lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch.isalpha():
            continue
        else:
            out.append("-")
    slug = "".join(out)
    if max_length is not None and len(slug) > max_length:
        slug = slug[: max_length + 1].rsplit("-", 1)[0]
    return slug
