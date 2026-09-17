#include "LUCIDA_DepthCore.h"

#include "depthgen/DepthGen_Image.h"

#include <algorithm>
#include <cmath>
#include <limits>

namespace lucida_depth {
namespace {

constexpr float kAlphaEpsilon = 1.0e-6f;

float Clamp01(float value) noexcept {
	return std::max(0.0f, std::min(1.0f, value));
}

int ModelPatch(int model) noexcept {
	return model == ModelDepthAnythingV2Small ? depthgen::kDav2Patch : depthgen::kZipDepthPatch;
}

int ClampQuality(int quality) noexcept {
	return std::max(static_cast<int>(QualityFast), std::min(static_cast<int>(QualityCustom), quality));
}

std::vector<float> ReadAlpha(const std::vector<unsigned char>& rgba, int width, int height) {
	std::vector<float> alpha(static_cast<size_t>(width) * static_cast<size_t>(height));
	for (size_t index = 0; index < alpha.size(); ++index) {
		alpha[index] = rgba[index * 4U + 3U] * depthgen::kByteToUnit;
	}
	return alpha;
}

std::vector<float> ReadInferenceTensor(
	const std::vector<unsigned char>& rgba,
	int source_width,
	int source_height,
	int inference_width,
	int inference_height,
	bool linear_to_srgb) {
	const size_t plane = static_cast<size_t>(inference_width) * static_cast<size_t>(inference_height);
	std::vector<float> tensor(plane * 3U);
	struct ResampleCoordinate {
		int low = 0;
		int high = 0;
		float fraction = 0.0f;
	};
	std::vector<ResampleCoordinate> x_coordinates(static_cast<size_t>(inference_width));
	std::vector<ResampleCoordinate> y_coordinates(static_cast<size_t>(inference_height));
	for (int x = 0; x < inference_width; ++x) {
		const float source_x = inference_width > 1
			? static_cast<float>(x) * static_cast<float>(source_width - 1) /
				static_cast<float>(inference_width - 1)
			: 0.0f;
		const int x0 = static_cast<int>(std::floor(source_x));
		x_coordinates[static_cast<size_t>(x)] = {
			x0, std::min(x0 + 1, source_width - 1), source_x - static_cast<float>(x0)};
	}
	for (int y = 0; y < inference_height; ++y) {
		const float source_y = inference_height > 1
			? static_cast<float>(y) * static_cast<float>(source_height - 1) /
				static_cast<float>(inference_height - 1)
			: 0.0f;
		const int y0 = static_cast<int>(std::floor(source_y));
		y_coordinates[static_cast<size_t>(y)] = {
			y0, std::min(y0 + 1, source_height - 1), source_y - static_cast<float>(y0)};
	}
	for (int y = 0; y < inference_height; ++y) {
		const ResampleCoordinate& y_coordinate = y_coordinates[static_cast<size_t>(y)];
		const float fy = y_coordinate.fraction;
		const float top_weight = 1.0f - fy;
		const float bottom_weight = fy;
		for (int x = 0; x < inference_width; ++x) {
			const ResampleCoordinate& x_coordinate = x_coordinates[static_cast<size_t>(x)];
			const float fx = x_coordinate.fraction;
			const float left_weight = 1.0f - fx;
			const float right_weight = fx;
			const float weights[4] = {
				left_weight * top_weight, right_weight * top_weight,
				left_weight * bottom_weight, right_weight * bottom_weight};
			const int xs[4] = {x_coordinate.low, x_coordinate.high,
				x_coordinate.low, x_coordinate.high};
			const int ys[4] = {y_coordinate.low, y_coordinate.low,
				y_coordinate.high, y_coordinate.high};
			float red = 0.0f;
			float green = 0.0f;
			float blue = 0.0f;
			float alpha = 0.0f;
			for (int tap = 0; tap < 4; ++tap) {
				const size_t pixel = (static_cast<size_t>(ys[tap]) * static_cast<size_t>(source_width) +
					static_cast<size_t>(xs[tap])) * 4U;
				const float weight = weights[tap];
				red += rgba[pixel] * depthgen::kByteToUnit * weight;
				green += rgba[pixel + 1U] * depthgen::kByteToUnit * weight;
				blue += rgba[pixel + 2U] * depthgen::kByteToUnit * weight;
				alpha += rgba[pixel + 3U] * depthgen::kByteToUnit * weight;
			}
			float colour[3] = {0.0f, 0.0f, 0.0f};
			if (alpha > kAlphaEpsilon) {
				colour[0] = Clamp01(red / alpha);
				colour[1] = Clamp01(green / alpha);
				colour[2] = Clamp01(blue / alpha);
				if (linear_to_srgb) {
					colour[0] = depthgen::LinearToSrgb(colour[0]);
					colour[1] = depthgen::LinearToSrgb(colour[1]);
					colour[2] = depthgen::LinearToSrgb(colour[2]);
				}
			}
			const size_t index = static_cast<size_t>(y) * static_cast<size_t>(inference_width) +
				static_cast<size_t>(x);
			for (size_t channel = 0; channel < 3U; ++channel) {
				tensor[channel * plane + index] = colour[channel];
			}
		}
	}
	return tensor;
}

} // namespace

int ShortEdge(const Settings& settings) noexcept {
	if (settings.quality == QualityCustom) {
		return std::max(256, std::min(2160, settings.custom_short_edge));
	}
	if (settings.model == ModelDepthAnythingV2Small) {
		if (settings.quality == QualityFast) return 384;
		if (settings.quality == QualityHigh) return 736;
		return 518;
	}
	if (settings.quality == QualityFast) return 512;
	if (settings.quality == QualityHigh) return 1080;
	return 768;
}

bool ProcessFrame(
	const std::vector<unsigned char>& rgba,
	int source_width,
	int source_height,
	const Settings& input_settings,
	depthgen::TemporalHistory* history,
	std::int32_t time,
	std::int32_t time_step,
	std::vector<float>* depth,
	std::vector<float>* alpha,
	depthgen::InferenceProvider* provider,
	std::string* error) {
	try {
		if (!depth || !alpha || source_width <= 0 || source_height <= 0 ||
			rgba.size() != static_cast<size_t>(source_width) * static_cast<size_t>(source_height) * 4U) {
			if (error) *error = "DepthGen received an invalid FFGL frame.";
			return false;
		}
		Settings settings = input_settings;
		settings.model = settings.model == ModelDepthAnythingV2Small
			? ModelDepthAnythingV2Small : ModelZipDepth;
		settings.quality = ClampQuality(settings.quality);
		settings.far_percentile = Clamp01(settings.far_percentile / 100.0f) * 100.0f;
		settings.near_percentile = Clamp01(settings.near_percentile / 100.0f) * 100.0f;
		if (settings.near_percentile <= settings.far_percentile) {
			settings.far_percentile = std::min(settings.far_percentile, 99.0f);
			settings.near_percentile = std::max(settings.far_percentile + 0.1f, 100.0f);
			settings.near_percentile = std::min(settings.near_percentile, 100.0f);
		}
		settings.contrast = std::max(0.01f, std::min(4.0f, settings.contrast));
		settings.alpha_threshold = Clamp01(settings.alpha_threshold);
		settings.temporal_stability = std::max(0.0f, std::min(100.0f, settings.temporal_stability));

		const int patch = ModelPatch(settings.model);
		int inference_width = 0;
		int inference_height = 0;
		depthgen::ComputeInferenceSize(source_width, source_height, ShortEdge(settings),
			&inference_width, &inference_height, patch);
		if (inference_width <= 0 || inference_height <= 0) {
			if (error) *error = "DepthGen could not compute a valid inference size.";
			return false;
		}
		*alpha = ReadAlpha(rgba, source_width, source_height);
		std::vector<float> tensor = ReadInferenceTensor(rgba, source_width, source_height,
			inference_width, inference_height, settings.linear_to_srgb);
		if (settings.model == ModelDepthAnythingV2Small) {
			depthgen::ApplyImageNetToPlanarRgb(&tensor, inference_width, inference_height);
		}
		depthgen::InferenceResult result;
		depthgen::InferenceProvider local_provider = depthgen::InferenceProvider::Unavailable;
		std::string inference_error;
		const depthgen::DepthModel model = settings.model == ModelDepthAnythingV2Small
			? depthgen::DepthModel::DepthAnythingV2Small : depthgen::DepthModel::ZipDepth;
		if (!depthgen::InferDepth(tensor, inference_width, inference_height, model, &result,
			&local_provider, &inference_error)) {
			if (provider) *provider = local_provider;
			if (error) *error = inference_error;
			return false;
		}
		if (provider) *provider = local_provider;
		depthgen::FloatImage raw_depth;
		raw_depth.width = result.width;
		raw_depth.height = result.height;
		raw_depth.values = std::move(result.depth);
		depthgen::FloatImage full_depth = depthgen::ResizeBilinearAligned(raw_depth,
			source_width, source_height);
		for (float& value : full_depth.values) {
			if (!std::isfinite(value)) value = 0.0f;
		}
		depthgen::DepthLevels levels = depthgen::ComputeDepthLevels(full_depth.values, *alpha,
			settings.alpha_threshold, settings.use_alpha_for_levels, settings.far_percentile,
			settings.near_percentile);
		depthgen::TemporalRange previous;
		const depthgen::TemporalLayout layout{
			source_width,
			source_height,
			settings.model,
			ShortEdge(settings),
			settings.far_percentile,
			settings.near_percentile,
			settings.contrast,
			settings.alpha_threshold,
			settings.temporal_stability,
			settings.invert,
			settings.linear_to_srgb,
			settings.use_alpha_for_levels};
		const bool have_previous = history && settings.temporal_stability > 0.0f &&
			history->CopyPrevious(time, time_step, layout, &previous);
		if (have_previous) {
			levels = depthgen::SmoothMappingRange(levels, previous.mapping,
				settings.temporal_stability / 100.0f);
		}
		depthgen::ApplyDepthLevels(&full_depth.values, levels, settings.contrast, settings.invert);
		if (have_previous) {
			depthgen::AlignUnitQuantiles(&full_depth.values, *alpha, settings.alpha_threshold,
				previous.quantiles, settings.temporal_stability / 100.0f);
		}
		if (history) {
			history->Store(time, layout,
				depthgen::MeasureUnitRange(full_depth.values, *alpha, settings.alpha_threshold, levels));
		}
		*depth = std::move(full_depth.values);
		return depth->size() == static_cast<size_t>(source_width) * static_cast<size_t>(source_height);
	} catch (const std::exception& exception) {
		if (error) *error = std::string("DepthGen frame processing failed: ") + exception.what();
	} catch (...) {
		if (error) *error = "DepthGen frame processing failed with an unknown exception.";
	}
	return false;
}

} // namespace lucida_depth
