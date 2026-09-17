#pragma once

#include "depthgen/DepthGen_Inference.h"
#include "depthgen/DepthGen_Temporal.h"

#include <cstdint>
#include <string>
#include <vector>

namespace lucida_depth {

enum Model : int {
	ModelZipDepth = 1,
	ModelDepthAnythingV2Small = 2,
};

enum Quality : int {
	QualityFast = 1,
	QualityBalanced = 2,
	QualityHigh = 3,
	QualityCustom = 4,
};

enum InputTransfer : int {
	TransferSrgb = 1,
	TransferLinearToSrgb = 2,
};

enum OutputAlpha : int {
	PreserveAlpha = 1,
	OpaqueAlpha = 2,
};

struct Settings {
	int model = ModelZipDepth;
	int quality = QualityBalanced;
	int custom_short_edge = 768;
	float far_percentile = 2.0f;
	float near_percentile = 98.0f;
	float contrast = 1.0f;
	float alpha_threshold = 0.0f;
	float temporal_stability = 0.0f;
	bool invert = false;
	bool linear_to_srgb = false;
	bool use_alpha_for_levels = true;
	bool preserve_alpha = true;
};

int ShortEdge(const Settings& settings) noexcept;

// Converts one premultiplied RGBA8 FFGL texture readback into the exact
// DepthGen image/inference/temporal pipeline. The output is a full-resolution
// unit depth map and the source alpha, both owned by the caller.
bool ProcessFrame(
	const std::vector<unsigned char>& rgba,
	int source_width,
	int source_height,
	const Settings& settings,
	depthgen::TemporalHistory* history,
	std::int32_t time,
	std::int32_t time_step,
	std::vector<float>* depth,
	std::vector<float>* alpha,
	depthgen::InferenceProvider* provider,
	std::string* error);

} // namespace lucida_depth
