def test_coding_js_has_save_helpers():
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / 'static' / 'coding.js'
    s = p.read_text(encoding='utf-8')
    assert 'saveOrRenameThread' in s
    assert 'loadRecent' in s
    assert '/api/threads' in s
