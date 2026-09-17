#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

#include "DEPTH_FX.h"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <vector>

#include <ffgl/FFGLLib.h>
#include <ffglex/FFGLScopedSamplerActivation.h>
#include <ffglex/FFGLScopedShaderBinding.h>
#include <ffglex/FFGLScopedTextureBinding.h>
#include <ffglquickstart/FFGLParam.h>
#include <ffglquickstart/FFGLParamOption.h>
#include <ffglquickstart/FFGLParamRange.h>

using namespace ffglqs;

namespace
{
constexpr int kDepthTextureSize = 518;

static CFFGLPluginInfo PluginInfo(
	PluginFactory< DEPTHFX >,
	"DF01",
	"DEPTH_FX",
	2,
	1,
	1,
	0,
	FF_EFFECT,
	"Real-time Depth Anything depth-pass generator. Resolume supplies the input texture.",
	"LUCIDA RESOLUME"
);
}

DEPTHFX::DEPTHFX()
{
	AddParam(Param::Create("DepthEngine", FF_TYPE_FILE, 0.0f));
	AddParam(ParamRange::Create("DepthContrast", 1.0f, ParamRange::Range(0.0f, 4.0f)));
	AddParam(ParamOption::Create("DepthInvert", {{"OFF", 0.0f}, {"ON", 1.0f}}, 0.0f));
	AddParam(ParamRange::Create("DepthSmooth", 0.0f, ParamRange::Range(0.0f, 1.0f)));

	SetFragmentShader(R"(
		uniform sampler2D depthTexture;
		uniform vec2 depthResolution;
		uniform float DepthContrast;
		uniform float DepthInvert;
		uniform float DepthSmooth;
		uniform float DepthAvailable;

		vec3 inferno(float value)
		{
			value = clamp(value, 0.0, 1.0);
			const vec3 c0 = vec3(0.001462, 0.000466, 0.013866);
			const vec3 c1 = vec3(0.087411, 0.044556, 0.224813);
			const vec3 c2 = vec3(0.341500, 0.062325, 0.429425);
			const vec3 c3 = vec3(0.578304, 0.148039, 0.404411);
			const vec3 c4 = vec3(0.735683, 0.215906, 0.330245);
			const vec3 c5 = vec3(0.865006, 0.316822, 0.226055);
			const vec3 c6 = vec3(0.978422, 0.557937, 0.034931);
			const vec3 c7 = vec3(0.989587, 0.782004, 0.104551);
			const vec3 c8 = vec3(0.988362, 0.998364, 0.644924);
			if (value < 0.125) return mix(c0, c1, value / 0.125);
			if (value < 0.250) return mix(c1, c2, (value - 0.125) / 0.125);
			if (value < 0.375) return mix(c2, c3, (value - 0.250) / 0.125);
			if (value < 0.500) return mix(c3, c4, (value - 0.375) / 0.125);
			if (value < 0.625) return mix(c4, c5, (value - 0.500) / 0.125);
			if (value < 0.750) return mix(c5, c6, (value - 0.625) / 0.125);
			if (value < 0.875) return mix(c6, c7, (value - 0.750) / 0.125);
			return mix(c7, c8, (value - 0.875) / 0.125);
		}

		float readDepth(vec2 uv)
		{
			float centre = texture(depthTexture, uv).r;
			vec2 texel = 1.0 / max(depthResolution, vec2(1.0));
			float neighbours = 0.25 * (
				texture(depthTexture, uv + vec2(texel.x, 0.0)).r +
				texture(depthTexture, uv - vec2(texel.x, 0.0)).r +
				texture(depthTexture, uv + vec2(0.0, texel.y)).r +
				texture(depthTexture, uv - vec2(0.0, texel.y)).r
			);
			float depth = mix(centre, neighbours, clamp(DepthSmooth, 0.0, 1.0));
			depth = clamp((depth - 0.5) * DepthContrast + 0.5, 0.0, 1.0);
			return DepthInvert > 0.5 ? 1.0 - depth : depth;
		}

		void main()
		{
			vec4 original = texture(inputTexture, i_uv);
			if (DepthAvailable < 0.5)
			{
				fragColor = original;
				return;
			}
			float depth = readDepth(i_uv);
			fragColor = vec4(inferno(depth), 1.0);
		}
	)");
}

DEPTHFX::~DEPTHFX()
{
	Clean();
}

void DEPTHFX::Log(const std::string& message) const
{
	FFGLLog::LogToHost(message.c_str());
	char temporaryDirectory[MAX_PATH] = {};
	const DWORD length = GetTempPathA(static_cast<DWORD>(sizeof(temporaryDirectory)), temporaryDirectory);
	if (length == 0 || length >= sizeof(temporaryDirectory))
		return;
	std::ofstream runtimeLog(std::string(temporaryDirectory) + "DEPTH_FX_runtime.log", std::ios::app);
	if (runtimeLog)
		runtimeLog << message << '\n';
}

std::string DEPTHFX::DecodeFileUri(const char* value)
{
	if (value == nullptr)
		return std::string();
	std::string decoded(value);
	if (decoded.rfind("file://", 0) == 0)
	{
		decoded.erase(0, 7);
		if (decoded.rfind("/", 0) == 0 && decoded.size() > 2 && decoded[2] == ':')
			decoded.erase(decoded.begin());
	}
	std::string result;
	result.reserve(decoded.size());
	for (size_t index = 0; index < decoded.size(); ++index)
	{
		if (decoded[index] == '%' && index + 2 < decoded.size())
		{
			const std::string hex = decoded.substr(index + 1, 2);
			char* end = nullptr;
			const long parsed = std::strtol(hex.c_str(), &end, 16);
			if (end != nullptr && *end == '\0')
			{
				result.push_back(static_cast<char>(parsed));
				index += 2;
				continue;
			}
		}
		result.push_back(decoded[index] == '/' ? '\\' : decoded[index]);
	}
	return result;
}

std::string DEPTHFX::FindDefaultEngine()
{
	char userProfile[4096] = {};
	const DWORD length = GetEnvironmentVariableA("USERPROFILE", userProfile, static_cast<DWORD>(sizeof(userProfile)));
	if (length == 0 || length >= sizeof(userProfile))
		return std::string();
	const std::string candidate = std::string(userProfile) + "\\Desktop\\trash\\depth-anything-tensorrt\\depth_anything_v2_vitb.engine";
	const DWORD attributes = GetFileAttributesA(candidate.c_str());
	if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0)
		return std::string();
	return candidate;
}

void DEPTHFX::EnsureDepthTexture(int width, int height)
{
	if (depthTexture != 0 && depthWidth == width && depthHeight == height)
		return;
	ReleaseDepthTexture();
	glGenTextures(1, &depthTexture);
	if (depthTexture == 0)
		return;
	std::vector<float> neutral(static_cast<size_t>(width) * static_cast<size_t>(height) * 4, 0.5f);
	for (size_t index = 0; index < neutral.size(); index += 4)
		neutral[index + 3] = 1.0f;
	glBindTexture(GL_TEXTURE_2D, depthTexture);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glTexImage2D(
		GL_TEXTURE_2D,
		0,
		GL_RGBA32F,
		width,
		height,
		0,
		GL_RGBA,
		GL_FLOAT,
		neutral.data()
	);
	glBindTexture(GL_TEXTURE_2D, 0);
	depthWidth = width;
	depthHeight = height;
}

void DEPTHFX::ReleaseDepthTexture()
{
	if (depthTexture != 0)
		glDeleteTextures(1, &depthTexture);
	depthTexture = 0;
	depthWidth = 0;
	depthHeight = 0;
}

bool DEPTHFX::ProcessHostReadback(const FFGLTextureStruct& input, std::string& errorMessage)
{
	const size_t pixelCount = static_cast<size_t>(input.Width) * static_cast<size_t>(input.Height);
	if (pixelCount == 0)
	{
		errorMessage = "la textura de entrada no tiene píxeles";
		return false;
	}
	readbackPixels.resize(pixelCount * 4);
	GLint previousTexture = 0;
	glGetIntegerv(GL_TEXTURE_BINDING_2D, &previousTexture);
	glBindTexture(GL_TEXTURE_2D, input.Handle);
	glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, readbackPixels.data());
	const GLenum readError = glGetError();
	glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(previousTexture));
	if (readError != GL_NO_ERROR)
	{
		errorMessage = "glGetTexImage falló con código " + std::to_string(static_cast<unsigned int>(readError));
		return false;
	}

	hostDepthPixels.resize(static_cast<size_t>(depthWidth) * static_cast<size_t>(depthHeight) * 4);
	char cudaErrorMessage[1024] = {};
	if (!DEPTHFX_CUDA_ProcessHost(
		cudaBridge,
		readbackPixels.data(),
		static_cast<int>(input.Width),
		static_cast<int>(input.Height),
		depthWidth,
		depthHeight,
		hostDepthPixels.data(),
		hostDepthPixels.size(),
		cudaErrorMessage,
		sizeof(cudaErrorMessage)
	))
	{
		errorMessage = cudaErrorMessage[0] == '\0' ? "falló la inferencia de respaldo CUDA/TensorRT" : cudaErrorMessage;
		return false;
	}
	UploadDepthPixels();
	return true;
}

void DEPTHFX::UploadDepthPixels()
{
	if (depthTexture == 0 || hostDepthPixels.empty())
		return;
	GLint previousTexture = 0;
	glGetIntegerv(GL_TEXTURE_BINDING_2D, &previousTexture);
	glBindTexture(GL_TEXTURE_2D, depthTexture);
	glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
	glTexSubImage2D(
		GL_TEXTURE_2D,
		0,
		0,
		0,
		depthWidth,
		depthHeight,
		GL_RGBA,
		GL_FLOAT,
		hostDepthPixels.data()
	);
	glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(previousTexture));
}

void DEPTHFX::MarkCudaFailure(const std::string& message)
{
	if (!cudaFailureLogged)
	{
		Log("DEPTH_FX: " + message + ". Se conserva la textura original.");
		cudaFailureLogged = true;
	}
}

FFResult DEPTHFX::Init()
{
	cudaBridge = DEPTHFX_CUDA_Create();
	if (cudaBridge == nullptr)
		return FF_FAIL;
	enginePath = FindDefaultEngine();
	if (!enginePath.empty())
		Log("DEPTH_FX: engine local encontrado: " + enginePath);
	EnsureDepthTexture(kDepthTextureSize, kDepthTextureSize);
	return depthTexture == 0 ? FF_FAIL : FF_SUCCESS;
}

void DEPTHFX::Update()
{
	// FFGL delivers the current clip texture to Render(). No video is opened here.
}

void DEPTHFX::Clean()
{
	if (cudaBridge != nullptr)
	{
		DEPTHFX_CUDA_Destroy(cudaBridge);
		cudaBridge = nullptr;
	}
	ReleaseDepthTexture();
}

FFResult DEPTHFX::Render(ProcessOpenGLStruct* inputTextures)
{
	if (inputTextures == nullptr || inputTextures->numInputTextures < 1 || inputTextures->inputTextures == nullptr || inputTextures->inputTextures[0] == nullptr)
		return FF_FAIL;

	const FFGLTextureStruct& input = *inputTextures->inputTextures[0];
	if (!renderLogged)
	{
		Log("DEPTH_FX: Render recibido, input=" + std::to_string(input.Width) + "x" + std::to_string(input.Height));
		renderLogged = true;
	}
	EnsureDepthTexture(kDepthTextureSize, kDepthTextureSize);
	if (depthTexture == 0)
		return FF_FAIL;
	depthAvailable = false;

	if (engineDirty && !enginePath.empty() && cudaBridge != nullptr)
	{
		char errorMessage[1024] = {};
		if (DEPTHFX_CUDA_LoadEngine(cudaBridge, enginePath.c_str(), errorMessage, sizeof(errorMessage)))
		{
			cudaFailureLogged = false;
			Log("DEPTH_FX: engine TensorRT cargado; la inferencia recibe la textura de Resolume.");
		}
		else
		{
			MarkCudaFailure(errorMessage[0] == '\0' ? "no se pudo cargar el engine TensorRT" : errorMessage);
		}
		engineDirty = false;
	}

	if (!enginePath.empty() && cudaBridge != nullptr && !cudaFailureLogged)
	{
		std::string errorMessage;
		if (!ProcessHostReadback(input, errorMessage))
			MarkCudaFailure(errorMessage);
		else
			depthAvailable = true;
	}

	ffglex::ScopedShaderBinding shaderBinding(shader.GetGLID());
	ffglex::ScopedSamplerActivation activateSampler0(0);
	ffglex::Scoped2DTextureBinding textureBinding0(input.Handle);
	shader.Set("inputTexture", 0);

	ffglex::ScopedSamplerActivation activateSampler1(1);
	ffglex::Scoped2DTextureBinding textureBinding1(depthTexture);
	shader.Set("depthTexture", 1);
	shader.Set("depthResolution", static_cast<float>(depthWidth), static_cast<float>(depthHeight));
	shader.Set("DepthAvailable", depthAvailable ? 1.0f : 0.0f);

	const FFGLTexCoords maxCoords = GetMaxGLTexCoords(input);
	shader.Set("maxUV", maxCoords.s, maxCoords.t);
	quad.Draw();
	return FF_SUCCESS;
}

FFResult DEPTHFX::SetTextParameter(unsigned int index, const char* value)
{
	if (index == PARAM_ENGINE_FILE)
	{
		const std::string selectedPath = DecodeFileUri(value);
		if (selectedPath.empty() && !enginePath.empty())
		{
			Log("DEPTH_FX: se ignoró una actualización vacía de DepthEngine.");
			return FF_SUCCESS;
		}
		enginePath = selectedPath;
		Log("DEPTH_FX: DepthEngine seleccionado: " + enginePath);
		engineDirty = true;
		cudaFailureLogged = false;
		depthAvailable = false;
		return FF_SUCCESS;
	}
	return Effect::SetTextParameter(index, value);
}

char* DEPTHFX::GetTextParameter(unsigned int index)
{
	if (index != PARAM_ENGINE_FILE)
		return Effect::GetTextParameter(index);
	static char buffer[4096];
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(enginePath.size(), sizeof(buffer) - 1);
	std::copy(enginePath.begin(), enginePath.begin() + length, buffer);
	return buffer;
}
