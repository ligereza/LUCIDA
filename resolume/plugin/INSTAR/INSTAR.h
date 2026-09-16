#pragma once

#include <FFGLSDK.h>
#include <ffglex/FFGLScreenQuad.h>

#include "INSTAR_IMAGE.h"
#include "INSTAR_RENDERER.h"
#include "INSTAR_XML.h"

#include <string>

class INSTAR final : public ffglqs::Source
{
public:
	INSTAR();
	~INSTAR() override = default;

	const char* GetShortName() override
	{
		static const char* shortName = "INSTAR";
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
	bool LoadVenue();
	void UploadScene();
	bool LoadRaster();
	FFResult RenderRaster();
	bool ExportMapXml();

	INSTARSceneRenderer renderer;
	ffglex::FFGLShader rasterShader;
	ffglex::FFGLScreenQuad rasterQuad;
	GLuint rasterTexture = 0;
	INSTARScene scene;
	INSTARImage rasterImage;
	std::string venuePath;
	std::string loadedPath;
	std::string mapPath;
	std::string outputPath = "INSTAR_AdvancedOutput.xml";
	float yaw = 0.5f;
	float pitch = 0.5f;
	float zoom = 0.55f;
	float brightness = 0.85f;
	bool sceneDirty = true;
	bool rasterDirty = true;
	bool rasterReady = false;
	bool exportRequested = false;
	unsigned int lastWidth = 1920;
	unsigned int lastHeight = 1080;

	enum Parameter : unsigned int
	{
		PARAM_MODE = 0,
		PARAM_VENUE_FILE = 1,
		PARAM_MAP_FILE = 2,
		PARAM_EXPORT_MAP_XML = 3,
		PARAM_OUTPUT_XML = 4,
		PARAM_VIEW = 5,
		PARAM_YAW = 6,
		PARAM_PITCH = 7,
		PARAM_ZOOM = 8,
		PARAM_BRIGHTNESS = 9,
		PARAM_CANVAS_WIDTH = 10,
		PARAM_CANVAS_HEIGHT = 11,
	};
};
