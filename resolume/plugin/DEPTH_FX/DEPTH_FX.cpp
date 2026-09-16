#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

#include "DEPTH_FX.h"

#include "../INSTAR/INSTAR_IMAGE.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>

#include <ffglex/FFGLScopedSamplerActivation.h>
#include <ffglex/FFGLScopedShaderBinding.h>
#include <ffglex/FFGLScopedTextureBinding.h>
#include <ffgl/FFGLLib.h>
#include <ffglquickstart/FFGLParam.h>
#include <ffglquickstart/FFGLParamOption.h>
#include <ffglquickstart/FFGLParamRange.h>

using namespace ffglqs;

namespace
{
std::string DecodeFileUri(const std::string& value)
{
	if (value.rfind("file://", 0) != 0)
		return value;
	std::string decoded = value.substr(7);
	if (decoded.rfind("/", 0) == 0 && decoded.size() > 2 && decoded[2] == ':')
		decoded.erase(decoded.begin());
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

std::string JsonString(const std::string& document, const std::string& key, const std::string& fallback)
{
	const std::string marker = "\"" + key + "\"";
	const size_t keyPosition = document.find(marker);
	if (keyPosition == std::string::npos)
		return fallback;
	const size_t colon = document.find(':', keyPosition + marker.size());
	if (colon == std::string::npos)
		return fallback;
	const size_t firstQuote = document.find('"', colon + 1);
	if (firstQuote == std::string::npos)
		return fallback;
	std::string result;
	for (size_t index = firstQuote + 1; index < document.size(); ++index)
	{
		if (document[index] == '\\' && index + 1 < document.size())
		{
			const char escaped = document[++index];
			if (escaped == 'n')
				result.push_back('\n');
			else if (escaped == 'r')
				result.push_back('\r');
			else if (escaped == 't')
				result.push_back('\t');
			else
				result.push_back(escaped);
		}
		else if (document[index] == '"')
		{
			return result;
		}
		else
		{
			result.push_back(document[index]);
		}
	}
	return fallback;
}

double JsonNumber(const std::string& document, const std::string& key, double fallback)
{
	const std::string marker = "\"" + key + "\"";
	const size_t keyPosition = document.find(marker);
	if (keyPosition == std::string::npos)
		return fallback;
	const size_t colon = document.find(':', keyPosition + marker.size());
	if (colon == std::string::npos)
		return fallback;
	const char* begin = document.c_str() + colon + 1;
	char* end = nullptr;
	const double parsed = std::strtod(begin, &end);
	return end == begin ? fallback : parsed;
}

std::string JoinPath(const std::string& directory, const std::string& name)
{
	if (directory.empty())
		return name;
	if (directory.back() == '\\' || directory.back() == '/')
		return directory + name;
	return directory + "\\" + name;
}

std::string ParentPath(const std::string& path)
{
	const size_t separator = path.find_last_of("\\/");
	return separator == std::string::npos ? std::string() : path.substr(0, separator);
}
}

static CFFGLPluginInfo PluginInfo(
	PluginFactory< DEPTHFX >,
	"DF01",
	"DEPTH_FX",
	2,
	1,
	1,
	0,
	FF_EFFECT,
	"Offline depth-driven displacement effect for Resolume.",
	"LUCIDA RESOLUME"
);

DEPTHFX::DEPTHFX()
{
	AddParam(Param::Create("DepthManifest", FF_TYPE_FILE, 0.0f));
	AddParam(ParamRange::Create("DepthAmount", 0.035f, ParamRange::Range(-0.25f, 0.25f)));
	AddParam(ParamRange::Create("DepthVertical", 0.0f, ParamRange::Range(-0.25f, 0.25f)));
	AddParam(ParamRange::Create("DepthBias", 0.0f, ParamRange::Range(-1.0f, 1.0f)));
	AddParam(ParamRange::Create("DepthContrast", 1.0f, ParamRange::Range(0.0f, 4.0f)));
	AddParam(ParamOption::Create("DepthInvert", {{"OFF", 0.0f}, {"ON", 1.0f}}, 0.0f));
	AddParam(ParamRange::Create("DepthSmooth", 0.0f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("EffectMix", 1.0f, ParamRange::Range(0.0f, 1.0f)));
	SetFragmentShader(R"(
		uniform sampler2D depthTexture;
		uniform vec2 depthResolution;
		uniform float DepthAmount;
		uniform float DepthVertical;
		uniform float DepthBias;
		uniform float DepthContrast;
		uniform float DepthInvert;
		uniform float DepthSmooth;
		uniform float EffectMix;

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
			depth = clamp((depth - 0.5) * DepthContrast + 0.5 + DepthBias, 0.0, 1.0);
			return DepthInvert > 0.5 ? 1.0 - depth : depth;
		}

		void main()
		{
			vec4 original = texture(inputTexture, i_uv);
			float depth = readDepth(i_uv);
			vec2 displacement = (depth - 0.5) * vec2(DepthAmount, DepthVertical);
			vec2 displacedUV = clamp(i_uv + displacement, vec2(0.0), vec2(1.0));
			vec4 displaced = texture(inputTexture, displacedUV);
			fragColor = mix(original, displaced, clamp(EffectMix, 0.0, 1.0));
		}
	)");
}

FFResult DEPTHFX::Init()
{
	glGenTextures(1, &depthTexture);
	if (depthTexture == 0)
		return FF_FAIL;
	glBindTexture(GL_TEXTURE_2D, depthTexture);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	const unsigned char neutralDepth[4] = {128, 128, 128, 255};
	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, neutralDepth);
	glBindTexture(GL_TEXTURE_2D, 0);
	return FF_SUCCESS;
}

void DEPTHFX::Clean()
{
	if (depthTexture != 0)
		glDeleteTextures(1, &depthTexture);
	depthTexture = 0;
	depthImage = INSTARImage();
	loadedFrame = -1;
	uploadedWidth = 0;
	uploadedHeight = 0;
	depthReady = false;
}

void DEPTHFX::Log(const std::string& message) const
{
	FFGLLog::LogToHost(message.c_str());
}

bool DEPTHFX::LoadManifest()
{
	manifestDirty = false;
	depthReady = false;
	loadedFrame = -1;
	sequence = DepthSequence();
	sequence.manifestPath = manifestPath;
	if (manifestPath.empty())
	{
		if (!loggedMissingManifest)
		{
			Log("DEPTH_FX: selecciona un depth-manifest.json; se conserva la imagen original.");
			loggedMissingManifest = true;
		}
		return false;
	}

	std::ifstream input(manifestPath.c_str(), std::ios::in | std::ios::binary);
	if (!input)
	{
		Log("DEPTH_FX: no se pudo abrir DepthManifest: " + manifestPath);
		return false;
	}
	const std::string document((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
	const std::string framesDirectory = JsonString(document, "frames_dir", "frames");
	sequence.framesDirectory = framesDirectory.empty() ? ParentPath(manifestPath) : JoinPath(ParentPath(manifestPath), framesDirectory);
	sequence.prefix = JsonString(document, "prefix", "depth_");
	sequence.extension = JsonString(document, "extension", ".png");
	sequence.frameCount = static_cast<int>(JsonNumber(document, "frame_count", 0.0));
	sequence.startIndex = static_cast<int>(JsonNumber(document, "start_index", 0.0));
	sequence.zeroPad = static_cast<int>(JsonNumber(document, "zero_pad", 6.0));
	sequence.fps = static_cast<float>(JsonNumber(document, "fps", 30.0));
	if (sequence.frameCount <= 0 || sequence.fps <= 0.0f || sequence.extension.empty())
	{
		Log("DEPTH_FX: manifest inválido; requiere frame_count, fps y extension válidos.");
		return false;
	}
	loggedMissingManifest = false;
	Log("DEPTH_FX: depth sequence cargada (" + std::to_string(sequence.frameCount) + " frames, " + std::to_string(sequence.fps) + " fps).");
	return true;
}

std::string DEPTHFX::FramePath(int frameIndex) const
{
	std::ostringstream number;
	if (sequence.zeroPad > 0)
		number << std::setw(sequence.zeroPad) << std::setfill('0');
	number << (sequence.startIndex + frameIndex);
	return JoinPath(sequence.framesDirectory, sequence.prefix + number.str() + sequence.extension);
}

bool DEPTHFX::LoadDepthFrame(int frameIndex)
{
	if (frameIndex < 0 || frameIndex >= sequence.frameCount)
		return false;
	if (loadedFrame == frameIndex && depthReady)
		return true;
	std::string error;
	INSTARImage loaded;
	if (!LoadINSTARImage(FramePath(frameIndex), loaded, error))
	{
		Log("DEPTH_FX: no se pudo cargar frame de profundidad " + std::to_string(frameIndex) + ": " + error);
		depthReady = false;
		return false;
	}
	depthImage = loaded;
	loadedFrame = frameIndex;
	depthReady = true;
	return true;
}

void DEPTHFX::UploadDepthFrame()
{
	if (!depthReady || depthTexture == 0 || depthImage.width == 0 || depthImage.height == 0)
		return;
	glBindTexture(GL_TEXTURE_2D, depthTexture);
	glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
	if (uploadedWidth != static_cast<int>(depthImage.width) || uploadedHeight != static_cast<int>(depthImage.height))
	{
		glTexImage2D(
			GL_TEXTURE_2D,
			0,
			GL_RGBA8,
			static_cast<GLsizei>(depthImage.width),
			static_cast<GLsizei>(depthImage.height),
			0,
			GL_RGBA,
			GL_UNSIGNED_BYTE,
			depthImage.rgba.data()
		);
		uploadedWidth = static_cast<int>(depthImage.width);
		uploadedHeight = static_cast<int>(depthImage.height);
	}
	else
	{
		glTexSubImage2D(
			GL_TEXTURE_2D,
			0,
			0,
			0,
			static_cast<GLsizei>(depthImage.width),
			static_cast<GLsizei>(depthImage.height),
			GL_RGBA,
			GL_UNSIGNED_BYTE,
			depthImage.rgba.data()
		);
	}
	glBindTexture(GL_TEXTURE_2D, 0);
}

void DEPTHFX::Update()
{
	if (manifestDirty)
		LoadManifest();
	if (!depthReady)
		return;
	int frameIndex = static_cast<int>(std::floor(std::max(0.0, hostTime) * sequence.fps));
	if (frameIndex >= sequence.frameCount)
		frameIndex = sequence.frameCount - 1;
	if (LoadDepthFrame(frameIndex))
		UploadDepthFrame();
}

FFResult DEPTHFX::Render(ProcessOpenGLStruct* inputTextures)
{
	if (inputTextures == nullptr || inputTextures->numInputTextures < 1 || inputTextures->inputTextures == nullptr || inputTextures->inputTextures[0] == nullptr)
		return FF_FAIL;

	ffglex::ScopedSamplerActivation activateSampler0(0);
	ffglex::Scoped2DTextureBinding textureBinding0(inputTextures->inputTextures[0]->Handle);
	shader.Set("inputTexture", 0);

	ffglex::ScopedSamplerActivation activateSampler1(1);
	ffglex::Scoped2DTextureBinding textureBinding1(depthTexture);
	shader.Set("depthTexture", 1);
	shader.Set("depthResolution", static_cast<float>(std::max(1, uploadedWidth)), static_cast<float>(std::max(1, uploadedHeight)));

	const FFGLTexCoords maxCoords = GetMaxGLTexCoords(*inputTextures->inputTextures[0]);
	shader.Set("maxUV", maxCoords.s, maxCoords.t);
	quad.Draw();
	return FF_SUCCESS;
}

FFResult DEPTHFX::SetTextParameter(unsigned int index, const char* value)
{
	if (index == PARAM_DEPTH_MANIFEST)
	{
		manifestPath = DecodeFileUri(value == nullptr ? "" : value);
		manifestDirty = true;
		return FF_SUCCESS;
	}
	return Effect::SetTextParameter(index, value);
}

char* DEPTHFX::GetTextParameter(unsigned int index)
{
	if (index != PARAM_DEPTH_MANIFEST)
		return Effect::GetTextParameter(index);
	static char buffer[4096];
	std::fill(buffer, buffer + sizeof(buffer), '\0');
	const size_t length = std::min(manifestPath.size(), sizeof(buffer) - 1);
	std::copy(manifestPath.begin(), manifestPath.begin() + length, buffer);
	return buffer;
}
