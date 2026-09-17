#pragma once

#include <cstddef>

struct DEPTHFX_CUDA;

extern "C"
{
DEPTHFX_CUDA* DEPTHFX_CUDA_Create();
void DEPTHFX_CUDA_Destroy(DEPTHFX_CUDA* bridge);
bool DEPTHFX_CUDA_LoadEngine(
	DEPTHFX_CUDA* bridge,
	const char* enginePath,
	char* errorMessage,
	size_t errorMessageSize
);
bool DEPTHFX_CUDA_Process(
	DEPTHFX_CUDA* bridge,
	unsigned int inputTexture,
	int inputWidth,
	int inputHeight,
	unsigned int outputTexture,
	int outputWidth,
	int outputHeight,
	char* errorMessage,
	size_t errorMessageSize
);
bool DEPTHFX_CUDA_ProcessHost(
	DEPTHFX_CUDA* bridge,
	const unsigned char* rgbaPixels,
	int inputWidth,
	int inputHeight,
	int outputWidth,
	int outputHeight,
	float* outputPixels,
	size_t outputPixelCount,
	char* errorMessage,
	size_t errorMessageSize
);
}
