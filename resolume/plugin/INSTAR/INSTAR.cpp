#include "INSTAR.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <sstream>
#include <utility>

#ifdef _WIN32
#include <direct.h>
#include <sys/stat.h>
#else
#include <sys/stat.h>
#endif

using namespace ffglqs;

namespace
{
constexpr int MODE_RASTER_PIXEL_MAP = 0;
constexpr int MODE_XML_PLANES = 1;
constexpr int MODE_PLANO_3D = 2;

float BoundedFloat(float value, float fallback, float minimum, float maximum)
{
	if (!std::isfinite(value))
		return fallback;
	return std::max(minimum, std::min(maximum, value));
}

std::pair<long long, long long> GetFileSignature(const std::string& path)
{
	if (path.empty())
		return {0, 0};
#ifdef _WIN32
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

std::string PathKey(const std::string& path)
{
	std::string value = path;
#ifdef _WIN32
	char fullPath[32768] = {};
	if (_fullpath(fullPath, path.c_str(), sizeof(fullPath)) != nullptr)
		value = fullPath;
#endif
	for (char& character : value)
	{
		if (character == '\\')
			character = '/';
		character = static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
	}
	return value;
}

bool PathsEquivalent(const std::string& left, const std::string& right)
{
	return !left.empty() && !right.empty() && PathKey(left) == PathKey(right);
}
}

static CFFGLPluginInfo PluginInfo(
	PluginFactory< INSTAR >,
	"IN01",
	"INSTAR",
	2,
	1,
	1,
	0,
	FF_SOURCE,
	"Raster mapping, Advanced Output planes and plan extrusion preview for Resolume.",
	"LUCIDA RESOLUME"
);

INSTAR::INSTAR()
{
	AddParam(ParamOption::Create("Mode", {
		{"RASTER_PIXEL_MAP", static_cast<float>(MODE_RASTER_PIXEL_MAP)},
		{"XML_PLANES", static_cast<float>(MODE_XML_PLANES)},
		{"PLANO_3D", static_cast<float>(MODE_PLANO_3D)},
	}, MODE_XML_PLANES));
	AddParam(Param::Create("MapFile", FF_TYPE_FILE, 0.0f));
	AddParam(Param::Create("TemplateXML", FF_TYPE_FILE, 0.0f));
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
	AddParam(ParamRange::Create("Depth", depth, ParamRange::Range(-10.0f, 10.0f)));
	for (unsigned int index = 0; index < 32U; ++index)
	{
		const std::string name = std::string("SliceDepth") + (index < 9U ? "0" : "") + std::to_string(index + 1U);
		AddParam(ParamRange::Create(name, 0.0f, ParamRange::Range(-10.0f, 10.0f)));
		SetParamVisibility(PARAM_SLICE_DEPTH_01 + index, false, false);
	}
	AddParam(ParamRange::Create("CameraDistance", cameraDistance, ParamRange::Range(1.0f, 20.0f)));
	AddParam(Param::Create("PlanFile", FF_TYPE_FILE, 0.0f));
	AddParam(ParamRange::Create("PlanScale", planScale, ParamRange::Range(0.001f, 10.0f)));
	AddParam(ParamRange::Create("ExtrusionHeight", extrusionHeight, ParamRange::Range(0.0f, 20.0f)));
}

void INSTAR::ConfigureSliceDepthParams(size_t sliceCount)
{
	const size_t visibleCount = std::min<size_t>(sliceCount, 32U);
	for (unsigned int index = 0; index < 32U; ++index)
		SetParamVisibility(PARAM_SLICE_DEPTH_01 + index, index < visibleCount, true);
	if (sliceCount > 32U)
		FFGLLog::LogToHost("INSTAR: hay más de 32 slices; los controles visibles cubren los primeros 32");
}

FFResult INSTAR::Init()
{
	if (renderer.Init() != FF_SUCCESS)
		return FF_FAIL;
	const char* rasterVertexShader = R"(
		#version 410 core
		layout(location = 0) in vec3 position;
		layout(location = 1) in vec2 texCoord;
		uniform vec2 u_scale;
		out vec2 i_uv;
		void main()
		{
			gl_Position = vec4(position.xy * u_scale, position.z, 1.0);
			i_uv = texCoord;
		}
	)";
	const char* rasterFragmentShader = R"(
		#version 410 core
		in vec2 i_uv;
		uniform sampler2D inputTexture;
		uniform float u_brightness;
		out vec4 fragColor;
		void main()
		{
			vec4 pixel = texture(inputTexture, i_uv);
			fragColor = vec4(pixel.rgb * u_brightness, pixel.a);
		}
	)";
	const char* overlayVertexShader = R"(
		#version 410 core
		layout(location = 0) in vec3 position;
		layout(location = 1) in vec3 colour;
		uniform vec2 u_scale;
		out vec3 v_colour;
		void main()
		{
			gl_Position = vec4(position.xy * u_scale, 0.0, 1.0);
			v_colour = colour;
		}
	)";
	const char* overlayFragmentShader = R"(
		#version 410 core
		in vec3 v_colour;
		out vec4 fragColor;
		void main()
		{
			fragColor = vec4(v_colour, 1.0);
		}
	)";
	if (!rasterShader.Compile(rasterVertexShader, rasterFragmentShader) ||
		!rasterOverlayShader.Compile(overlayVertexShader, overlayFragmentShader) ||
		!rasterQuad.Initialise(true))
		return FF_FAIL;
	glGenTextures(1, &rasterTexture);
	glGenVertexArrays(1, &rasterOverlayVao);
	glGenBuffers(1, &rasterOverlayVbo);
	if (rasterTexture == 0 || rasterOverlayVao == 0 || rasterOverlayVbo == 0)
		return FF_FAIL;
	LoadScene();
	UploadScene();
	LoadRaster();
	return FF_SUCCESS;
}

void INSTAR::Clean()
{
	if (rasterTexture != 0)
		glDeleteTextures(1, &rasterTexture);
	if (rasterOverlayVbo != 0)
		glDeleteBuffers(1, &rasterOverlayVbo);
	if (rasterOverlayVao != 0)
		glDeleteVertexArrays(1, &rasterOverlayVao);
	rasterTexture = 0;
	rasterOverlayVbo = 0;
	rasterOverlayVao = 0;
	rasterQuad.Release();
	rasterShader.FreeGLResources();
	rasterOverlayShader.FreeGLResources();
	renderer.Clean();
}

bool INSTAR::LoadScene()
{
	const int mode = static_cast<int>(GetFloatParameter(PARAM_MODE));
	if (mode == MODE_XML_PLANES)
	{
		const std::string activeTemplatePath = previewTemplatePath.empty() ? templatePath : previewTemplatePath;
		if (activeTemplatePath.empty())
		{
			scene = BuildINSTARFlatPlaneDemoScene();
			ConfigureSliceDepthParams(0);
			loadedFileSignature = {0, 0};
			loadedPath.clear();
			sceneDirty = false;
			return true;
		}
		std::string error;
		INSTARScene loaded;
		if (!LoadINSTARAdvancedOutputPlanes(activeTemplatePath, loaded, error))
		{
			const std::string message = "INSTAR: TemplateXML inválido para XML_PLANES: " + error;
			FFGLLog::LogToHost(message.c_str());
			scene = BuildINSTARFlatPlaneDemoScene();
			ConfigureSliceDepthParams(0);
			loadedFileSignature = GetFileSignature(activeTemplatePath);
			loadedPath = activeTemplatePath;
			sceneDirty = false;
			return false;
		}
		ConfigureSliceDepthParams(loaded.inputPlanes.size());
		std::vector<float> depths(loaded.inputPlanes.size(), BoundedFloat(depth, 0.0f, -10.0f, 10.0f));
		for (size_t index = 0; index < depths.size() && index < 32U; ++index)
			depths[index] = BoundedFloat(depth + sliceDepths[index], 0.0f, -10.0f, 10.0f);
		ApplyINSTARInputPlaneDepths(loaded, depths);
		scene = loaded;
		loadedFileSignature = GetFileSignature(activeTemplatePath);
		loadedPath = activeTemplatePath;
		sceneDirty = false;
		return true;
	}
	if (mode == MODE_PLANO_3D)
	{
		// A plan is a separate input contract: its 2D SVG geometry becomes
		// the front-view footprint and the plugin extrudes that geometry. It
		// must never fall back to XML slices or to a fictional venue shell.
		if (planPath.empty())
		{
			scene = INSTARScene();
			ConfigureSliceDepthParams(0);
			loadedFileSignature = {0, 0};
			loadedPath.clear();
			sceneDirty = false;
			return true;
		}
		std::string error;
		INSTARScene loaded;
		if (!LoadINSTARPlanSvg(planPath, loaded, error, extrusionHeight, planScale))
		{
			const std::string message = "INSTAR: PlanFile inválido para PLANO_3D: " + error;
			FFGLLog::LogToHost(message.c_str());
			scene = INSTARScene();
			ConfigureSliceDepthParams(0);
			loadedFileSignature = GetFileSignature(planPath);
			loadedPath = planPath;
			sceneDirty = false;
			return false;
		}
		ConfigureSliceDepthParams(0);
		scene = loaded;
		loadedFileSignature = GetFileSignature(planPath);
		loadedPath = planPath;
		sceneDirty = false;
		return true;
	}
	if (mode == MODE_RASTER_PIXEL_MAP)
	{
		// RASTER_PIXEL_MAP owns the frame. Keep a small scene available for a
		// later mode switch, but does not load XML while raster is active.
		scene = BuildINSTARFlatPlaneDemoScene();
		ConfigureSliceDepthParams(0);
		loadedRasterSignature = {0, 0};
		loadedFileSignature = {0, 0};
		loadedPath.clear();
		sceneDirty = false;
		return true;
	}
	return false;
}

void INSTAR::UploadScene()
{
	renderer.Upload(scene);
}

bool INSTAR::LoadRaster()
{
	rasterDirty = false;
	rasterReady = false;
	if (mapPath.empty())
	{
		loadedRasterSignature = {0, 0};
		return true;
	}
	std::string error;
	INSTARImage loaded;
	if (!LoadINSTARImage(mapPath, loaded, error))
	{
		std::string message = "INSTAR: MapFile no es un raster compatible: " + error;
		FFGLLog::LogToHost(message.c_str());
		loadedRasterSignature = GetFileSignature(mapPath);
		return false;
	}
	rasterImage = loaded;
	rasterSurfaces = DetectINSTARSurfaces(rasterImage, rasterImage.width, rasterImage.height);
	BuildRasterOverlay();
	glBindTexture(GL_TEXTURE_2D, rasterTexture);
	glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glTexImage2D(
		GL_TEXTURE_2D,
		0,
		GL_RGBA,
		static_cast<GLsizei>(rasterImage.width),
		static_cast<GLsizei>(rasterImage.height),
		0,
		GL_RGBA,
		GL_UNSIGNED_BYTE,
		rasterImage.rgba.data()
	);
	glBindTexture(GL_TEXTURE_2D, 0);
	rasterReady = true;
	loadedRasterSignature = GetFileSignature(mapPath);
	return true;
}

void INSTAR::BuildRasterOverlay()
{
	rasterOverlayVertices.clear();
	if (rasterImage.width == 0 || rasterImage.height == 0 || rasterOverlayVao == 0 || rasterOverlayVbo == 0)
		return;
	for (size_t index = 0; index < rasterSurfaces.size(); ++index)
	{
		const INSTARSurface& surface = rasterSurfaces[index];
		const float left = surface.x / static_cast<float>(rasterImage.width) * 2.0f - 1.0f;
		const float right = (surface.x + surface.width) / static_cast<float>(rasterImage.width) * 2.0f - 1.0f;
		const float top = 1.0f - surface.y / static_cast<float>(rasterImage.height) * 2.0f;
		const float bottom = 1.0f - (surface.y + surface.height) / static_cast<float>(rasterImage.height) * 2.0f;
		const float red = 0.15f + static_cast<float>((index * 37U) % 55U) / 100.0f;
		const float green = 0.70f + static_cast<float>((index * 19U) % 25U) / 100.0f;
		const float blue = 0.70f + static_cast<float>((index * 11U) % 25U) / 100.0f;
		const INSTARVec3 points[] = {
			{left, top, 0.0f}, {right, top, 0.0f},
			{right, top, 0.0f}, {right, bottom, 0.0f},
			{right, bottom, 0.0f}, {left, bottom, 0.0f},
			{left, bottom, 0.0f}, {left, top, 0.0f},
		};
		for (const INSTARVec3& point : points)
			rasterOverlayVertices.push_back({point, red, green, blue});
	}
	ffglex::ScopedShaderBinding binding(rasterOverlayShader.GetGLID());
	glBindVertexArray(rasterOverlayVao);
	glBindBuffer(GL_ARRAY_BUFFER, rasterOverlayVbo);
	glBufferData(GL_ARRAY_BUFFER, static_cast<GLsizeiptr>(rasterOverlayVertices.size() * sizeof(INSTARVertex)), rasterOverlayVertices.data(), GL_STATIC_DRAW);
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(0));
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(sizeof(INSTARVec3)));
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glBindVertexArray(0);
}

FFResult INSTAR::RenderRaster()
{
	glDisable(GL_DEPTH_TEST);
	glClearColor(0.005f, 0.005f, 0.007f, 1.0f);
	glClear(GL_COLOR_BUFFER_BIT);
	if (!rasterReady || !rasterShader.IsReady() || rasterTexture == 0)
		return FF_SUCCESS;
	const unsigned int width = currentViewport.width > 0 ? currentViewport.width : 1920;
	const unsigned int height = currentViewport.height > 0 ? currentViewport.height : 1080;
	const float imageAspect = static_cast<float>(rasterImage.width) / static_cast<float>(rasterImage.height);
	const float viewportAspect = static_cast<float>(width) / static_cast<float>(height);
	float scaleX = 1.0f;
	float scaleY = 1.0f;
	if (imageAspect > viewportAspect)
		scaleY = viewportAspect / imageAspect;
	else
		scaleX = imageAspect / viewportAspect;
	ffglex::ScopedShaderBinding binding(rasterShader.GetGLID());
	rasterShader.Set("inputTexture", 0);
	rasterShader.Set("u_scale", scaleX, scaleY);
	rasterShader.Set("u_brightness", 0.2f + brightness * 1.2f);
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, rasterTexture);
	rasterQuad.Draw();
	glBindTexture(GL_TEXTURE_2D, 0);
	if (!rasterOverlayVertices.empty() && rasterOverlayShader.IsReady())
	{
		ffglex::ScopedShaderBinding overlayBinding(rasterOverlayShader.GetGLID());
		rasterOverlayShader.Set("u_scale", scaleX, scaleY);
		glBindVertexArray(rasterOverlayVao);
		glLineWidth(2.0f);
		glDrawArrays(GL_LINES, 0, static_cast<GLsizei>(rasterOverlayVertices.size()));
		glBindVertexArray(0);
	}
	return FF_SUCCESS;
}

void INSTAR::Update()
{
	const int mode = static_cast<int>(GetFloatParameter(PARAM_MODE));
	const bool sceneFileMode = mode == MODE_XML_PLANES || mode == MODE_PLANO_3D;
	const std::string desiredPath = mode == MODE_XML_PLANES ?
		(previewTemplatePath.empty() ? templatePath : previewTemplatePath) :
		(mode == MODE_PLANO_3D ? planPath : std::string());
	const std::pair<long long, long long> desiredSignature = sceneFileMode ? GetFileSignature(desiredPath) : std::pair<long long, long long>{0, 0};
	if (sceneDirty || loadedPath != desiredPath || (sceneFileMode && desiredSignature != loadedFileSignature))
	{
		LoadScene();
		UploadScene();
	}
	const std::pair<long long, long long> desiredRasterSignature = (mode == MODE_XML_PLANES || mode == MODE_RASTER_PIXEL_MAP) ? GetFileSignature(mapPath) : std::pair<long long, long long>{0, 0};
	if (rasterDirty || ((mode == MODE_XML_PLANES || mode == MODE_RASTER_PIXEL_MAP) && desiredRasterSignature != loadedRasterSignature))
		LoadRaster();
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
	if (!templatePath.empty() && PathsEquivalent(templatePath, outputPath))
	{
		FFGLLog::LogToHost("INSTAR: OutputXML no puede sobrescribir TemplateXML");
		return false;
	}

	INSTARImage image;
	std::string error;
	if (!LoadINSTARImage(mapPath, image, error))
	{
		std::string message = "INSTAR: MapFile no es un raster compatible: " + error;
		FFGLLog::LogToHost(message.c_str());
		return false;
	}
	const std::vector<INSTARSurface> surfaces = DetectINSTARSurfaces(image, image.width, image.height);
	if (surfaces.empty())
	{
		FFGLLog::LogToHost("INSTAR: no se detectaron superficies; no se genera XML");
		return false;
	}
	std::string xml;
	std::string exportMessage;
	if (templatePath.empty())
	{
		xml = BuildINSTARAdvancedOutputXml(image.width, image.height, surfaces);
		exportMessage = "INSTAR: AdvancedOutput.xml virtual generado; sin routing físico confirmado";
	}
	else
	{
		std::ifstream templateFile(templatePath.c_str());
		if (!templateFile.is_open())
		{
			FFGLLog::LogToHost("INSTAR: no se pudo abrir TemplateXML");
			return false;
		}
		const std::string templateXml((std::istreambuf_iterator<char>(templateFile)), std::istreambuf_iterator<char>());
		INSTARTemplateInfo templateInfo;
		std::string templateError;
		if (!ReadINSTARAdvancedOutputTemplateInfo(templateXml, templateInfo, templateError))
		{
			const std::string message = "INSTAR: TemplateXML inválido: " + templateError;
			FFGLLog::LogToHost(message.c_str());
			return false;
		}
		const std::vector<INSTARSurfaceMapping> mappings = ScaleINSTARSurfacesToTemplate(
			surfaces, image.width, image.height, templateInfo);
		xml = BuildINSTARAdvancedOutputXmlFromTemplate(templateXml, mappings);
		exportMessage = "INSTAR: AdvancedOutput.xml generado desde template; routing físico conservado";
	}
	if (xml.empty())
	{
		FFGLLog::LogToHost("INSTAR: no se pudo construir un Advanced Output compatible");
		return false;
	}
	std::ofstream file(outputPath.c_str(), std::ios::out | std::ios::trunc);
	if (!file.is_open())
	{
		FFGLLog::LogToHost("INSTAR: no se pudo escribir OutputXML");
		return false;
	}
	file << xml;
	const bool written = file.good();
	file.close();
	if (written)
	{
		INSTARScene generatedPreview;
		std::string generatedError;
		if (!LoadINSTARAdvancedOutputPlanes(outputPath, generatedPreview, generatedError))
		{
			const std::string message = "INSTAR: OutputXML escrito pero no es reutilizable en XML_PLANES: " + generatedError;
			FFGLLog::LogToHost(message.c_str());
			return false;
		}
		previewTemplatePath = outputPath;
		loadedPath.clear();
		sceneDirty = true;
		FFGLLog::LogToHost(exportMessage.c_str());
		FFGLLog::LogToHost("INSTAR: OutputXML validado y cargado automáticamente en XML_PLANES");
	}
	else
		FFGLLog::LogToHost("INSTAR: error al escribir AdvancedOutput.xml");
	return written;
}

FFResult INSTAR::Render(ProcessOpenGLStruct*)
{
	if (static_cast<int>(GetFloatParameter(PARAM_MODE)) == MODE_RASTER_PIXEL_MAP)
		return RenderRaster();
	const int view = static_cast<int>(GetFloatParameter(PARAM_VIEW));
	const INSTARCamera camera = SelectINSTARCamera(view, yaw, pitch, zoom, cameraDistance);
	return renderer.Render(
		scene,
		camera,
		brightness,
		currentViewport.width,
		currentViewport.height,
		rasterTexture,
		static_cast<int>(GetFloatParameter(PARAM_MODE)) == MODE_XML_PLANES && rasterReady
	);
}

FFResult INSTAR::SetFloatParameter(unsigned int index, float value)
{
	if (index == PARAM_EXPORT_MAP_XML)
	{
		if (value != 0.0f)
			exportRequested = true;
	}
	else if (index == PARAM_MODE)
	{
		sceneDirty = true;
		if (static_cast<int>(value) == MODE_XML_PLANES || static_cast<int>(value) == MODE_RASTER_PIXEL_MAP)
			rasterDirty = true;
	}
	else if (index == PARAM_DEPTH)
	{
		depth = BoundedFloat(value, 0.0f, -10.0f, 10.0f);
		sceneDirty = true;
	}
	else if (index == PARAM_YAW)
		yaw = BoundedFloat(value, 0.5f, 0.0f, 1.0f);
	else if (index == PARAM_PITCH)
		pitch = BoundedFloat(value, 0.5f, 0.0f, 1.0f);
	else if (index == PARAM_ZOOM)
		zoom = BoundedFloat(value, 0.55f, 0.0f, 1.0f);
	else if (index == PARAM_BRIGHTNESS)
		brightness = BoundedFloat(value, 0.85f, 0.0f, 1.0f);
	else if (index == PARAM_CAMERA_DISTANCE)
		cameraDistance = BoundedFloat(value, 3.5f, 1.0f, 20.0f);
	else if (index == PARAM_PLAN_SCALE)
	{
		planScale = BoundedFloat(value, 1.0f, 0.001f, 10.0f);
		sceneDirty = true;
	}
	else if (index == PARAM_EXTRUSION_HEIGHT)
	{
		extrusionHeight = BoundedFloat(value, 3.0f, 0.0f, 20.0f);
		sceneDirty = true;
	}
	else if (index >= PARAM_SLICE_DEPTH_01 && index <= PARAM_SLICE_DEPTH_32)
	{
		sliceDepths[index - PARAM_SLICE_DEPTH_01] = BoundedFloat(value, 0.0f, -10.0f, 10.0f);
		sceneDirty = true;
	}
	return Source::SetFloatParameter(index, value);
}

FFResult INSTAR::SetTextParameter(unsigned int index, const char* value)
{
	const std::string safeValue = value == nullptr ? "" : value;
	if (index == PARAM_MAP_FILE)
	{
		mapPath = safeValue;
		rasterDirty = true;
		return FF_SUCCESS;
	}
	if (index == PARAM_TEMPLATE_XML)
	{
		templatePath = safeValue;
		previewTemplatePath.clear();
		sceneDirty = true;
		return FF_SUCCESS;
	}
	if (index == PARAM_OUTPUT_XML)
	{
		outputPath = safeValue.empty() ? "INSTAR_AdvancedOutput.xml" : safeValue;
		previewTemplatePath.clear();
		sceneDirty = true;
		return FF_SUCCESS;
	}
	if (index == PARAM_PLAN_FILE)
	{
		planPath = safeValue;
		sceneDirty = true;
		return FF_SUCCESS;
	}
	return Source::SetTextParameter(index, value);
}

char* INSTAR::GetTextParameter(unsigned int index)
{
	static char buffer[4096];
	const std::string* value = nullptr;
	if (index == PARAM_MAP_FILE)
		value = &mapPath;
	else if (index == PARAM_TEMPLATE_XML)
		value = &templatePath;
	else if (index == PARAM_OUTPUT_XML)
		value = &outputPath;
	else if (index == PARAM_PLAN_FILE)
		value = &planPath;
	if (value == nullptr)
		return Source::GetTextParameter(index);
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(value->size(), sizeof(buffer) - 1);
	std::copy(value->begin(), value->begin() + length, buffer);
	return buffer;
}
