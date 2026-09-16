#pragma once

#include <FFGLSDK.h>

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
	bool ExportMapXml();

	INSTARSceneRenderer renderer;
	INSTARScene scene;
	std::string venuePath;
	std::string loadedPath;
	std::string mapPath;
	std::string outputPath = "INSTAR_AdvancedOutput.xml";
	float yaw = 0.5f;
	float pitch = 0.5f;
	float zoom = 0.55f;
	float brightness = 0.85f;
	bool sceneDirty = true;
	bool exportRequested = false;
	unsigned int lastWidth = 1920;
	unsigned int lastHeight = 1080;

	enum Parameter : unsigned int
	{
		PARAM_VENUE_FILE = 0,
		PARAM_MAP_FILE = 1,
		PARAM_EXPORT_MAP_XML = 2,
		PARAM_OUTPUT_XML = 3,
		PARAM_VIEW = 4,
		PARAM_YAW = 5,
		PARAM_PITCH = 6,
		PARAM_ZOOM = 7,
		PARAM_BRIGHTNESS = 8,
		PARAM_CANVAS_WIDTH = 9,
		PARAM_CANVAS_HEIGHT = 10,
	};
};
