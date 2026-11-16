"""Build the per-area share cards.

For every area (1F passage x front/back, balcony passage, 2F passage x
front/back, and the three arena zones) this writes:
  og/<id>.png   1200x630 card image, drawn by makeOgImage() in index.html
  s/<id>.html   small page whose OGP tags point at that image, so X shows
                the image as a large card when the page link is posted

Usage (needs Python Playwright and a Chromium/Chrome binary):
  python3 tools/build_og.py [--base https://<user>.github.io/<repo>/] [--chrome /path/to/chrome]

Run it again whenever the map or the area texts in index.html change.
"""
import argparse
import base64
import html
import pathlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://yukachiii.github.io/lovelive-fest-tokyo-seatmap/"

PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | ラブライブ！フェス 東京ドーム 座席ファインダー</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="ラブライブ！フェス 東京ドーム 座席ファインダー（非公式）">
<meta property="og:title" content="ラブライブ！フェス 東京ドーム 座席：{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{base}s/{id}.html">
<meta property="og:image" content="{base}og/{id}.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="東京ドームの図で「{title}」を示した画像">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="ラブライブ！フェス 東京ドーム 座席：{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{base}og/{id}.png">
<style>
:root {{ --bg: #f4eff3; --surface: #ffffff; --ink: #23131d; --muted: #6e5a67; --line: #e4d6df; --accent: #c8246b; color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #150e13; --surface: #20161d; --ink: #f3e8ef; --muted: #b29fab; --line: #3a2a35; --accent: #ff6fa8; color-scheme: dark; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: "Hiragino Sans", "Noto Sans JP", sans-serif; line-height: 1.6; }}
main {{ max-width: 640px; margin: 0 auto; padding: 24px 16px 40px; display: grid; gap: 14px; }}
.eyebrow {{ margin: 0; font-size: 12px; font-weight: 700; color: var(--accent); }}
h1 {{ margin: 0; font-size: 22px; line-height: 1.35; text-wrap: balance; }}
img {{ width: 100%; height: auto; border-radius: 12px; border: 1px solid var(--line); background: var(--surface); }}
p {{ margin: 0; }}
.muted {{ color: var(--muted); font-size: 14px; }}
.btn {{ display: inline-block; justify-self: start; background: var(--accent); color: #fff; text-decoration: none; font-weight: 700; border-radius: 10px; padding: 12px 18px; }}
.btn:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.copy {{ text-align: center; color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); padding-top: 8px; }}
</style>
</head>
<body>
<main>
  <p class="eyebrow">ラブライブ！フェス Encore in TOKYO DOME　2027.2.13–14　東京ドーム</p>
  <h1>{title}</h1>
  <img src="../og/{id}.png" width="1200" height="630" alt="東京ドームの図で「{title}」を示した画像">
  <p>{sub}　{dist}</p>
  <p class="muted">位置と距離は、公開情報から推定した目安です。ステージ配置はまだ公開されていないため仮のものです。非公式のファンツールで、主催者・会場とは関係ありません。</p>
  <a class="btn" href="../">自分の席を調べる</a>
  <p class="copy">©ゆいゆい</p>
</main>
</body>
</html>
"""


def shrink(path):
    """Reduce the PNG to a 256-colour palette to keep the repo small (optional, needs Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        return
    with Image.open(path) as im:
        im.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE, help="public URL of the site, ending with /")
    ap.add_argument("--chrome", default=None, help="path to a Chrome/Chromium binary")
    ap.add_argument("--offline", action="store_true", help="skip Google Fonts (uses system Japanese fonts)")
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"

    og_dir, s_dir = ROOT / "og", ROOT / "s"
    og_dir.mkdir(exist_ok=True)
    s_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chrome) if args.chrome else p.chromium.launch()
        page = browser.new_page()
        page.route("**/fonts.g*/**", lambda r: r.abort() if args.offline else r.continue_())
        page.goto((ROOT / "index.html").as_uri())
        page.wait_for_timeout(1000)
        ids = page.evaluate("window.__og.ids()")
        for area_id in ids:
            info = page.evaluate("id => window.__og.info(id)", area_id)
            data_url = page.evaluate("id => window.__og.make(id)", area_id)
            png = og_dir / f"{area_id}.png"
            png.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
            shrink(png)
            e = {k: html.escape(str(v), quote=True) for k, v in info.items()}
            desc = f"{e['sub']}／{e['dist']}／東京ドーム（位置は目安・ステージ配置は仮）"
            (s_dir / f"{area_id}.html").write_text(
                PAGE.format(base=html.escape(base, quote=True), desc=desc, **e), encoding="utf-8")
        browser.close()
    print(f"built {len(ids)} cards")


if __name__ == "__main__":
    main()
