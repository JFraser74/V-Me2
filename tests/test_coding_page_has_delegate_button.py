def test_coding_html_has_delegate_button():
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / 'static' / 'coding.html'
    s = p.read_text(encoding='utf-8')
    assert 'id="btnDelegate"' in s
