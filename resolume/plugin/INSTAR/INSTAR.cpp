#include "INSTAR.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>

using namespace ffglqs;

static CFFGLPluginInfo PluginInfo(
	PluginFactory< INSTAR >,
	"IN01",
	"INSTAR",
	2,
	1,
	1,
	0,
	FF_EFFECT,
	"Live mapping guide and Advanced Output XML generator for Resolume.",
	"LUCIDA RESOLUME"
);

INSTAR::INSTAR() :
	outputPath("INSTAR_AdvancedOutput.xml")
{
	SetFragmentShader(R"(
		in vec2 i_uv;
		uniform sampler2D inputTexture;
		uniform float GuideOpacity;
		uniform float GuideDetail;
		uniform vec4 GuideColor;

		float line(float distanceToLine, float width)
		{
			return 1.0 - smoothstep(width, width + 0.003, distanceToLine);
		}

		void main()
		{
			vec4 base = texture(inputTexture, i_uv);
			vec2 distanceToEdge = min(i_uv, 1.0 - i_uv);
			float border = max(
				line(distanceToEdge.x, 0.018),
				line(distanceToEdge.y, 0.018)
			);

			float gridSpacing = mix(0.25, 0.125, clamp(GuideDetail, 0.0, 1.0));
			vec2 gridCell = abs(fract(i_uv / gridSpacing) - 0.5);
			float grid = max(
				line(gridCell.x * gridSpacing, 0.004),
				line(gridCell.y * gridSpacing, 0.004)
			) * clamp(GuideDetail, 0.0, 1.0);

			float guide = max(border, grid * 0.7);
			float alpha = clamp(GuideOpacity, 0.0, 1.0) * guide;
			fragColor = vec4(mix(base.rgb, GuideColor.rgb, alpha), base.a);
		}
	)");

	AddParam(ParamEvent::Create("ExportXML"));
	AddParam(ParamText::create("Profile", ""));
	AddParam(ParamText::create("OutputXML", outputPath));
	AddParam(Param::Create("GuideOpacity", 0.35f));
	AddParam(Param::Create("GuideDetail", 0.0f));
	AddHueColorParam("GuideColor");
}

FFResult INSTAR::SetFloatParameter(unsigned int index, float value)
{
	if (index == PARAM_EXPORT_XML)
	{
		if (value != 0.0f)
			exportRequested = true;
		return Effect::SetFloatParameter(index, value);
	}
	return Effect::SetFloatParameter(index, value);
}

FFResult INSTAR::SetTextParameter(unsigned int index, const char* value)
{
	const std::string safeValue = value == nullptr ? "" : value;
	if (index == PARAM_PROFILE)
	{
		profilePath = safeValue;
		return FF_SUCCESS;
	}
	if (index == PARAM_OUTPUT_XML)
	{
		outputPath = safeValue.empty() ? "INSTAR_AdvancedOutput.xml" : safeValue;
		return FF_SUCCESS;
	}
	return Effect::SetTextParameter(index, value);
}

char* INSTAR::GetTextParameter(unsigned int index)
{
	static char buffer[4096];
	const std::string* value = nullptr;
	if (index == PARAM_PROFILE)
		value = &profilePath;
	else if (index == PARAM_OUTPUT_XML)
		value = &outputPath;
	if (value == nullptr)
		return Effect::GetTextParameter(index);
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(value->size(), sizeof(buffer) - 1);
	std::copy(value->begin(), value->begin() + length, buffer);
	return buffer;
}

void INSTAR::Update()
{
	if (currentViewport.width > 0 && currentViewport.height > 0)
	{
		lastWidth = currentViewport.width;
		lastHeight = currentViewport.height;
	}
	if (exportRequested)
	{
		exportRequested = false;
		ExportAdvancedOutput();
	}
}

std::vector<INSTAR::Surface> INSTAR::LoadProfile(unsigned int fallbackWidth, unsigned int fallbackHeight) const
{
	unsigned int canvasWidth = fallbackWidth > 0 ? fallbackWidth : 1920;
	unsigned int canvasHeight = fallbackHeight > 0 ? fallbackHeight : 1080;
	std::vector<Surface> surfaces;

	if (!profilePath.empty())
	{
		std::ifstream file(profilePath.c_str());
		std::string line;
		while (std::getline(file, line))
		{
			std::istringstream input(line);
			std::string command;
			input >> command;
			if (command.empty() || command[0] == '#')
				continue;
			if (command == "canvas")
			{
				unsigned int width = 0, height = 0;
				if (input >> width >> height && width > 0 && height > 0)
				{
					canvasWidth = width;
					canvasHeight = height;
				}
				continue;
			}
			if (command != "surface")
				continue;

			Surface surface;
			if (!(input >> surface.name >> surface.x >> surface.y >> surface.width >> surface.height))
				continue;
			if (surface.name.empty() || surface.width <= 0.0f || surface.height <= 0.0f)
				continue;
			if (surface.x < 0.0f || surface.y < 0.0f ||
				surface.x + surface.width > canvasWidth || surface.y + surface.height > canvasHeight)
				continue;
			surfaces.push_back(surface);
		}
	}

	if (surfaces.empty())
	{
		Surface fallback;
		fallback.name = "FULL_CANVAS";
		fallback.width = static_cast<float>(canvasWidth);
		fallback.height = static_cast<float>(canvasHeight);
		surfaces.push_back(fallback);
	}
	return surfaces;
}

bool INSTAR::ExportAdvancedOutput()
{
	const std::vector<Surface> surfaces = LoadProfile(lastWidth, lastHeight);
	unsigned int canvasWidth = lastWidth > 0 ? lastWidth : 1920;
	unsigned int canvasHeight = lastHeight > 0 ? lastHeight : 1080;
	if (!profilePath.empty())
	{
		std::ifstream file(profilePath.c_str());
		std::string line;
		while (std::getline(file, line))
		{
			std::istringstream input(line);
			std::string command;
			unsigned int width = 0, height = 0;
			if ((input >> command >> width >> height) && command == "canvas" && width > 0 && height > 0)
			{
				canvasWidth = width;
				canvasHeight = height;
				break;
			}
		}
	}

	const std::vector<INSTARSurface> xmlSurfaces(surfaces.begin(), surfaces.end());
	const std::string xml = BuildINSTARAdvancedOutputXml(canvasWidth, canvasHeight, xmlSurfaces);
	std::ofstream file(outputPath.c_str(), std::ios::out | std::ios::trunc);
	if (!file.is_open())
	{
		FFGLLog::LogToHost("INSTAR: no se pudo escribir OutputXML");
		return false;
	}

	file << xml;

	file.close();
	FFGLLog::LogToHost("INSTAR: AdvancedOutput.xml generado");
	return true;
}
