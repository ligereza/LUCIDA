#pragma once

#include <FFGLSDK.h>

#include "INSTAR_SCENE.h"
#include "INSTAR_XML.h"

#include <string>

class INSTARCapture final : public ffglqs::Source
{
public:
	INSTARCapture();
	~INSTARCapture() override = default;

	const char* GetShortName() override
	{
		static const char* shortName = "INSTAR CAPTURE";
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
	bool ExportSceneXml();

	ffglex::FFGLShader sceneShader;
	GLuint vao = 0;
	GLuint vbo = 0;
	GLuint triangleVao = 0;
	GLuint triangleVbo = 0;
	INSTARScene scene;
	std::string modelPath;
	std::string loadedPath;
	std::string outputPath = "INSTAR_CAPTURE_AdvancedOutput.xml";
	float yaw = 0.5f;
	float pitch = 0.5f;
	float zoom = 0.55f;
	float brightness = 0.85f;
	bool sceneDirty = true;
	bool exportRequested = false;

	enum Parameter : unsigned int
	{
		PARAM_MODEL_FILE = 0,
		PARAM_EXPORT_XML = 1,
		PARAM_OUTPUT_XML = 2,
		PARAM_VIEW = 3,
		PARAM_YAW = 4,
		PARAM_PITCH = 5,
		PARAM_ZOOM = 6,
		PARAM_BRIGHTNESS = 7,
		PARAM_CANVAS_WIDTH = 8,
		PARAM_CANVAS_HEIGHT = 9,
	};
};
