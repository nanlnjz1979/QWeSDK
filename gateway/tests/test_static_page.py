from pathlib import Path


STATIC = Path(__file__).parents[1] / "static"


def test_workspace_has_real_result_bindings_and_no_demo_metrics():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "getJson('/api/datasets')" in javascript
    assert "'/api/backtests'" in javascript
    assert "/result" in javascript
    assert "summary.totalReturn" in javascript
    assert "series.equityCurve" in javascript
    assert "localStorage" in javascript
    assert "lastRunId" in javascript
    assert "28.6" not in html + javascript
    assert "mock" not in html.lower() + javascript.lower()


def test_workspace_has_mobile_layout_and_trade_log_regions():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "@media(max-width:600px)" in css
    assert 'id="equity-chart"' in html
    assert 'id="trade-body"' in html
    assert 'id="event-log"' in html
    assert 'id="capital" type="number" min="1000" step="1000"' in html
