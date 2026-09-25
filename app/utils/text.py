import html
import re

def escape_html(value: str | None) -> str:
    return html.escape(value or '')


def text_chunks(value: str, limit=3900, *, html_mode=False):
    """Bound UTF-16 and serialized size, without splitting entities or HTML tags."""
    tokens = re.findall(r'<[^>]+>|&(?:#\d+|#x[0-9a-fA-F]+|\w+);|[\s\S]', value) if html_mode else value
    stack = []
    chunk = ''
    units = 0
    for token in tokens:
        size = len(token.encode('utf-16-le')) // 2
        closing = ''.join(f'</{name}>' for name, _ in reversed(stack))
        if chunk and units + size + len(closing) > limit:
            yield chunk + closing
            chunk = ''.join(tag for _, tag in stack)
            units = len(chunk.encode('utf-16-le')) // 2
        if html_mode and token.startswith('<'):
            if token.startswith('</'):
                if stack:
                    stack.pop()
            elif not token.endswith('/>'):
                match = re.match(r'<([\w-]+)', token)
                if match:
                    stack.append((match.group(1), token))
        chunk += token
        units += size
    if chunk:
        yield chunk
