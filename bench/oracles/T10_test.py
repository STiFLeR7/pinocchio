import os, sys
sys.path.insert(0, os.getcwd())
from slug.core import slugify

def test_collapses_dashes():
    assert slugify("a--b") == "a-b"
