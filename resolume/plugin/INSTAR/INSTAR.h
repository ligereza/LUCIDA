#pragma once

#include <FFGLSDK.h>
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

	std::vector<Surface> LoadProfile(unsigned int fallbackWidth, unsigned int fallbackHeight) const;
	bool ExportAdvancedOutput();

	std::string profilePath;
	std::string outputPath;
	bool exportRequested = false;
	unsigned int lastWidth = 1920;
	unsigned int lastHeight = 1080;

	enum Parameter : unsigned int
	{
		PARAM_EXPORT_XML = 0,
		PARAM_PROFILE = 1,
		PARAM_OUTPUT_XML = 2,
		PARAM_GUIDE_OPACITY = 3,
		PARAM_GUIDE_DETAIL = 4,
		PARAM_GUIDE_COLOR = 5,
	};
};
