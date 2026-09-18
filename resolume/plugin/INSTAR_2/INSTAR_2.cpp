#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <sys/stat.h>
#endif

#include "INSTAR_2.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <iterator>

#include <ffgl/FFGLLog.h>

using namespace ffglqs;

namespace
{
constexpr int MODE_VIEW_AEREO = 0;
constexpr int MODE_VIEW_PISTA = 1;
constexpr int MODE_VIEW_LIBRE = 2;

#ifdef _WIN32
std::wstring Utf8ToWidePath(const std::string& path)
{
	const int wideLength = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path.c_str(), -1, nullptr, 0);
	if (wideLength <= 0)
		return std::wstring();
	std::wstring result(static_cast<size_t>(wideLength), L'\0');
	if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path.c_str(), -1, &result[0], wideLength) <= 0)
		return std::wstring();
	return result;
}
#endif
}

static CFFGLPluginInfo PluginInfo(
	PluginFactory<INSTAR_2>,
	"IN02",
	"INSTAR 2",
	2,
	1,
	1,
	0,
	FF_EFFECT,
	"Live 3D preview of an Advanced Output XML using the Resolume input texture.",
	"LUCIDA RESOLUME");

INSTAR_2::INSTAR_2()
{
	SetMinInputs(1);
	SetMaxInputs(1);
	SetFragmentShader("void main() { fragColor = vec4(0.0); }");
	AddParam(Param::Create("TemplateXML", FF_TYPE_FILE, 0.0f));
	AddParam(ParamBool::Create("FollowActiveXML", true));
	AddParam(ParamOption::Create("View", {
		{"AEREO", static_cast<float>(MODE_VIEW_AEREO)},
		{"PISTA", static_cast<float>(MODE_VIEW_PISTA)},
		{"LIBRE", static_cast<float>(MODE_VIEW_LIBRE)},
	}, MODE_VIEW_AEREO));
	AddParam(ParamRange::Create("Yaw", yaw_, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("Pitch", pitch_, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("Zoom", zoom_, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("Brightness", brightness_, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("Depth", depth_, ParamRange::Range(-10.0f, 10.0f)));
	for (unsigned int index = 0; index < 32U; ++index)
	{
		sliceEnabled_[index] = true;
		const std::string enabledName = std::string("SliceEnabled") + (index < 9U ? "0" : "") + std::to_string(index + 1U);
		AddParam(ParamBool::Create(enabledName, true));
	}
	for (unsigned int index = 0; index < 32U; ++index)
	{
		const std::string name = std::string("SliceDepth") + (index < 9U ? "0" : "") + std::to_string(index + 1U);
		AddParam(ParamRange::Create(name, 0.0f, ParamRange::Range(-10.0f, 10.0f)));
		SetParamVisibility(PARAM_SLICE_DEPTH_01 + index, false, false);
		SetParamVisibility(PARAM_SLICE_ENABLED_01 + index, false, false);
	}
	AddParam(ParamRange::Create("CameraDistance", cameraDistance_, ParamRange::Range(1.0f, 20.0f)));
	AddParam(ParamTrigger::Create("UseActiveXML"));
	AddParam(ParamTrigger::Create("ReloadXML"));

	SetParamDisplayName(PARAM_TEMPLATE_XML, "Advanced Output XML", false);
	SetParamDisplayName(PARAM_FOLLOW_ACTIVE_XML, "Follow Active XML", false);
	SetParamDisplayName(PARAM_VIEW, "View", false);
	SetParamDisplayName(PARAM_YAW, "Yaw", false);
	SetParamDisplayName(PARAM_PITCH, "Pitch", false);
	SetParamDisplayName(PARAM_ZOOM, "Zoom", false);
	SetParamDisplayName(PARAM_BRIGHTNESS, "Brightness", false);
	SetParamDisplayName(PARAM_DEPTH, "Global Depth", false);
	SetParamDisplayName(PARAM_CAMERA_DISTANCE, "Camera Distance", false);
	SetParamDisplayName(PARAM_USE_ACTIVE_XML, "Use Active XML", false);
	SetParamDisplayName(PARAM_RELOAD_XML, "Reload XML", false);
	SetParamGroup(PARAM_TEMPLATE_XML, "Scene");
	SetParamGroup(PARAM_FOLLOW_ACTIVE_XML, "Scene");
	SetParamGroup(PARAM_VIEW, "Camera");
	SetParamGroup(PARAM_YAW, "Camera");
	SetParamGroup(PARAM_PITCH, "Camera");
	SetParamGroup(PARAM_ZOOM, "Camera");
	SetParamGroup(PARAM_BRIGHTNESS, "Output");
	SetParamGroup(PARAM_DEPTH, "Depth");
	SetParamGroup(PARAM_CAMERA_DISTANCE, "Camera");
	SetParamGroup(PARAM_USE_ACTIVE_XML, "Scene");
	SetParamGroup(PARAM_RELOAD_XML, "Scene");
	for (unsigned int index = 0; index < 32U; ++index)
	{
		SetParamGroup(PARAM_SLICE_ENABLED_01 + index, "Slices");
		SetParamGroup(PARAM_SLICE_DEPTH_01 + index, "Depth");
	}
}

INSTAR_2::FileSignature INSTAR_2::GetFileSignature(const std::string& path)
{
	if (path.empty())
		return {0, 0};

#ifdef _WIN32
	const std::wstring widePath = Utf8ToWidePath(path);
	WIN32_FILE_ATTRIBUTE_DATA data = {};
	if (!widePath.empty() && GetFileAttributesExW(widePath.c_str(), GetFileExInfoStandard, &data) != 0)
	{
		ULARGE_INTEGER writeTime = {};
		writeTime.LowPart = data.ftLastWriteTime.dwLowDateTime;
		writeTime.HighPart = data.ftLastWriteTime.dwHighDateTime;
		ULARGE_INTEGER fileSize = {};
		fileSize.LowPart = data.nFileSizeLow;
		fileSize.HighPart = data.nFileSizeHigh;
		return {static_cast<long long>(writeTime.QuadPart), static_cast<long long>(fileSize.QuadPart)};
	}
	struct _stat64 info = {};
	if (_stat64(path.c_str(), &info) != 0)
		return {0, 0};
	return {static_cast<long long>(info.st_mtime), static_cast<long long>(info.st_size)};
#else
	struct stat info = {};
	if (stat(path.c_str(), &info) != 0)
		return {0, 0};
	return {static_cast<long long>(info.st_mtime), static_cast<long long>(info.st_size)};
#endif
}

std::string INSTAR_2::ResolveActivePresetPath()
{
#ifdef _WIN32
	const char* userProfile = std::getenv("USERPROFILE");
	if (userProfile == nullptr || userProfile[0] == '\0')
		return std::string();
	const std::string roots[] = {
		std::string(userProfile) + "\\Documents\\Resolume Arena",
		std::string(userProfile) + "\\Documents\\Resolume Avenue",
		std::string(userProfile) + "\\My Documents\\Resolume Arena",
	};
	for (const std::string& root : roots)
	{
		const std::string preferencePath = root + "\\Preferences\\AdvancedOutput.xml";
		std::ifstream preference(preferencePath.c_str(), std::ios::binary);
		if (!preference.is_open())
			continue;
		const std::string xml((std::istreambuf_iterator<char>(preference)), std::istreambuf_iterator<char>());
		const size_t attribute = xml.find("presetFile=");
		if (attribute == std::string::npos)
			continue;
		size_t valueStart = attribute + std::strlen("presetFile=");
		if (valueStart >= xml.size())
			continue;
		const char quote = xml[valueStart] == '\'' || xml[valueStart] == '"' ? xml[valueStart] : '\0';
		if (quote != '\0')
			++valueStart;
		const size_t valueEnd = quote != '\0' ? xml.find(quote, valueStart) : xml.find_first_of(" \t\r\n>", valueStart);
		if (valueEnd == std::string::npos || valueEnd <= valueStart)
			continue;
		std::string preset = xml.substr(valueStart, valueEnd - valueStart);
		if (preset.find(".xml") == std::string::npos)
			preset += ".xml";
		const bool absolute = preset.size() > 1U && preset[1] == ':';
		const std::string path = absolute ? preset : root + "\\Presets\\Advanced Output\\" + preset;
		if (GetFileSignature(path) != FileSignature{0, 0})
			return path;
	}
#endif
	return std::string();
}

void INSTAR_2::Log(const std::string& message) const
{
	FFGLLog::LogToHost(("INSTAR 2: " + message).c_str());
}

void INSTAR_2::ConfigureSliceDepthParams(size_t sliceCount, const std::vector<std::string>& names)
{
	const size_t visibleCount = std::min<size_t>(sliceCount, 32U);
	for (unsigned int index = 0; index < 32U; ++index)
	{
		SetParamVisibility(PARAM_SLICE_DEPTH_01 + index, index < visibleCount, true);
		SetParamVisibility(PARAM_SLICE_ENABLED_01 + index, index < visibleCount, true);
		const std::string baseName = std::string("SliceDepth") + (index < 9U ? "0" : "") + std::to_string(index + 1U);
		const std::string displayName = index < names.size() && !names[index].empty() ?
			baseName + " [" + names[index] + "]" : baseName;
		SetParamDisplayName(PARAM_SLICE_DEPTH_01 + index, displayName, true);
		const std::string enabledName = index < names.size() && !names[index].empty() ?
			std::string("Use ") + names[index] : std::string("Use Slice") + (index < 9U ? "0" : "") + std::to_string(index + 1U);
		SetParamDisplayName(PARAM_SLICE_ENABLED_01 + index, enabledName, true);
	}
	visibleSliceCount_ = static_cast<unsigned int>(visibleCount);
}

void INSTAR_2::FollowActivePresetIfNeeded()
{
	if (!followActivePreset_)
		return;
	if (!templatePath_.empty() && (++activePresetPollCounter_ % 15U) != 0U)
		return;
	activePresetPollCounter_ = 0;
	const std::string activePath = ResolveActivePresetPath();
	if (activePath.empty() || activePath == templatePath_)
		return;
	templatePath_ = activePath;
	lastAttemptPath_.clear();
	lastAttemptSignature_ = {0, 0};
	sceneDirty_ = true;
	Log("preset Advanced Output activo detectado: " + templatePath_);
}

bool INSTAR_2::ReloadSceneIfNeeded(bool force)
{
	const FileSignature signature = GetFileSignature(templatePath_);
	if (templatePath_.empty())
	{
		if (!scene_.lineVertices.empty() || !scene_.triangleVertices.empty() || !activePath_.empty())
		{
			scene_ = INSTARScene();
			renderer_.Upload(scene_);
			ConfigureSliceDepthParams(0, {});
		}
		activePath_.clear();
		activeSignature_ = {0, 0};
		lastAttemptPath_.clear();
		lastAttemptSignature_ = {0, 0};
		selectedSliceCount_ = 0;
		sceneDirty_ = false;
		return true;
	}

	if (!force && !sceneDirty_ && activePath_ == templatePath_ && activeSignature_ == signature)
		return true;
	if (!force && !sceneDirty_ && lastAttemptPath_ == templatePath_ && lastAttemptSignature_ == signature)
		return false;

	INSTARScene candidate;
	std::string error;
	lastAttemptPath_ = templatePath_;
	lastAttemptSignature_ = signature;
	if (!LoadINSTARAdvancedOutputPlanes(templatePath_, candidate, error))
	{
		Log("XML inválido; se conserva la última escena válida: " + error);
		sceneDirty_ = false;
		return false;
	}

	std::vector<std::string> names;
	std::vector<INSTARInputPlane> selectedPlanes;
	std::vector<float> selectedDepths;
	for (size_t index = 0; index < candidate.inputPlanes.size(); ++index)
	{
		names.push_back(candidate.inputPlanes[index].name);
		if (index < 32U && !sliceEnabled_[index])
			continue;
		selectedPlanes.push_back(candidate.inputPlanes[index]);
		selectedDepths.push_back(std::max(-10.0f, std::min(10.0f,
			depth_ + (index < 32U ? sliceDepths_[index] : 0.0f))));
	}
	ConfigureSliceDepthParams(candidate.inputPlanes.size(), names);
	candidate.inputPlanes = std::move(selectedPlanes);
	selectedSliceCount_ = static_cast<unsigned int>(candidate.inputPlanes.size());
	ApplyINSTARInputPlaneDepths(candidate, selectedDepths);

	scene_ = std::move(candidate);
	renderer_.Upload(scene_);
	activePath_ = templatePath_;
	activeSignature_ = signature;
	sceneDirty_ = false;
	Log("XML cargado en vivo: " + std::to_string(selectedSliceCount_) + "/" +
		std::to_string(visibleSliceCount_) + " slices activos");
	return true;
}

FFResult INSTAR_2::Init()
{
	return renderer_.Init();
}

void INSTAR_2::Clean()
{
	renderer_.Clean();
	scene_ = INSTARScene();
}

void INSTAR_2::Update()
{
	FollowActivePresetIfNeeded();
	const bool force = reloadRequested_;
	reloadRequested_ = false;
	ReloadSceneIfNeeded(force);
}

FFResult INSTAR_2::Render(ProcessOpenGLStruct* inputTextures)
{
	GLuint inputTexture = 0;
	bool useTexture = false;
	if (inputTextures != nullptr && inputTextures->numInputTextures > 0 && inputTextures->inputTextures != nullptr &&
		inputTextures->inputTextures[0] != nullptr)
	{
		inputTexture = inputTextures->inputTextures[0]->Handle;
		useTexture = inputTexture != 0;
	}
	const int view = static_cast<int>(GetFloatParameter(PARAM_VIEW));
	const INSTARCamera camera = SelectINSTARCamera(view, yaw_, pitch_, zoom_, cameraDistance_);
	return renderer_.Render(
		scene_, camera, brightness_, currentViewport.width, currentViewport.height, inputTexture, useTexture);
}

FFResult INSTAR_2::SetFloatParameter(unsigned int index, float value)
{
	if (index == PARAM_FOLLOW_ACTIVE_XML)
	{
		followActivePreset_ = value > 0.5f;
		sceneDirty_ = sceneDirty_ || followActivePreset_;
	}
	else if (index == PARAM_USE_ACTIVE_XML)
	{
		if (value != 0.0f)
		{
			followActivePreset_ = true;
			GetParam("FollowActiveXML")->SetValue(1.0f);
			templatePath_.clear();
			lastAttemptPath_.clear();
			lastAttemptSignature_ = {0, 0};
			sceneDirty_ = true;
		}
	}
	else if (index == PARAM_RELOAD_XML)
	{
		if (value != 0.0f)
			reloadRequested_ = true;
	}
	else if (index == PARAM_YAW)
		yaw_ = std::max(0.0f, std::min(1.0f, value));
	else if (index == PARAM_PITCH)
		pitch_ = std::max(0.0f, std::min(1.0f, value));
	else if (index == PARAM_ZOOM)
		zoom_ = std::max(0.0f, std::min(1.0f, value));
	else if (index == PARAM_BRIGHTNESS)
		brightness_ = std::max(0.0f, std::min(1.0f, value));
	else if (index == PARAM_DEPTH)
	{
		depth_ = std::max(-10.0f, std::min(10.0f, value));
		sceneDirty_ = true;
	}
	else if (index == PARAM_CAMERA_DISTANCE)
		cameraDistance_ = std::max(1.0f, std::min(20.0f, value));
	else if (index >= PARAM_SLICE_DEPTH_01 && index <= PARAM_SLICE_DEPTH_32)
	{
		sliceDepths_[index - PARAM_SLICE_DEPTH_01] = std::max(-10.0f, std::min(10.0f, value));
		sceneDirty_ = true;
	}
	else if (index >= PARAM_SLICE_ENABLED_01 && index <= PARAM_SLICE_ENABLED_32)
	{
		sliceEnabled_[index - PARAM_SLICE_ENABLED_01] = value > 0.5f;
		sceneDirty_ = true;
	}
	return Effect::SetFloatParameter(index, value);
}

FFResult INSTAR_2::SetTextParameter(unsigned int index, const char* value)
{
	if (index == PARAM_TEMPLATE_XML)
	{
		templatePath_ = value == nullptr ? std::string() : std::string(value);
		followActivePreset_ = false;
		GetParam("FollowActiveXML")->SetValue(0.0f);
		lastAttemptPath_.clear();
		lastAttemptSignature_ = {0, 0};
		sceneDirty_ = true;
		return FF_SUCCESS;
	}
	return Effect::SetTextParameter(index, value);
}

char* INSTAR_2::GetTextParameter(unsigned int index)
{
	if (index != PARAM_TEMPLATE_XML)
		return Effect::GetTextParameter(index);
	static char buffer[4096];
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(templatePath_.size(), sizeof(buffer) - 1U);
	std::copy(templatePath_.begin(), templatePath_.begin() + static_cast<std::ptrdiff_t>(length), buffer);
	return buffer;
}
