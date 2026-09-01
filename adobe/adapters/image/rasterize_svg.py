import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def svg_dimensions(source):
    root = ET.parse(source).getroot()
    values = []
    try:
        values = [float(item) for item in root.attrib.get("viewBox", "").replace(",", " ").split()]
    except ValueError:
        values = []
    if len(values) == 4:
        return max(1.0, values[2]), max(1.0, values[3])
    def dimension(value, fallback):
        try:
            return max(1.0, float(str(value or "").replace("px", "")))
        except ValueError:
            return fallback
    return dimension(root.attrib.get("width"), 1.0), dimension(root.attrib.get("height"), 1.0)


def rasterize_cairo(source, output, width, background):
    try:
        # CairoSVG normally imports cairocffi, which needs a separate native
        # cairo DLL on Windows. pycairo ships a working native extension here;
        # its API is compatible with the CairoSVG surface calls we use.
        try:
            import cairo
            sys.modules["cairocffi"] = cairo
        except ImportError:
            pass
        import cairosvg
        cairosvg.svg2png(url=source, write_to=output, output_width=width, background_color=background)
        return "cairosvg"
    except Exception:
        return None


def browser_path():
    candidates = [
        os.environ.get("BROWSER_EXE"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    return next((item for item in candidates if item and os.path.exists(item)), None)


def rasterize_browser(source, output, width, background):
    browser = browser_path()
    if not browser:
        return None
    source_width, source_height = svg_dimensions(source)
    height = max(1, round(width * source_height / source_width))
    temp_root = tempfile.mkdtemp(prefix="agent-svg-raster-")
    try:
        html_path = os.path.join(temp_root, "render.html")
        profile = os.path.join(temp_root, "profile")
        html_body = "" if background is None else f"background:{html.escape(background)};"
        html_document = f"<!doctype html><html><head><meta charset='utf-8'><style>html,body{{margin:0;padding:0;overflow:hidden;{html_body}}}img{{display:block;width:{width}px;height:auto}}</style></head><body><img src='{Path(source).as_uri()}'></body></html>"
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(html_document)
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            "--force-device-scale-factor=1",
            "--default-background-color=00000000",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            f"--screenshot={output}",
            Path(html_path).as_uri(),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output):
            return "browser"
        return None
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=2048)
    parser.add_argument("--background", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    source = os.path.abspath(args.input)
    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    width = max(1, int(args.width))
    renderer = rasterize_cairo(source, output, width, args.background)
    if renderer is None:
        renderer = rasterize_browser(source, output, width, args.background)
    if renderer is None:
        raise RuntimeError("No SVG rasterizer available: CairoSVG lacks its native cairo runtime and Edge/Chrome was not found.")
    print(json.dumps({"png": output, "source": source, "width": width, "renderer": renderer}))


if __name__ == "__main__":
    main()
