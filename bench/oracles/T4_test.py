import os, sys
sys.path.insert(0, os.getcwd())
from slug.core import slugify

def test_transliterates_accents():
    assert slugify("café") == "cafe"
    assert slugify("Crème Brûlée") == "creme-brulee"
