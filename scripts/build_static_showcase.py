#!/usr/bin/env python3
"""Build the public static showcase from the production HTML template."""

from pathlib import Path
import json
import sys


REPLACEMENTS = {
    '<html lang="zh-CN">': '<html lang="zh-CN" data-static-root=".">',
    '<link rel="stylesheet" href="/static/css/tokens.css">': '<link rel="stylesheet" href="static/css/tokens.css">',
    '<link rel="stylesheet" href="/static/css/layout.css">': '<link rel="stylesheet" href="static/css/layout.css">',
    '<link rel="stylesheet" href="/static/css/components.css">': '<link rel="stylesheet" href="static/css/components.css">\n  <link rel="stylesheet" href="static/css/showcase.css">',
    '<body>': '<body class="static-showcase">',
    '  <main class="main">': '  <main class="main">\n    <div class="showcase-banner"><strong>静态展示版</strong><span>界面与当前产品一致 · 数据为脱敏快照 · 不连接实时行情、模型、数据库或券商</span></div>',
    '<span class="status-pill warning">真实接口</span>': '<span class="status-pill muted">静态快照</span>',
    '先解析与校验，确认后才写入数据库': '先解析与校验，确认后只写入本页内存',
    '<script src="/static/vendor/lightweight-charts/lightweight-charts.standalone.production.js"></script>': '<script src="static/vendor/lightweight-charts/lightweight-charts.standalone.production.js"></script>',
    '<script src="/static/js/api.js"></script>': '<script src="static/js/api-static.js"></script>',
    '<script src="/static/js/app.js"></script>': '<script src="static/js/app.js"></script>',
}


def build(source: Path, destination: Path, fixture_path: Path) -> None:
    html = source.read_text(encoding="utf-8")
    for original, replacement in REPLACEMENTS.items():
        count = html.count(original)
        if count != 1:
            raise RuntimeError(f"Expected one template marker, found {count}: {original}")
        html = html.replace(original, replacement)
    fixtures = fixture_path.read_text(encoding="utf-8")
    json.loads(fixtures)
    fixtures = fixtures.replace("</", "<\\/")
    script_marker = '  <script src="static/vendor/lightweight-charts/lightweight-charts.standalone.production.js"></script>'
    embedded = f'  <script id="staticFixtures" type="application/json">{fixtures}</script>\n{script_marker}'
    if html.count(script_marker) != 1:
        raise RuntimeError("Expected one static vendor script marker")
    html = html.replace(script_marker, embedded)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: build_static_showcase.py SOURCE DESTINATION FIXTURES")
    build(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
