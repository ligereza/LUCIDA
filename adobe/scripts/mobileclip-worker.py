#!/usr/bin/env python3
"""JSONL worker for the official Apple MobileCLIP checkpoint.

The checkpoint is converted once to ONNX. The resident app worker then uses
ONNX Runtime's CUDA execution provider and does not import PyTorch.
"""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import html
import io
import json
import os
import re
import sys
import time
from pathlib import Path


# The model runs on CUDA. Keep the CPU side deliberately bounded: SVG parsing,
# rasterization and pixel preparation are host work, and NumPy/ORT should not
# create a large secondary thread pool while the GPU is processing a batch.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"


RUNTIME_CACHE = {}
TOKENIZER_CACHE = {}
CUDA_DLL_HANDLES = []
CUPY_KERNEL_CACHE = {}
CUPY_SHARED_STREAM = None


def configure_cuda_dlls():
    """Make the installed CUDA 11.x DLLs visible to Python extension modules."""

    if os.name != "nt" or CUDA_DLL_HANDLES:
        return
    candidates = []
    for variable in ("CUDA_PATH_V11_8", "CUDA_PATH"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value) / "bin")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    candidates.append(Path(program_files) / "NVIDIA GPU Computing Toolkit" / "CUDA" / "v11.8" / "bin")
    seen = set()
    for directory in candidates:
        directory = directory.resolve()
        if directory in seen or not (directory / "nvrtc64_112_0.dll").is_file():
            continue
        seen.add(directory)
        try:
            CUDA_DLL_HANDLES.append(os.add_dll_directory(str(directory)))
        except (AttributeError, OSError):
            pass
        os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
        return


CUDA_PREPROCESS_KERNEL = r"""
extern "C" __global__
void mobileclip_preprocess(
    const unsigned char* source,
    const long long* offsets,
    const int* widths,
    const int* heights,
    float* destination,
    int count
) {
    const int output_width = 256;
    const int output_height = 256;
    const int area = output_width * output_height;
    const long long index = (long long)blockIdx.x * blockDim.x + threadIdx.x;
    const long long total = (long long)count * 3 * area;
    if (index >= total) return;

    const int channel = (int)((index / area) % 3);
    const long long image_index = index / (3 * area);
    const int pixel = (int)(index % area);
    const int output_y = pixel / output_width;
    const int output_x = pixel % output_width;
    const int width = widths[image_index];
    const int height = heights[image_index];
    const float scale = 256.0f / (float)(width < height ? width : height);
    const int resized_width = max(256, (int)roundf((float)width * scale));
    const int resized_height = max(256, (int)roundf((float)height * scale));
    const int crop_left = (resized_width - 256) / 2;
    const int crop_top = (resized_height - 256) / 2;

    // Match the center-crop pipeline with bilinear sampling directly from the
    // packed RGB bitmap, avoiding a CPU resize and HWC->CHW intermediate.
    const float source_x = ((float)(output_x + crop_left) + 0.5f) / scale - 0.5f;
    const float source_y = ((float)(output_y + crop_top) + 0.5f) / scale - 0.5f;
    const int x0 = max(0, min(width - 1, (int)floorf(source_x)));
    const int y0 = max(0, min(height - 1, (int)floorf(source_y)));
    const int x1 = min(width - 1, x0 + 1);
    const int y1 = min(height - 1, y0 + 1);
    const float dx = source_x - floorf(source_x);
    const float dy = source_y - floorf(source_y);
    const long long offset = offsets[image_index];
    const long long p00 = offset + ((long long)y0 * width + x0) * 3 + channel;
    const long long p01 = offset + ((long long)y0 * width + x1) * 3 + channel;
    const long long p10 = offset + ((long long)y1 * width + x0) * 3 + channel;
    const long long p11 = offset + ((long long)y1 * width + x1) * 3 + channel;
    const float top = (float)source[p00] * (1.0f - dx) + (float)source[p01] * dx;
    const float bottom = (float)source[p10] * (1.0f - dx) + (float)source[p11] * dx;
    destination[index] = (top * (1.0f - dy) + bottom * dy) / 255.0f;
}
"""


def import_optional(name):
    if name == "cupy":
        configure_cuda_dlls()
    try:
        return __import__(name)
    except Exception:
        return None


def get_cupy():
    cupy = import_optional("cupy")
    if cupy is None:
        raise RuntimeError("CuPy preprocessing was requested but cupy-cuda11x is not installed")
    return cupy


def get_shared_cupy_stream():
    global CUPY_SHARED_STREAM

    cupy = get_cupy()
    if CUPY_SHARED_STREAM is None:
        CUPY_SHARED_STREAM = cupy.cuda.Stream(non_blocking=True)
    return CUPY_SHARED_STREAM


def cupy_preprocess(images):
    """Pack a batch once on the host and fuse resize/crop/scale/layout on CUDA."""

    import numpy as np

    cupy = get_cupy()
    started = time.perf_counter()
    arrays = []
    offsets = []
    widths = []
    heights = []
    total_bytes = 0
    for image in images:
        array = np.ascontiguousarray(np.asarray(image.convert("RGB"), dtype=np.uint8))
        if array.ndim != 3 or array.shape[2] != 3 or array.shape[0] <= 0 or array.shape[1] <= 0:
            raise RuntimeError("Image has no visible RGB dimensions")
        arrays.append(array)
        offsets.append(total_bytes)
        heights.append(array.shape[0])
        widths.append(array.shape[1])
        total_bytes += int(array.size)
    pinned_memory = cupy.cuda.alloc_pinned_memory(total_bytes)
    packed = np.frombuffer(pinned_memory, dtype=np.uint8, count=total_bytes)
    cursor = 0
    for array in arrays:
        end = cursor + int(array.size)
        packed[cursor:end] = array.reshape(-1)
        cursor = end
    host_pack_ms = (time.perf_counter() - started) * 1000

    stream = get_shared_cupy_stream()
    transfer_started = time.perf_counter()
    with stream:
        source = cupy.asarray(packed)
        device_offsets = cupy.asarray(np.asarray(offsets, dtype=np.int64))
        device_widths = cupy.asarray(np.asarray(widths, dtype=np.int32))
        device_heights = cupy.asarray(np.asarray(heights, dtype=np.int32))
        destination = cupy.empty((len(images), 3, 256, 256), dtype=cupy.float32)
    transfer_ms = (time.perf_counter() - transfer_started) * 1000

    kernel = CUPY_KERNEL_CACHE.get("mobileclip_preprocess")
    if kernel is None:
        kernel = cupy.RawKernel(CUDA_PREPROCESS_KERNEL, "mobileclip_preprocess", options=("--std=c++11",))
        CUPY_KERNEL_CACHE["mobileclip_preprocess"] = kernel
    kernel_started = time.perf_counter()
    threads = 256
    blocks = (destination.size + threads - 1) // threads
    kernel(
        (blocks,),
        (threads,),
        (source, device_offsets, device_widths, device_heights, destination, np.int32(len(images))),
        stream=stream,
    )
    kernel_ms = (time.perf_counter() - kernel_started) * 1000
    return destination, {
        "cupyHostPackMs": host_pack_ms,
        "cupyTransferMs": transfer_ms,
        "cupyKernelMs": kernel_ms,
        "cupyPinnedHostBytes": total_bytes,
        "cupySharedStream": 1,
    }, (pinned_memory, source, device_offsets, device_widths, device_heights)


def add_repo(repo_path):
    # Kept for status/diagnostics so the runtime still reports the official
    # Apple source used to create the ONNX graphs.
    if repo_path and repo_path not in sys.path:
        sys.path.insert(0, repo_path)


def model_files(request):
    model_path = Path(os.path.abspath(request["modelPath"]))
    base = model_path.parent
    stem = model_path.stem
    return {
        "image": Path(request.get("imageModelPath") or base / f"{stem}.image.onnx"),
        "text": Path(request.get("textModelPath") or base / f"{stem}.text.onnx"),
        "tokenizer": Path(request.get("tokenizerPath") or base / f"{stem}.tokenizer.json"),
    }


def session_batch_size(session):
    """Return a fixed image batch dimension, if this graph has one."""

    shape = session.get_inputs()[0].shape
    if not shape:
        return None
    value = shape[0]
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def bytes_to_unicode():
    bs = list(range(ord("!"), ord("~") + 1))
    bs += list(range(ord("¡"), ord("¬") + 1))
    bs += list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    extra = 0
    for value in range(2**8):
        if value not in bs:
            bs.append(value)
            cs.append(2**8 + extra)
            extra += 1
    return dict(zip(bs, (chr(value) for value in cs)))


class ClipTokenizer:
    def __init__(self, path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.context_length = int(payload["contextLength"])
        self.sot_token_id = int(payload["sotToken"])
        self.eot_token_id = int(payload["eotToken"])
        self.encoder = {str(key): int(value) for key, value in payload["encoder"].items()}
        self.bpe_ranks = {
            (str(pair[0]), str(pair[1])): rank
            for rank, pair in enumerate(payload["merges"])
        }
        self.byte_encoder = bytes_to_unicode()
        self.cache = {}
        pattern = payload.get("pattern") or r"'s|'t|'re|'ve|'m|'ll|'d|[^\s]+"
        try:
            import regex

            self.pattern = regex.compile(pattern, regex.IGNORECASE)
        except Exception:
            # This fallback is sufficient for ASCII-only queries, while the
            # normal path uses the same Unicode regex engine as OpenCLIP.
            self.pattern = re.compile(r"'s|'t|'re|'ve|'m|'ll|'d|[^\s]+", re.IGNORECASE)

    @staticmethod
    def get_pairs(word):
        return {(word[index], word[index + 1]) for index in range(len(word) - 1)}

    def bpe(self, token):
        if token in self.cache:
            return self.cache[token]
        word = tuple(token[:-1]) + (token[-1] + "</w>",)
        pairs = self.get_pairs(word)
        if not pairs:
            return token + "</w>"
        while True:
            bigram = min(pairs, key=lambda pair: self.bpe_ranks.get(pair, float("inf")))
            if bigram not in self.bpe_ranks:
                break
            first, second = bigram
            new_word = []
            index = 0
            while index < len(word):
                try:
                    next_index = word.index(first, index)
                    new_word.extend(word[index:next_index])
                    index = next_index
                except ValueError:
                    new_word.extend(word[index:])
                    break
                if index < len(word) - 1 and word[index] == first and word[index + 1] == second:
                    new_word.append(first + second)
                    index += 2
                else:
                    new_word.append(word[index])
                    index += 1
            word = tuple(new_word)
            if len(word) == 1:
                break
            pairs = self.get_pairs(word)
        result = " ".join(word)
        self.cache[token] = result
        return result

    def encode(self, text):
        text = html.unescape(html.unescape(text)).strip().lower()
        tokens = []
        for token in self.pattern.findall(text):
            encoded = "".join(self.byte_encoder[value] for value in token.encode("utf-8"))
            tokens.extend(self.encoder[value] for value in self.bpe(encoded).split(" "))
        return tokens

    def encode_batch(self, texts):
        import numpy as np

        result = np.zeros((len(texts), self.context_length), dtype=np.int64)
        eot_indices = np.zeros((len(texts),), dtype=np.int64)
        for row, text in enumerate(texts):
            values = [self.sot_token_id] + self.encode(str(text)) + [self.eot_token_id]
            if len(values) > self.context_length:
                values = values[: self.context_length]
                values[-1] = self.eot_token_id
            result[row, : len(values)] = values
            eot_indices[row] = max(0, len(values) - 1)
        return result, eot_indices

    def __call__(self, texts):
        return self.encode_batch(texts)[0]


def load_tokenizer(path):
    key = str(path)
    if key not in TOKENIZER_CACHE:
        TOKENIZER_CACHE[key] = ClipTokenizer(path)
    return TOKENIZER_CACHE[key]


def load_ort_session(path, requested, profile_path=None, user_compute_stream=None, cuda_graph=False):
    import onnxruntime as ort

    if not path.is_file():
        raise RuntimeError(f"ONNX graph does not exist: {path}")
    try:
        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls(directory="")
    except Exception:
        pass
    available = ort.get_available_providers()
    if requested == "cpu":
        providers = ["CPUExecutionProvider"]
    elif requested == "cuda":
        if "CUDAExecutionProvider" not in available:
            raise RuntimeError("CUDAExecutionProvider is not available in ONNX Runtime")
        providers = ["CUDAExecutionProvider"]
    else:
        providers = ["CUDAExecutionProvider"] if "CUDAExecutionProvider" in available else ["CPUExecutionProvider"]
    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = 1
    session_options.inter_op_num_threads = 1
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session_config = {
        "intraOpThreads": 1,
        "interOpThreads": 1,
        "executionMode": "ORT_SEQUENTIAL",
        "intraOpAllowSpinning": False,
        "interOpAllowSpinning": False,
        "intraOpSpinDurationUs": 0,
        "interOpSpinDurationUs": 0,
        "profiling": bool(profile_path),
    }
    session_options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    session_options.add_session_config_entry("session.inter_op.allow_spinning", "0")
    session_options.add_session_config_entry("session.intra_op.spin_duration_us", "0")
    session_options.add_session_config_entry("session.inter_op.spin_duration_us", "0")
    if profile_path:
        session_options.enable_profiling = True
        session_options.profile_file_prefix = str(profile_path)
    if user_compute_stream and requested != "cpu":
        cuda_options = {
            "device_id": "0",
            "user_compute_stream": str(user_compute_stream),
            # Keep CUDA copies serialized on ORT's default stream. With
            # zero, ORT documents possible races; the input is already bound
            # on the user stream, so disabling the default copy path is not
            # needed here.
            "do_copy_in_default_stream": "1",
        }
        if cuda_graph:
            cuda_options["enable_cuda_graph"] = "1"
        providers = [("CUDAExecutionProvider", cuda_options)] if "CUDAExecutionProvider" in available else providers
        session_config["userComputeStream"] = str(user_compute_stream)
        session_config["cudaGraph"] = bool(cuda_graph)
    try:
        session = ort.InferenceSession(str(path), sess_options=session_options, providers=providers)
    except Exception:
        if requested not in (None, "", "auto") or providers == ["CPUExecutionProvider"]:
            raise
        session = ort.InferenceSession(str(path), sess_options=session_options, providers=["CPUExecutionProvider"])
    actual = "cuda" if "CUDAExecutionProvider" in session.get_providers() else "cpu"
    return session, actual, session_config


def load_runtime(request):
    paths = model_files(request)
    requested = request.get("device", "auto")
    profile_path = request.get("profilePath")
    cuda_graph = bool(request.get("cudaGraph"))
    user_compute_stream = None
    if str(request.get("preprocessBackend") or "cupy").lower() == "cupy":
        user_compute_stream = get_shared_cupy_stream().ptr
    key = (str(paths["image"]), str(paths["text"]), str(paths["tokenizer"]), requested, str(profile_path or ""), str(user_compute_stream or ""), cuda_graph)
    if key in RUNTIME_CACHE:
        return RUNTIME_CACHE[key]
    tokenizer = load_tokenizer(paths["tokenizer"])
    image_session, image_device, image_config = load_ort_session(paths["image"], requested, profile_path, user_compute_stream, cuda_graph)
    try:
        text_session, text_device, text_config = load_ort_session(paths["text"], image_device if requested in (None, "", "auto") else requested)
    except Exception:
        # ORT 1.18.1 can execute the image graph on CUDA but lacks a CUDA
        # kernel for the exported text ArgMax. Text queries are tiny, so keep
        # the large image index on CUDA and use the CPU only for query text.
        if requested not in (None, "", "auto") or image_device != "cuda":
            raise
        text_session, text_device, text_config = load_ort_session(paths["text"], "cpu")
    device = image_device
    value = {
        "image": image_session,
        "text": text_session,
        "tokenizer": tokenizer,
        "device": device,
        "textDevice": text_device,
        "sessionConfig": {"image": image_config, "text": text_config},
        "profilePath": str(profile_path) if profile_path else None,
        "paths": paths,
    }
    RUNTIME_CACHE[key] = value
    return value


def status(request):
    add_repo(request.get("repoPath") or os.environ.get("MOBILECLIP_REPO"))
    ort = import_optional("onnxruntime")
    pillow = import_optional("PIL")
    cairosvg = import_optional("cairosvg")
    resvg = import_optional("resvg_py")
    cupy = import_optional("cupy")
    numpy = import_optional("numpy")
    regex = import_optional("regex")
    threadpoolctl = import_optional("threadpoolctl")
    cupy_cuda = False
    cupy_error = None
    if cupy:
        try:
            cupy_cuda = int(cupy.cuda.runtime.getDeviceCount()) > 0
        except Exception as error:
            cupy_error = str(error)
    result = {
        "ok": True,
        "python": sys.executable,
        "pythonVersion": sys.version.split()[0],
        "torch": False,
        "torchVersion": None,
        "mobileclip": bool(request.get("repoPath") and Path(request["repoPath"]).is_dir()),
        "onnxruntime": ort is not None,
        "onnxruntimeVersion": getattr(ort, "__version__", None) if ort else None,
        "onnxImage": False,
        "onnxText": False,
        "tokenizer": False,
        "providers": [],
        "cuda": False,
        "cudaName": None,
        "pillow": pillow is not None,
        "cairosvg": cairosvg is not None,
        "resvg": resvg is not None,
        "cupy": cupy is not None,
        "cupyVersion": getattr(cupy, "__version__", None) if cupy else None,
        "cupyCuda": cupy_cuda,
        "cupyError": cupy_error,
        "numpy": numpy is not None,
        "regex": regex is not None,
        "threadpoolctl": threadpoolctl is not None,
        "threadpoolInfo": [],
    }
    paths = model_files(request)
    result["onnxImage"] = paths["image"].is_file()
    result["onnxText"] = paths["text"].is_file()
    result["tokenizer"] = paths["tokenizer"].is_file()
    if ort:
        try:
            result["providers"] = ort.get_available_providers()
            if result["onnxImage"] and result["onnxText"] and result["tokenizer"]:
                runtime = load_runtime(request)
                result["device"] = runtime["device"]
                result["cuda"] = runtime["device"] == "cuda"
                result["activeProviders"] = runtime["image"].get_providers()
                result["textDevice"] = runtime["textDevice"]
                result["sessionConfig"] = runtime["sessionConfig"]
                if threadpoolctl:
                    result["threadpoolInfo"] = threadpoolctl.threadpool_info()
        except Exception as error:
            result["error"] = str(error)
    return result


def flatten_transparency(image, metrics=None):
    from PIL import Image

    started = time.perf_counter()
    if image.mode not in ("RGBA", "LA") and "transparency" not in image.info:
        result = image.convert("RGB")
    else:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        result = background.convert("RGB")
    if metrics is not None:
        metrics["alphaMs"] = metrics.get("alphaMs", 0.0) + (time.perf_counter() - started) * 1000
    return result


def render_svg(file_path, metrics=None, renderer="auto"):
    resvg = import_optional("resvg_py")
    cairosvg = import_optional("cairosvg")
    selected = renderer
    if selected in (None, "", "auto"):
        # resvg remains opt-in until its PNG bridge and SVG compatibility pass
        # the same-resource benchmark. CairoSVG is the stable default.
        selected = "cairosvg" if cairosvg is not None else "resvg"
    if selected == "resvg":
        if resvg is None:
            raise RuntimeError("The resvg renderer was requested but resvg_py is not installed")
        started = time.perf_counter()
        png = resvg.svg_to_bytes(svg_path=str(file_path), background="#ffffff", width=1024)
        if metrics is not None:
            metrics["svgResvgMs"] = metrics.get("svgResvgMs", 0.0) + (time.perf_counter() - started) * 1000
            metrics["svgResvgCount"] = metrics.get("svgResvgCount", 0) + 1
        return png
    if selected != "cairosvg" or cairosvg is None:
        raise RuntimeError(f"Unsupported SVG renderer: {selected}")
    read_started = time.perf_counter()
    source = Path(file_path).read_bytes()
    if metrics is not None:
        metrics["readMs"] = metrics.get("readMs", 0.0) + (time.perf_counter() - read_started) * 1000
    raster_started = time.perf_counter()
    png = cairosvg.svg2png(bytestring=source, background_color="#ffffff", output_width=1024)
    if metrics is not None:
        metrics["svgCairoMs"] = metrics.get("svgCairoMs", 0.0) + (time.perf_counter() - raster_started) * 1000
        metrics["svgCairoCount"] = metrics.get("svgCairoCount", 0) + 1
    return png


def open_visual(file_path, metrics=None, renderer="auto"):
    from PIL import Image

    suffix = Path(file_path).suffix.lower()
    if suffix == ".svg":
        png = render_svg(file_path, metrics, renderer)
        decode_started = time.perf_counter()
        with Image.open(io.BytesIO(png)) as image:
            result = image.convert("RGB").copy()
        if metrics is not None:
            metrics["imageDecodeMs"] = metrics.get("imageDecodeMs", 0.0) + (time.perf_counter() - decode_started) * 1000
        return result
    read_started = time.perf_counter()
    with Image.open(file_path) as image:
        result = image.copy()
    if metrics is not None:
        metrics["imageDecodeMs"] = metrics.get("imageDecodeMs", 0.0) + (time.perf_counter() - read_started) * 1000
    return flatten_transparency(result, metrics)


def preprocess(image, metrics=None):
    import numpy as np
    from PIL import Image

    image = image.convert("RGB")
    width, height = image.size
    if width <= 0 or height <= 0:
        raise RuntimeError("Image has no visible dimensions")
    resize_started = time.perf_counter()
    scale = 256.0 / min(width, height)
    resized = image.resize((max(256, round(width * scale)), max(256, round(height * scale))), Image.Resampling.BILINEAR)
    left = (resized.width - 256) // 2
    top = (resized.height - 256) // 2
    cropped = resized.crop((left, top, left + 256, top + 256))
    if metrics is not None:
        metrics["resizeCropMs"] = metrics.get("resizeCropMs", 0.0) + (time.perf_counter() - resize_started) * 1000
    tensor_started = time.perf_counter()
    values = np.asarray(cropped, dtype=np.float32) / 255.0
    result = np.transpose(values, (2, 0, 1))
    if metrics is not None:
        metrics["tensorMs"] = metrics.get("tensorMs", 0.0) + (time.perf_counter() - tensor_started) * 1000
    return result


def prepare_batch(batch_files, renderer="auto", preprocess_backend="cpu"):
    """Rasterize and preprocess one bounded batch on the CPU."""

    started = time.perf_counter()
    tensors = []
    valid_files = []
    failed = []
    metrics = {}
    for item in batch_files:
        try:
            image = open_visual(item["file"], metrics, renderer)
            if preprocess_backend == "cupy":
                tensors.append(image)
            else:
                tensors.append(preprocess(image, metrics))
            valid_files.append(item)
        except Exception as error:
            failed.append({"assetId": item.get("assetId"), "file": item.get("file"), "error": str(error)})
    return tensors, valid_files, failed, (time.perf_counter() - started) * 1000, metrics


def normalize(values):
    import numpy as np

    values = np.asarray(values, dtype=np.float32)
    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    return values / np.maximum(norms, 1e-12)


def encode_images(request):
    import numpy as np

    started = time.time()
    cpu_started = time.process_time()
    requested_batch_size = max(1, min(128, int(request.get("batchSize") or 24)))
    files = request.get("files") or []
    if bool(request.get("cudaGraph")) and len(files) > requested_batch_size:
        raise RuntimeError("CUDA Graph experimental mode currently requires one fixed batch; use a single batch or leave cudaGraph disabled")
    runtime = load_runtime(request)
    session = runtime["image"]
    fixed_batch_size = session_batch_size(session)
    batch_size = fixed_batch_size or requested_batch_size
    output_path = Path(os.path.abspath(request["outputPath"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    encoded_items = []
    failed = []
    dimension = 0
    preprocess_ms = 0.0
    inference_ms = 0.0
    batches = 0
    stage_metrics = {}
    profile_files = []
    preprocess_workers = max(1, min(2, int(request.get("preprocessWorkers") or 1)))
    renderer = str(request.get("renderer") or "auto").lower()
    preprocess_backend = str(request.get("preprocessBackend") or "cupy").lower()
    if preprocess_backend == "auto":
        preprocess_backend = "cupy" if import_optional("cupy") is not None else "cpu"
    if preprocess_backend not in ("cpu", "cupy"):
        raise RuntimeError(f"Unsupported preprocess backend: {preprocess_backend}")
    if preprocess_backend == "cupy" and runtime["device"] != "cuda":
        raise RuntimeError("CuPy preprocessing requires the MobileCLIP image session to run on CUDA")
    batch_ranges = [files[start : start + batch_size] for start in range(0, len(files), batch_size)]
    with output_path.open("wb") as output:
        # Keep only a bounded CPU producer. The next batch is prepared while
        # CUDA is embedding the current one, so the GPU does not wait for SVG
        # rasterization, without allowing the CPU to fan out across the machine.
        with ThreadPoolExecutor(max_workers=preprocess_workers, thread_name_prefix="mobileclip-prep") as producer:
            next_batch = producer.submit(prepare_batch, batch_ranges[0], renderer, preprocess_backend) if batch_ranges else None
            for batch_index in range(len(batch_ranges)):
                tensors, valid_files, batch_failed, batch_preprocess_ms, batch_metrics = next_batch.result()
                preprocess_ms += batch_preprocess_ms
                failed.extend(batch_failed)
                for key, value in batch_metrics.items():
                    stage_metrics[key] = stage_metrics.get(key, 0.0) + value
                if batch_index + 1 < len(batch_ranges):
                    next_batch = producer.submit(prepare_batch, batch_ranges[batch_index + 1], renderer, preprocess_backend)
                if not tensors:
                    continue
                valid_count = len(valid_files)
                model_tensors = tensors
                if fixed_batch_size and valid_count < fixed_batch_size:
                    # A fixed ONNX graph needs a full batch. Repeating the
                    # first valid image keeps the input shape stable; padded
                    # rows are discarded before writing the index vectors.
                    model_tensors = tensors + [tensors[0]] * (fixed_batch_size - valid_count)
                if preprocess_backend == "cupy":
                    batch, cupy_metrics, cupy_resources = cupy_preprocess(model_tensors)
                    for key, value in cupy_metrics.items():
                        stage_metrics[key] = stage_metrics.get(key, 0.0) + value
                else:
                    batch = np.stack(model_tensors).astype(np.float32, copy=False)
                    cupy_resources = None
                inference_started = time.perf_counter()
                if preprocess_backend == "cupy":
                    io_binding = session.io_binding()
                    io_binding.bind_input(
                        name=input_name,
                        device_type="cuda",
                        device_id=0,
                        element_type=np.float32,
                        shape=tuple(batch.shape),
                        buffer_ptr=batch.data.ptr,
                    )
                    io_binding.bind_output(name=output_name, device_type="cuda", device_id=0)
                    session.run_with_iobinding(io_binding)
                    features = io_binding.copy_outputs_to_cpu()[0]
                else:
                    features = session.run([output_name], {input_name: batch})[0]
                features = normalize(features)[:valid_count]
                del cupy_resources
                inference_ms += (time.perf_counter() - inference_started) * 1000
                batches += 1
                dimension = int(features.shape[-1])
                output.write(np.asarray(features, dtype="<f4").tobytes(order="C"))
                encoded_items.extend({"assetId": item.get("assetId"), "file": item.get("file")} for item in valid_files)
    if runtime.get("profilePath"):
        try:
            profile_files.append(runtime["image"].end_profiling())
        except Exception:
            pass
    finished = time.time()
    cpu_time_ms = (time.process_time() - cpu_started) * 1000
    elapsed_ms = max((finished - started) * 1000, 0.001)
    return {
        "ok": True,
        "items": encoded_items,
        "failed": failed,
        "dimension": dimension,
        "device": runtime["device"],
        "preprocessWorkers": preprocess_workers,
        "requestedBatchSize": requested_batch_size,
        "modelBatchSize": fixed_batch_size,
        "preprocessBackend": preprocess_backend,
        "renderer": renderer,
        "batches": batches,
        "preprocessMs": round(preprocess_ms),
        "inferenceMs": round(inference_ms),
        "stagesMs": {key: round(value) for key, value in stage_metrics.items()},
        "profileFiles": profile_files,
        "cpuTimeMs": round(cpu_time_ms),
        "cpuPercentOfOneCore": round((cpu_time_ms / elapsed_ms) * 100, 1),
        "elapsedMs": round(elapsed_ms),
    }


def encode_text(request):
    import numpy as np

    runtime = load_runtime(request)
    texts = [str(value) for value in (request.get("texts") or [])]
    if not texts:
        return {"ok": True, "vectors": "", "dimension": 0, "count": 0, "device": runtime["device"]}
    session = runtime["text"]
    tokens, eot_indices = runtime["tokenizer"].encode_batch(texts)
    input_name = session.get_inputs()[0].name
    eot_name = session.get_inputs()[1].name
    output_name = session.get_outputs()[0].name
    features = normalize(session.run([output_name], {input_name: tokens, eot_name: eot_indices})[0])
    values = np.asarray(features, dtype="<f4").tobytes(order="C")
    return {
        "ok": True,
        "vectors": base64.b64encode(values).decode("ascii"),
        "dimension": int(features.shape[-1]),
        "count": len(texts),
        "device": runtime["device"],
    }


def handle(request):
    operation = request.get("op")
    if operation == "status":
        return status(request)
    if operation == "encode_images":
        return encode_images(request)
    if operation == "encode_text":
        return encode_text(request)
    raise RuntimeError(f"Unknown MobileCLIP worker operation: {operation}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdio", action="store_true")
    args = parser.parse_args()
    if not args.stdio:
        raise SystemExit("Use --stdio")
    for line in sys.stdin:
        if not line.strip():
            continue
        request = None
        try:
            request = json.loads(line)
            response = handle(request)
            response["id"] = request.get("id")
        except Exception as error:
            response = {"id": request.get("id") if request else None, "ok": False, "error": str(error)}
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
