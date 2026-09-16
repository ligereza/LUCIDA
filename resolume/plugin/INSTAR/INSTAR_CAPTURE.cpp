#include "INSTAR_CAPTURE.h"

#include <algorithm>

using namespace ffglqs;

static CFFGLPluginInfo PluginInfo(
	PluginFactory< INSTARCapture >,
	"IC01",
	"INSTAR CAPTURE",
	2,
	1,
	1,
	0,
	FF_SOURCE,
	"3D venue and LED surface visualizer for Resolume.",
	"LUCIDA RESOLUME"
);

INSTARCapture::INSTARCapture()
{
	SetFragmentShader(R"(
		void main()
		{
			fragColor = vec4(0.005, 0.008, 0.015, 1.0);
		}
	)");
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

FFResult INSTARCapture::Init()
{
	const char* vertexShader = R"(
		#version 410 core
		layout(location = 0) in vec3 position;
		layout(location = 1) in vec3 colour;
		uniform float u_yaw;
		uniform float u_pitch;
		uniform float u_zoom;
		uniform float u_aspect;
		out vec3 v_colour;
		void main()
		{
			float cy = cos(u_yaw);
			float sy = sin(u_yaw);
			vec3 p = vec3(cy * position.x - sy * position.z, position.y, sy * position.x + cy * position.z);
			float cp = cos(u_pitch);
			float sp = sin(u_pitch);
			p = vec3(p.x, cp * p.y - sp * p.z, sp * p.y + cp * p.z);
			p.z += 3.5;
			float perspective = u_zoom / max(0.5, p.z);
			gl_Position = vec4(p.x * perspective / max(0.1, u_aspect), p.y * perspective, 0.0, 1.0);
			v_colour = colour;
		}
	)";
	const char* fragmentShader = R"(
		#version 410 core
		in vec3 v_colour;
		uniform float u_brightness;
		out vec4 fragColor;
		void main()
		{
			fragColor = vec4(v_colour * u_brightness, 1.0);
		}
	)";
	if (!sceneShader.Compile(vertexShader, fragmentShader))
		return FF_FAIL;
	glGenVertexArrays(1, &vao);
	glGenBuffers(1, &vbo);
	if (vao == 0 || vbo == 0)
		return FF_FAIL;
	LoadScene();
	UploadScene();
	return FF_SUCCESS;
}

void INSTARCapture::Clean()
{
	if (vbo != 0)
		glDeleteBuffers(1, &vbo);
	if (vao != 0)
		glDeleteVertexArrays(1, &vao);
	vbo = 0;
	vao = 0;
	sceneShader.FreeGLResources();
}

bool INSTARCapture::LoadScene()
{
	if (modelPath.empty())
	{
		scene = BuildINSTARDemoScene();
		loadedPath.clear();
		sceneDirty = false;
		return true;
	}
	std::string error;
	INSTARScene loaded;
	if (!LoadINSTARObj(modelPath, loaded, error))
	{
		FFGLLog::LogToHost("INSTAR CAPTURE: OBJ inválido; se usa escena demo");
		scene = BuildINSTARDemoScene();
		loadedPath.clear();
		sceneDirty = false;
		return false;
	}
	scene = loaded;
	loadedPath = modelPath;
	sceneDirty = false;
	return true;
}

void INSTARCapture::UploadScene()
{
	if (vao == 0 || vbo == 0)
		return;
	ffglex::ScopedShaderBinding binding(sceneShader.GetGLID());
	glBindVertexArray(vao);
	glBindBuffer(GL_ARRAY_BUFFER, vbo);
	glBufferData(GL_ARRAY_BUFFER, static_cast<GLsizeiptr>(scene.lineVertices.size() * sizeof(INSTARVertex)), scene.lineVertices.data(), GL_STATIC_DRAW);
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(0));
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(sizeof(INSTARVec3)));
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glBindVertexArray(0);
}

void INSTARCapture::Update()
{
	if (sceneDirty || loadedPath != modelPath)
	{
		LoadScene();
		UploadScene();
	}
}

FFResult INSTARCapture::Render(ProcessOpenGLStruct*)
{
	glDisable(GL_DEPTH_TEST);
	glClearColor(0.005f, 0.008f, 0.015f, 1.0f);
	glClear(GL_COLOR_BUFFER_BIT);
	if (!sceneShader.IsReady() || scene.lineVertices.empty())
		return FF_SUCCESS;
	float selectedYaw = (yaw - 0.5f) * 6.2831853f;
	float selectedPitch = (pitch - 0.5f) * 2.2f;
	const int view = static_cast<int>(GetFloatParameter(PARAM_VIEW));
	if (view == 0)
	{
		selectedYaw = 0.75f;
		selectedPitch = -0.75f;
	}
	else if (view == 1)
	{
		selectedYaw = 0.0f;
		selectedPitch = -0.15f;
	}
	const float aspect = currentViewport.height > 0 ? static_cast<float>(currentViewport.width) / static_cast<float>(currentViewport.height) : 1.777f;
	ffglex::ScopedShaderBinding binding(sceneShader.GetGLID());
	sceneShader.Set("u_yaw", selectedYaw);
	sceneShader.Set("u_pitch", selectedPitch);
	sceneShader.Set("u_zoom", 0.8f + zoom * 1.8f);
	sceneShader.Set("u_aspect", aspect);
	sceneShader.Set("u_brightness", 0.2f + brightness * 1.2f);
	glBindVertexArray(vao);
	glDrawArrays(GL_LINES, 0, static_cast<GLsizei>(scene.lineVertices.size()));
	glBindVertexArray(0);
	return FF_SUCCESS;
}

FFResult INSTARCapture::SetFloatParameter(unsigned int index, float value)
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

FFResult INSTARCapture::SetTextParameter(unsigned int index, const char* value)
{
	if (index == PARAM_MODEL_FILE)
	{
		modelPath = value == nullptr ? "" : value;
		sceneDirty = true;
		return FF_SUCCESS;
	}
	return Source::SetTextParameter(index, value);
}

char* INSTARCapture::GetTextParameter(unsigned int index)
{
	static char buffer[4096];
	if (index != PARAM_MODEL_FILE)
		return Source::GetTextParameter(index);
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(modelPath.size(), sizeof(buffer) - 1);
	std::copy(modelPath.begin(), modelPath.begin() + length, buffer);
	return buffer;
}
