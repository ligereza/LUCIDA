#include "LUCIDA_DepthParamMapping.h"

#include <iostream>

int main() {
	using namespace lucida_depth_ffgl;
	if (ModelFromOption(0.0f) != lucida_depth::ModelZipDepth ||
		ModelFromOption(1.0f) != lucida_depth::ModelDepthAnythingV2Small ||
		QualityFromOption(0.0f) != lucida_depth::QualityFast ||
		QualityFromOption(1.0f) != lucida_depth::QualityBalanced ||
		QualityFromOption(2.0f) != lucida_depth::QualityHigh ||
		QualityFromOption(3.0f) != lucida_depth::QualityCustom ||
		!LinearTransferFromOption(1.0f) || LinearTransferFromOption(0.0f) ||
		!PreserveAlphaFromOption(0.0f) || PreserveAlphaFromOption(1.0f) ||
		InferenceRateFromOption(0.0f) != 1 || InferenceRateFromOption(1.0f) != 2 ||
		InferenceRateFromOption(2.0f) != 3 || InferenceRateFromOption(3.0f) != 4 ||
		OptionIndex(-1.0f, 4) != 0 || OptionIndex(99.0f, 4) != 3) {
		std::cerr << "FFGL parameter index mapping contract failed\n";
		return 1;
	}
	std::cout << "FFGL parameter index mapping contract passed\n";
	return 0;
}
