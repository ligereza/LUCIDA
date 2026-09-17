# LUCIDA Depth

`LUCIDA Depth` is the FFGL adapter for the open-source DepthGen effect. It
receives the current Resolume texture, runs the DepthGen inference and
post-processing core in-process, and returns a monochrome relative-depth map
with source-alpha preservation.

The adapter is intentionally thin. DepthGen's model selection, quality sizes,
percentile mapping, contrast, inversion, temporal stability, alpha handling,
exception containment and provider fallback remain in the ported core. The
After Effects SmartFX host code and the historical TensorRT/`.engine` bridge
are not part of this target.

## Build prerequisites

- Windows, Visual Studio 2022 x64 and CMake.
- The official Resolume FFGL SDK at `C:/IA/vendor/resolume-ffgl`.
- The verified DepthGen resources in the build asset directory:
  - `zipdepth_base_npu_dynamic.onnx`
  - `depth_anything_v2_vits_dml.onnx`
  - `DepthGen-onnxruntime.dll`
- ONNX Runtime 1.17.3 DirectML headers under `build/native/include`.

The current workspace obtains those resources from the DepthGen v1.0.1
release and keeps them in the ignored `work/resolume-plugin-build` tree. The
models and runtime are embedded into the DLL as private resources; Resolume
does not need a manual model-path selector, a server, a Python process or a
TensorRT engine file.

To reproduce the ignored build inputs on another Windows checkout, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\resolume\plugin\LUCIDA_DEPTH\tools\Fetch-DepthGenResources.ps1
```

## Controls

The controls are grouped as follows:

- `Model`: `ZipDepth` is the faster default; `Depth Anything V2 Small` is a
  second DepthGen model with a different quality/speed profile.
- `Quality`: `Fast`, `Balanced`, `High`, or `Custom`. `Custom` activates
  `Custom Short Edge` (256–2160 px); the other modes use DepthGen's fixed
  model-specific sizes.
- `Far/Near Percentile`: clips the low/high ends of the depth distribution
  before normalization. The useful default is 2% / 98%; narrower values give
  more local contrast but can discard scene range.
- `Contrast` and `Invert`: shape the normalized map after percentile mapping.
- `Temporal Stability`: 0–100%; stabilizes range and quantiles without
  spatially smearing the depth map. It resets safely when relevant controls
  change.
- `Reset Temporal`: trigger it after a deliberate camera/clip change when you
  want to discard the previous temporal history immediately. Automatic scene
  cut detection remains active as well.
- `Input Transfer`: choose `Assume sRGB` for normal video textures, or
  `Linear to sRGB` when the incoming texture is linear.
- `Use Alpha for Levels` and `Alpha Threshold`: exclude transparent/low-alpha
  pixels from percentile calculation. They do not remove alpha from output.
- `Output Alpha`: `Preserve Source Alpha` keeps the input alpha; `Opaque`
  forces the returned depth texture to alpha 1. This is visible with clips
  that actually contain transparency; an opaque source looks identical.
- `Effect Mix`: blends the depth result with the source, from 0 to 1.
- `Inference Rate`: calculates every frame, 2, 3, or 4 frames. The default is
  every 2 frames for live performance; use every frame for maximum temporal
  responsiveness.
- `Output Style` (CCTV VFX): keeps `Depth Map` as the technical default and
  adds `Thermal Depth`, `Silhouette`, `Depth Edges` and `CCTV Composite`. The
  extra controls are contextual: `Depth Bands` quantizes the map, while
  `Silhouette Threshold`, `Edge Gain`, `CCTV Scanlines` and `CCTV Noise` only
  appear for the styles that use them. These are GPU display passes over the
  same DepthGen result; they do not run a second model.
- `CCTV Aura`, `CCTV Rays` and `CCTV Aura + Rays` are the electric modes. Aura
  expands depth discontinuities into a controllable field; Rays emit a set of
  animated, depth-aware jagged arcs from `Ray Origin X/Y`. `Ray Angle` sets the
  main direction; `Ray Length`, `Ray Spread` and `Ray Density` control the arc
  layout; `Ray Branching` creates coherent secondary forks; and `Ray Flicker`
  animates a moving discharge front and pulse without rebuilding the depth map.
  The bolt is built from deterministic piecewise segments rather than a radial
  blur, so each branch has a stable jagged path while its energy travels along
  it. `Emission Depth` and
  `Depth Gate Width` restrict the effect to a depth band; `Depth Occlusion`
  suppresses energy behind nearer surfaces; `Normal Alignment` makes rays
  respond to the orientation of the depth surface. `Electric Color` and
  `Electric Color2` are RGB controls, so the electricity is not restricted to a
  fixed palette. These modes preserve the source image underneath the energy
  and can be followed by Smoke or Feedback in the Resolume chain.

### Electric-field design basis

The electric modes are an original 2.5D GPU adaptation for CCTV, not a copied
third-party effect. Their design combines coherent value noise/fBm for temporal
continuity, controlled secondary branches inspired by midpoint-displacement
lightning systems, and depth gradients for surface response/occlusion. The
reference points are the public [procedural lightning system in cel-lab](https://github.com/FoundryLogger/cel-lab),
the probabilistic binary-tree approach described in
[A probabilistic technique for the synthetic imagery of lightning](https://www.sciencedirect.com/science/article/abs/pii/S0097849399000382),
and the GPU gradient/occlusion techniques discussed in
[GPU Gems 3, procedural GPU terrain](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-1-generating-complex-procedural-terrains-using-gpu).
The implementation remains screen-space relative depth, so it preserves
foreground/background ordering without claiming calibrated metric 3D.

The default output is a visible grayscale depth map. Put the effect on a clip
or on a layer/effect chain receiving Layers Below. If inference fails, the
plugin logs the reason and keeps Resolume alive with the last valid depth
texture.

## Installation and first test

After building, keep these files together from
`work/resolume-plugin-build/Extra Effects/`:

- `LUCIDA_Depth.dll`
- `LUCIDA_Depth_README.md`
- `THIRD_PARTY_NOTICES.md`
- `model-manifest.json`

Copy the DLL and the three companion files to
`%USERPROFILE%\Documents\Resolume\Extra Effects`, or add the build
`Extra Effects` folder directly in Resolume Preferences → Video → FFGL
Directories. Restart Resolume and look for the exact effect name `LUCIDA
Depth`.

For the first test, use a moving clip or camera with visible people and
objects, apply `LUCIDA Depth` as an effect (or feed Layers Below), leave
`Effect Mix` at 1.0, and use `Quality = Fast`. The expected image is a moving
grayscale relative-depth map: near and far surfaces should not simply follow
brightness. Move `Invert`, `Near/Far Percentile`, `Temporal Stability` and
`Quality` to verify the controls. The runtime log is
`%TEMP%\LUCIDA_Depth_runtime.log`.

After opening Resolume, the live state can be inspected without changing the
composition:

```powershell
powershell -ExecutionPolicy Bypass -File .\resolume\plugin\LUCIDA_DEPTH\tools\Inspect-LUCIDA-DepthLive.ps1
```

## Performance path

The FFGL readback uses a three-buffer pixel-pack ring and OpenGL fences. A
completed transfer is consumed only when it is ready, so the render thread does
not wait for the GPU; the inference itself runs on one worker thread and keeps
the newest completed map. The depth upload uses a single R32F channel instead
of an RGBA float texture. `InferenceRate` defaults to every 2 frames; use Every
Frame when temporal responsiveness is more important than throughput. Runtime
diagnostics are limited to startup, errors and completed inference events so
the performance path does not write a file on every render call. Actual live
FPS still depends on composition resolution and must be measured in Resolume.

For a host-independent performance check, the Release build also produces
`LUCIDA_DEPTH_CORE_BENCH.exe`. Pass the source dimensions, for example:

```powershell
.\Release\LUCIDA_DEPTH_CORE_BENCH.exe 1920 1080
```

This measures warmed-up DepthGen processing separately from Resolume's texture
readback and host scheduling. On the development machine, 1920×1080 measured
about 18.7 FPS for ZipDepth Fast, 9.5 FPS for ZipDepth Balanced and 6.5 FPS
for Depth Anything V2 Small Fast; those are core measurements, not a claim
about live Resolume FPS.

`LUCIDA_DEPTH_SHADER_SMOKE.exe` can also render the electric modes at a chosen
size, for example `...ShaderSmoke.exe LUCIDA_Depth.cpp 1920 1080`. Its GPU
finish measurement is intentionally conservative because the smoke waits for
the GPU and reads the framebuffer back; it is a regression signal, not a live
FPS claim.
