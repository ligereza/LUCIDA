#pragma once

#include "LUCIDA_DepthCore.h"

#include <algorithm>
#include <cmath>

namespace lucida_depth_ffgl {

inline int OptionIndex(float value, int option_count) noexcept {
	if (option_count <= 0) return 0;
	const int index = static_cast<int>(std::lround(value));
	return std::max(0, std::min(option_count - 1, index));
}

inline int ModelFromOption(float value) noexcept {
	return OptionIndex(value, 2) == 1
		? lucida_depth::ModelDepthAnythingV2Small : lucida_depth::ModelZipDepth;
}

inline int QualityFromOption(float value) noexcept {
	return OptionIndex(value, 4) + 1;
}

inline bool LinearTransferFromOption(float value) noexcept {
	return OptionIndex(value, 2) == 1;
}

inline bool PreserveAlphaFromOption(float value) noexcept {
	return OptionIndex(value, 2) == 0;
}

inline int InferenceRateFromOption(float value) noexcept {
	return OptionIndex(value, 4) + 1;
}

} // namespace lucida_depth_ffgl
