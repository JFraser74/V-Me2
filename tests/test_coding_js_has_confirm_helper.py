def test_coding_js_has_confirm_helper():
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / 'static' / 'coding.js'
    s = p.read_text(encoding='utf-8')
    assert 'vmConfirm' in s
