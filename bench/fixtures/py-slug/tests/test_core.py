from slug import slugify


def test_words_are_joined_with_dashes():
    assert slugify("Hello World") == "hello-world"


def test_plain_word_is_lowercased():
    assert slugify("ABC") == "abc"
