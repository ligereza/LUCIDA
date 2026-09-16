from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

import cv2
import numpy as np

from resolume_adapter.instar_template import (
    apply_input_svg_to_template,
    apply_raster_image_to_template,
    apply_routed_layout_to_template,
)
from resolume_adapter.resolume import extract_advanced_output_map


class InstarInputTemplateTests(unittest.TestCase):
    def test_routed_layout_changes_only_input_rect(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.xml"
            interchange = root / "interchange.json"
            layout = root / "layout.json"
            output = root / "candidate.xml"
            template.write_text(
                '''<?xml version="1.0" encoding="utf-8"?>
<XmlState><ScreenSetup><CurrentCompositionTextureSize width="1000" height="500"/><screens>
<Screen name="Screen"><Params name="Params"/><OutputDevice><OutputDeviceVirtual name="Physical" deviceId="D1" width="1920" height="1080"/></OutputDevice><layers>
<Slice><Params name="Common"><Param name="Name" value="MX40 A ETH 1"/></Params><InputRect><v x="0" y="0"/><v x="10" y="0"/><v x="10" y="10"/><v x="0" y="10"/></InputRect><OutputRect><v x="200" y="300"/><v x="600" y="300"/><v x="600" y="500"/><v x="200" y="500"/></OutputRect></Slice>
</layers></Screen></screens></ScreenSetup></XmlState>''',
                encoding="utf-8",
            )
            interchange.write_text(
                json.dumps({
                    "format": "pixel-peeker.interchange/1",
                    "project": {"name": "Test"},
                    "wall": {"widthPx": 1000, "heightPx": 500},
                    "processors": [{
                        "name": "MX40 A",
                        "model": "MX40 Pro",
                        "manufacturer": "NovaStar",
                        "deviceCapacityPx": 9000000,
                        "usedPx": 400000,
                        "ports": [{
                            "label": "ETH 1",
                            "linkSpeedGbps": 10,
                            "capacityPx": 659722,
                            "usedPx": 400000,
                            "utilisationPct": 61,
                            "cabinets": [{
                                "order": 1,
                                "id": "cab-1",
                                "model": "P3.9",
                                "xPx": 100,
                                "yPx": 50,
                                "widthPx": 400,
                                "heightPx": 200,
                            }],
                        }],
                    }],
                }),
                encoding="utf-8",
            )
            layout.write_text(
                json.dumps({"regions": [{"name": "CENTRAL", "bounds": {"x": 100, "y": 50, "width": 400, "height": 200}}]}),
                encoding="utf-8",
            )

            report = apply_routed_layout_to_template(template, interchange, layout, output)
            parsed = extract_advanced_output_map(output)
            item = parsed["slices"][0]

            self.assertEqual(report["validation"]["status"], "PASS")
            self.assertEqual(report["physical_status"], "UNVERIFIED")
            self.assertEqual(item["input"]["bounds"], {"x": 100.0, "y": 50.0, "width": 400.0, "height": 200.0})
            self.assertEqual(item["output"]["bounds"], {"x": 200.0, "y": 300.0, "width": 400.0, "height": 200.0})
            self.assertIn('deviceId="D1"', output.read_text(encoding="utf-8"))

    def test_updates_input_rect_and_preserves_output_rect(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.xml"
            source = root / "input.svg"
            output = root / "candidate.xml"
            template.write_text(
                '''<?xml version="1.0" encoding="utf-8"?>
<XmlState name="Venue"><ScreenSetup name="ScreenSetup">
<CurrentCompositionTextureSize width="1000" height="500"/><screens><Screen name="Screen" uniqueId="screen-1">
<Params name="Params"><Param name="Name" value="Screen"/><Param name="Enabled" value="1"/></Params>
<OutputDevice><OutputDeviceVirtual name="Virtual" deviceId="Virtual" width="1920" height="1080"/></OutputDevice>
<layers><Slice uniqueId="slice-1"><Params name="Common"><Param name="Name" value="MAIN"/></Params>
<InputRect orientation="0"><v x="0" y="0"/><v x="100" y="0"/><v x="100" y="100"/><v x="0" y="100"/></InputRect>
<OutputRect orientation="0"><v x="200" y="300"/><v x="600" y="300"/><v x="600" y="500"/><v x="200" y="500"/></OutputRect>
</Slice></layers></Screen></screens></ScreenSetup></XmlState>''',
                encoding="utf-8",
            )
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500"><rect id="MAIN" x="400" y="100" width="500" height="250"/></svg>',
                encoding="utf-8",
            )

            report = apply_input_svg_to_template(template, source, output)
            parsed = extract_advanced_output_map(output)
            item = parsed["slices"][0]

            self.assertEqual(report["validation"]["status"], "PASS")
            self.assertEqual(item["input"]["bounds"], {"x": 400.0, "y": 100.0, "width": 500.0, "height": 250.0})
            self.assertEqual(item["output"]["bounds"], {"x": 200.0, "y": 300.0, "width": 400.0, "height": 200.0})

    def test_alias_match_is_explicit_and_partial_templates_stay_in_review(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.xml"
            source = root / "input.svg"
            output = root / "candidate.xml"
            template.write_text(
                '''<?xml version="1.0" encoding="utf-8"?>
<XmlState><ScreenSetup><CurrentCompositionTextureSize width="1000" height="500"/><screens>
<Screen name="Screen"><Params name="Params"/><layers>
<Slice><Params name="Common"><Param name="Name" value="MAIN CENTER"/></Params><InputRect><v x="0" y="0"/><v x="1" y="0"/><v x="1" y="1"/><v x="0" y="1"/></InputRect><OutputRect><v x="0" y="0"/><v x="1" y="0"/><v x="1" y="1"/><v x="0" y="1"/></OutputRect></Slice>
<Slice><Params name="Common"><Param name="Name" value="OTHER"/></Params><InputRect><v x="0" y="0"/><v x="1" y="0"/><v x="1" y="1"/><v x="0" y="1"/></InputRect><OutputRect><v x="0" y="0"/><v x="1" y="0"/><v x="1" y="1"/><v x="0" y="1"/></OutputRect></Slice>
</layers></Screen></screens></ScreenSetup></XmlState>''',
                encoding="utf-8",
            )
            source.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500"><rect id="CENTRAL" x="100" y="50" width="500" height="250"/></svg>',
                encoding="utf-8",
            )

            report = apply_input_svg_to_template(template, source, output, aliases={"CENTRAL": "MAIN CENTER"})

            self.assertEqual(report["validation"]["status"], "REVIEW")
            self.assertEqual(report["matched_slices"], ["MAIN CENTER"])
            self.assertEqual(report["unmatched_template"], ["OTHER"])
            self.assertEqual(report["match_methods"], {"MAIN CENTER": "alias"})

    def test_raster_image_updates_template_input_without_touching_output(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "map.png"
            template = root / "template.xml"
            output = root / "candidate.xml"
            pixels = np.zeros((500, 800, 3), dtype=np.uint8)
            cv2.rectangle(pixels, (20, 40), (780, 160), (0, 255, 255), -1)
            self.assertTrue(cv2.imwrite(str(image), pixels))
            template.write_text(
                '''<?xml version="1.0" encoding="utf-8"?>
<XmlState><ScreenSetup><CurrentCompositionTextureSize width="1000" height="500"/><screens>
<Screen name="Screen"><Params name="Params"/><OutputDevice><OutputDeviceVirtual name="Display" deviceId="Display" width="1920" height="1080"/></OutputDevice><layers>
<Slice><Params name="Common"><Param name="Name" value="MAIN_SURFACE"/></Params><InputRect><v x="0" y="0"/><v x="1" y="0"/><v x="1" y="1"/><v x="0" y="1"/></InputRect><OutputRect><v x="200" y="300"/><v x="600" y="300"/><v x="600" y="500"/><v x="200" y="500"/></OutputRect></Slice>
</layers></Screen></screens></ScreenSetup></XmlState>''',
                encoding="utf-8",
            )

            report = apply_raster_image_to_template(template, image, output, canvas_size=(1000, 500))
            parsed = extract_advanced_output_map(output)
            item = parsed["slices"][0]

            self.assertEqual(report["validation"]["status"], "PASS")
            self.assertEqual(report["source"]["input_kind"], "raster")
            self.assertEqual(report["source"]["input_image"], str(image.resolve()))
            self.assertEqual(item["input"]["bounds"], {"x": 0.0, "y": 0.0, "width": 1000.0, "height": 500.0})
            self.assertEqual(item["output"]["bounds"], {"x": 200.0, "y": 300.0, "width": 400.0, "height": 200.0})
