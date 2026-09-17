#include "LUCIDA_DepthCore.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace {

std::vector<unsigned char> MakeFrame(int width, int height, int phase) {
	std::vector<unsigned char> rgba(static_cast<size_t>(width) * static_cast<size_t>(height) * 4U);
	for (int y = 0; y < height; ++y) {
		for (int x = 0; x < width; ++x) {
			const float fx = static_cast<float>(x) / static_cast<float>(std::max(width - 1, 1));
			const float fy = static_cast<float>(y) / static_cast<float>(std::max(height - 1, 1));
			const float wave = 0.5f + 0.5f * std::sin((fx * 9.0f + fy * 5.0f + phase) * 3.14159265f);
			const size_t index = (static_cast<size_t>(y) * static_cast<size_t>(width) +
				static_cast<size_t>(x)) * 4U;
			rgba[index] = static_cast<unsigned char>(std::round((0.15f + 0.75f * fx) * 255.0f));
			rgba[index + 1U] = static_cast<unsigned char>(std::round((0.10f + 0.80f * fy) * 255.0f));
			rgba[index + 2U] = static_cast<unsigned char>(std::round((0.05f + 0.90f * wave) * 255.0f));
			rgba[index + 3U] = 255U;
		}
	}
	return rgba;
}

bool RunCase(const std::string& name, int model, int quality, int custom_edge,
	const std::vector<unsigned char>& first, const std::vector<unsigned char>& second,
	int width, int height) {
	lucida_depth::Settings settings;
	settings.model = model;
	settings.quality = quality;
	settings.custom_short_edge = custom_edge;
	settings.temporal_stability = 0.0f;
	depthgen::TemporalHistory history;
	std::vector<float> depth;
	std::vector<float> alpha;
	depthgen::InferenceProvider provider = depthgen::InferenceProvider::Unavailable;
	std::string error;
	if (!lucida_depth::ProcessFrame(first, width, height, settings, &history, 1, 1,
		&depth, &alpha, &provider, &error)) {
		std::cerr << name << " warmup failed: " << error << "\n";
		return false;
	}
	constexpr int kMeasuredFrames = 3;
	double total_ms = 0.0;
	double minimum_ms = 1.0e30;
	for (int frame = 0; frame < kMeasuredFrames; ++frame) {
		const auto& source = frame % 2 == 0 ? second : first;
		const auto started = std::chrono::steady_clock::now();
		if (!lucida_depth::ProcessFrame(source, width, height, settings, &history,
			2 + frame, 1, &depth, &alpha, &provider, &error)) {
			std::cerr << name << " frame failed: " << error << "\n";
			return false;
		}
		const double elapsed = std::chrono::duration<double, std::milli>(
			std::chrono::steady_clock::now() - started).count();
		total_ms += elapsed;
		minimum_ms = std::min(minimum_ms, elapsed);
	}
	std::cout << name << " provider=" << depthgen::InferenceProviderName(provider)
		<< " short_edge=" << lucida_depth::ShortEdge(settings)
		<< " avg_ms=" << total_ms / kMeasuredFrames
		<< " min_ms=" << minimum_ms
		<< " approx_fps=" << 1000.0 / (total_ms / kMeasuredFrames) << "\n";
	return true;
}

} // namespace

int main(int argc, char** argv) {
	int width = 1280;
	int height = 720;
	if (argc >= 3) {
		width = std::max(64, std::atoi(argv[1]));
		height = std::max(64, std::atoi(argv[2]));
	}
	const auto first = MakeFrame(width, height, 0);
	const auto second = MakeFrame(width, height, 1);
	bool success = true;
	success = RunCase("ZipDepth Fast", lucida_depth::ModelZipDepth,
		lucida_depth::QualityFast, 512, first, second, width, height) && success;
	success = RunCase("ZipDepth Balanced", lucida_depth::ModelZipDepth,
		lucida_depth::QualityBalanced, 768, first, second, width, height) && success;
	success = RunCase("Depth Anything V2 Small Fast", lucida_depth::ModelDepthAnythingV2Small,
		lucida_depth::QualityFast, 384, first, second, width, height) && success;
	return success ? 0 : 1;
}
