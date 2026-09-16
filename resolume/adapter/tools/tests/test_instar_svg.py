from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from resolume_adapter.instar_svg import build_svg_mapping
from resolume_adapter.resolume import extract_advanced_output_map


class InstarSvgMappingTests(unittest.TestCase):
    def test_svg_candidate_round_trips_through_existing_reader(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.svg"
            output = root / "output.xml"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500">'
                '<rect id="MAIN" x="0" y="0" width="500" height="500"/>'
                '<g transform="translate(500 0)"><polygon id="SIDE" points="0,0 500,0 450,500 0,500"/></g>'
                '</svg>',
                encoding="utf-8",
            )

            report = build_svg_mapping(source, output, composition_size=(1000, 500), output_size=(1920, 1080))
            parsed = extract_advanced_output_map(output)

            self.assertEqual(report["validation"]["status"], "WARN")
            self.assertEqual(parsed["composition"], {"width": 1000, "height": 500})
            self.assertEqual(parsed["statistics"]["slices"], 2)
            self.assertEqual([item["name"] for item in parsed["slices"]], ["MAIN", "SIDE"])
            self.assertEqual(parsed["screens"][0]["devices"][0]["width"], 1920)
            self.assertEqual(parsed["screens"][0]["devices"][0]["height"], 1080)

    def test_separate_output_svg_keeps_input_and_output_geometry(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.svg"
            output_source = root / "output.svg"
            output = root / "output.xml"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500">'
                '<rect id="CENTER" x="100" y="50" width="400" height="300"/></svg>',
                encoding="utf-8",
            )
            output_source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080">'
                '<rect id="CENTER_OUT" x="200" y="100" width="800" height="600"/></svg>',
                encoding="utf-8",
            )

            build_svg_mapping(source, output, output_svg=output_source)
            parsed = extract_advanced_output_map(output)
            item = parsed["slices"][0]

            self.assertEqual(item["input"]["bounds"], {"x": 100.0, "y": 50.0, "width": 400.0, "height": 300.0})
            self.assertEqual(item["output"]["bounds"], {"x": 200.0, "y": 100.0, "width": 800.0, "height": 600.0})

    def test_svg_ignores_background_and_outline_when_surface_fills_are_marked(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "annotated-map.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500">'
                '<rect x="0" y="0" width="1000" height="500" fill="#000000"/>'
                '<rect x="0" y="0" width="400" height="500" fill="#00ffff" fill-opacity="0.85"/>'
                '<rect x="0" y="0" width="400" height="500" fill="none" stroke="#ffffff"/>'
                '<rect x="500" y="0" width="400" height="500" fill="#ffaa00" fill-opacity="0.85"/>'
                '<text x="950" y="20">not a surface</text>'
                '</svg>',
                encoding="utf-8",
            )

            report = build_svg_mapping(source, Path(directory) / "output.xml")

            self.assertEqual([item["name"] for item in report["slices"]], ["Slice_002", "Slice_004"])

    def test_svg_report_canvas_and_text_annotations_are_not_surfaces(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "report-map.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1400">'
                '<rect x="0" y="0" width="1200" height="1400" fill="#07080b"/>'
                '<g transform="translate(0 100)">'
                '<rect x="0" y="0" width="1000" height="1200" fill="#000000"/>'
                '<rect x="0" y="0" width="500" height="600" fill="#00ffff" fill-opacity="0.85"/>'
                '<text x="20" y="40">PANTALLA CENTRAL</text>'
                '</g><text x="20" y="40">Full Canvas Layout</text></svg>',
                encoding="utf-8",
            )

            report = build_svg_mapping(source, Path(directory) / "output.xml")

            self.assertEqual(report["composition"], {"width": 1000, "height": 1200})
            self.assertEqual([item["name"] for item in report["slices"]], ["PANTALLA CENTRAL"])

    def test_svg_extracts_surface_name_before_inline_dimensions(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "inline-label-map.svg"
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500">'
                '<rect x="0" y="0" width="500" height="500" fill="#00ffff" fill-opacity="0.85"/>'
                '<text x="20" y="40">CIELO - CARA LARGA N 6.0 x 0.5 m 1536x128px pos(0,784)</text>'
                '</svg>',
                encoding="utf-8",
            )

            report = build_svg_mapping(source, Path(directory) / "output.xml")

            self.assertEqual([item["name"] for item in report["slices"]], ["CIELO - CARA LARGA N"])


if __name__ == "__main__":
    unittest.main()
