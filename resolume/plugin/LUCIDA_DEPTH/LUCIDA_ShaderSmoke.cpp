#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <GL/glew.h>
#include <GL/wglew.h>
#endif

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

namespace {

LRESULT CALLBACK WindowProc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
	return DefWindowProcA(window, message, wparam, lparam);
}

std::string ReadFragmentShader(const std::string& path) {
	std::ifstream file(path, std::ios::binary);
	if (!file) return {};
	const std::string source((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
	const std::string begin = "constexpr char kFragmentShader[] = R\"(";
	const size_t begin_pos = source.find(begin);
	if (begin_pos == std::string::npos) return {};
	const size_t body_begin = begin_pos + begin.size();
	const size_t body_end = source.find(")\";", body_begin);
	if (body_end == std::string::npos) return {};
	return source.substr(body_begin, body_end - body_begin);
}

std::string MakeFragmentShader(const std::string& body) {
	return R"GLSL(#version 410 core
in vec2 i_uv;
out vec4 fragColor;
uniform sampler2D inputTexture;
uniform vec2 resolution;
uniform float time;
uniform float deltaTime;
uniform int frame;
uniform float bpm;
uniform float phase;
uniform float Model;
uniform float Quality;
uniform float FarPercentile;
uniform float NearPercentile;
uniform float Contrast;
uniform bool Invert;
uniform float TemporalStability;
uniform float CustomShortEdge;
uniform float InputTransfer;
uniform bool UseAlphaForLevels;
uniform float AlphaThreshold;
uniform float OutputAlpha;
uniform float EffectMix;
uniform float InferenceRate;
uniform bool ResetTemporal;
uniform float OutputStyle;
uniform float DepthBands;
uniform float SilhouetteThreshold;
uniform float EdgeGain;
uniform float CCTVScanlines;
uniform float CCTVNoise;
uniform float AuraRadius;
uniform float AuraFalloff;
uniform float RayLength;
uniform float RaySpread;
uniform float RayDensity;
uniform float RayBranching;
uniform float RayFlicker;
uniform float DepthOcclusion;
uniform float ElectricEnergy;
uniform float RayOriginX;
uniform float RayOriginY;
uniform float EmissionDepth;
uniform float DepthGateWidth;
uniform float NormalAlignment;
uniform float RayAngle;
uniform vec3 ElectricColor;
uniform vec3 ElectricColor2;
)GLSL" + body;
}

bool CompileShader(GLuint shader, const std::string& source, const char* label) {
	const char* text = source.c_str();
	glShaderSource(shader, 1, &text, nullptr);
	glCompileShader(shader);
	GLint status = GL_FALSE;
	glGetShaderiv(shader, GL_COMPILE_STATUS, &status);
	if (status == GL_TRUE) return true;
	GLint length = 0;
	glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &length);
	std::string log(static_cast<size_t>(std::max(length, 1)), '\0');
	glGetShaderInfoLog(shader, length, nullptr, log.data());
	std::cerr << label << " compile failed:\n" << log << "\n";
	return false;
}

void SetFloat(GLuint program, const char* name, float value) {
	const GLint location = glGetUniformLocation(program, name);
	if (location >= 0) glUniform1f(location, value);
}

void SetInt(GLuint program, const char* name, int value) {
	const GLint location = glGetUniformLocation(program, name);
	if (location >= 0) glUniform1i(location, value);
}

void SetVec3(GLuint program, const char* name, float r, float g, float b) {
	const GLint location = glGetUniformLocation(program, name);
	if (location >= 0) glUniform3f(location, r, g, b);
}

void SetVec2(GLuint program, const char* name, float x, float y) {
	const GLint location = glGetUniformLocation(program, name);
	if (location >= 0) glUniform2f(location, x, y);
}

bool RenderElectricStyle(GLuint program, int output_style, GLuint input_texture,
	GLuint depth_texture, GLuint framebuffer, int width, int height,
	const char* visual_output_path = nullptr, float render_time = 0.37f) {
	std::vector<float> depth(static_cast<size_t>(width) * static_cast<size_t>(height));
	for (int y = 0; y < height; ++y) {
		for (int x = 0; x < width; ++x) {
			const float fx = static_cast<float>(x) / static_cast<float>(width - 1);
			const float fy = static_cast<float>(y) / static_cast<float>(height - 1);
			const float dx = fx - 0.5f;
			const float dy = fy - 0.5f;
			const float object = (dx * dx + dy * dy) < 0.11f ? 0.75f : 0.25f;
			depth[static_cast<size_t>(y) * width + x] = object + fx * 0.05f;
		}
	}
	glBindTexture(GL_TEXTURE_2D, depth_texture);
	glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height, GL_RED, GL_FLOAT, depth.data());

	float quad[] = {
		-1.0f, -1.0f, 0.0f, 0.0f,
		 1.0f, -1.0f, 1.0f, 0.0f,
		-1.0f,  1.0f, 0.0f, 1.0f,
		 1.0f,  1.0f, 1.0f, 1.0f};
	GLuint vao = 0;
	GLuint vbo = 0;
	glGenVertexArrays(1, &vao);
	glGenBuffers(1, &vbo);
	glBindVertexArray(vao);
	glBindBuffer(GL_ARRAY_BUFFER, vbo);
	glBufferData(GL_ARRAY_BUFFER, sizeof(quad), quad, GL_STATIC_DRAW);
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), nullptr);
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float),
		reinterpret_cast<const void*>(2 * sizeof(float)));

	glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
	glViewport(0, 0, width, height);
	glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
	glClear(GL_COLOR_BUFFER_BIT);
	glUseProgram(program);
	SetInt(program, "inputTexture", 0);
	SetInt(program, "depthTexture", 1);
	SetFloat(program, "time", render_time);
	SetVec2(program, "resolution", static_cast<float>(width), static_cast<float>(height));
	SetFloat(program, "OutputStyle", static_cast<float>(output_style));
	SetFloat(program, "OutputAlpha", 1.0f);
	SetFloat(program, "EffectMix", 1.0f);
	SetFloat(program, "DepthBands", 0.0f);
	SetFloat(program, "EdgeGain", 18.0f);
	SetFloat(program, "AuraRadius", 8.0f);
	SetFloat(program, "AuraFalloff", 1.2f);
	SetFloat(program, "RayLength", 0.75f);
	SetFloat(program, "RaySpread", 0.25f);
	SetFloat(program, "RayDensity", 10.0f);
	SetFloat(program, "RayAngle", 0.0f);
	SetFloat(program, "RayBranching", 0.55f);
	SetFloat(program, "RayFlicker", 0.45f);
	SetFloat(program, "DepthOcclusion", 0.8f);
	SetFloat(program, "ElectricEnergy", 4.0f);
	SetFloat(program, "RayOriginX", 0.5f);
	SetFloat(program, "RayOriginY", 0.5f);
	SetFloat(program, "EmissionDepth", 0.5f);
	SetFloat(program, "DepthGateWidth", 1.0f);
	SetFloat(program, "NormalAlignment", 0.35f);
	SetFloat(program, "CCTVNoise", 0.0f);
	SetFloat(program, "CCTVScanlines", 0.0f);
	SetVec3(program, "ElectricColor", 0.0f, 0.8f, 1.0f);
	SetVec3(program, "ElectricColor2", 0.8f, 0.95f, 1.0f);
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, input_texture);
	glActiveTexture(GL_TEXTURE1);
	glBindTexture(GL_TEXTURE_2D, depth_texture);
	glBindVertexArray(vao);
	const auto started = std::chrono::steady_clock::now();
	glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
	glFinish();
	const double gpu_finish_ms = std::chrono::duration<double, std::milli>(
		std::chrono::steady_clock::now() - started).count();
	std::vector<unsigned char> pixels(static_cast<size_t>(width) * static_cast<size_t>(height) * 4U);
	glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
	const double total_ms = std::chrono::duration<double, std::milli>(
		std::chrono::steady_clock::now() - started).count();
	unsigned char minimum = 255;
	unsigned char maximum = 0;
	int nonzero = 0;
	for (size_t index = 0; index < pixels.size(); index += 4) {
		const unsigned char value = std::max(pixels[index], std::max(pixels[index + 1], pixels[index + 2]));
		minimum = std::min(minimum, value);
		maximum = std::max(maximum, value);
		if (value > 2) ++nonzero;
	}
	if (visual_output_path != nullptr && visual_output_path[0] != '\0') {
		std::ofstream image(visual_output_path, std::ios::binary | std::ios::trunc);
		if (!image) {
			std::cerr << "could not write visual smoke output: " << visual_output_path << "\n";
			return false;
		}
		image << "P6\n" << width << " " << height << "\n255\n";
		for (int y = height - 1; y >= 0; --y) {
			for (int x = 0; x < width; ++x) {
				const size_t index = (static_cast<size_t>(y) * static_cast<size_t>(width) +
					static_cast<size_t>(x)) * 4U;
				image.put(static_cast<char>(pixels[index + 0]));
				image.put(static_cast<char>(pixels[index + 1]));
				image.put(static_cast<char>(pixels[index + 2]));
			}
		}
	}
	glDeleteBuffers(1, &vbo);
	glDeleteVertexArrays(1, &vao);
	if (maximum <= minimum || nonzero < 8) {
		std::cerr << "electric style " << output_style << " rendered flat/empty: min="
			<< static_cast<int>(minimum) << " max=" << static_cast<int>(maximum)
			<< " nonzero=" << nonzero << "\n";
		return false;
	}
	std::cout << "electric style " << output_style << " rendered: min="
		<< static_cast<int>(minimum) << " max=" << static_cast<int>(maximum)
		<< " nonzero=" << nonzero << " gpu_finish_ms=" << gpu_finish_ms
		<< " total_with_readback_ms=" << total_ms << "\n";
	return true;
}

} // namespace

int main(int argc, char** argv) {
#ifndef _WIN32
	std::cerr << "Windows-only shader smoke\n";
	return 2;
#else
	const std::string source_path = argc > 1 ? argv[1] :
		"C:/IA/LUCIDA/resolume/plugin/LUCIDA_DEPTH/LUCIDA_Depth.cpp";
	const int render_width = argc > 3 ? std::max(64, std::atoi(argv[2])) : 64;
	const int render_height = argc > 3 ? std::max(64, std::atoi(argv[3])) : 64;
	const char* visual_output_path = argc > 4 ? argv[4] : nullptr;
	const float render_time = argc > 5 ? static_cast<float>(std::atof(argv[5])) : 0.37f;
	const std::string body = ReadFragmentShader(source_path);
	if (body.empty()) {
		std::cerr << "Could not extract kFragmentShader from " << source_path << "\n";
		return 3;
	}
	const char class_name[] = "LUCIDA_Depth_ShaderSmoke";
	WNDCLASSA window_class{};
	window_class.style = CS_OWNDC;
	window_class.lpfnWndProc = WindowProc;
	window_class.hInstance = GetModuleHandleA(nullptr);
	window_class.lpszClassName = class_name;
	RegisterClassA(&window_class);
	HWND window = CreateWindowA(class_name, class_name, WS_OVERLAPPEDWINDOW,
		0, 0, 64, 64, nullptr, nullptr, window_class.hInstance, nullptr);
	if (!window) return 4;
	HDC device = GetDC(window);
	PIXELFORMATDESCRIPTOR descriptor{};
	descriptor.nSize = sizeof(descriptor);
	descriptor.nVersion = 1;
	descriptor.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER;
	descriptor.iPixelType = PFD_TYPE_RGBA;
	descriptor.cColorBits = 32;
	descriptor.cAlphaBits = 8;
	descriptor.cDepthBits = 24;
	const int format = ChoosePixelFormat(device, &descriptor);
	if (format == 0 || !SetPixelFormat(device, format, &descriptor)) return 5;
	HGLRC context = wglCreateContext(device);
	if (!context || !wglMakeCurrent(device, context)) return 6;
	glewExperimental = GL_TRUE;
	if (glewInit() != GLEW_OK) return 7;
	std::cout << "OpenGL " << reinterpret_cast<const char*>(glGetString(GL_VERSION)) << "\n";
	const std::string vertex_source = R"GLSL(#version 410 core
layout(location = 0) in vec4 vPosition;
layout(location = 1) in vec2 vUV;
out vec2 i_uv;
void main() { gl_Position = vPosition; i_uv = vUV; }
)GLSL";
	const GLuint vertex = glCreateShader(GL_VERTEX_SHADER);
	const GLuint fragment = glCreateShader(GL_FRAGMENT_SHADER);
	const bool vertex_ok = CompileShader(vertex, vertex_source, "vertex");
	const bool fragment_ok = CompileShader(fragment, MakeFragmentShader(body), "fragment");
	GLuint program = glCreateProgram();
	glAttachShader(program, vertex);
	glAttachShader(program, fragment);
	glLinkProgram(program);
	GLint link_status = GL_FALSE;
	glGetProgramiv(program, GL_LINK_STATUS, &link_status);
	if (link_status != GL_TRUE) {
		GLint length = 0;
		glGetProgramiv(program, GL_INFO_LOG_LENGTH, &length);
		std::string log(static_cast<size_t>(std::max(length, 1)), '\0');
		glGetProgramInfoLog(program, length, nullptr, log.data());
		std::cerr << "program link failed:\n" << log << "\n";
	}
	const bool success = vertex_ok && fragment_ok && link_status == GL_TRUE;
	GLuint input_texture = 0;
	GLuint depth_texture = 0;
	GLuint color_texture = 0;
	GLuint framebuffer = 0;
	if (success) {
		const int size = 64;
		std::vector<unsigned char> black(static_cast<size_t>(size) * static_cast<size_t>(size) * 4U, 0);
		for (size_t index = 3; index < black.size(); index += 4) black[index] = 255;
		glGenTextures(1, &input_texture);
		glBindTexture(GL_TEXTURE_2D, input_texture);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, size, size, 0, GL_RGBA, GL_UNSIGNED_BYTE, black.data());
		glGenTextures(1, &depth_texture);
		glBindTexture(GL_TEXTURE_2D, depth_texture);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, size, size, 0, GL_RED, GL_FLOAT, nullptr);
		glGenTextures(1, &color_texture);
		glBindTexture(GL_TEXTURE_2D, color_texture);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, size, size, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
		glGenFramebuffers(1, &framebuffer);
		glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
		glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color_texture, 0);
		if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
			std::cerr << "shader smoke framebuffer is incomplete\n";
			return 1;
		}
		// Reallocate the fixtures to the requested benchmark size after creating
		// the small default textures used by the smoke test.
		if (render_width != size || render_height != size) {
			glBindTexture(GL_TEXTURE_2D, input_texture);
			glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, render_width, render_height, 0,
				GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
			glBindTexture(GL_TEXTURE_2D, depth_texture);
			glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, render_width, render_height, 0,
				GL_RED, GL_FLOAT, nullptr);
			glBindTexture(GL_TEXTURE_2D, color_texture);
			glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, render_width, render_height, 0,
				GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
		}
		std::vector<unsigned char> source_fixture(static_cast<size_t>(render_width) *
			static_cast<size_t>(render_height) * 4U, 255);
		for (int y = 0; y < render_height; ++y) {
			for (int x = 0; x < render_width; ++x) {
				const float fx = static_cast<float>(x) / static_cast<float>(std::max(render_width - 1, 1));
				const float fy = static_cast<float>(y) / static_cast<float>(std::max(render_height - 1, 1));
				const float dx = fx - 0.5f;
				const float dy = fy - 0.5f;
				const float subject = (dx * dx + dy * dy) < 0.11f ? 1.0f : 0.0f;
				const size_t index = (static_cast<size_t>(y) * static_cast<size_t>(render_width) +
					static_cast<size_t>(x)) * 4U;
				source_fixture[index + 0] = static_cast<unsigned char>(18.0f + subject * 58.0f + fx * 18.0f);
				source_fixture[index + 1] = static_cast<unsigned char>(22.0f + subject * 44.0f + fy * 14.0f);
				source_fixture[index + 2] = static_cast<unsigned char>(30.0f + subject * 38.0f);
			}
		}
		glBindTexture(GL_TEXTURE_2D, input_texture);
		glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, render_width, render_height,
			GL_RGBA, GL_UNSIGNED_BYTE, source_fixture.data());
		if (!RenderElectricStyle(program, 0, input_texture, depth_texture, framebuffer,
			render_width, render_height) ||
			!RenderElectricStyle(program, 5, input_texture, depth_texture, framebuffer,
				render_width, render_height) ||
			!RenderElectricStyle(program, 6, input_texture, depth_texture, framebuffer,
				render_width, render_height, visual_output_path, render_time) ||
			!RenderElectricStyle(program, 7, input_texture, depth_texture, framebuffer,
			render_width, render_height)) return 1;
	}
	glDeleteFramebuffers(1, &framebuffer);
	glDeleteTextures(1, &color_texture);
	glDeleteTextures(1, &depth_texture);
	glDeleteTextures(1, &input_texture);
	glDeleteProgram(program);
	glDeleteShader(vertex);
	glDeleteShader(fragment);
	wglMakeCurrent(nullptr, nullptr);
	wglDeleteContext(context);
	ReleaseDC(window, device);
	DestroyWindow(window);
	UnregisterClassA(class_name, window_class.hInstance);
	return success ? 0 : 1;
#endif
}
