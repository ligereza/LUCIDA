from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from resolume_adapter.instar_template import apply_input_svg_to_template
from resolume_adapter.resolume import extract_advanced_output_map


class InstarInputTemplateTests(unittest.TestCase):
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
