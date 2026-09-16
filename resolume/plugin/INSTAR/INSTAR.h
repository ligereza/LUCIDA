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
		PARAM_EDGE_BUDGET = 2,
		PARAM_MAP_FILE = 3,
		PARAM_EXPORT_MAP_XML = 4,
		PARAM_OUTPUT_XML = 5,
		PARAM_VIEW = 6,
		PARAM_YAW = 7,
		PARAM_PITCH = 8,
		PARAM_ZOOM = 9,
		PARAM_BRIGHTNESS = 10,
		PARAM_CANVAS_WIDTH = 11,
		PARAM_CANVAS_HEIGHT = 12,
	};
};
