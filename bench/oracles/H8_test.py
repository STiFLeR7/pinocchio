import os, sys
sys.path.insert(0, os.getcwd())
from slug.core import slugify

def test_max_length_never_cuts_mid_word():
    assert slugify("hello wonderful world", max_length=15) == "hello-wonderful"
    assert slugify("hello wonderful world", max_length=13) == "hello"
    assert slugify("hello world") == "hello-world"
