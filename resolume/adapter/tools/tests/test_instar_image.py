from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import cv2
import numpy as np

from resolume_adapter.instar_image import _annotate_regions, _extract_ocr_metadata, build_raster_mapping, detect_raster_surfaces
from resolume_adapter.resolume import extract_advanced_output_map


class InstarRasterMappingTests(unittest.TestCase):
    def _image(self, path: Path) -> None:
        image = np.zeros((500, 800, 3), dtype=np.uint8)
        cv2.rectangle(image, (20, 80), (420, 160), (0, 255, 255), -1)
        cv2.rectangle(image, (20, 170), (420, 450), (255, 0, 0), -1)
        cv2.rectangle(image, (20, 460), (420, 490), (0, 140, 255), -1)
        cv2.rectangle(image, (450, 80), (600, 450), (255, 0, 255), -1)
        cv2.rectangle(image, (610, 80), (780, 450), (0, 0, 255), -1)
        self.assertTrue(cv2.imwrite(str(path), image))

    def test_detects_five_large_surface_regions(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "mapping.png"
            self._image(image)
            report = detect_raster_surfaces(image, canvas_size=(4186, 1283))

            self.assertEqual(len(report["regions"]), 5)
            self.assertEqual(report["validation"]["status"], "REVIEW")
            self.assertEqual(
                [region["source_color_family"] for region in report["regions"]],
                ["yellow", "magenta", "red", "blue", "orange"],
            )

    def test_raster_candidate_round_trips_as_five_slices(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "mapping.png"
            xml = root / "mapping.xml"
            self._image(image)
            report = build_raster_mapping(image, xml, canvas_size=(4186, 1283))
            parsed = extract_advanced_output_map(xml)

            self.assertEqual(len(report["regions"]), 5)
            self.assertEqual(parsed["statistics"]["slices"], 5)
            self.assertEqual(parsed["composition"], {"width": 4186, "height": 1283})

    def test_ocr_lines_resolve_names_and_dimensions_by_region(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "mapping.png"
            self._image(image)
            report = detect_raster_surfaces(image, canvas_size=(4186, 1283))
            report["ocr"] = {
                "available": True,
                "lines": [
                    {"x": 100, "y": 90, "width": 100, "height": 20, "text": "BANNER FRONTAL"},
                    {"x": 100, "y": 220, "width": 100, "height": 20, "text": "CENTRAL W 2560 x H 1024"},
                ],
            }

            resolved = _annotate_regions(report)

            self.assertEqual(resolved, 2)
            self.assertEqual(report["regions"][0]["name"], "BANNER_FRONTAL")
            central = next(region for region in report["regions"] if region["name"] == "CENTRAL")
            self.assertEqual(central["declared_resolution"], {"width": 2560, "height": 1024, "source": "ocr"})
            self.assertEqual(central["bounds"]["width"], 2560.0)
            self.assertEqual(central["bounds"]["height"], 1024.0)
            self.assertEqual(central["geometry_source"], "raster_detection_plus_ocr_dimensions")

    def test_ocr_metadata_extracts_canvas_panel_spec_and_total(self) -> None:
        metadata = _extract_ocr_metadata({
            "text": "Resolución Total: 4186px x 1283px Paneles Activos: 320 un. P3.9 50 50 cm Área Física Total: 80.00 m2",
            "lines": [],
        })

        self.assertEqual(metadata["canvas_size"], {"width": 4186, "height": 1283, "source": "ocr"})
        self.assertEqual(metadata["pixel_pitch_mm"], 3.9)
        self.assertEqual(metadata["panel_size_cm"], {"width": 50.0, "height": 50.0})
        self.assertEqual(metadata["active_panels"], 320)
        self.assertEqual(metadata["physical_area_m2"], 80.0)


if __name__ == "__main__":
    unittest.main()
