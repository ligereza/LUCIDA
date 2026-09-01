import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".ppm"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract an alpha matte from baked checkerboard icon backgrounds while preserving existing alpha."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Single image input. Use --rows/--columns to split a sheet.")
    source.add_argument("--plan", help="JSON plan with one or more source images and optional grid splits.")
    parser.add_argument("--output", required=True, help="Output manifest JSON path.")
    parser.add_argument("--assets-dir", help="Directory where cleaned PNG assets are written. Defaults beside the manifest.")
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--columns", type=int, default=1)
    parser.add_argument("--overlap", type=int, default=0)
    parser.add_argument("--prefix", default="icon")
    parser.add_argument(
        "--light-threshold",
        type=int,
        default=185,
        help="Deprecated compatibility option. Matte detection is now structural and does not erase pixels from this threshold.",
    )
    parser.add_argument(
        "--neutral-threshold",
        type=int,
        default=18,
        help="Deprecated compatibility option. Matte detection is now structural and does not erase pixels from this threshold.",
    )
    parser.add_argument("--orphan-area", type=int, default=64, help="Maximum area of a detached checkerboard residue to clear.")
    parser.add_argument("--grabcut-iterations", type=int, default=5, help="GrabCut refinement passes after checkerboard seed detection.")
    parser.add_argument("--padding", type=int, default=16)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def normalized_path(value, base=None):
    target = Path(value)
    if not target.is_absolute() and base:
        target = Path(base) / target
    return target.resolve()


def source_has_transparency(image):
    if image.mode not in {"RGBA", "LA"}:
        return False
    alpha = image.getchannel("A")
    low, high = alpha.getextrema()
    return low < 255 or high < 255


def edge_connected_mask(mask):
    count, labels, _, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if count <= 1:
        return np.zeros(candidate.shape, dtype=bool)
    edge_labels = np.unique(np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1])))
    edge_labels = edge_labels[edge_labels > 0]
    return np.isin(labels, edge_labels)


def infer_checkerboard(luminance):
    """Infer a checkerboard grid from repeated edge luminance, without a color-key threshold."""
    height, width = luminance.shape
    band = max(2, min(12, min(width, height) // 8))
    side_masks = []
    for side in ("top", "bottom", "left", "right"):
        edge = np.zeros(luminance.shape, dtype=bool)
        if side == "top": edge[:band, :] = True
        elif side == "bottom": edge[-band:, :] = True
        elif side == "left": edge[:, :band] = True
        else: edge[:, -band:] = True
        side_masks.append(edge)

    def find_best(xs, ys):
        if len(xs) < 160:
            return None
        if len(xs) > 5000:
            step = int(np.ceil(len(xs) / 5000))
            xs, ys = xs[::step], ys[::step]
        values = luminance[ys, xs]
        best = None
        for cell_size in range(12, 33):
            for phase_x in range(cell_size):
                x_cells = (xs + phase_x) // cell_size
                for phase_y in range(cell_size):
                    parity = (x_cells + (ys + phase_y) // cell_size) & 1
                    values_a = values[parity == 0]
                    values_b = values[parity == 1]
                    if len(values_a) < 40 or len(values_b) < 40:
                        continue
                    # Medians and median absolute deviations keep artwork touching
                    # the edge from turning into a background color model.
                    mean_a, mean_b = float(np.median(values_a)), float(np.median(values_b))
                    separation = abs(mean_a - mean_b)
                    noise = float(np.median(np.abs(values_a - mean_a)) + np.median(np.abs(values_b - mean_b)))
                    confidence = separation / (1 + noise)
                    if not best or confidence > best["confidence"]:
                        best = {
                            "cellSize": cell_size,
                            "phaseX": phase_x,
                            "phaseY": phase_y,
                            "levels": [round(mean_a, 2), round(mean_b, 2)],
                            "confidence": confidence,
                        }
        return best

    best = None
    for edge in side_masks:
        ys, xs = np.where(edge)
        result = find_best(xs, ys)
        if result and (not best or result["confidence"] > best["confidence"]):
            best = result
    if not best or abs(best["levels"][0] - best["levels"][1]) < 2.5 or best["confidence"] < 0.8:
        return None
    best["confidence"] = round(best["confidence"], 3)
    return best


def checker_reference_mask(luminance, checker):
    """Select pixels that agree with the inferred repeated grid, not with a generic color range."""
    height, width = luminance.shape
    cell_size = checker["cellSize"]
    x_cells = (np.arange(width) + checker["phaseX"]) // cell_size
    y_cells = (np.arange(height) + checker["phaseY"]) // cell_size
    parity = (y_cells[:, None] + x_cells[None, :]) & 1
    levels = np.asarray(checker["levels"], dtype=np.float32)
    expected = levels[parity]
    separation = abs(float(levels[0] - levels[1]))
    # The margin is tied to the two observed grid levels. It is only used to
    # make background seeds; it never independently deletes a pixel.
    tolerance = max(8.0, min(28.0, separation * 0.8 + 4.0))
    return np.abs(luminance - expected) <= tolerance


def checker_cells_mask(reference, luminance, checker):
    """Find whole cells that behave like the inferred matte and use them as soft background seeds."""
    height, width = reference.shape
    cell_size = checker["cellSize"]
    x_cells = (np.arange(width) + checker["phaseX"]) // cell_size
    y_cells = (np.arange(height) + checker["phaseY"]) // cell_size
    levels = checker["levels"]
    output = np.zeros(reference.shape, dtype=bool)
    tolerance = max(8.0, min(28.0, abs(levels[0] - levels[1]) * 0.8 + 4.0))
    for cell_y in np.unique(y_cells):
        y_indexes = np.where(y_cells == cell_y)[0]
        top, bottom = y_indexes[0], y_indexes[-1] + 1
        for cell_x in np.unique(x_cells):
            x_indexes = np.where(x_cells == cell_x)[0]
            left, right = x_indexes[0], x_indexes[-1] + 1
            tile_reference = reference[top:bottom, left:right]
            if float(tile_reference.mean()) < 0.82:
                continue
            expected = levels[(int(cell_x) + int(cell_y)) & 1]
            values = luminance[top:bottom, left:right][tile_reference]
            if len(values) and abs(float(values.mean()) - expected) <= tolerance:
                output[top:bottom, left:right] |= tile_reference
    return output


def checker_orphan_mask(alpha, reference, maximum_area):
    """Remove only tiny opaque fragments that still agree with the inferred checkerboard grid."""
    if maximum_area <= 0:
        return np.zeros(alpha.shape, dtype=bool), {"components": 0, "pixels": 0, "passes": 0}
    working_alpha = alpha.copy()
    output = np.zeros(alpha.shape, dtype=bool)
    kernel = np.ones((5, 5), dtype=np.uint8)
    components = 0
    passes = 0
    while passes < 12:
        count, labels, stats, _ = cv2.connectedComponentsWithStats((working_alpha > 0).astype(np.uint8), connectivity=8)
        pass_mask = np.zeros(alpha.shape, dtype=bool)
        for label in range(1, count):
            _, _, _, _, area = stats[label]
            if area > maximum_area:
                continue
            component = labels == label
            if float(reference[component].mean()) < 0.82:
                continue
            expanded = cv2.dilate(component.astype(np.uint8), kernel, iterations=1).astype(bool)
            ring = expanded & ~component
            if ring.any() and float((working_alpha[ring] == 0).mean()) >= 0.82:
                pass_mask |= component
                components += 1
        if not pass_mask.any():
            break
        working_alpha[pass_mask] = 0
        output |= pass_mask
        passes += 1
    return output, {"components": components, "pixels": int(output.sum()), "passes": passes}


def grabcut_alpha(rgb, certain_background, probable_background, iterations):
    """Refine structural checkerboard seeds with GrabCut; no global color key is used as final alpha."""
    height, width = certain_background.shape
    seed_pixels = int((certain_background | probable_background).sum())
    if min(height, width) < 32 or seed_pixels < 64:
        alpha = np.where(certain_background, 0, 255).astype(np.uint8)
        return alpha, {"mode": "structural-fallback", "iterations": 0, "seedPixels": seed_pixels}

    mask = np.full((height, width), cv2.GC_PR_FGD, dtype=np.uint8)
    mask[probable_background] = cv2.GC_PR_BGD
    mask[certain_background] = cv2.GC_BGD
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(
            cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
            mask,
            None,
            background_model,
            foreground_model,
            max(1, iterations),
            cv2.GC_INIT_WITH_MASK,
        )
    except cv2.error as error:
        alpha = np.where(certain_background | probable_background, 0, 255).astype(np.uint8)
        return alpha, {
            "mode": "structural-fallback",
            "iterations": 0,
            "seedPixels": seed_pixels,
            "error": str(error).split("\n")[0],
        }

    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    return alpha, {
        "mode": "grabcut",
        "iterations": max(1, iterations),
        "seedPixels": seed_pixels,
        "certainBackgroundPixels": int(certain_background.sum()),
        "probableBackgroundPixels": int(probable_background.sum()),
        "foregroundPixels": int((alpha > 0).sum()),
        "backgroundPixels": int((alpha == 0).sum()),
    }


def remove_background(image, light_threshold, neutral_threshold, orphan_area, grabcut_iterations):
    rgba = image.convert("RGBA")
    if source_has_transparency(rgba):
        return rgba, {"mode": "preserved-alpha", "transparentPixels": 0}
    source = np.asarray(rgba).copy()
    rgb = source[:, :, :3]
    luminance = rgb.astype(np.float32).mean(axis=2)
    checker = infer_checkerboard(luminance)
    if not checker:
        alpha = np.full(luminance.shape, 255, dtype=np.uint8)
        source[:, :, 3] = alpha
        return Image.fromarray(source, "RGBA"), {
            "mode": "checkerboard-unrecognized",
            "transparentPixels": 0,
            "checkerboard": None,
            "note": "No repeated checkerboard grid was detected, so no pixels were erased.",
        }

    reference_mask = checker_reference_mask(luminance, checker)
    edge_mask = edge_connected_mask(reference_mask)
    cells_mask = checker_cells_mask(reference_mask, luminance, checker)
    alpha, grabcut = grabcut_alpha(rgb, edge_mask, cells_mask & ~edge_mask, grabcut_iterations)
    orphan_mask, orphan_stats = checker_orphan_mask(alpha, reference_mask, orphan_area)
    alpha[orphan_mask] = 0
    source[:, :, 3] = alpha
    return Image.fromarray(source, "RGBA"), {
        "mode": "checkerboard-grabcut" if grabcut["mode"] == "grabcut" else "checkerboard-structural-fallback",
        "transparentPixels": int((alpha == 0).sum()),
        "edgeConnectedPixels": int(edge_mask.sum()),
        "checkerCellPixels": int(cells_mask.sum()),
        "checkerboard": checker,
        "grabcut": grabcut,
        "orphanResidues": orphan_stats,
    }


def trim_alpha(image, padding):
    alpha = image.getchannel("A")
    box = alpha.getbbox()
    if not box:
        return image, [0, 0, image.width, image.height]
    left, top, right, bottom = box
    padded = (
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    )
    return image.crop(padded), list(padded)


def split_boxes(width, height, rows, columns, overlap):
    boxes = []
    for row in range(rows):
        for column in range(columns):
            left = max(0, round(column * width / columns) - overlap)
            top = max(0, round(row * height / rows) - overlap)
            right = min(width, round((column + 1) * width / columns) + overlap)
            bottom = min(height, round((row + 1) * height / rows) + overlap)
            boxes.append((left, top, right, bottom))
    return boxes


def load_entries(args):
    if args.input:
        return [{
            "input": args.input,
            "rows": max(1, args.rows),
            "columns": max(1, args.columns),
            "overlap": max(0, args.overlap),
            "prefix": args.prefix,
            "names": [],
        }]

    plan_path = normalized_path(args.plan)
    with open(plan_path, "r", encoding="utf-8") as handle:
        plan = json.load(handle)
    entries = plan.get("sources", plan if isinstance(plan, list) else [])
    if not isinstance(entries, list) or not entries:
        raise ValueError("Plan must contain a non-empty sources array")
    plan_dir = plan_path.parent
    normalized = []
    for index, item in enumerate(entries, start=1):
        if not item.get("input"):
            raise ValueError(f"Plan source {index} is missing input")
        normalized.append({
            "input": str(normalized_path(item["input"], plan_dir)),
            "rows": max(1, int(item.get("rows", 1))),
            "columns": max(1, int(item.get("columns", 1))),
            "overlap": max(0, int(item.get("overlap", 0))),
            "prefix": item.get("prefix", f"icon-{index:02d}"),
            "names": item.get("names", []),
        })
    return normalized


def safe_name(value):
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    normalized = "".join(char if char in allowed else "-" for char in value.strip())
    return normalized.strip("-") or "icon"


def write_asset(image, target, force):
    if target.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG")


def main():
    args = parse_args()
    manifest_path = normalized_path(args.output)
    if manifest_path.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite existing manifest: {manifest_path}")
    assets_dir = normalized_path(args.assets_dir) if args.assets_dir else manifest_path.parent / f"{manifest_path.stem}-assets"
    entries = load_entries(args)
    assets = []

    for source_index, entry in enumerate(entries, start=1):
        source = normalized_path(entry["input"])
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image input: {source}")
        if not source.is_file():
            raise FileNotFoundError(f"Input image not found: {source}")
        source_image = Image.open(source)
        boxes = split_boxes(source_image.width, source_image.height, entry["rows"], entry["columns"], entry["overlap"])
        names = entry["names"]
        if names and len(names) != len(boxes):
            raise ValueError(f"Plan source {source_index} defines {len(names)} names for {len(boxes)} tiles")

        for tile_index, box in enumerate(boxes, start=1):
            tile = source_image.crop(box)
            cleaned, background = remove_background(
                tile,
                args.light_threshold,
                args.neutral_threshold,
                max(0, args.orphan_area),
                max(1, args.grabcut_iterations),
            )
            final_image, trim_box = trim_alpha(cleaned, max(0, args.padding))
            stem = names[tile_index - 1] if names else f"{entry['prefix']}-{tile_index:02d}"
            filename = f"{safe_name(stem)}.png"
            target = assets_dir / filename
            write_asset(final_image, target, args.force)
            assets.append({
                "id": Path(filename).stem,
                "file": str(target),
                "source": str(source),
                "sourceIndex": source_index,
                "tileIndex": tile_index,
                "sourceBox": list(box),
                "trimBox": trim_box,
                "width": final_image.width,
                "height": final_image.height,
                "alpha": True,
                "background": background,
            })

    manifest = {
        "version": 1,
        "operation": "icon-checkerboard-matte-extraction",
        "outputDirectory": str(assets_dir),
        "lightThreshold": args.light_threshold,
        "neutralThreshold": args.neutral_threshold,
        "orphanArea": args.orphan_area,
        "grabcutIterations": args.grabcut_iterations,
        "padding": args.padding,
        "assets": assets,
        "files": [asset["file"] for asset in assets],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"manifest": str(manifest_path), "assets": len(assets), "files": manifest["files"]}))


if __name__ == "__main__":
    main()
