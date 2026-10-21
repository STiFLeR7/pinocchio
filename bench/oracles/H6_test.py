import os, sys
sys.path.insert(0, os.getcwd())
from slug.core import slugify

def test_no_trailing_dash():
    assert slugify("Hello World!") == "hello-world"
