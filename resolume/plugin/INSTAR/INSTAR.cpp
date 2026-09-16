#include "INSTAR.h"
#include "INSTAR_IMAGE.h"

#include <algorithm>
#include <cctype>
#include <fstream>

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
	// FFGL file parameter: the host supplies the selected path through
	// SetTextParameter; the plugin never asks for an existing XML.
	AddParam(Param::Create("MapFile", FF_TYPE_FILE, 0.0f));
	AddParam(ParamText::create("OutputXML", outputPath));
	AddParam(Param::Create("CanvasWidth", FF_TYPE_INTEGER, 0.0f));
	AddParam(Param::Create("CanvasHeight", FF_TYPE_INTEGER, 0.0f));
	SetParamRange(PARAM_CANVAS_WIDTH, 0.0f, 16384.0f);
	SetParamRange(PARAM_CANVAS_HEIGHT, 0.0f, 16384.0f);
	AddParam(ParamOption::Create("View", {
		{"AEREO", 0.0f},
		{"PISTA", 1.0f},
		{"LIBRE", 2.0f},
	}, 0));
	AddParam(Param::Create("GuideOpacity", 0.35f));
	AddParam(Param::Create("GuideDetail", 0.0f));
	AddHueColorParam("GuideColor");
}

static bool IsObjPath(const std::string& path)
{
	const size_t dot = path.find_last_of('.');
	if (dot == std::string::npos)
		return false;
	std::string extension = path.substr(dot);
	std::transform(extension.begin(), extension.end(), extension.begin(), [](unsigned char character) {
		return static_cast<char>(std::tolower(character));
	});
	return extension == ".obj";
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
	if (index == PARAM_MAP_FILE)
	{
		mapPath = safeValue;
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
	if (index == PARAM_MAP_FILE)
		value = &mapPath;
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

std::vector<INSTAR::Surface> INSTAR::LoadMap(unsigned int canvasWidth, unsigned int canvasHeight)
{
	const unsigned int width = canvasWidth > 0 ? canvasWidth : 1920;
	const unsigned int height = canvasHeight > 0 ? canvasHeight : 1080;
	std::vector<Surface> surfaces;
	if (!mapPath.empty())
	{
		if (IsObjPath(mapPath))
		{
			INSTARScene scene;
			std::string error;
			if (LoadINSTARObj(mapPath, scene, error))
			{
				const int view = static_cast<int>(GetFloatParameter(PARAM_VIEW));
				const INSTARCamera camera = SelectINSTARCamera(view, 0.5f, 0.5f, 0.55f);
				const std::vector<INSTARProjectedSurface> projected = ProjectINSTARSurfaces(
					scene, camera.yaw, camera.pitch, camera.zoom, width, height);
				for (const INSTARProjectedSurface& source : projected)
				{
					Surface surface;
					surface.name = source.name;
					surface.x = source.x;
					surface.y = source.y;
					surface.width = source.width;
					surface.height = source.height;
					surfaces.push_back(surface);
				}
			}
			else
			{
				std::string message = "INSTAR: no se pudo leer OBJ de MapFile: " + error;
				FFGLLog::LogToHost(message.c_str());
			}
		}
		else
		{
			INSTARImage image;
			std::string error;
			if (LoadINSTARImage(mapPath, image, error))
				surfaces = DetectINSTARSurfaces(image, width, height);
			else
			{
				std::string message = "INSTAR: no se pudo leer MapFile: " + error;
				FFGLLog::LogToHost(message.c_str());
			}
		}
	}
	else
	{
		FFGLLog::LogToHost("INSTAR: MapFile vacío; se genera canvas completo");
	}

	if (surfaces.empty())
	{
		Surface fallback;
		fallback.name = "FULL_CANVAS";
		fallback.width = static_cast<float>(width);
		fallback.height = static_cast<float>(height);
		surfaces.push_back(fallback);
	}
	return surfaces;
}

bool INSTAR::ExportAdvancedOutput()
{
	unsigned int canvasWidth = lastWidth > 0 ? lastWidth : 1920;
	unsigned int canvasHeight = lastHeight > 0 ? lastHeight : 1080;
	const float configuredWidth = GetFloatParameter(PARAM_CANVAS_WIDTH);
	const float configuredHeight = GetFloatParameter(PARAM_CANVAS_HEIGHT);
	if (configuredWidth >= 1.0f)
		canvasWidth = static_cast<unsigned int>(configuredWidth);
	if (configuredHeight >= 1.0f)
		canvasHeight = static_cast<unsigned int>(configuredHeight);
	const std::vector<Surface> surfaces = LoadMap(canvasWidth, canvasHeight);

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
