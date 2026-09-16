#pragma once

#include <FFGLSDK.h>
#include <ffglex/FFGLScreenQuad.h>

#include "INSTAR_IMAGE.h"
#include "INSTAR_RENDERER.h"
#include "INSTAR_XML.h"

#include <string>
#include <vector>
#include <utility>

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
	bool LoadScene();
	void ConfigureSliceDepthParams(size_t sliceCount);
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
	std::string loadedPath;
	std::string mapPath;
	std::string templatePath;
	std::string previewTemplatePath;
	std::string outputPath = "INSTAR_AdvancedOutput.xml";
	std::pair<long long, long long> loadedFileSignature = {0, 0};
	std::pair<long long, long long> loadedRasterSignature = {0, 0};
	float yaw = 0.5f;
	float pitch = 0.5f;
	float zoom = 0.55f;
	float cameraDistance = 3.5f;
	float brightness = 0.85f;
	float depth = 0.0f;
	float sliceDepths[32] = {};
	bool sceneDirty = true;
	bool rasterDirty = true;
	bool rasterReady = false;
	bool exportRequested = false;

	enum Parameter : unsigned int
	{
		PARAM_MODE = 0,
		PARAM_MAP_FILE = 1,
		PARAM_TEMPLATE_XML = 2,
		PARAM_EXPORT_MAP_XML = 3,
		PARAM_OUTPUT_XML = 4,
		PARAM_VIEW = 5,
		PARAM_YAW = 6,
		PARAM_PITCH = 7,
		PARAM_ZOOM = 8,
		PARAM_BRIGHTNESS = 9,
		PARAM_DEPTH = 10,
		PARAM_SLICE_DEPTH_01 = 11,
		PARAM_SLICE_DEPTH_32 = 42,
		PARAM_CAMERA_DISTANCE = 43,
	};
};
