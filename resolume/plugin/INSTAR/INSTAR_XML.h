#pragma once

#include <string>
#include <vector>

struct INSTARSurface
{
	std::string name;
	float x = 0.0f;
	float y = 0.0f;
	float width = 0.0f;
	float height = 0.0f;
};

struct INSTARSurfaceMapping
{
	std::string name;
	INSTARSurface input;
	INSTARSurface output;
};

struct INSTARTemplateInfo
{
	unsigned int inputWidth = 0;
	unsigned int inputHeight = 0;
	unsigned int outputWidth = 0;
	unsigned int outputHeight = 0;
	unsigned long long firstSliceId = 0;
};

// Builds a standalone virtual-screen Advanced Output document.
std::string BuildINSTARAdvancedOutputXml(
	unsigned int canvasWidth,
	unsigned int canvasHeight,
	const std::vector<INSTARSurface>& surfaces
);

bool ReadINSTARAdvancedOutputTemplateInfo(
	const std::string& templateXml,
	INSTARTemplateInfo& info,
	std::string& error
);

std::vector<INSTARSurfaceMapping> ScaleINSTARSurfacesToTemplate(
	const std::vector<INSTARSurface>& surfaces,
	unsigned int sourceWidth,
	unsigned int sourceHeight,
	const INSTARTemplateInfo& templateInfo
);

std::string BuildINSTARAdvancedOutputXmlFromTemplate(
	const std::string& templateXml,
	const std::vector<INSTARSurfaceMapping>& mappings
);
