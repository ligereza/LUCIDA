import json

import pytest

from resolume_adapter.instar_routing import import_pixel_peeker_routing
from resolume_adapter.media import ResolumeAdapterError


def interchange() -> dict:
    return {
        "format": "pixel-peeker.interchange/1",
        "generatedBy": "Pixel Peeker",
        "project": {"name": "Fonda test"},
        "signal": {"bitDepth": 8, "frameRateHz": 60, "ledRefreshHz": 3840},
        "wall": {
            "widthPx": 2560,
            "heightPx": 1024,
            "referencePitchMm": 3.9,
            "approximatePixelMap": False,
            "cabinetCount": 2,
            "totalPixels": 262144,
        },
        "capacityModel": {"note": "test", "wireBitsPerPixel": 24},
        "processors": [
            {
                "name": "MX40 A",
                "model": "MX40 Pro",
                "manufacturer": "NovaStar",
                "deviceCapacityPx": 9000000,
                "usedPx": 262144,
                "ports": [
                    {
                        "label": "ETH 1",
                        "linkSpeedGbps": 10,
                        "capacityPx": 659722,
                        "usedPx": 262144,
                        "utilisationPct": 40,
                        "cabinets": [
                            {"order": 1, "id": "cab-1", "model": "P3.9", "xPx": 0, "yPx": 0, "widthPx": 2560, "heightPx": 512},
                            {"order": 2, "id": "cab-2", "model": "P3.9", "xPx": 0, "yPx": 512, "widthPx": 2560, "heightPx": 512},
                        ],
                    }
                ],
            }
        ],
        "unpatchedCabinets": [],
    }


def test_import_derives_port_bounds_without_claiming_physical_truth():
    report = import_pixel_peeker_routing(interchange())

    port = report["processors"][0]["ports"][0]
    assert port["bounds"] == {"x": 0, "y": 0, "width": 2560, "height": 1024}
    assert report["status"] == {
        "import_status": "IMPORTED",
        "geometry_status": "NOT_COMPARED",
        "physical_status": "UNVERIFIED",
    }
    assert report["validation"]["status"] == "REVIEW"


def test_import_matches_a_layout_report_exactly(tmp_path):
    interchange_path = tmp_path / "wall-interchange.json"
    layout_path = tmp_path / "layout.json"
    interchange_path.write_text(json.dumps(interchange()), encoding="utf-8")
    layout_path.write_text(
        json.dumps({"regions": [{"name": "CENTRAL", "bounds": {"x": 0, "y": 0, "width": 2560, "height": 1024}}]}),
        encoding="utf-8",
    )

    report = import_pixel_peeker_routing(interchange_path, layout_report=layout_path)

    assert report["comparison"]["geometry_status"] == "GEOMETRIC_MATCH"
    assert report["comparison"]["matches"][0]["surface"] == "CENTRAL"
    assert report["comparison"]["matches"][0]["method"] == "exact_geometry"
    assert report["validation"]["status"] == "PASS"
    assert report["status"]["physical_status"] == "UNVERIFIED"


def test_import_accepts_svg_slice_points(tmp_path):
    layout_path = tmp_path / "svg-layout.json"
    layout_path.write_text(
        json.dumps({
            "slices": [{
                "name": "CENTRAL",
                "input_points": [[0, 0], [2560, 0], [2560, 1024], [0, 1024]],
            }]
        }),
        encoding="utf-8",
    )

    report = import_pixel_peeker_routing(interchange(), layout_report=layout_path)

    assert report["comparison"]["geometry_status"] == "GEOMETRIC_MATCH"
    assert report["comparison"]["matches"][0]["surface"] == "CENTRAL"


def test_import_rejects_another_json_schema():
    with pytest.raises(ResolumeAdapterError, match="Formato no soportado"):
        import_pixel_peeker_routing({"format": "pixel-peeker.project/1"})


def test_import_rejects_negative_tolerance():
    with pytest.raises(ResolumeAdapterError, match="no puede ser negativa"):
        import_pixel_peeker_routing(interchange(), tolerance=-1)
