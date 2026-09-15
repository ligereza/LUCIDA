import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.resolume_adapter.adapt import build_adaptation_plan, build_filter_graph, render_task
from tools.resolume_adapter.instar import discover_media_files, run_instar
from tools.resolume_adapter.media import ResolumeAdapterError, format_fps, has_alpha, parse_fraction
from tools.resolume_adapter.nayade import build_experiment_matrix, create_session, get_next_step, record_event
from tools.resolume_adapter.processors import (
    build_processor_snapshot,
    diagnose_case,
    discover_serial_devices,
    match_processor_profiles,
    validate_processor_case,
    validate_processor_case_document,
)
from tools.resolume_adapter.preflight import preflight_file, sidecar_from_report
from tools.resolume_adapter.contracts import build_clip_profile, derive_behavior_profile, suggest_semantic_cues
from tools.resolume_adapter.resolume import (
    build_mapping_plan,
    extract_advanced_output_map,
    extract_cue_map,
    run_resolume_audit,
)
from tools.resolume_adapter.testcard import build_testcard_spec, render_testcard


class AdaptationTests(unittest.TestCase):
    def test_filter_graph_preserves_target_for_crop_and_pattern(self):
        source = {"video": {"width": 1920, "height": 1080}}
        crop = build_filter_graph("crop", source, 1520, 180)
        pattern = build_filter_graph("pattern", source, 1520, 180, axis="horizontal")
        marquee = build_filter_graph("marquee", source, 1520, 180, axis="horizontal")
        self.assertIn("crop=1520:180", crop)
        self.assertIn("hstack=inputs=", pattern)
        self.assertIn("crop=1520:180:", marquee)
        self.assertIn("mod(t*120", marquee)
    def test_adaptation_plan_deduplicates_shared_input_group(self):
        mapping_plan = {
            "plan_type": "InstarResolumeMappingPlan",
            "source_map": {"path": "venue.xml"},
            "slice_candidates": [
                {
                    "slice_id": "bottom-1",
                    "slice_name": "ABAJO 1",
                    "input_group_id": "group-bottom",
                    "target": {"width": 1520, "height": 180},
                    "fallback_strategies": [
                        {
                            "operation": "pattern",
                            "input_group_id": "group-bottom",
                            "axis": "horizontal",
                            "candidate_assets": [
                                {
                                    "asset_id": "asset-1",
                                    "asset_path": "clip.mp4",
                                    "filename": "clip.mp4",
                                    "score": 0.9,
                                    "status": "candidate",
                                },
                            ],
                        },
                    ],
                },
                {
                    "slice_id": "bottom-2",
                    "slice_name": "ABAJO 2",
                    "input_group_id": "group-bottom",
                    "target": {"width": 1520, "height": 180},
                    "fallback_strategies": [
                        {
                            "operation": "pattern",
                            "input_group_id": "group-bottom",
                            "axis": "horizontal",
                            "candidate_assets": [
                                {
                                    "asset_id": "asset-1",
                                    "asset_path": "clip.mp4",
                                    "filename": "clip.mp4",
                                    "score": 0.9,
                                    "status": "candidate",
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        plan = build_adaptation_plan(mapping_plan, "artifacts/adaptation")
        self.assertEqual(len(plan["tasks"]), 1)
        self.assertEqual(plan["tasks"][0]["target"]["input_group_id"], "group-bottom")
        self.assertTrue(plan["tasks"][0]["requires_preview"])
        self.assertFalse(plan["dxv_export_requested"])

    def test_adaptation_plan_declares_separate_dxv_output(self):
        plan = build_adaptation_plan(
            {"plan_type": "InstarResolumeMappingPlan", "slice_candidates": []},
            "previews",
            dxv_output_dir="dxv",
        )
        self.assertTrue(plan["dxv_export_requested"])
        self.assertTrue(plan["dxv_output_dir"].endswith("dxv"))

    def test_existing_preview_can_be_validated_without_rendering(self):
        with TemporaryDirectory() as directory:
            preview = Path(directory) / "preview.mp4"
            preview.write_bytes(b"placeholder")
            task = {
                "task_id": "adapt-001",
                "source": str(preview),
                "output": str(preview),
                "strategy": "pattern",
                "axis": "horizontal",
                "target": {"width": 1520, "height": 180},
            }
            probe = {
                "video": {
                    "codec_name": "h264",
                    "width": 1520,
                    "height": 180,
                    "avg_frame_rate": "30/1",
                    "r_frame_rate": "30/1",
                    "pix_fmt": "yuv420p",
                },
                "format": {"duration": "1.0"},
                "audio": None,
            }
            with patch("tools.resolume_adapter.adapt.probe_media", return_value=probe):
                result = render_task(task)
            self.assertEqual(result["status"], "EXISTS")
            self.assertEqual(result["output_video"]["width"], 1520)

    def test_nayade_matrix_includes_instar_adaptations(self):
        slices = [{"slice_id": "slice-1", "slice_name": "banner", "input_group_id": "group-1", "orientation": "horizontal"}]
        adaptations = [{
            "task_id": "adapt-001",
            "strategy": "marquee",
            "axis": "horizontal",
            "target": {"input_group_id": "group-1", "width": 1520, "height": 180},
            "output": "preview.mp4",
            "dxv": {"output": "preview_DXV.mov"},
        }]
        steps = build_experiment_matrix(slices, adaptations=adaptations)
        step = next(item for item in steps if item["operation"] == "instar_adaptation")
        self.assertEqual(step["targets"], ["group-1"])
        self.assertEqual(step["parameters"]["dxv"], "preview_DXV.mov")

    def test_nayade_next_and_record_advance_the_planned_step(self):
        with TemporaryDirectory() as directory:
            session_path = Path(directory) / "session.json"
            session = {
                "session_type": "NayadeSoundcheckSession",
                "planned_steps": [{
                    "step_id": "step-001",
                    "operation": "baseline",
                    "scope": "input_group",
                    "targets": ["group-1"],
                    "parameters": {},
                    "expected_checks": ["geometry"],
                    "result": "planned",
                }],
                "events": [],
                "targets": {"input_groups": ["group-1"]},
            }
            session_path.write_text(json.dumps(session), encoding="utf-8")
            self.assertEqual(get_next_step(session_path)["step_id"], "step-001")
            event = record_event(
                session_path,
                operation="baseline",
                result="approved",
                targets=["group-1"],
            )
            self.assertEqual(event["planned_step_id"], "step-001")
            self.assertIsNone(get_next_step(session_path))


class MediaHelpersTests(unittest.TestCase):
    def test_parse_fraction(self):
        self.assertAlmostEqual(parse_fraction("30000/1001"), 29.97002997, places=5)

    def test_parse_invalid_fraction(self):
        self.assertIsNone(parse_fraction("0/0"))
        self.assertIsNone(parse_fraction("N/A"))

    def test_format_fps(self):
        self.assertEqual(format_fps("60/1"), "60")
        self.assertEqual(format_fps("30000/1001"), "29.97")

    def test_detect_alpha_pixel_formats(self):
        self.assertTrue(has_alpha({"codec_name": "cfhd", "pix_fmt": "gbrap12le"}))
        self.assertFalse(has_alpha({"codec_name": "h264", "pix_fmt": "yuv420p"}))
        self.assertIsNone(has_alpha({"codec_name": "dxv", "pix_fmt": "rgba"}))


class InstarTests(unittest.TestCase):
    def test_behavior_profile_separates_inferred_pattern_from_protected_content(self):
        samples = [
            {
                "time_s": index * 0.25,
                "mean_luma": 40 + (index % 4) * 20,
                "min_luma": 0,
                "max_luma": 180,
                "mean_rgb": [40 + (index % 4) * 20] * 3,
                "delta": 20,
            }
            for index in range(16)
        ]
        report = {
            "input": "abstract_loop.mp4",
            "video": {"width": 1920, "height": 1080, "duration_seconds": 4.0},
            "analysis": {
                "samples": samples,
                "motion": {"mean": 0.08},
                "periodicity": {"status": "candidate", "period_s": 1.0, "confidence": 0.9},
            },
        }

        behavior = derive_behavior_profile(report)
        profile = build_clip_profile(report, source_path="abstract_loop.mp4")

        self.assertEqual(behavior["status"], "inferred")
        self.assertEqual(behavior["pattern"]["horizontal"]["status"], "inferred")
        self.assertEqual(behavior["transformations"]["rotate_90"]["status"], "review")
        self.assertIn("behavior", profile["visual"])

        spatial_report = dict(report)
        spatial_report["analysis"] = dict(report["analysis"])
        spatial_report["analysis"]["spatial"] = {
            "edge_similarity_horizontal": 0.92,
            "edge_similarity_vertical": 0.31,
            "edge_energy_horizontal": 0.30,
            "edge_energy_vertical": 0.02,
        }
        spatial_behavior = derive_behavior_profile(spatial_report)
        self.assertEqual(spatial_behavior["pattern"]["horizontal"]["status"], "candidate")
        self.assertEqual(spatial_behavior["pattern"]["vertical"]["status"], "weak")
        self.assertIn("gpu_spatial_edge_analysis", spatial_behavior["pattern"]["horizontal"]["basis"])

        protected = derive_behavior_profile({"video": {"width": 1920, "height": 1080}}, source_path="sponsor_logo.mp4")
        self.assertEqual(protected["transformations"]["flip_horizontal"]["status"], "review")
        self.assertEqual(protected["pattern"]["horizontal"]["status"], "not_available")

        geometric = derive_behavior_profile({"video": {"width": 1920, "height": 1080}}, source_path="circulo_loop.mp4")
        self.assertTrue(geometric["geometry_test"]["required"])
        self.assertEqual(geometric["content_flags"]["geometry_tokens"], ["circulo"])

    def test_suggests_change_strobe_and_loop_cues_from_visual_series(self):
        pattern = [
            (20, 0, 40),
            (24, 4, 44),
            (40, 20, 60),
            (25, 15, 45),
            (20, 5, 40),
            (24, 4, 44),
            (40, 20, 60),
            (25, 15, 45),
            (220, 220, 250),
            (20, 220, 250),
            (220, 220, 250),
            (20, 220, 250),
            (25, 5, 45),
            (30, 5, 50),
            (40, 10, 60),
            (25, 15, 45),
        ]
        samples = []
        for index in range(48):
            mean_luma, delta, max_luma = pattern[index % len(pattern)]
            samples.append(
                {
                    "time_s": index * 0.25,
                    "mean_luma": mean_luma,
                    "min_luma": 0,
                    "max_luma": max_luma,
                    "delta": delta,
                }
            )

        suggestions = suggest_semantic_cues(
            {
                "samples": samples,
                "periodicity": {"status": "candidate", "period_s": 4.0, "confidence": 0.9},
                "flash_screening": {
                    "candidates": [
                        {"time_s": 2.0},
                        {"time_s": 2.25},
                        {"time_s": 2.5},
                        {"time_s": 2.75},
                    ]
                },
            },
            duration_seconds=12.0,
        )

        roles = {cue["role"] for cue in suggestions["cues"]}
        self.assertEqual(suggestions["status"], "REVIEW")
        self.assertIn("change", roles)
        self.assertIn("strobe_window", roles)
        self.assertIn("loop", roles)
        self.assertTrue(any(cue.get("strobe_candidate") for cue in suggestions["cues"] if cue["role"] == "change"))
        loop = next(cue for cue in suggestions["cues"] if cue["role"] == "loop")
        self.assertLess(loop["in_position_s"], loop["out_position_s"])

    def test_does_not_invent_cues_for_static_visual(self):
        samples = [
            {
                "time_s": index * 0.25,
                "mean_luma": 100,
                "min_luma": 80,
                "max_luma": 120,
                "delta": 0,
            }
            for index in range(32)
        ]

        suggestions = suggest_semantic_cues(
            {
                "samples": samples,
                "periodicity": {"status": "candidate", "period_s": 1.0, "confidence": 0.8},
            },
            duration_seconds=8.0,
        )

        self.assertEqual(suggestions["status"], "NO_CANDIDATES")
        self.assertEqual(suggestions["cues"], [])

    def test_semantic_cues_require_enough_samples(self):
        suggestions = suggest_semantic_cues({"samples": [{"time_s": 0.0}] * 7})

        self.assertEqual(suggestions["status"], "NOT_AVAILABLE")
        self.assertEqual(suggestions["cues"], [])

    def test_preflight_separates_mp4_container_from_alpha(self):
        with TemporaryDirectory() as directory:
            media = Path(directory) / "clip.mp4"
            media.write_bytes(b"placeholder")
            probe = {
                "format": {
                    "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                    "format_long_name": "ISO Media, MP4 Base Media v1",
                    "duration": "4.0",
                    "size": "11",
                },
                "video": {
                    "codec_name": "h264",
                    "codec_long_name": "H.264",
                    "width": 1920,
                    "height": 1080,
                    "pix_fmt": "yuv420p",
                    "avg_frame_rate": "30/1",
                    "r_frame_rate": "30/1",
                    "field_order": "progressive",
                },
                "audio": None,
            }
            with patch("tools.resolume_adapter.preflight.probe_media", return_value=probe):
                report = preflight_file(media)

            self.assertEqual(report["container"]["name"], "MP4/ISO BMFF")
            self.assertEqual(report["video"]["codec"], "h264")
            self.assertEqual(report["alpha"]["status"], "absent")
            self.assertEqual(report["overall_status"], "PASS")

            sidecar = sidecar_from_report(report)
            self.assertEqual(sidecar["technical"]["alpha"]["encoded"], False)
            self.assertEqual(sidecar["media"]["filename"], "clip.mp4")

    def test_discover_media_files_is_recursive_and_filters_extensions(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clip.MP4").touch()
            (root / "notes.txt").touch()
            nested = root / "nested"
            nested.mkdir()
            (nested / "loop.mov").touch()

            self.assertEqual(
                discover_media_files(root),
                [root / "clip.MP4", nested / "loop.mov"],
            )

    def test_run_instar_aggregates_shared_diagnostics(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.mp4"
            second = root / "second.mov"
            first.touch()
            second.touch()

            def fake_diagnose(path, **_kwargs):
                status = "PASS" if Path(path).name == "first.mp4" else "WARN"
                return {
                    "overall_status": status,
                    "video": {"codec": "dxv", "width": 1920, "height": 1080, "average_fps": "60"},
                }

            with patch("tools.resolume_adapter.instar.preflight_file", side_effect=fake_diagnose):
                report = run_instar(root)

            self.assertEqual(report["overall_status"], "WARN")
            self.assertEqual(report["files_found"], 2)
            self.assertEqual(report["mode"], "technical")
            self.assertEqual([item["status"] for item in report["items"]], ["PASS", "WARN"])


class ResolumeAuditTests(unittest.TestCase):
    def test_advanced_output_keeps_input_and_output_geometry_separate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            preset = root / "venue.xml"
            preset.write_text(
                '''<?xml version="1.0" encoding="utf-8"?>
<XmlState name="Venue">
  <versionInfo name="Resolume Arena" majorVersion="7" minorVersion="27" microVersion="1" revision="1"/>
  <ScreenSetup name="ScreenSetup">
    <CurrentCompositionTextureSize width="1920" height="1080"/>
    <screens>
      <Screen name="Screen 1" uniqueId="screen-1">
        <Params name="Params">
          <Param name="Name" value="Screen 1"/>
          <Param name="Enabled" value="1"/>
        </Params>
        <OutputDevice>
          <OutputDeviceVirtual name="VirtualScreen 1" deviceId="VirtualScreen 1" width="2560" height="1440"/>
        </OutputDevice>
        <layers>
          <Slice uniqueId="slice-1">
            <Params name="Common">
              <Param name="Name" value="central"/>
              <Param name="Enabled" value="1"/>
            </Params>
            <Params name="Input">
              <ParamChoice name="Input Source" value="0:1"/>
              <Param name="SoftEdgeEnable" value="0"/>
            </Params>
            <Params name="Output">
              <Param name="Flip" value="0"/>
              <Param name="Is Key" value="0"/>
              <Param name="Black BG" value="0"/>
            </Params>
            <InputRect orientation="0">
              <v x="0" y="0"/><v x="1920" y="0"/><v x="1920" y="1080"/><v x="0" y="1080"/>
            </InputRect>
            <OutputRect orientation="0">
              <v x="100" y="50"/><v x="2020" y="50"/><v x="2020" y="1130"/><v x="100" y="1130"/>
            </OutputRect>
            <Warper>
              <Params name="Warper"><ParamChoice name="Point Mode" value="PM_LINEAR"/></Params>
              <BezierWarper controlWidth="4" controlHeight="4"/>
              <Homography>
                <src><v x="100" y="50"/><v x="2020" y="50"/><v x="2020" y="1130"/><v x="100" y="1130"/></src>
                <dst><v x="100" y="50"/><v x="2020" y="50"/><v x="2020" y="1130"/><v x="100" y="1130"/></dst>
              </Homography>
            </Warper>
          </Slice>
        </layers>
      </Screen>
    </screens>
  </ScreenSetup>
</XmlState>''',
                encoding="utf-8",
            )

            output_map = extract_advanced_output_map(preset)

            self.assertEqual(output_map["composition"], {"width": 1920, "height": 1080})
            self.assertEqual(output_map["statistics"]["slices"], 1)
            self.assertEqual(output_map["statistics"]["virtual_outputs"], 1)
            slice_item = output_map["slices"][0]
            self.assertEqual(slice_item["input_dimensions"]["width"], 1920.0)
            self.assertEqual(slice_item["output_dimensions"]["width"], 1920.0)
            self.assertEqual(slice_item["input"]["bounds"]["x"], 0.0)
            self.assertEqual(slice_item["output"]["bounds"]["x"], 100.0)
            self.assertFalse(slice_item["warper"]["has_active_warp"])

    def test_geometry_profile_detects_non_uniform_scaling(self):
        output_map = {
            "source": {"path": "venue.xml"},
            "composition": {"width": 1920, "height": 1080},
            "validation": {"status": "PASS"},
            "screens": [],
            "slices": [
                {
                    "id": "banner",
                    "screen_name": "Screen 1",
                    "name": "banner",
                    "enabled": True,
                    "input": {"axis_aligned": True, "bounds": {"x": 0, "y": 0, "width": 1000, "height": 100}},
                    "output": {"axis_aligned": True, "bounds": {"x": 0, "y": 0, "width": 1200, "height": 100}},
                    "input_dimensions": {"width": 1000.0, "height": 100.0, "aspect_ratio": 10.0},
                    "output_dimensions": {"width": 1200.0, "height": 100.0, "aspect_ratio": 12.0},
                    "output_controls": {"is_key": False},
                    "warper": {"has_active_warp": False},
                },
            ],
        }

        plan = build_mapping_plan(output_map, [])

        geometry = plan["slices"][0]["geometry"]
        self.assertEqual(geometry["status"], "FAIL")
        self.assertEqual(geometry["circle_output_aspect_ratio"], 1.2)
        self.assertEqual(geometry["deformation_percent"], 20.0)
        self.assertTrue(geometry["requires_geometry_test"])

    def test_testcard_spec_uses_shared_input_group_and_renders_png(self):
        output_map = {
            "source": {"path": "venue.xml"},
            "composition": {"width": 320, "height": 180},
            "slices": [
                {
                    "id": "left",
                    "name": "Left",
                    "screen_name": "Screen 1",
                    "enabled": True,
                    "input_group_id": "group-1",
                    "input": {"bounds": {"x": 0, "y": 0, "width": 160, "height": 180}},
                },
                {
                    "id": "right",
                    "name": "Right",
                    "screen_name": "Screen 1",
                    "enabled": True,
                    "input_group_id": "group-1",
                    "input": {"bounds": {"x": 0, "y": 0, "width": 160, "height": 180}},
                },
            ],
        }

        spec = build_testcard_spec(output_map, duration_seconds=1, fps=10)
        self.assertEqual(spec["input_groups"], 1)
        self.assertEqual(spec["slices"], 2)
        self.assertIn("circle_and_square_geometry", spec["test_modes"])

        with TemporaryDirectory() as directory:
            report = render_testcard(output_map, Path(directory) / "testcard.png", duration_seconds=1, fps=10)
            self.assertTrue(Path(report["render"]["output"]).is_file())
            self.assertEqual(report["render"]["frames_rendered"], 1)


class NayadeSessionTests(unittest.TestCase):
    def test_experiment_matrix_is_grouped_and_includes_surface_operations(self):
        slices = [
            {"slice_id": "banner", "slice_name": "Banner", "input_group_id": "group-horizontal", "orientation": "horizontal", "aspect_ratio": 8.0},
            {"slice_id": "totem", "slice_name": "Totem", "input_group_id": "group-vertical", "orientation": "vertical", "aspect_ratio": 0.2},
        ]

        steps = build_experiment_matrix(slices)

        self.assertEqual(steps[0]["operation"], "baseline")
        self.assertEqual(steps[0]["targets"], ["group-horizontal", "group-vertical"])
        marquee = [step for step in steps if step["operation"] == "marquee"]
        self.assertEqual({step["parameters"]["axis"] for step in marquee}, {"horizontal", "vertical"})
        self.assertTrue(all(step["scope"] == "input_group" for step in steps))

    def test_session_records_soundcheck_event_without_changing_source(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mapping.json"
            source.write_text(
                '{"testcard_type":"InstarResolumeGeometryTestCard",'
                '"composition":{"width":320,"height":180},'
                '"slices_detail":[{"slice_id":"banner","slice_name":"Banner",'
                '"input_group_id":"group-1","bounds":{"x":0,"y":0,"width":320,"height":36}}]}',
                encoding="utf-8",
            )
            session_path = root / "session.json"
            session = create_session(source, session_path, seed=7)
            original = source.read_text(encoding="utf-8")
            event = record_event(
                session_path,
                operation="marquee",
                result="approved",
                targets=["group-1"],
                parameters={"axis": "horizontal", "speed": 0.18},
                notes="La franja se lee limpia y no invade el slice vecino.",
            )
            saved = json.loads(session_path.read_text(encoding="utf-8"))

            self.assertEqual(session["seed"], 7)
            self.assertEqual(event["event_id"], "event-001")
            self.assertEqual(saved["events"][0]["result"], "approved")
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_mapping_plan_ranks_asset_by_input_aspect_and_requires_review_on_ties(self):
        output_map = {
            "source": {"path": "venue.xml"},
            "composition": {"width": 1920, "height": 1080},
            "validation": {"status": "PASS"},
            "screens": [],
            "slices": [
                {
                    "id": "central",
                    "screen_name": "Screen 1",
                    "name": "central",
                    "enabled": True,
                    "hints": ["central", "landscape"],
                    "input_dimensions": {"width": 1920.0, "height": 1080.0, "aspect_ratio": 1.777778},
                    "output_dimensions": {"width": 1920.0, "height": 1080.0, "aspect_ratio": 1.777778},
                    "output_controls": {"is_key": False},
                    "warper": {"has_active_warp": False},
                },
                {
                    "id": "banner",
                    "screen_name": "Screen 1",
                    "name": "banner",
                    "enabled": True,
                    "hints": ["horizontal", "ultrawide"],
                    "input_dimensions": {"width": 1920.0, "height": 180.0, "aspect_ratio": 10.666667},
                    "output_dimensions": {"width": 1920.0, "height": 180.0, "aspect_ratio": 10.666667},
                    "output_controls": {"is_key": False},
                    "warper": {"has_active_warp": False},
                },
            ],
        }
        assets = [
            {
                "asset_id": "landscape-1",
                "path": "landscape.mov",
                "width": 1920,
                "height": 1080,
                "aspect_ratio": 1.777778,
                "orientation": "landscape",
                "alpha": False,
                "tokens": ["landscape"],
            }
        ]

        plan = build_mapping_plan(output_map, assets)

        self.assertEqual(plan["assignments"][0]["slice_id"], "central")
        self.assertFalse(plan["assignments"][0]["requires_review"])
        self.assertEqual(plan["assignments"][0]["scaling"]["mode"], "fill")
        self.assertNotEqual(plan["assignments"][0]["scaling"]["mode"], "stretch")
        self.assertEqual(plan["slice_candidates"][1]["slice_id"], "banner")

        banner_map = dict(output_map)
        banner_map["slices"] = [output_map["slices"][1]]
        banner_plan = build_mapping_plan(banner_map, assets)
        banner_scaling = banner_plan["assignments"][0]["scaling"]
        self.assertEqual(banner_scaling["mode"], "fit")
        self.assertIn("vertical", banner_scaling["fill_crop_axes"])
        self.assertTrue(banner_scaling["requires_review"])
        self.assertEqual(banner_plan["assignments"][0]["match_quality"], "NO_GOOD_MATCH")
        self.assertEqual(banner_plan["slice_candidates"][0]["candidate_status"], "NO_GOOD_MATCH")
        self.assertEqual(len(banner_plan["slice_candidates"][0]["candidates"]), 1)

        distorted_slice = dict(output_map["slices"][0])
        distorted_slice["output_dimensions"] = {
            "width": 2000.0,
            "height": 1080.0,
            "aspect_ratio": 1.851852,
        }
        distorted_map = dict(output_map)
        distorted_map["slices"] = [distorted_slice]
        distorted_plan = build_mapping_plan(distorted_map, assets)
        distorted_scaling = distorted_plan["assignments"][0]["scaling"]
        self.assertTrue(distorted_scaling["mapping_distortion_risk"])
        self.assertTrue(distorted_scaling["requires_review"])

    def test_mapping_plan_uses_behavior_when_surface_needs_adaptation(self):
        output_map = {
            "source": {"path": "venue.xml"},
            "composition": {"width": 1920, "height": 1080},
            "validation": {"status": "PASS"},
            "screens": [],
            "slices": [
                {
                    "id": "banner",
                    "screen_name": "Screen 1",
                    "name": "banner",
                    "enabled": True,
                    "hints": ["horizontal", "ultrawide"],
                    "input_dimensions": {"width": 1920.0, "height": 180.0, "aspect_ratio": 10.666667},
                    "output_dimensions": {"width": 1920.0, "height": 180.0, "aspect_ratio": 10.666667},
                    "output_controls": {"is_key": False},
                    "warper": {"has_active_warp": False},
                },
            ],
        }
        behavior = {
            "pattern": {
                "horizontal": {"score": 0.95, "status": "candidate"},
            },
            "marquee": {"horizontal": {"score": 0.70, "status": "review"}},
        }
        assets = [
            {
                "asset_id": "abstract-16x9",
                "path": "abstract-16x9.mp4",
                "width": 1920,
                "height": 1080,
                "aspect_ratio": 1.777778,
                "orientation": "landscape",
                "alpha": False,
                "tokens": [],
                "behavior": behavior,
            },
            {
                "asset_id": "wide-3x1",
                "path": "wide-3x1.mp4",
                "width": 1920,
                "height": 540,
                "aspect_ratio": 3.555556,
                "orientation": "landscape",
                "alpha": False,
                "tokens": [],
            },
        ]

        plan = build_mapping_plan(output_map, assets)

        assignment = next(item for item in plan["assignments"] if item["asset_id"] == "abstract-16x9")
        self.assertGreater(assignment["match"]["behavior_score"], 0.0)
        self.assertIn("comportamiento pattern horizontal", " ".join(assignment["match"]["reasons"]))
        self.assertEqual(plan["slice_candidates"][0]["candidates"][0]["asset_id"], "abstract-16x9")
        fallbacks = plan["slice_candidates"][0]["fallback_strategies"]
        self.assertEqual({item["operation"] for item in fallbacks}, {"pattern", "marquee"})
        self.assertEqual({item["axis"] for item in fallbacks}, {"horizontal"})
        self.assertEqual(fallbacks[0]["input_group_id"], "input-group-auto-001")
        self.assertTrue(all(item["requires_preview"] for item in fallbacks))

    def test_extracts_cue_points_and_layer_transition(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "loop.mp4"
            media.touch()
            composition = root / "show.avc"
            composition.write_text(
                f'''<?xml version="1.0" encoding="utf-8"?>
<Composition name="Composition" numDecks="1" numLayers="1" numColumns="1">
  <CompositionInfo name="Cue Test" width="1920" height="1080"/>
  <Layer layerIndex="0">
    <ClipTransition name="ClipTransition">
      <Params name="Params">
        <ParamRange name="Duration" T="DOUBLE" default="0" value="1.25"/>
      </Params>
    </ClipTransition>
  </Layer>
  <Deck name="Deck">
    <Clip name="Clip" uniqueId="clip-1" layerIndex="0" columnIndex="0">
      <PreloadData><VideoFile value="{media}"/></PreloadData>
      <Params name="Params">
        <Param name="Name" T="STRING" value="Visual test"/>
        <ParamChoice name="TransportType" value="0"/>
      </Params>
      <Transport name="Transport">
        <Params name="Params">
          <ParamRange name="Position" T="DOUBLE" value="0">
            <PhaseSourceTransportTimeline defaultMillisecondsDuration="10000" defaultBeatsDuration="32">
              <Beats_double detectedTempo="128" manualTempo="120" numDetectedBeats="32" numManualBeats="32"/>
            </PhaseSourceTransportTimeline>
            <ValueRange name="minMax" min="0" max="10000"/>
          </ParamRange>
          <ParamPoints6 name="CuePoints" value="4000">
            <Param name="Position1" value="0"/>
            <Param name="Position2" value="4000"/>
            <Param name="Position3" value="-1"/>
          </ParamPoints6>
        </Params>
      </Transport>
      <VideoTrack><VideoSource><VideoFormatReaderSource fileName="{media}"/></VideoSource></VideoTrack>
    </Clip>
  </Deck>
</Composition>''',
                encoding="utf-8",
            )

            cue_map = extract_cue_map(composition)

            self.assertEqual(cue_map["map_type"], "ResolumeCueMap")
            self.assertEqual(cue_map["statistics"]["clips_with_cues"], 1)
            self.assertEqual(cue_map["statistics"]["cue_points"], 2)
            clip = cue_map["clips"][0]
            self.assertEqual(clip["name"], "Visual test")
            self.assertEqual(clip["transport"]["duration_ms"], 10000.0)
            self.assertEqual(clip["transport"]["detected_tempo"], 128.0)
            self.assertEqual(clip["cues"][1]["position_s"], 4.0)
            self.assertEqual(clip["cues"][1]["normalized"], 0.4)
            self.assertEqual(clip["empty_cue_slots"], [3])
            self.assertEqual(clip["layer_transition_ms"], 1250.0)

    def test_audit_extracts_composition_and_deduplicates_media(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "loop.mp4"
            media.touch()
            composition = root / "show.avc"
            composition.write_text(
                f'''<?xml version="1.0" encoding="utf-8"?>
<Composition name="Composition" numDecks="1" numLayers="2" numColumns="3">
  <versionInfo name="Resolume Arena" majorVersion="7" minorVersion="26" microVersion="0" revision="1"/>
  <CompositionInfo name="Test Show" width="1920" height="1080"/>
  <Deck name="Deck">
    <Clip name="Clip" layerIndex="0" columnIndex="0">
      <VideoTrack><VideoSource width="1920" height="1080" type="VideoFormatReaderSource">
        <VideoFormatReaderSource fileName="{media}"/>
      </VideoSource></VideoTrack>
    </Clip>
    <Clip name="Clip" layerIndex="1" columnIndex="0">
      <VideoTrack><VideoSource width="1920" height="1080" type="VideoFormatReaderSource">
        <VideoFormatReaderSource fileName="{media}"/>
      </VideoSource></VideoTrack>
    </Clip>
  </Deck>
</Composition>''',
                encoding="utf-8",
            )

            report = run_resolume_audit(composition, skip_media=True)

            self.assertEqual(report["overall_status"], "WARN")
            self.assertEqual(report["composition"]["name"], "Test Show")
            self.assertEqual(report["composition"]["width"], 1920)
            self.assertEqual(report["statistics"]["clips"], 2)
            self.assertEqual(report["statistics"]["media_files"], 1)
            self.assertEqual(report["media"][0]["occurrences"], 2)
            self.assertEqual(report["media"][0]["status"], "NOT_ANALYZED")

    def test_audit_creates_safe_plan_for_non_dxv_media(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "loop.mp4"
            media.touch()
            composition = root / "show.avc"
            composition.write_text(
                f'<Composition><CompositionInfo name="Show" width="1920" height="1080"/>'
                f'<Clip layerIndex="0" columnIndex="0"><VideoFile value="{media}"/></Clip></Composition>',
                encoding="utf-8",
            )

            with patch("tools.resolume_adapter.resolume.diagnose_file", return_value={
                "overall_status": "WARN",
                "video": {"codec": "h264", "width": 1920, "height": 1080},
            }):
                report = run_resolume_audit(composition)

            risks = [action["risk"] for action in report["action_plan"]]
            operations = [action["operation"] for action in report["action_plan"]]
            self.assertEqual(report["overall_status"], "WARN")
            self.assertIn("SAFE", risks)
            self.assertIn("create_derived_media", operations)


class ProcessorTests(unittest.TestCase):
    def test_match_processor_profile_uses_descriptor_without_opening_port(self):
        device = {
            "device": "COM7",
            "description": "NovaStar VX600 USB Control",
            "manufacturer": "NovaStar",
            "product": "VX600",
            "vid_pid": "1234:5678",
        }

        matches = match_processor_profiles(device)

        self.assertEqual(matches[0]["profile_id"], "novastar-vx600")
        self.assertIn("keyword:novastar", matches[0]["reasons"])

    def test_unknown_snapshot_is_read_only_and_requires_module_profile(self):
        snapshot = build_processor_snapshot({"transport": "usb_serial", "device": "COM99"})

        self.assertTrue(snapshot["read_only"])
        self.assertEqual(snapshot["identification"]["model"]["value"], "unknown-led-processor")
        self.assertIsNone(snapshot["module_profile_id"])
        self.assertTrue(snapshot["safety"]["unknown_device_write_blocked"])
        self.assertFalse(snapshot["safety"]["commands_sent"])
        self.assertFalse(snapshot["safety"]["writes_attempted"])

    def test_discovery_never_opens_ports(self):
        fake_port = type(
            "FakePort",
            (),
            {
                "device": "COM7",
                "description": "NovaStar VX600 USB Control",
                "manufacturer": "NovaStar",
                "product": "VX600",
                "serial_number": "SN-1",
                "interface": "USB",
                "location": "1-2",
                "hwid": "USB VID:PID=1234:5678",
                "vid": 0x1234,
                "pid": 0x5678,
            },
        )()
        with patch("serial.tools.list_ports.comports", return_value=[fake_port]) as comports:
            report = discover_serial_devices()

        comports.assert_called_once_with()
        self.assertTrue(report["read_only"])
        self.assertFalse(report["safety"]["ports_opened"])
        self.assertFalse(report["safety"]["commands_sent"])
        self.assertEqual(report["devices"][0]["best_match"]["profile_id"], "novastar-vx600")

    def test_saturday_case_keeps_before_black_and_marks_unknown_range_state(self):
        report = diagnose_case(Path("data/cases/soundcheck-2026-08-29-vc2.json"))
        finding_ids = {finding["id"] for finding in report["findings"]}

        self.assertIn("raised_black_level", finding_ids)
        self.assertIn("extreme_gamma_low_brightness", finding_ids)
        self.assertIn("multi_stage_level_compensation", finding_ids)
        self.assertNotIn("possible_double_range_conversion", finding_ids)
        self.assertIn("processor_range_state_not_recorded", finding_ids)

    def test_case_validation_returns_a_shareable_summary_without_source_path(self):
        path = Path("data/cases/soundcheck-2026-08-29-vc2.json")

        report = validate_processor_case(path)

        self.assertTrue(report["valid"])
        self.assertEqual(report["report_type"], "NayadeProcessorCaseValidation")
        self.assertFalse(report["safety"]["source_path_exposed"])
        self.assertNotIn(str(path.resolve()), json.dumps(report))

        diagnosis = diagnose_case(path)
        self.assertEqual(diagnosis["source_case"], "soundcheck-2026-08-29-vc2")
        self.assertFalse(diagnosis["safety"]["source_path_exposed"])
        self.assertNotIn(str(path.resolve()), json.dumps(diagnosis))

    def test_case_validation_rejects_incomplete_records_before_diagnosis(self):
        case = json.loads(Path("data/cases/soundcheck-2026-08-29-vc2.json").read_text(encoding="utf-8"))
        case.pop("event_sequence")

        with self.assertRaises(ResolumeAdapterError):
            validate_processor_case_document(case)


if __name__ == "__main__":
    unittest.main()
