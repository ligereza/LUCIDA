"""Punto de entrada inicial para el núcleo de RESOLUME_ADAPTER."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from adapters.vj import VJProjectError, build_stage_event, load_project_document, project_stage_document
from adapters.vj.replay import (
    ReplayError,
    load_fixture,
    replay_plugin_bridge_path,
    replay_project_manifest_path,
    replay_semantic_light_field_path,
)
from resolume_adapter.adapt import run_adaptation, text_report as adapt_text_report, write_adaptation_plan
from resolume_adapter.diagnose import diagnose_file, text_report
from resolume_adapter.doctor import doctor_text_report, run_doctor, write_doctor_report
from resolume_adapter.dxv import convert_to_dxv
from resolume_adapter.imago import (
    build_show_session,
    load_session as load_imago_session,
    next_proposal,
    record_event as record_imago_event,
    record_result as record_imago_result,
    write_session as write_imago_session,
)
from resolume_adapter.html_report import write_html_report
from resolume_adapter.incidents import INCIDENT_CATEGORIES, build_incident_plan, incident_text_report, write_incident_plan
from resolume_adapter.instar import run_instar, text_report as instar_text_report, write_report
from resolume_adapter.instar_image import build_raster_mapping, raster_mapping_text_report, write_raster_mapping_report
from resolume_adapter.instar_svg import build_svg_mapping, svg_mapping_text_report, write_svg_mapping_report
from resolume_adapter.manifest import write_manifest
from resolume_adapter.media import ResolumeAdapterError
from resolume_adapter.nayade import (
    build_session_report,
    create_session,
    get_next_step,
    record_event,
    session_report_text,
    text_report as nayade_text_report,
)
from resolume_adapter.output_probe import output_probe_text_report, probe_windows_output
from resolume_adapter.processors import (
    case_text_report,
    catalog_text_report,
    diagnose_case,
    discover_serial_devices,
    discovery_text_report,
    load_processor_catalog,
    snapshot_from_serial_device,
    snapshot_text_report,
    validate_processor_case,
    write_json as write_processor_json,
)
from resolume_adapter.reconcile import (
    load_reconciliation_document,
    reconcile_signal_chain,
    reconciliation_text_report,
)
from resolume_adapter.protocol import build_soundcheck_protocol, protocol_text_report
from resolume_adapter.cue_plan import build_cue_plan, cue_plan_text_report, write_cue_plan
from resolume_adapter.resolume import (
    advanced_output_text_report,
    build_mapping_plan,
    cue_text_report,
    extract_advanced_output_map,
    extract_cue_map,
    load_catalog_assets,
    run_resolume_audit,
    text_report as resolume_text_report,
    write_advanced_output_report,
    write_cue_map,
    write_report as write_resolume_report,
)
from resolume_adapter.show_profile import load_show_profile, target_values
from resolume_adapter.testcard import render_testcard, text_report as testcard_text_report, write_testcard_report


def _resolution(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("La resolución debe tener el formato ANCHOxALTO.") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("La resolución debe ser positiva.")
    return width, height


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="resolume_adapter", description="Herramientas RESOLUME_ADAPTER para flujo VJ.")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser(
        "doctor",
        help="Comprueba el entorno portable sin controlar Resolume ni hardware.",
    )
    doctor.add_argument("--report", help="Ruta opcional para guardar el diagnóstico JSON.")

    incident = commands.add_parser(
        "incident-plan",
        help="Genera un plan de evidencia y recuperación reversible para un incidente VJ.",
    )
    incident.add_argument("category", choices=INCIDENT_CATEGORIES)
    incident.add_argument("--stage", choices=("preflight", "soundcheck", "show"), default="soundcheck")
    incident.add_argument("--report", help="Ruta opcional para guardar el plan JSON.")

    instar = commands.add_parser("instar", help="Ejecuta el preflight de media de una carpeta.")
    instar.add_argument("media_root", help="Carpeta raíz con los videos del show.")
    instar.add_argument("--report", help="Ruta opcional para guardar el informe JSON.")
    instar.add_argument("--target-fps", type=float, help="FPS de la composición o salida objetivo.")
    instar.add_argument("--target-resolution", type=_resolution, help="Resolución objetivo, por ejemplo 1920x1080.")
    instar.add_argument("--target-codec", help="Codec objetivo opcional, por ejemplo dxv.")
    instar.add_argument("--deep", action="store_true", help="Además del preflight, ejecuta el diagnóstico visual/luminancia.")
    instar.add_argument("--gpu", action="store_true", help="Analiza frames con NVDEC/CUDA; no hace fallback silencioso a CPU.")
    instar.add_argument("--gpu-max-frames", type=int, default=900, help="Máximo de frames para el análisis GPU por archivo.")
    instar.add_argument("--gpu-batch-size", type=int, default=16, help="Cantidad de frames por lote en el decoder GPU.")
    instar.add_argument("--max-samples", type=int, default=300, help="Máximo de muestras de luminancia en modo --deep.")
    instar.add_argument("--sidecars-dir", help="Carpeta opcional para escribir un .resolume_adapter.json por visual.")
    instar.add_argument("--show-profile", help="Perfil JSON de destino para comparar compatibilidad.")
    instar.add_argument("--cache-db", help="Base SQLite local para reutilizar análisis sin repetirlos.")
    instar.add_argument("--html-report", help="Ruta opcional para generar un reporte HTML navegable.")
    instar.add_argument("--manifest", help="Ruta opcional para generar un manifiesto portable de assets.")
    instar.add_argument("--ffmpeg", default="ffmpeg", help="Ruta o nombre de FFmpeg.")
    instar.add_argument("--ffprobe", default="ffprobe", help="Ruta o nombre de FFprobe.")

    diagnose = commands.add_parser("diagnose", help="Analiza un archivo de video y genera recomendaciones.")
    diagnose.add_argument("input", help="Archivo de video a analizar.")
    diagnose.add_argument("--report", help="Ruta opcional para guardar el informe JSON.")
    diagnose.add_argument("--target-fps", type=float, help="FPS de la composición o salida objetivo.")
    diagnose.add_argument("--target-resolution", type=_resolution, help="Resolución objetivo, por ejemplo 1920x1080.")
    diagnose.add_argument("--max-samples", type=int, default=300, help="Máximo de muestras de luminancia (default: 300).")
    diagnose.add_argument("--ffmpeg", default="ffmpeg", help="Ruta o nombre de FFmpeg.")
    diagnose.add_argument("--ffprobe", default="ffprobe", help="Ruta o nombre de FFprobe.")

    dxv = commands.add_parser("dxv", help="Convierte y valida un archivo usando el encoder DXV disponible.")
    dxv.add_argument("input", help="Archivo de video de entrada.")
    dxv.add_argument("-o", "--output", help="Archivo .mov de salida.")
    dxv.add_argument("--fps", type=float, help="FPS constante de salida; omitir conserva el timeline de entrada.")
    dxv.add_argument("--resolution", type=_resolution, help="Resolución de salida, por ejemplo 1920x1080.")
    dxv.add_argument("--alpha", action="store_true", help="Solicita formato DXV con alpha si el encoder lo soporta.")
    dxv.add_argument("--overwrite", action="store_true", help="Permite reemplazar la salida existente.")
    dxv.add_argument("--dry-run", action="store_true", help="Muestra la operación sin convertir.")
    dxv.add_argument("--ffmpeg", default="ffmpeg", help="Ruta o nombre de FFmpeg.")
    dxv.add_argument("--ffprobe", default="ffprobe", help="Ruta o nombre de FFprobe.")

    vj_replay = commands.add_parser(
        "vj-replay",
        help="Reproduce el flujo INSTAR, NAYADE e IMAGO desde un fixture sintetico.",
    )
    vj_replay.add_argument("fixture", help="Fixture JSON de replay de puentes VJ.")
    vj_replay.add_argument("--report", help="Ruta opcional para guardar el reporte JSON.")

    vj_project_replay = commands.add_parser(
        "vj-project-replay",
        help="Reproduce un manifest JSON con reportes de INSTAR, NAYADE e IMAGO.",
    )
    vj_project_replay.add_argument("manifest", help="Manifest JSON de la sesion VJ.")
    vj_project_replay.add_argument("--report", help="Ruta opcional para guardar el reporte JSON.")

    vj_project = commands.add_parser(
        "vj-project",
        help="Convierte un reporte de etapa en un evento o proyeccion VJ segura.",
    )
    vj_project.add_argument("stage", choices=("instar", "nayade", "imago"))
    vj_project.add_argument("input", help="Reporte JSON de la etapa.")
    vj_project.add_argument("--event-id", required=True, help="Identificador estable del evento.")
    vj_project.add_argument("--sequence", required=True, type=int, help="Secuencia explicita del productor.")
    vj_project.add_argument("--mode", choices=("event", "projection"), default="event")
    vj_project.add_argument("--previous", help="Proyeccion VJ anterior para validar el orden de fases.")
    vj_project.add_argument("--processor-observation", help="Observacion JSON solo para la etapa nayade.")
    vj_project.add_argument("--output", help="Ruta opcional para guardar el resultado JSON.")

    imago = commands.add_parser("imago-session", help="Registra observaciones proposal-only del show.")
    imago_commands = imago.add_subparsers(dest="imago_command", required=True)
    imago_init = imago_commands.add_parser("init", help="Crea una sesion de show.")
    imago_init.add_argument("-o", "--output", required=True)
    imago_init.add_argument("--session-id", default="imago-session")
    imago_init.add_argument("--name", default="IMAGO Show")
    imago_init.add_argument("--created-at")
    imago_event = imago_commands.add_parser("event", help="Registra un evento observado.")
    imago_event.add_argument("session")
    imago_event.add_argument("--event-type", required=True, choices=("show_started", "cue_fired", "guard_window_requested", "incident_detected", "recovery_started", "recovery_verified", "show_closed"))
    imago_event.add_argument("--payload", default="{}")
    imago_event.add_argument("--recorded-at")
    imago_result = imago_commands.add_parser("result", help="Registra un resultado de propuesta.")
    imago_result.add_argument("session")
    imago_result.add_argument("--proposal-id", required=True)
    imago_result.add_argument("--result", required=True, choices=("accepted", "rejected", "review"))
    imago_result.add_argument("--notes", default="")
    imago_result.add_argument("--recorded-at")

    resolume = commands.add_parser(
        "resolume-audit",
        help="Audita una composición .avc en modo lectura y genera un plan de optimización.",
    )
    resolume.add_argument("composition", help="Archivo .avc de Resolume.")
    resolume.add_argument("--report", help="Ruta opcional para guardar el informe JSON.")
    resolume.add_argument("--target-fps", type=float, help="FPS de la composición o salida objetivo.")
    resolume.add_argument("--target-resolution", type=_resolution, help="Resolución objetivo, por ejemplo 1920x1080.")
    resolume.add_argument("--max-samples", type=int, default=300, help="Máximo de muestras de luminancia por archivo.")
    resolume.add_argument("--skip-media", action="store_true", help="Lee la composición sin ejecutar FFprobe sobre los medios.")
    resolume.add_argument("--ffmpeg", default="ffmpeg", help="Ruta o nombre de FFmpeg.")
    resolume.add_argument("--ffprobe", default="ffprobe", help="Ruta o nombre de FFprobe.")

    cues = commands.add_parser(
        "resolume-cues",
        help="Extrae los CUES y el transporte de una composición .avc en modo lectura.",
    )
    cues.add_argument("composition", help="Archivo .avc de Resolume.")
    cues.add_argument("--report", help="Ruta opcional para guardar el mapa JSON de cues.")

    cue_plan = commands.add_parser(
        "instar-cue-plan",
        help="Organiza candidatos CUE de uno o más perfiles INSTAR en seis slots revisables.",
    )
    cue_plan.add_argument("profiles", nargs="+", help="Perfiles ClipProfile JSON generados por INSTAR.")
    cue_plan.add_argument("--report", help="Ruta opcional para guardar el plan JSON.")

    mapping = commands.add_parser(
        "instar-map",
        aliases=["resolume-output"],
        help="Lee Advanced Output y cruza sus slices con un catálogo INSTAR, sin modificar Resolume.",
    )
    mapping.add_argument("advanced_output", help="Preset .xml de Resolume Advanced Output.")
    mapping.add_argument("--catalog", help="Informe INSTAR o AssetManifest JSON con los perfiles de visuales.")
    mapping.add_argument("--report", help="Ruta opcional para guardar el mapa o plan JSON.")
    mapping.add_argument("--max-candidates", type=int, default=6, help="Máximo de candidatos por visual y slice.")

    svg_mapping = commands.add_parser(
        "instar-map-svg",
        help="Convierte un SVG vectorial en un candidato XML de Advanced Output para Resolume Arena.",
    )
    svg_mapping.add_argument("input_svg", help="SVG con las superficies del canvas de composición.")
    svg_mapping.add_argument("--output-svg", help="SVG opcional con la geometría física de salida, en el mismo orden.")
    svg_mapping.add_argument("--composition-size", type=_resolution, help="Resolución de composición si el SVG no declara viewBox.")
    svg_mapping.add_argument("--output-size", type=_resolution, help="Resolución del output; por defecto usa la composición o el Output SVG.")
    svg_mapping.add_argument("--xml", required=True, help="Ruta de salida para el XML de Advanced Output.")
    svg_mapping.add_argument("--screen-name", default="INSTAR SVG Map", help="Nombre de la pantalla virtual generada.")
    svg_mapping.add_argument("--resolume-minor", type=int, default=27, help="Minor de Arena declarado en el XML (default: 27).")
    svg_mapping.add_argument("--report", help="Ruta opcional para guardar el candidato JSON.")

    image_mapping = commands.add_parser(
        "instar-map-image",
        help="Detecta superficies grandes en una imagen de mapping y genera un XML candidato para Resolume Arena.",
    )
    image_mapping.add_argument("image", help="PNG/JPG/PDF rasterizado con el plano de mapping.")
    image_mapping.add_argument("--canvas-size", type=_resolution, required=True, help="Resolución del canvas descrita por el plano.")
    image_mapping.add_argument("--output-size", type=_resolution, help="Resolución del output; por defecto usa el canvas.")
    image_mapping.add_argument("--xml", required=True, help="Ruta de salida para el XML candidato.")
    image_mapping.add_argument("--svg", help="Guarda también el SVG geométrico intermedio.")
    image_mapping.add_argument("--screen-name", default="INSTAR Raster Map", help="Nombre de la pantalla virtual generada.")
    image_mapping.add_argument("--min-area-ratio", type=float, default=0.005, help="Área mínima de una región respecto de la imagen.")
    image_mapping.add_argument("--ocr-exe", help="Ejecutable OCR opcional que emita el protocolo OCR_LINE de INSTAR.")
    image_mapping.add_argument("--report", help="Ruta opcional para guardar el candidato JSON.")

    adapt = commands.add_parser(
        "instar-adapt",
        help="Genera previews target-specific desde un plan INSTAR sin modificar las fuentes.",
    )
    adapt.add_argument("mapping_plan", help="Plan JSON generado por instar-map.")
    adapt.add_argument("-o", "--output-dir", required=True, help="Carpeta donde guardar los previews.")
    adapt.add_argument(
        "--strategy",
        choices=["auto", "crop", "fit_background", "pattern", "marquee"],
        default="auto",
        help="Estrategia a renderizar (default: auto).",
    )
    adapt.add_argument("--max-variants", type=int, default=1, help="Candidatos por estrategia y grupo.")
    adapt.add_argument("--duration", type=float, default=6.0, help="Duración de cada preview en segundos.")
    adapt.add_argument("--speed-pixels", type=float, default=120.0, help="Velocidad marquee en píxeles/segundo.")
    adapt.add_argument("--encoder", choices=["auto", "h264_nvenc", "libx264"], default="auto")
    adapt.add_argument(
        "--dxv-output-dir",
        help="Exporta cada preview a un DXV candidato en esta carpeta, sin sobrescribir archivos existentes.",
    )
    adapt.add_argument("--no-mirror-alternate", action="store_true", help="No espejar copias alternas en pattern/marquee.")
    adapt.add_argument("--report", help="Ruta opcional para guardar el plan de adaptación JSON.")
    adapt.add_argument("--ffmpeg", default="ffmpeg", help="Ruta o nombre de FFmpeg.")
    adapt.add_argument("--ffprobe", default="ffprobe", help="Ruta o nombre de FFprobe.")

    testcard = commands.add_parser(
        "instar-testcard",
        aliases=["nayade-testcard"],
        help="Genera una tarjeta de prueba geométrica desde Advanced Output, sin modificar Resolume.",
    )
    testcard.add_argument("advanced_output", help="Preset .xml de Resolume Advanced Output.")
    testcard.add_argument("-o", "--output", required=True, help="Salida .png, .mp4, .mov o .mkv.")
    testcard.add_argument("--duration", type=float, default=12.0, help="Duración del video en segundos (default: 12).")
    testcard.add_argument("--fps", type=float, default=30.0, help="FPS del video (default: 30).")
    testcard.add_argument("--report", help="Ruta opcional para guardar la especificación JSON.")
    testcard.add_argument("--ffmpeg", default="ffmpeg", help="Ruta o nombre de FFmpeg para salidas de video.")

    session = commands.add_parser(
        "nayade-session",
        help="Crea y registra una sesión reproducible de pruebas de soundcheck.",
    )
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_init = session_commands.add_parser("init", help="Inicia la matriz de experimentación desde un informe INSTAR/NAYADE.")
    session_init.add_argument("source", help="Informe JSON de mapping o tarjeta de prueba.")
    session_init.add_argument("-o", "--output", required=True, help="Archivo JSON de sesión a crear.")
    session_init.add_argument("--name", help="Nombre legible de la sesión.")
    session_init.add_argument("--seed", type=int, help="Semilla reproducible para variaciones futuras.")
    session_init.add_argument("--catalog", help="Informe INSTAR o AssetManifest para ordenar candidatos de pattern/marquee.")
    session_init.add_argument(
        "--adaptation-plan",
        help="Plan INSTAR de previews/DXV target-specific que se incorporará a la matriz de soundcheck.",
    )
    session_init.add_argument(
        "--protocol",
        help="Protocolo NAYADE de procesador que se incorporará como checks planificados antes de la matriz visual.",
    )

    session_record = session_commands.add_parser("record", help="Registra el resultado de una prueba del soundcheck.")
    session_record.add_argument("session", help="Archivo JSON de sesión NAYADE.")
    session_record.add_argument("--operation", required=True, help="Operación probada, por ejemplo flip_horizontal o marquee.")
    session_record.add_argument("--result", required=True, choices=["planned", "running", "approved", "rejected", "review"])
    session_record.add_argument("--scope", default="input_group", help="Alcance: global, composition, input_group, slice o clip.")
    session_record.add_argument("--target", action="append", default=[], help="Objetivo; repetir la opción para varios input groups.")
    session_record.add_argument("--parameters", help="Objeto JSON con parámetros de la variación.")
    session_record.add_argument("--notes", default="", help="Observación del VJ o del operador.")
    session_record.add_argument("--step-id", help="Paso planificado exacto que se está registrando.")
    session_record.add_argument("--output", help="Archivo nuevo para registrar sin modificar la sesión de origen.")
    session_next = session_commands.add_parser("next", help="Muestra la próxima prueba pendiente de la sesión.")
    session_next.add_argument("session", help="Archivo JSON de sesión NAYADE.")
    session_report = session_commands.add_parser("report", help="Resume el estado de una sesión sin exponer notas privadas.")
    session_report.add_argument("session", help="Archivo JSON de sesión NAYADE.")
    session_report.add_argument("--report", help="Ruta opcional para guardar el resumen JSON.")

    processor = commands.add_parser(
        "nayade-processor",
        aliases=["processor"],
        help="Inspecciona procesadores LED y diagnostica casos NAYADE sin escribir en hardware.",
    )
    processor_commands = processor.add_subparsers(dest="processor_command", required=True)
    processor_catalog = processor_commands.add_parser("catalog", help="Muestra los perfiles locales de procesadores.")
    processor_catalog.add_argument("--catalog", help="Ruta alternativa al catálogo JSON.")
    processor_discover = processor_commands.add_parser("discover", help="Enumera puertos USB/COM sin abrirlos.")
    processor_discover.add_argument("--catalog", help="Ruta alternativa al catálogo JSON.")
    processor_discover.add_argument("--report", help="Ruta opcional para guardar el descubrimiento JSON.")
    processor_snapshot = processor_commands.add_parser("snapshot", help="Crea un snapshot de un puerto en modo lectura.")
    processor_snapshot.add_argument("--device", required=True, help="Puerto, por ejemplo COM3.")
    processor_snapshot.add_argument("--model", help="Perfil exacto confirmado por el operador; evita inferencias.")
    processor_snapshot.add_argument("--catalog", help="Ruta alternativa al catálogo JSON.")
    processor_snapshot.add_argument("-o", "--output", required=True, help="Archivo JSON del snapshot.")
    processor_case = processor_commands.add_parser("diagnose-case", help="Diagnostica un caso de soundcheck ya registrado.")
    processor_case.add_argument("case", help="Caso JSON de NAYADE.")
    processor_case.add_argument("--report", help="Ruta opcional para guardar el diagnóstico JSON.")
    processor_validate_case = processor_commands.add_parser("validate-case", help="Valida el contrato de un caso NAYADE.")
    processor_validate_case.add_argument("case", help="Caso JSON de NAYADE.")
    processor_validate_case.add_argument("--report", help="Ruta opcional para guardar la validación JSON.")
    processor_reconcile = processor_commands.add_parser("reconcile", help="Reconcilia evidencia de señal, procesador, módulo y mapping.")
    processor_reconcile.add_argument("--signal-profile", help="Perfil JSON de señal.")
    processor_reconcile.add_argument("--processor-observation", help="Observación JSON del procesador.")
    processor_reconcile.add_argument("--processor-snapshot", help="Snapshot JSON de descubrimiento.")
    processor_reconcile.add_argument("--module-profile", help="Perfil JSON del módulo LED.")
    processor_reconcile.add_argument("--mapping", help="Mapa o plan JSON de Advanced Output.")
    processor_reconcile.add_argument("--output-probe", help="Sonda JSON de salida Windows/GPU.")
    processor_reconcile.add_argument("--report", help="Ruta opcional para guardar la reconciliación JSON.")
    processor_protocol = processor_commands.add_parser("protocol", help="Genera un protocolo de soundcheck basado en evidencia, sin tocar hardware.")
    processor_protocol.add_argument("--case", help="Caso JSON de NAYADE; se diagnostica antes de generar el protocolo.")
    processor_protocol.add_argument("--reconciliation", help="Reconciliación JSON de cadena.")
    processor_protocol.add_argument("--mapping", help="Mapa o plan JSON de Advanced Output.")
    processor_protocol.add_argument("--report", help="Ruta opcional para guardar el protocolo JSON.")
    processor_probe = processor_commands.add_parser("probe-output", help="Captura salida Windows/GPU y EDID en solo lectura.")
    processor_probe.add_argument("--timeout", type=float, default=10.0, help="Tiempo máximo de consulta WMI en segundos.")
    processor_probe.add_argument("--report", required=True, help="Archivo JSON de la sonda.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            report = run_doctor()
            print(doctor_text_report(report))
            if args.report:
                report_path = write_doctor_report(report, args.report)
                print(f"\nDiagnóstico JSON: {report_path}")
            return 1 if report["overall_status"] == "FAIL" else 0

        if args.command == "incident-plan":
            plan = build_incident_plan(args.category, stage=args.stage)
            print(incident_text_report(plan))
            if args.report:
                report_path = write_incident_plan(plan, args.report)
                print(f"\nPlan JSON: {report_path}")
            return 0

        if args.command == "instar":
            show_profile = load_show_profile(args.show_profile) if args.show_profile else None
            profile_target = target_values(show_profile) if show_profile else {}
            width = height = None
            if args.target_resolution:
                width, height = args.target_resolution
            else:
                width = profile_target.get("width")
                height = profile_target.get("height")
            target_fps = args.target_fps if args.target_fps is not None else profile_target.get("fps")
            target_codec = args.target_codec if args.target_codec is not None else profile_target.get("codec")
            report = run_instar(
                args.media_root,
                ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe,
                target_fps=target_fps,
                target_width=width,
                target_height=height,
                max_samples=args.max_samples,
                target_codec=target_codec,
                deep=args.deep,
                sidecars_dir=args.sidecars_dir,
                gpu=args.gpu,
                gpu_max_frames=args.gpu_max_frames,
                gpu_batch_size=args.gpu_batch_size,
                show_profile=show_profile,
                cache_db=args.cache_db,
            )
            if show_profile:
                report["show_profile"] = {
                    "profile_id": show_profile.get("profile_id"),
                    "name": show_profile.get("name"),
                    "path": show_profile.get("path"),
                    "target": show_profile.get("target") or show_profile.get("output") or show_profile,
                }
            print(instar_text_report(report))
            if args.report:
                report_path = write_report(report, args.report)
                print(f"\nInforme JSON: {report_path}")
            if args.html_report:
                html_path = write_html_report(report, args.html_report)
                print(f"Reporte HTML: {html_path}")
            if args.manifest:
                manifest_path = write_manifest(report, args.manifest)
                print(f"Manifiesto: {manifest_path}")
            return 1 if report["overall_status"] == "FAIL" else 0

        if args.command == "diagnose":
            width = height = None
            if args.target_resolution:
                width, height = args.target_resolution
            report = diagnose_file(
                args.input,
                ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe,
                target_fps=args.target_fps,
                target_width=width,
                target_height=height,
                max_samples=args.max_samples,
            )
            print(text_report(report))
            if args.report:
                report_path = Path(args.report).expanduser().resolve()
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"\nInforme JSON: {report_path}")
            return 0

        if args.command == "dxv":
            width = height = None
            if args.resolution:
                width, height = args.resolution
            result = convert_to_dxv(
                args.input,
                args.output,
                ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe,
                fps=args.fps,
                width=width,
                height=height,
                alpha=args.alpha,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
            )
            if result.get("dry_run"):
                print("RESOLUME_ADAPTER DXV ASSISTANT — dry run")
                print(shlex.join(result["command"]))
            else:
                print("RESOLUME_ADAPTER DXV ASSISTANT")
                print(f"Estado: {result['status']}")
                print(f"Entrada: {result['input']}")
                print(f"Salida: {result['output']}")
                print(f"Codec: {result['video'].get('codec')}")
                print(f"Resolución: {result['video'].get('width')} × {result['video'].get('height')}")
                print(f"FPS: {result['video'].get('average_fps')}")
            return 0

        if args.command == "vj-replay":
            replay_input = Path(args.fixture).expanduser().resolve()
            replay_document = load_fixture(replay_input)
            if isinstance(replay_document, dict) and replay_document.get("replay_type") == "ResolumeAdapterSemanticLightFieldReplay":
                report = replay_semantic_light_field_path(replay_input)
            else:
                report = replay_plugin_bridge_path(replay_input)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if args.report:
                report_path = Path(args.report).expanduser().resolve()
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"\nReporte VJ replay: {report_path}")
            return 0 if report["status"] == "PASS" else 1

        if args.command == "vj-project-replay":
            report = replay_project_manifest_path(args.manifest)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if args.report:
                report_path = Path(args.report).expanduser().resolve()
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"\nReporte VJ project replay: {report_path}")
            return 0 if report["status"] == "PASS" else 1

        if args.command == "vj-project":
            document = load_project_document(args.input)
            previous = load_project_document(args.previous) if args.previous else None
            processor_observation = (
                load_project_document(args.processor_observation)
                if args.processor_observation
                else None
            )
            if args.mode == "projection":
                result = project_stage_document(
                    args.stage,
                    document,
                    event_id=args.event_id,
                    sequence=args.sequence,
                    previous=previous,
                    processor_observation=processor_observation,
                )
            else:
                if previous is not None:
                    raise VJProjectError("--previous requires --mode projection.")
                result = build_stage_event(
                    args.stage,
                    document,
                    event_id=args.event_id,
                    sequence=args.sequence,
                    processor_observation=processor_observation,
                )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if args.output:
                output_path = Path(args.output).expanduser().resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"\nResultado VJ project: {output_path}")
            return 0

        if args.command == "imago-session":
            if args.imago_command == "init":
                session = build_show_session(
                    session_id=args.session_id,
                    name=args.name,
                    created_at=args.created_at,
                )
                output = write_imago_session(session, args.output)
                print(json.dumps({"status": "created", "output": str(output), "next": next_proposal(session)}, ensure_ascii=False, indent=2))
                return 0
            if args.imago_command == "event":
                session = load_imago_session(args.session)
                try:
                    payload = json.loads(args.payload)
                except json.JSONDecodeError as exc:
                    raise ResolumeAdapterError("--payload must be valid JSON.") from exc
                if not isinstance(payload, dict):
                    raise ResolumeAdapterError("--payload must contain an object.")
                updated = record_imago_event(
                    session,
                    event_type=args.event_type,
                    payload=payload,
                    recorded_at=args.recorded_at,
                )
                output = write_imago_session(updated, args.session)
                print(json.dumps({"status": "recorded", "output": str(output), "next": next_proposal(updated)}, ensure_ascii=False, indent=2))
                return 0
            if args.imago_command == "result":
                session = load_imago_session(args.session)
                updated = record_imago_result(
                    session,
                    proposal_id=args.proposal_id,
                    result=args.result,
                    notes=args.notes,
                    recorded_at=args.recorded_at,
                )
                output = write_imago_session(updated, args.session)
                print(json.dumps({"status": "recorded", "output": str(output), "next": next_proposal(updated)}, ensure_ascii=False, indent=2))
                return 0

        if args.command == "resolume-audit":
            width = height = None
            if args.target_resolution:
                width, height = args.target_resolution
            report = run_resolume_audit(
                args.composition,
                ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe,
                target_fps=args.target_fps,
                target_width=width,
                target_height=height,
                max_samples=args.max_samples,
                skip_media=args.skip_media,
            )
            print(resolume_text_report(report))
            if args.report:
                report_path = write_resolume_report(report, args.report)
                print(f"\nInforme JSON: {report_path}")
            return 1 if report["overall_status"] == "FAIL" else 0

        if args.command == "resolume-cues":
            cue_map = extract_cue_map(args.composition)
            print(cue_text_report(cue_map))
            if args.report:
                report_path = write_cue_map(cue_map, args.report)
                print(f"\nMapa JSON: {report_path}")
            return 0

        if args.command == "instar-cue-plan":
            profiles = [load_project_document(path) for path in args.profiles]
            plan = build_cue_plan(profiles)
            print(cue_plan_text_report(plan))
            if args.report:
                report_path = write_cue_plan(plan, args.report)
                print(f"\nPlan JSON: {report_path}")
            return 0

        if args.command in {"instar-map", "resolume-output"}:
            output_map = extract_advanced_output_map(args.advanced_output)
            report = output_map
            if args.catalog:
                assets = load_catalog_assets(args.catalog)
                report = build_mapping_plan(
                    output_map,
                    assets,
                    max_candidates=max(1, args.max_candidates),
                )
            print(advanced_output_text_report(report))
            if args.report:
                report_path = write_advanced_output_report(report, args.report)
                print(f"\nInforme JSON: {report_path}")
            status = report.get("status") or (report.get("validation") or {}).get("status")
            return 1 if status == "FAIL" else 0

        if args.command == "instar-map-svg":
            report = build_svg_mapping(
                args.input_svg,
                args.xml,
                composition_size=args.composition_size,
                output_svg=args.output_svg,
                output_size=args.output_size,
                screen_name=args.screen_name,
                resolume_minor=args.resolume_minor,
            )
            print(svg_mapping_text_report(report))
            if args.report:
                report_path = write_svg_mapping_report(report, args.report)
                print(f"\nCandidato JSON: {report_path}")
            return 0 if (report.get("validation") or {}).get("status") != "FAIL" else 1

        if args.command == "instar-map-image":
            report = build_raster_mapping(
                args.image,
                args.xml,
                canvas_size=args.canvas_size,
                output_size=args.output_size,
                svg_output=args.svg,
                screen_name=args.screen_name,
                min_area_ratio=args.min_area_ratio,
                ocr_executable=args.ocr_exe,
            )
            print(raster_mapping_text_report(report))
            if args.report:
                report_path = write_raster_mapping_report(report, args.report)
                print(f"\nCandidato JSON: {report_path}")
            return 0

        if args.command == "instar-adapt":
            plan = run_adaptation(
                args.mapping_plan,
                args.output_dir,
                strategy=args.strategy,
                max_variants=args.max_variants,
                duration_seconds=args.duration,
                speed_pixels=args.speed_pixels,
                ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe,
                encoder=args.encoder,
                mirror_alternate=not args.no_mirror_alternate,
                dxv_output_dir=args.dxv_output_dir,
            )
            print(adapt_text_report(plan))
            report_path = args.report or str(Path(args.output_dir).expanduser().resolve() / "instar-adaptation-plan.json")
            saved = write_adaptation_plan(plan, report_path)
            print(f"\nPlan de adaptación: {saved}")
            return 0

        if args.command in {"instar-testcard", "nayade-testcard"}:
            output_map = extract_advanced_output_map(args.advanced_output)
            report = render_testcard(
                output_map,
                args.output,
                duration_seconds=args.duration,
                fps=args.fps,
                ffmpeg=args.ffmpeg,
            )
            print(testcard_text_report(report))
            if args.report:
                report_path = write_testcard_report(report, args.report)
                print(f"\nInforme JSON: {report_path}")
            return 0

        if args.command == "nayade-session":
            if args.session_command == "init":
                session_document = create_session(
                    args.source,
                    args.output,
                    name=args.name,
                    seed=args.seed,
                    catalog_path=args.catalog,
                    adaptation_plan_path=args.adaptation_plan,
                    protocol_path=args.protocol,
                )
                print(nayade_text_report(session_document))
                print(f"\nSesión JSON: {Path(args.output).expanduser().resolve()}")
                return 0

            if args.session_command == "record":
                parameters = {}
                if args.parameters:
                    try:
                        parameters = json.loads(args.parameters)
                    except json.JSONDecodeError as exc:
                        raise ResolumeAdapterError("--parameters debe ser un objeto JSON válido.") from exc
                    if not isinstance(parameters, dict):
                        raise ResolumeAdapterError("--parameters debe contener un objeto JSON.")
                event = record_event(
                    args.session,
                    operation=args.operation,
                    result=args.result,
                    scope=args.scope,
                    targets=args.target,
                    parameters=parameters,
                    notes=args.notes,
                    step_id=args.step_id,
                    output_path=args.output,
                )
                session_path = Path(args.session).expanduser().resolve()
                session_document = json.loads(session_path.read_text(encoding="utf-8"))
                print(nayade_text_report(session_document, event=event))
                return 0
            if args.session_command == "next":
                session_path = Path(args.session).expanduser().resolve()
                session_document = json.loads(session_path.read_text(encoding="utf-8"))
                step = get_next_step(session_path)
                print(nayade_text_report(session_document))
                if step is None:
                    print("\nNo quedan pasos pendientes.")
                else:
                    print("\nPRÓXIMO PASO")
                    print(f"ID: {step.get('step_id')}")
                    print(f"Operación: {step.get('operation')}")
                    print(f"Alcance: {step.get('scope')}")
                    print(f"Objetivos: {', '.join(step.get('targets') or [])}")
                    print(f"Parámetros: {json.dumps(step.get('parameters') or {}, ensure_ascii=False)}")
                    print(f"Comprobar: {', '.join(step.get('expected_checks') or [])}")
                return 0
            if args.session_command == "report":
                report = build_session_report(args.session)
                print(session_report_text(report))
                if args.report:
                    report_path = write_processor_json(report, args.report)
                    print(f"\nReporte JSON: {report_path}")
                return 0
        if args.command in {"nayade-processor", "processor"}:
            if args.processor_command == "catalog":
                catalog = load_processor_catalog(args.catalog)
                print(catalog_text_report(catalog))
                return 0
            if args.processor_command == "discover":
                report = discover_serial_devices(args.catalog)
                print(discovery_text_report(report))
                if args.report:
                    report_path = write_processor_json(report, args.report)
                    print(f"\nDescubrimiento JSON: {report_path}")
                return 0
            if args.processor_command == "snapshot":
                snapshot = snapshot_from_serial_device(
                    args.device,
                    model=args.model,
                    catalog_path=args.catalog,
                )
                print(snapshot_text_report(snapshot))
                report_path = write_processor_json(snapshot, args.output)
                print(f"\nSnapshot JSON: {report_path}")
                return 0
            if args.processor_command == "diagnose-case":
                report = diagnose_case(args.case)
                print(case_text_report(report))
                if args.report:
                    report_path = write_processor_json(report, args.report)
                    print(f"\nDiagnóstico JSON: {report_path}")
                return 0
            if args.processor_command == "validate-case":
                report = validate_processor_case(args.case)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                if args.report:
                    report_path = write_processor_json(report, args.report)
                    print(f"\nValidación JSON: {report_path}")
                return 0
            if args.processor_command == "reconcile":
                documents = {
                    name: load_reconciliation_document(path)
                    for name, path in (
                        ("signal_profile", args.signal_profile),
                        ("processor_observation", args.processor_observation),
                        ("processor_snapshot", args.processor_snapshot),
                        ("module_profile", args.module_profile),
                        ("mapping", args.mapping),
                        ("output_probe", args.output_probe),
                    )
                    if path
                }
                report = reconcile_signal_chain(documents)
                print(reconciliation_text_report(report))
                if args.report:
                    report_path = write_processor_json(report, args.report)
                    print(f"\nReconciliación JSON: {report_path}")
                return 1 if report["status"] == "FAIL" else 0
            if args.processor_command == "protocol":
                case_report = diagnose_case(args.case) if args.case else None
                reconciliation = load_reconciliation_document(args.reconciliation) if args.reconciliation else None
                mapping = load_reconciliation_document(args.mapping) if args.mapping else None
                report = build_soundcheck_protocol(case_report, reconciliation, mapping)
                print(protocol_text_report(report))
                if args.report:
                    report_path = write_processor_json(report, args.report)
                    print(f"\nProtocolo JSON: {report_path}")
                return 0
            if args.processor_command == "probe-output":
                report = probe_windows_output(timeout_seconds=args.timeout)
                print(output_probe_text_report(report))
                report_path = write_processor_json(report, args.report)
                print(f"\nSonda JSON: {report_path}")
                return 0
    except (ResolumeAdapterError, ReplayError, VJProjectError) as exc:
        print(f"RESOLUME_ADAPTER ERROR: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
