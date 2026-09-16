#include "INSTAR_3D.h"

#include <algorithm>
#include <cctype>

namespace
{
int HexDigit(char value)
{
	if (value >= '0' && value <= '9')
		return value - '0';
	if (value >= 'a' && value <= 'f')
		return value - 'a' + 10;
	if (value >= 'A' && value <= 'F')
		return value - 'A' + 10;
	return -1;
}

std::string DecodeFileUri(std::string value)
{
	while (!value.empty() && std::isspace(static_cast<unsigned char>(value.front())))
		value.erase(value.begin());
	while (!value.empty() && std::isspace(static_cast<unsigned char>(value.back())))
		value.pop_back();
	if (value.size() >= 2 && value.front() == '"' && value.back() == '"')
		value = value.substr(1, value.size() - 2);
	if (value.compare(0, 7, "file://") == 0)
	{
		value.erase(0, 7);
		if (value.size() >= 3 && value[0] == '/' && value[2] == ':')
			value.erase(0, 1);
	}
	std::string decoded;
	for (size_t index = 0; index < value.size(); ++index)
	{
		if (value[index] == '%' && index + 2 < value.size())
		{
			const int high = HexDigit(value[index + 1]);
			const int low = HexDigit(value[index + 2]);
			if (high >= 0 && low >= 0)
			{
				decoded.push_back(static_cast<char>((high << 4) | low));
				index += 2;
				continue;
			}
		}
		decoded.push_back(value[index]);
	}
	return decoded;
}
}

using namespace ffglqs;

static CFFGLPluginInfo PluginInfo(
	PluginFactory< INSTAR3D >,
	"I3D1",
	"INSTAR 3D",
	2,
	1,
	1,
	0,
	FF_SOURCE,
	"Low-cost OBJ/MTL model visualizer for Resolume compositions.",
	"LUCIDA RESOLUME"
);

INSTAR3D::INSTAR3D()
{
	AddParam(Param::Create("ModelFile", FF_TYPE_FILE, 0.0f));
	AddParam(ParamOption::Create("View", {
		{"AEREO", 0.0f},
		{"PISTA", 1.0f},
		{"LIBRE", 2.0f},
	}, 0));
	AddParam(Param::Create("Yaw", yaw));
	AddParam(Param::Create("Pitch", pitch));
	AddParam(Param::Create("Zoom", zoom));
	AddParam(Param::Create("Brightness", brightness));
}

FFResult INSTAR3D::Init()
{
	if (renderer.Init() != FF_SUCCESS)
		return FF_FAIL;
	LoadScene();
	UploadScene();
	return FF_SUCCESS;
}

void INSTAR3D::Clean()
{
	renderer.Clean();
}

bool INSTAR3D::LoadScene()
{
	if (modelPath.empty())
	{
		scene = BuildINSTARModelDemoScene();
		loadedPath.clear();
		sceneDirty = false;
		return true;
	}
	std::string error;
	INSTARScene loaded;
	if (!LoadINSTARObj(modelPath, loaded, error))
	{
		const std::string message = "INSTAR 3D: no se pudo cargar ModelFile: " + modelPath + " (" + error + ")";
		FFGLLog::LogToHost(message.c_str());
		scene = BuildINSTARModelDemoScene();
		loadedPath.clear();
		sceneDirty = false;
		return false;
	}
	scene = loaded;
	loadedPath = modelPath;
	sceneDirty = false;
	return true;
}

void INSTAR3D::UploadScene()
{
	renderer.Upload(scene);
}

void INSTAR3D::Update()
{
	if (sceneDirty || loadedPath != modelPath)
	{
		LoadScene();
		UploadScene();
	}
}

FFResult INSTAR3D::Render(ProcessOpenGLStruct*)
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

FFResult INSTAR3D::SetFloatParameter(unsigned int index, float value)
{
	if (index == PARAM_YAW)
		yaw = value;
	else if (index == PARAM_PITCH)
		pitch = value;
	else if (index == PARAM_ZOOM)
		zoom = value;
	else if (index == PARAM_BRIGHTNESS)
		brightness = value;
	return Source::SetFloatParameter(index, value);
}

FFResult INSTAR3D::SetTextParameter(unsigned int index, const char* value)
{
	if (index == PARAM_MODEL_FILE)
	{
		modelPath = DecodeFileUri(value == nullptr ? "" : value);
		const std::string message = "INSTAR 3D: ModelFile recibido: " + modelPath;
		FFGLLog::LogToHost(message.c_str());
		sceneDirty = true;
		return FF_SUCCESS;
	}
	return Source::SetTextParameter(index, value);
}

char* INSTAR3D::GetTextParameter(unsigned int index)
{
	static char buffer[4096];
	if (index != PARAM_MODEL_FILE)
		return Source::GetTextParameter(index);
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(modelPath.size(), sizeof(buffer) - 1);
	std::copy(modelPath.begin(), modelPath.begin() + length, buffer);
	return buffer;
}
