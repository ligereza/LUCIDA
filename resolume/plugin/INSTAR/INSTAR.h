#pragma once

#include <FFGLSDK.h>
#include <ffglex/FFGLScreenQuad.h>

#include "INSTAR_IMAGE.h"
#include "INSTAR_RENDERER.h"
#include "INSTAR_XML.h"

#include <string>
#include <vector>

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
	INSTARTarimaConfig GetTarimaConfig();
	void UploadScene();
	bool LoadRaster();
	void BuildRasterOverlay();
	FFResult RenderRaster();
	bool ExportMapXml();

	INSTARSceneRenderer renderer;
	ffglex::FFGLShader rasterShader;
	ffglex::FFGLShader rasterOverlayShader;
	ffglex::FFGLScreenQuad rasterQuad;
	GLuint rasterTexture = 0;
	GLuint rasterOverlayVao = 0;
	GLuint rasterOverlayVbo = 0;
	INSTARScene scene;
	INSTARImage rasterImage;
	std::vector<INSTARSurface> rasterSurfaces;
	std::vector<INSTARVertex> rasterOverlayVertices;
	std::string venuePath;
	std::string loadedPath;
	std::string mapPath;
	std::string templatePath;
	std::string outputPath = "INSTAR_AdvancedOutput.xml";
	float yaw = 0.5f;
	float pitch = 0.5f;
	float zoom = 0.55f;
	float cameraDistance = 3.5f;
	float brightness = 0.85f;
	float sliceDepths[32] = {};
	bool sceneDirty = true;
	bool rasterDirty = true;
	bool rasterReady = false;
	bool exportRequested = false;

	enum Parameter : unsigned int
	{
		PARAM_MODE = 0,
		PARAM_VENUE_FILE = 1,
		PARAM_EDGE_BUDGET = 2,
		PARAM_CONFIDENCE_CEILING = 3,
		PARAM_MAP_FILE = 4,
		PARAM_TEMPLATE_XML = 5,
		PARAM_EXPORT_MAP_XML = 6,
		PARAM_OUTPUT_XML = 7,
		PARAM_VIEW = 8,
		PARAM_YAW = 9,
		PARAM_PITCH = 10,
		PARAM_ZOOM = 11,
		PARAM_BRIGHTNESS = 12,
		PARAM_SLICE_DEPTH_01 = 13,
		PARAM_SLICE_DEPTH_32 = 44,
		PARAM_STAGE_DIST = 45,
		PARAM_STAGE_WIDTH = 46,
		PARAM_STAGE_DEPTH = 47,
		PARAM_TOTEM_GAP = 48,
		PARAM_TILT = 49,
		PARAM_MODULE_WIDTH = 50,
		PARAM_MODULE_HEIGHT = 51,
		PARAM_SCREEN_COLUMNS = 52,
		PARAM_SCREEN_ROWS = 53,
		PARAM_TOTEM_COUNT = 54,
		PARAM_TOTEM_COLUMNS = 55,
		PARAM_TOTEM_ROWS = 56,
		PARAM_CAMERA_DISTANCE = 57,
	};
};
