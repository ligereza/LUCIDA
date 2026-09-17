#pragma once

#include "DepthGen_Image.h"

#include <cmath>
#include <cstdint>
#include <memory>
#include <mutex>
#include <vector>

namespace depthgen {

inline constexpr int kTemporalQuantileCount = 7;
inline constexpr float kTemporalPercentiles[kTemporalQuantileCount] = {
	5.0f, 15.0f, 25.0f, 50.0f, 75.0f, 85.0f, 95.0f};

struct TemporalLayout {
	int width = 0;
	int height = 0;
	int model = 0;
	int short_edge = 0;
	float far_percentile = 0.0f;
	float near_percentile = 100.0f;
	float contrast = 1.0f;
	float alpha_threshold = 0.0f;
	float temporal_stability = 0.0f;
	bool invert = false;
	bool linear_to_srgb = false;
	bool use_alpha_for_levels = true;

	static bool NearlyEqual(float left, float right) noexcept {
		return std::abs(left - right) <= 1.0e-5f;
	}

	bool operator==(const TemporalLayout& other) const noexcept {
		return width == other.width && height == other.height &&
			model == other.model && short_edge == other.short_edge &&
			NearlyEqual(far_percentile, other.far_percentile) &&
			NearlyEqual(near_percentile, other.near_percentile) &&
			NearlyEqual(contrast, other.contrast) &&
			NearlyEqual(alpha_threshold, other.alpha_threshold) &&
			NearlyEqual(temporal_stability, other.temporal_stability) &&
			invert == other.invert && linear_to_srgb == other.linear_to_srgb &&
			use_alpha_for_levels == other.use_alpha_for_levels;
	}
	bool operator!=(const TemporalLayout& other) const noexcept {
		return !(*this == other);
	}
};

struct TemporalRange {
	DepthLevels mapping;
	float quantiles[kTemporalQuantileCount] = {};
	bool valid = false;
};

// Mix Far/Near mapping endpoints toward the previous frame. No spatial blend.
DepthLevels SmoothMappingRange(const DepthLevels& current, const DepthLevels& previous,
	float stability01);

bool MeasureUnitQuantiles(
	const std::vector<float>& depth,
	const std::vector<float>& alpha,
	float alpha_threshold,
	float* quantiles);

// Piecewise-linear histogram match so current quantiles (including the median)
// approach the previous frame. Spatial structure is preserved; pixels are not mixed.
void AlignUnitQuantiles(
	std::vector<float>* current,
	const std::vector<float>& alpha,
	float alpha_threshold,
	const float* previous_quantiles,
	float stability01);

TemporalRange MeasureUnitRange(
	const std::vector<float>& depth,
	const std::vector<float>& alpha,
	float alpha_threshold,
	const DepthLevels& mapping);

// Thread-safe LRU of range statistics keyed by composition time.
class TemporalHistory {
public:
	static constexpr size_t kMaxFrames = 24;

	bool CopyPrevious(std::int32_t time, std::int32_t time_step, const TemporalLayout& layout,
		TemporalRange* previous) const;
	void Store(std::int32_t time, const TemporalLayout& layout, TemporalRange range);
	void Clear();

private:
	struct Entry {
		std::int32_t time = 0;
		TemporalLayout layout;
		TemporalRange range;
	};

	mutable std::mutex mutex_;
	std::vector<Entry> entries_;
};

std::uint64_t TemporalCacheCreate();
std::shared_ptr<TemporalHistory> TemporalCacheGet(std::uint64_t id);
void TemporalCacheRelease(std::uint64_t id);

} // namespace depthgen
