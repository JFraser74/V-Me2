def test_coding_js_has_attach_handler():
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / 'static' / 'coding.js'
    s = p.read_text(encoding='utf-8')
    assert 'attach-btn' in s
    assert "Document upload is not yet enabled" in s
