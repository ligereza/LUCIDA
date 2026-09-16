#pragma once

#include <FFGLSDK.h>
#include "INSTAR_SCENE.h"
#include "INSTAR_XML.h"

#include <string>
#include <vector>

class INSTAR final : public ffglqs::Effect
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

protected:
	void Update() override;

private:
	using Surface = INSTARSurface;

	std::vector<Surface> LoadMap(unsigned int canvasWidth, unsigned int canvasHeight);
	bool ExportAdvancedOutput();

	std::string mapPath;
	std::string outputPath;
	bool exportRequested = false;
	unsigned int lastWidth = 1920;
	unsigned int lastHeight = 1080;

	enum Parameter : unsigned int
	{
		PARAM_EXPORT_XML = 0,
		PARAM_MAP_FILE = 1,
		PARAM_OUTPUT_XML = 2,
		PARAM_CANVAS_WIDTH = 3,
		PARAM_CANVAS_HEIGHT = 4,
		PARAM_VIEW = 5,
		PARAM_GUIDE_OPACITY = 6,
		PARAM_GUIDE_DETAIL = 7,
		PARAM_GUIDE_COLOR = 8,
	};
};
