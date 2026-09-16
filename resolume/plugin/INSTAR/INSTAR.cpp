#include "INSTAR.h"

#include <algorithm>
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
	FF_SOURCE,
	"FLUJO-style venue Capture and explicit raster mapping export for Resolume.",
	"LUCIDA RESOLUME"
);

INSTAR::INSTAR()
{
	AddParam(Param::Create("VenueFile", FF_TYPE_FILE, 0.0f));
	AddParam(Param::Create("MapFile", FF_TYPE_FILE, 0.0f));
	AddParam(ParamEvent::Create("ExportMapXML"));
	AddParam(ParamText::create("OutputXML", outputPath));
	AddParam(ParamOption::Create("View", {
		{"AEREO", 0.0f},
		{"PISTA", 1.0f},
		{"LIBRE", 2.0f},
	}, 0));
	AddParam(Param::Create("Yaw", yaw));
	AddParam(Param::Create("Pitch", pitch));
	AddParam(Param::Create("Zoom", zoom));
	AddParam(Param::Create("Brightness", brightness));
	AddParam(Param::Create("CanvasWidth", FF_TYPE_INTEGER, 0.0f));
	AddParam(Param::Create("CanvasHeight", FF_TYPE_INTEGER, 0.0f));
	SetParamRange(PARAM_CANVAS_WIDTH, 0.0f, 16384.0f);
	SetParamRange(PARAM_CANVAS_HEIGHT, 0.0f, 16384.0f);
}

FFResult INSTAR::Init()
{
	if (renderer.Init() != FF_SUCCESS)
		return FF_FAIL;
	LoadVenue();
	UploadScene();
	return FF_SUCCESS;
}

void INSTAR::Clean()
{
	renderer.Clean();
}

bool INSTAR::LoadVenue()
{
	if (venuePath.empty())
	{
		scene = BuildINSTARDemoScene();
		loadedPath.clear();
		sceneDirty = false;
		return true;
	}
	std::string error;
	INSTARScene loaded;
	if (!LoadINSTARVenueJson(venuePath, loaded, error))
	{
		FFGLLog::LogToHost("INSTAR: VenueFile inválido; se usa escena demo");
		scene = BuildINSTARDemoScene();
		loadedPath.clear();
		sceneDirty = false;
		return false;
	}
	scene = loaded;
	loadedPath = venuePath;
	sceneDirty = false;
	return true;
}

void INSTAR::UploadScene()
{
	renderer.Upload(scene);
}

void INSTAR::Update()
{
	if (currentViewport.width > 0 && currentViewport.height > 0)
	{
		lastWidth = currentViewport.width;
		lastHeight = currentViewport.height;
	}
	if (sceneDirty || loadedPath != venuePath)
	{
		LoadVenue();
		UploadScene();
	}
	if (exportRequested)
	{
		exportRequested = false;
		ExportMapXml();
	}
}

bool INSTAR::ExportMapXml()
{
	if (mapPath.empty())
	{
		FFGLLog::LogToHost("INSTAR: MapFile vacío; ExportMapXML requiere PNG/JPG");
		return false;
	}
	unsigned int canvasWidth = lastWidth > 0 ? lastWidth : 1920;
	unsigned int canvasHeight = lastHeight > 0 ? lastHeight : 1080;
	const float configuredWidth = GetFloatParameter(PARAM_CANVAS_WIDTH);
	const float configuredHeight = GetFloatParameter(PARAM_CANVAS_HEIGHT);
	if (configuredWidth >= 1.0f)
		canvasWidth = static_cast<unsigned int>(configuredWidth);
	if (configuredHeight >= 1.0f)
		canvasHeight = static_cast<unsigned int>(configuredHeight);

	INSTARImage image;
	std::string error;
	if (!LoadINSTARImage(mapPath, image, error))
	{
		std::string message = "INSTAR: MapFile no es un raster compatible: " + error;
		FFGLLog::LogToHost(message.c_str());
		return false;
	}
	const std::vector<INSTARSurface> surfaces = DetectINSTARSurfaces(image, canvasWidth, canvasHeight);
	if (surfaces.empty())
	{
		FFGLLog::LogToHost("INSTAR: no se detectaron superficies; no se genera XML");
		return false;
	}
	const std::string xml = BuildINSTARAdvancedOutputXml(canvasWidth, canvasHeight, surfaces);
	std::ofstream file(outputPath.c_str(), std::ios::out | std::ios::trunc);
	if (!file.is_open())
	{
		FFGLLog::LogToHost("INSTAR: no se pudo escribir OutputXML");
		return false;
	}
	file << xml;
	const bool written = file.good();
	file.close();
	FFGLLog::LogToHost(written ? "INSTAR: AdvancedOutput.xml generado desde raster" : "INSTAR: error al escribir AdvancedOutput.xml");
	return written;
}

FFResult INSTAR::Render(ProcessOpenGLStruct*)
{
	const int view = static_cast<int>(GetFloatParameter(PARAM_VIEW));
	const INSTARCamera camera = SelectINSTARCamera(view, yaw, pitch, zoom);
	return renderer.Render(
		scene,
		camera,
		brightness,
		currentViewport.width,
		currentViewport.height
	);
}

FFResult INSTAR::SetFloatParameter(unsigned int index, float value)
{
	if (index == PARAM_EXPORT_MAP_XML)
	{
		if (value != 0.0f)
			exportRequested = true;
	}
	else if (index == PARAM_YAW)
		yaw = value;
	else if (index == PARAM_PITCH)
		pitch = value;
	else if (index == PARAM_ZOOM)
		zoom = value;
	else if (index == PARAM_BRIGHTNESS)
		brightness = value;
	return Source::SetFloatParameter(index, value);
}

FFResult INSTAR::SetTextParameter(unsigned int index, const char* value)
{
	const std::string safeValue = value == nullptr ? "" : value;
	if (index == PARAM_VENUE_FILE)
	{
		venuePath = safeValue;
		sceneDirty = true;
		return FF_SUCCESS;
	}
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
	return Source::SetTextParameter(index, value);
}

char* INSTAR::GetTextParameter(unsigned int index)
{
	static char buffer[4096];
	const std::string* value = nullptr;
	if (index == PARAM_VENUE_FILE)
		value = &venuePath;
	else if (index == PARAM_MAP_FILE)
		value = &mapPath;
	else if (index == PARAM_OUTPUT_XML)
		value = &outputPath;
	if (value == nullptr)
		return Source::GetTextParameter(index);
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(value->size(), sizeof(buffer) - 1);
	std::copy(value->begin(), value->begin() + length, buffer);
	return buffer;
}
