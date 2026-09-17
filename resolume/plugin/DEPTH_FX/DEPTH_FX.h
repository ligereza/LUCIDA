#pragma once

#include <FFGLSDK.h>
#include <ffglquickstart/FFGLEffect.h>
#include <ffglex/FFGLShader.h>

#include <string>
#include <vector>

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

class DEPTHFX final : public ffglqs::Effect
{
public:
	DEPTHFX();
	~DEPTHFX() override;

	const char* GetShortName() override
	{
		static const char* shortName = "DEPTH_FX";
		return shortName;
	}

	FFResult SetTextParameter(unsigned int index, const char* value) override;
	char* GetTextParameter(unsigned int index) override;

protected:
	FFResult Init() override;
	void Update() override;
	void Clean() override;
	FFResult Render(ProcessOpenGLStruct* inputTextures) override;

private:
	static std::string DecodeFileUri(const char* value);
	void Log(const std::string& message) const;
	void EnsureDepthTexture(int width, int height);
	void ReleaseDepthTexture();
	bool ProcessHostReadback(const FFGLTextureStruct& input, std::string& errorMessage);
	void UploadDepthPixels();
	void MarkCudaFailure(const std::string& message);

	static constexpr unsigned int PARAM_ENGINE_FILE = 0;
	static constexpr unsigned int PARAM_DEPTH_CONTRAST = 1;
	static constexpr unsigned int PARAM_DEPTH_INVERT = 2;
	static constexpr unsigned int PARAM_DEPTH_SMOOTH = 3;

	std::string enginePath;
	DEPTHFX_CUDA* cudaBridge = nullptr;
	GLuint depthTexture = 0;
	int depthWidth = 0;
	int depthHeight = 0;
	bool engineDirty = true;
	bool cudaFailureLogged = false;
	std::vector<unsigned char> readbackPixels;
	std::vector<float> hostDepthPixels;
};
