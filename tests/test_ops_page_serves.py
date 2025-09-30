def test_ops_page_serves():
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / 'static' / 'ops.html'
    s = p.read_text(encoding='utf-8')
    assert 'id="ops-table"' in s
