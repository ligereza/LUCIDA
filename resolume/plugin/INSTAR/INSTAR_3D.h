#pragma once

#include <FFGLSDK.h>

#include "INSTAR_IMAGE.h"
#include "INSTAR_RENDERER.h"

#include <string>

class INSTAR3D final : public ffglqs::Source
{
public:
	INSTAR3D();
	~INSTAR3D() override = default;

	const char* GetShortName() override
	{
		static const char* shortName = "INSTAR 3D";
		return shortName;
	}

	FFResult SetFloatParameter(unsigned int index, float value) override;
	FFResult SetTextParameter(unsigned int index, const char* value) override;
	char* GetTextParameter(unsigned int index) override;
	FFResult Render(ProcessOpenGLStruct* inputTextures) override;

protected:
	FFResult Init() override;
	void Update() override;
	void Clean() override;

	private:
	bool LoadScene();
	void UploadScene();
	bool LoadTexture();

	INSTARSceneRenderer renderer;
	GLuint textureId = 0;
	INSTARScene scene;
	INSTARImage textureImage;
	std::string modelPath;
	std::string loadedPath;
	std::string texturePath;
	std::string loadedTexturePath;
	float yaw = 0.5f;
	float pitch = 0.5f;
	float zoom = 0.55f;
	float brightness = 0.85f;
	bool sceneDirty = true;
	bool textureDirty = true;
	bool textureReady = false;

	enum Parameter : unsigned int
	{
		PARAM_MODEL_FILE = 0,
		PARAM_TEXTURE_FILE = 1,
		PARAM_VIEW = 2,
		PARAM_YAW = 3,
		PARAM_PITCH = 4,
		PARAM_ZOOM = 5,
		PARAM_BRIGHTNESS = 6,
	};
};
