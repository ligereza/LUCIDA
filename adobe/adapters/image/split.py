import argparse
import json
import os
from pathlib import Path

from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--columns", type=int, default=1)
    parser.add_argument("--mode", choices=["grid", "horizontal", "vertical"], default="grid")
    parser.add_argument("--overlap", type=int, default=0)
    parser.add_argument("--prefix", default="tile")
    return parser.parse_args()


def main():
    args = parse_args()
    source = os.path.abspath(args.input)
    manifest_path = os.path.abspath(args.output)
    image = Image.open(source).convert("RGBA")
    rows = max(1, args.rows)
    columns = max(1, args.columns)
    if args.mode == "horizontal":
        rows, columns = 1, columns
    elif args.mode == "vertical":
        rows, columns = rows, 1
    overlap = max(0, int(args.overlap))
    output_dir = os.path.splitext(manifest_path)[0] + "-tiles"
    os.makedirs(output_dir, exist_ok=True)
    assets = []
    for row in range(rows):
        for column in range(columns):
            left = round(column * image.width / columns) - overlap
            top = round(row * image.height / rows) - overlap
            right = round((column + 1) * image.width / columns) + overlap
            bottom = round((row + 1) * image.height / rows) + overlap
            box = (max(0, left), max(0, top), min(image.width, right), min(image.height, bottom))
            tile = image.crop(box)
            filename = f"{args.prefix}-r{row + 1:02d}-c{column + 1:02d}.png"
            target = os.path.join(output_dir, filename)
            tile.save(target, format="PNG")
            assets.append({
                "id": Path(filename).stem,
                "file": target,
                "kind": "image",
                "role": "illustration",
                "slideIndex": row * columns + column + 1,
                "row": row + 1,
                "column": column + 1,
                "box": list(box),
                "width": tile.width,
                "height": tile.height,
                "alpha": True,
            })
    result = {
        "version": 1,
        "source": source,
        "width": image.width,
        "height": image.height,
        "rows": rows,
        "columns": columns,
        "overlap": overlap,
        "assets": assets,
        "files": [item["file"] for item in assets],
    }
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"manifest": manifest_path, "assets": len(assets), "files": result["files"]}))


if __name__ == "__main__":
    main()
