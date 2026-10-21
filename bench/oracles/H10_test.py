import os, sys
sys.path.insert(0, os.getcwd())
from slug.core import slugify

def test_docstring_describes_behaviour():
    assert len(slugify.__doc__ or "") >= 60
    assert slugify("Hello World") == "hello-world"
