import argparse
import json
import os

from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-size", type=int, default=160)
    parser.add_argument("--threshold", type=int, default=8)
    return parser.parse_args()


def color(value):
    r, g, b, a = value
    return f"rgb({r},{g},{b})" if a >= 255 else f"rgba({r},{g},{b},{a / 255:.3f})"


def main():
    args = parse_args()
    image = Image.open(args.input).convert("RGBA")
    ratio = min(1.0, args.max_size / max(image.width, image.height))
    if ratio < 1.0:
        image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.Resampling.LANCZOS)
    pixels = image.load()
    paths = []
    for y in range(image.height):
        x = 0
        while x < image.width:
            start = x
            while x < image.width:
                current = pixels[x, y]
                if current[3] < args.threshold:
                    break
                x += 1
            if x > start:
                value = pixels[start, y]
                paths.append(f'<path d="M {start} {y} H {x} V {y + 1} H {start} Z" fill="{color(value)}"/>')
            x += 1
    svg = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    svg += f'<svg xmlns="http://www.w3.org/2000/svg" width="{image.width}" height="{image.height}" viewBox="0 0 {image.width} {image.height}" role="img" aria-labelledby="svg-title svg-desc">\n'
    svg += '<title id="svg-title">Vectorized image</title><desc id="svg-desc">Raster image converted to SVG paths by Agent Toolkit.</desc>\n'
    svg += "\n".join(paths)
    svg += "\n</svg>\n"
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(svg)
    print(json.dumps({"svg": os.path.abspath(args.output), "width": image.width, "height": image.height, "paths": len(paths)}))


if __name__ == "__main__":
    main()
