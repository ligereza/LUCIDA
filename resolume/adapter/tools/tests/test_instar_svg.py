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


if __name__ == "__main__":
    unittest.main()
