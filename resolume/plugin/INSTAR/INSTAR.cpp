#include "INSTAR.h"

#include <algorithm>
#include <fstream>
#include <iterator>

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
	AddParam(ParamOption::Create("Mode", {
		{"VENUE_3D", 0.0f},
		{"RASTER_PIXEL_MAP", 1.0f},
	}, 0));
	AddParam(Param::Create("VenueFile", FF_TYPE_FILE, 0.0f));
	AddParam(Param::Create("EdgeBudget", FF_TYPE_INTEGER, 800.0f));
	AddParam(ParamOption::Create("ConfidenceCeiling", {
		{"MEDIDO", 0.0f},
		{"CITADO", 1.0f},
		{"AJUSTADO", 2.0f},
		{"APORTADO", 3.0f},
		{"TODOS", 4.0f},
	}, 4));
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
	SetParamRange(PARAM_EDGE_BUDGET, 1.0f, 1000000.0f);
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
	LoadVenue();
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
	const unsigned int edgeBudget = static_cast<unsigned int>(std::max(1.0f, GetFloatParameter(PARAM_EDGE_BUDGET)));
	const int confidenceCeiling = static_cast<int>(std::max(0.0f, std::min(4.0f, GetFloatParameter(PARAM_CONFIDENCE_CEILING))));
	if (!LoadINSTARVenueJson(venuePath, loaded, error, edgeBudget, confidenceCeiling))
	{
		FFGLLog::LogToHost("INSTAR: VenueFile inválido; se usa escena demo");
		scene = BuildINSTARDemoScene();
		loadedPath.clear();
		sceneDirty = false;
		return false;
	}
	scene = loaded;
	if (scene.omittedEdges > 0)
	{
		const std::string message = "INSTAR: EdgeBudget omitió " + std::to_string(scene.omittedEdges) +
			" de " + std::to_string(scene.totalEdges) + " aristas";
		FFGLLog::LogToHost(message.c_str());
	}
	loadedPath = venuePath;
	sceneDirty = false;
	return true;
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
		return true;
	std::string error;
	INSTARImage loaded;
	if (!LoadINSTARImage(mapPath, loaded, error))
	{
		std::string message = "INSTAR: MapFile no es un raster compatible: " + error;
		FFGLLog::LogToHost(message.c_str());
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
	if (sceneDirty || loadedPath != venuePath)
	{
		LoadVenue();
		UploadScene();
	}
	if (rasterDirty && static_cast<int>(GetFloatParameter(PARAM_MODE)) == 1)
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
	if (templatePath.empty())
	{
		FFGLLog::LogToHost("INSTAR: TemplateXML vacío; se requiere un Advanced Output real");
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
	const std::vector<INSTARSurface> surfaces = DetectINSTARSurfaces(image, image.width, image.height);
	if (surfaces.empty())
	{
		FFGLLog::LogToHost("INSTAR: no se detectaron superficies; no se genera XML");
		return false;
	}
	const std::vector<INSTARSurfaceMapping> mappings = ScaleINSTARSurfacesToTemplate(
		surfaces, image.width, image.height, templateInfo);
	const std::string xml = BuildINSTARAdvancedOutputXmlFromTemplate(templateXml, mappings);
	if (xml.empty())
	{
		FFGLLog::LogToHost("INSTAR: no se pudo construir XML desde TemplateXML");
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
	FFGLLog::LogToHost(written ? "INSTAR: AdvancedOutput.xml generado desde raster" : "INSTAR: error al escribir AdvancedOutput.xml");
	return written;
}

FFResult INSTAR::Render(ProcessOpenGLStruct*)
{
	if (static_cast<int>(GetFloatParameter(PARAM_MODE)) == 1)
		return RenderRaster();
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
	else if (index == PARAM_MODE)
	{
		if (static_cast<int>(value) == 1)
			rasterDirty = true;
	}
	else if (index == PARAM_EDGE_BUDGET || index == PARAM_CONFIDENCE_CEILING)
	{
		sceneDirty = true;
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
		rasterDirty = true;
		return FF_SUCCESS;
	}
	if (index == PARAM_TEMPLATE_XML)
	{
		templatePath = safeValue;
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
	else if (index == PARAM_TEMPLATE_XML)
		value = &templatePath;
	else if (index == PARAM_OUTPUT_XML)
		value = &outputPath;
	if (value == nullptr)
		return Source::GetTextParameter(index);
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(value->size(), sizeof(buffer) - 1);
	std::copy(value->begin(), value->begin() + length, buffer);
	return buffer;
}
