#!/usr/bin/env python3
"""Export the official Apple MobileCLIP v1 checkpoint to ONNX.

This script is intentionally an offline conversion step. It loads only the
checkpoint supplied by the caller and writes image/text ONNX graphs plus the
CLIP tokenizer data needed by the lightweight runtime worker.
"""

import argparse
import gzip
import json
import os
import sys
from pathlib import Path


def load_model(model_name, checkpoint, repo_path, device):
    import torch
    import torch.nn.functional as F
    import mobileclip

    # The official SE block reshapes an already [B, C, 1, 1] tensor using a
    # channel value read dynamically from the input. That is equivalent to a
    # no-op in inference, but the legacy ONNX exporter cannot represent that
    # shape list with a dynamic batch. Keep the computation identical and
    # remove only the redundant view for export compatibility.
    from mobileclip.modules.common.mobileone import SEBlock

    def export_safe_se_forward(self, inputs):
        x = F.adaptive_avg_pool2d(inputs, output_size=(1, 1))
        x = self.reduce(x)
        x = F.relu(x)
        x = self.expand(x)
        return inputs * torch.sigmoid(x)

    SEBlock.forward = export_safe_se_forward

    model, _, _ = mobileclip.create_model_and_transforms(
        model_name,
        pretrained=None,
        reparameterize=False,
        device=device,
    )
    state = torch.load(checkpoint, map_location=device, weights_only=True)
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    model.load_state_dict(state, strict=True)
    model.eval()
    try:
        from mobileclip.modules.common.mobileone import reparameterize_model

        model = reparameterize_model(model)
        model.eval()
    except Exception:
        pass
    return model


def export_tokenizer(model_name, output_path, repo_path):
    import mobileclip

    tokenizer = mobileclip.get_tokenizer(model_name).tokenizer
    payload = {
        "schemaVersion": 1,
        "contextLength": 77,
        "sotToken": tokenizer.sot_token_id,
        "eotToken": tokenizer.eot_token_id,
        "encoder": tokenizer.encoder,
        "merges": [[first, second] for first, second in tokenizer.bpe_ranks],
        "pattern": tokenizer.pat.pattern,
        "clean": "lower",
    }
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class ImageEncoder:
    def __init__(self, model):
        import torch.nn as nn

        class Wrapper(nn.Module):
            def __init__(self, source):
                super().__init__()
                self.source = source

            def forward(self, image):
                return self.source.encode_image(image, normalize=True)

        self.module = Wrapper(model).eval()


class TextEncoder:
    def __init__(self, model):
        import torch
        import torch.nn.functional as F
        import torch.nn as nn

        class Wrapper(nn.Module):
            def __init__(self, source):
                super().__init__()
                self.source = source

            def forward(self, tokens, eot_indices):
                # MobileCLIP selects the EOT token with ArgMax internally.
                # Supplying its index from the tokenizer avoids ArgMax in the
                # ONNX graph, where older ORT releases lack the needed kernel.
                encoder = self.source.text_encoder
                token_emb = encoder.forward_embedding(tokens)
                for layer in encoder.transformer:
                    token_emb = layer(token_emb, key_padding_mask=None, attn_mask=None)
                token_emb = encoder.final_layer_norm(token_emb)
                index = eot_indices.to(torch.long).view(-1, 1, 1)
                index = index.expand(-1, 1, token_emb.shape[-1])
                selected = torch.gather(token_emb, 1, index).squeeze(1)
                features = selected @ encoder.projection_layer
                return F.normalize(features, dim=-1)

        self.module = Wrapper(model).eval()


def export_onnx(model_name, checkpoint, repo_path, output_dir, opset, image_batch_size=0, device="cuda"):
    import torch

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model = load_model(model_name, checkpoint, repo_path, device)

    image_wrapper = ImageEncoder(model).module
    fixed_image_batch = max(0, int(image_batch_size or 0))
    image_path = output_dir / (
        f"{model_name}.image.b{fixed_image_batch}.onnx"
        if fixed_image_batch
        else f"{model_name}.image.onnx"
    )
    image_input = torch.zeros(max(1, fixed_image_batch), 3, 256, 256, dtype=torch.float32, device=device)
    image_export = {
        "input_names": ["image"],
        "output_names": ["embedding"],
        "opset_version": opset,
        "do_constant_folding": True,
        "dynamo": False,
    }
    if not fixed_image_batch:
        image_export["dynamic_axes"] = {"image": {0: "batch"}, "embedding": {0: "batch"}}
    torch.onnx.export(image_wrapper, (image_input,), str(image_path), **image_export)

    text_wrapper = TextEncoder(model).module
    text_path = output_dir / f"{model_name}.text.onnx"
    text_input = torch.zeros(1, 77, dtype=torch.long, device=device)
    eot_input = torch.tensor([2], dtype=torch.long, device=device)
    torch.onnx.export(
        text_wrapper,
        (text_input, eot_input),
        str(text_path),
        input_names=["tokens", "eot_indices"],
        output_names=["embedding"],
        dynamic_axes={"tokens": {0: "batch"}, "eot_indices": {0: "batch"}, "embedding": {0: "batch"}},
        # ORT 1.18.1 has no CUDA/CPU implementation for ArgMax-13 in the
        # text graph. The older ArgMax-11 operator is equivalent here and is
        # supported by the lightweight runtime.
        opset_version=min(opset, 11),
        do_constant_folding=True,
        dynamo=False,
    )
    export_tokenizer(model_name, output_dir / f"{model_name}.tokenizer.json", repo_path)
    return image_path, text_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default="mobileclip_s2")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument(
        "--image-batch-size",
        type=int,
        default=0,
        help="Export a separate fixed-size image graph, e.g. 96; 0 keeps the dynamic graph.",
    )
    parser.add_argument(
        "--device",
        choices=("cuda", "cpu"),
        default="cuda",
        help="Device used to load and trace the model. CUDA is the default; CPU is an explicit fallback.",
    )
    args = parser.parse_args()
    repo_path = os.path.abspath(args.repo_path)
    if repo_path not in sys.path:
        sys.path.insert(0, repo_path)
    os.environ["PYTHONPATH"] = repo_path + os.pathsep + os.environ.get("PYTHONPATH", "")
    image_path, text_path = export_onnx(
        args.model_name,
        os.path.abspath(args.checkpoint),
        repo_path,
        os.path.abspath(args.output_dir),
        args.opset,
        args.image_batch_size,
        args.device,
    )
    print(json.dumps({"ok": True, "image": str(image_path), "text": str(text_path)}))


if __name__ == "__main__":
    main()
