# Third-party notices

## DepthGen

The DepthGen image, inference, temporal and model-integrity modules are ported
from `palf-gh/DepthGen`, MIT licensed:

https://github.com/palf-gh/DepthGen

The port preserves the original notice and uses the DepthGen v1.0.1 verified
resources. The FFGL adapter in this directory is LUCIDA code.

## Resolume FFGL SDK

The adapter is built against the official Resolume FFGL SDK, distributed under
the SDK's BSD-3-Clause license:

https://github.com/resolume/ffgl

The SDK's source notice remains in `C:/IA/vendor/resolume-ffgl` and is not
modified by this project.

## ONNX Runtime

The embedded private runtime is the DepthGen v1.0.1 Windows runtime resource.
ONNX Runtime is distributed by Microsoft under the MIT license. The package
notices and source attribution are available from:

https://github.com/microsoft/onnxruntime

Runtime resource SHA-256:

`e268219a33cf3898c16ae364efc79a4a656c87d2ee67fd872b079aca769fd97e`

## Model resources

The model resources are the verified DepthGen v1.0.1 payloads. They are kept
as embedded resources in the release DLL and are checked before session
creation:

- ZipDepth Base NPU: MIT; SHA-256 `0741a0d574609da33c5081b1054a2dd1e8845ecdbed9a5f69c48807c22400d59`.
- Depth Anything V2 Small DirectML repackage: Apache-2.0; SHA-256 `237cfaaf329bc97b9914c14e2d2497b1159cc05cca1b6d7a68aa42a262ea99bf`.

The model provenance and pinned upstream references are documented by
DepthGen in `docs/MODEL_PROVENANCE.md`.
