#include "LUCIDA_DepthCore.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

namespace {

std::vector<unsigned char> MakeFrame(int width, int height, bool alternate) {
	std::vector<unsigned char> rgba(static_cast<size_t>(width) * static_cast<size_t>(height) * 4U);
	for (int y = 0; y < height; ++y) {
		for (int x = 0; x < width; ++x) {
			const float fx = static_cast<float>(x) / static_cast<float>(width - 1);
			const float fy = static_cast<float>(y) / static_cast<float>(height - 1);
			const bool object = alternate
				? ((x - width * 3 / 4) * (x - width * 3 / 4) + (y - height / 2) * (y - height / 2) < width * width / 25)
				: ((x - width / 3) * (x - width / 3) + (y - height / 2) * (y - height / 2) < width * width / 20);
			const size_t index = (static_cast<size_t>(y) * static_cast<size_t>(width) + static_cast<size_t>(x)) * 4U;
			rgba[index] = static_cast<unsigned char>(std::round((object ? 0.95f : fx) * 255.0f));
			rgba[index + 1U] = static_cast<unsigned char>(std::round((object ? 0.15f : fy) * 255.0f));
			rgba[index + 2U] = static_cast<unsigned char>(std::round((object ? 0.10f : (1.0f - fx)) * 255.0f));
			rgba[index + 3U] = 255U;
		}
	}
	return rgba;
}

bool CheckResult(const std::vector<float>& values, const std::string& label) {
	if (values.empty()) {
		std::cerr << label << ": empty output\n";
		return false;
	}
	const auto [min_it, max_it] = std::minmax_element(values.begin(), values.end());
	const bool finite = std::all_of(values.begin(), values.end(), [](float value) { return std::isfinite(value); });
	if (!finite || *max_it - *min_it <= 1.0e-4f) {
		std::cerr << label << ": invalid or flat output (min=" << *min_it << ", max=" << *max_it << ")\n";
		return false;
	}
	std::cout << label << ": range=" << *min_it << ".." << *max_it << "\n";
	return true;
}

bool CheckTemporalQuantiles() {
	std::vector<float> depth;
	std::vector<float> alpha;
	depth.reserve(257);
	alpha.reserve(257);
	for (int index = 0; index < 257; ++index) {
		// Deliberately non-monotonic values exercise both order statistics and
		// the interpolation between adjacent percentile samples.
		depth.push_back(static_cast<float>((index * 73) % 257) / 256.0f);
		alpha.push_back(index % 19 == 0 ? 0.0f : 1.0f);
	}
	float actual[depthgen::kTemporalQuantileCount] = {};
	if (!depthgen::MeasureUnitQuantiles(depth, alpha, 0.5f, actual)) {
		std::cerr << "temporal quantile measurement failed\n";
		return false;
	}
	std::vector<float> sorted;
	for (size_t index = 0; index < depth.size(); ++index) {
		if (alpha[index] > 0.5f) sorted.push_back(depth[index]);
	}
	std::sort(sorted.begin(), sorted.end());
	for (int quantile = 0; quantile < depthgen::kTemporalQuantileCount; ++quantile) {
		const double position = static_cast<double>(depthgen::kTemporalPercentiles[quantile]) /
			100.0 * static_cast<double>(sorted.size() - 1);
		const size_t lower = static_cast<size_t>(std::floor(position));
		const size_t upper = std::min(lower + 1, sorted.size() - 1);
		const float expected = sorted[lower] +
			(sorted[upper] - sorted[lower]) * static_cast<float>(position - lower);
		if (std::abs(actual[quantile] - expected) > 1.0e-6f) {
			std::cerr << "temporal quantile mismatch at " << quantile << "\n";
			return false;
		}
	}
	return true;
}

} // namespace

int main() {
	if (!CheckTemporalQuantiles()) return 5;
	constexpr int width = 64;
	constexpr int height = 48;
	const auto first = MakeFrame(width, height, false);
	const auto second = MakeFrame(width, height, true);
	depthgen::TemporalHistory history;
	lucida_depth::Settings settings;
	settings.quality = lucida_depth::QualityCustom;
	settings.custom_short_edge = 256;
	settings.temporal_stability = 50.0f;
	settings.preserve_alpha = true;
	for (const int model : {lucida_depth::ModelZipDepth, lucida_depth::ModelDepthAnythingV2Small}) {
		settings.model = model;
		std::vector<float> depth;
		std::vector<float> alpha;
		depthgen::InferenceProvider provider = depthgen::InferenceProvider::Unavailable;
		std::string error;
		if (!lucida_depth::ProcessFrame(first, width, height, settings, &history, 1, 1,
			&depth, &alpha, &provider, &error)) {
			std::cerr << "first frame failed for model " << model << ": " << error << "\n";
			return 1;
		}
		std::cout << "model " << model << " provider=" << depthgen::InferenceProviderName(provider) << "\n";
		if (!CheckResult(depth, "model " + std::to_string(model) + " first") ||
			alpha.size() != depth.size()) return 2;
		std::vector<float> second_depth;
		std::vector<float> second_alpha;
		if (!lucida_depth::ProcessFrame(second, width, height, settings, &history, 2, 1,
			&second_depth, &second_alpha, &provider, &error)) {
			std::cerr << "second frame failed for model " << model << ": " << error << "\n";
			return 3;
		}
		if (!CheckResult(second_depth, "model " + std::to_string(model) + " second")) return 4;
	}
	std::cout << "provider path exercised successfully\n";
	return 0;
}
