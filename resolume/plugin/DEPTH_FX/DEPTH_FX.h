#pragma once

#include <FFGLSDK.h>
#include <ffglquickstart/FFGLEffect.h>
#include <ffglex/FFGLShader.h>

#include "../INSTAR/INSTAR_IMAGE.h"

#include <string>

class DEPTHFX final : public ffglqs::Effect
{
public:
	DEPTHFX();
	~DEPTHFX() override = default;

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
	struct DepthSequence
	{
		std::string manifestPath;
		std::string framesDirectory;
		std::string prefix = "depth_";
		std::string extension = ".png";
		int frameCount = 0;
		int startIndex = 0;
		int zeroPad = 6;
		float fps = 30.0f;
	};

	bool LoadManifest();
	bool LoadDepthFrame(int frameIndex);
	void UploadDepthFrame();
	std::string FramePath(int frameIndex) const;
	void Log(const std::string& message) const;

	static constexpr unsigned int PARAM_DEPTH_MANIFEST = 0;
	static constexpr unsigned int PARAM_DEPTH_AMOUNT = 1;
	static constexpr unsigned int PARAM_DEPTH_VERTICAL = 2;
	static constexpr unsigned int PARAM_DEPTH_BIAS = 3;
	static constexpr unsigned int PARAM_DEPTH_CONTRAST = 4;
	static constexpr unsigned int PARAM_DEPTH_INVERT = 5;
	static constexpr unsigned int PARAM_DEPTH_SMOOTH = 6;
	static constexpr unsigned int PARAM_EFFECT_MIX = 7;

	std::string manifestPath;
	DepthSequence sequence;
	INSTARImage depthImage;
	GLuint depthTexture = 0;
	int loadedFrame = -1;
	int uploadedWidth = 0;
	int uploadedHeight = 0;
	bool manifestDirty = true;
	bool depthReady = false;
	bool loggedMissingManifest = false;
};
