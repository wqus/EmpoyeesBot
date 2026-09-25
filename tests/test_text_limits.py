from html import unescape
import re
import pytest
from app.utils.text import text_chunks


@pytest.mark.parametrize('text', ['a' * 9000, '😀' * 5000, 'a&<>\n' * 2000], ids=['ascii', 'emoji', 'symbols'])
def test_plain_chunks_preserve_unicode_and_limits(text):
    chunks = list(text_chunks(text))
    assert ''.join(chunks) == text
    assert all(len(c.encode('utf-16-le')) // 2 <= 3900 for c in chunks)


def test_html_chunks_keep_tags_balanced_and_entities_intact():
    original = '<b><i>' + '😀 &amp; &lt;text&gt; ' * 900 + '</i></b>'
    chunks = list(text_chunks(original, html_mode=True))
    assert len(chunks) > 1
    assert all(c.startswith('<b><i>') and c.endswith('</i></b>') for c in chunks)
    assert all(len(c.encode('utf-16-le')) // 2 <= 3900 for c in chunks)
    strip = lambda value: unescape(re.sub('<[^>]*>', '', value))
    assert ''.join(map(strip, chunks)) == strip(original)
