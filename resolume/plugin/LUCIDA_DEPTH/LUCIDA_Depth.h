#pragma once

#include "LUCIDA_DepthCore.h"
#include "LUCIDA_InferenceWorker.h"

#include <ffglquickstart/FFGLEffect.h>
#include <ffglquickstart/FFGLParamBool.h>
#include <ffglquickstart/FFGLParamOption.h>
#include <ffglquickstart/FFGLParamRange.h>
#include <ffglquickstart/FFGLParamTrigger.h>

#include <memory>
#include <string>
#include <vector>

class LUCIDA_DEPTH final : public ffglqs::Effect {
public:
	LUCIDA_DEPTH();
	~LUCIDA_DEPTH() override;

	const char* GetShortName() override {
		static const char* short_name = "LUCIDA Depth";
		return short_name;
	}

protected:
	FFResult InitGL(const FFGLViewportStruct* viewport) override;
	FFResult ProcessOpenGL(ProcessOpenGLStruct* input_textures) override;
	FFResult Init() override;
	void Update() override;
	void Clean() override;
	FFResult Render(ProcessOpenGLStruct* input_textures) override;

private:
	static constexpr unsigned int PARAM_MODEL = 0;
	static constexpr unsigned int PARAM_QUALITY = 1;
	static constexpr unsigned int PARAM_FAR = 2;
	static constexpr unsigned int PARAM_NEAR = 3;
	static constexpr unsigned int PARAM_CONTRAST = 4;
	static constexpr unsigned int PARAM_INVERT = 5;
	static constexpr unsigned int PARAM_TEMPORAL = 6;
	static constexpr unsigned int PARAM_CUSTOM_EDGE = 7;
	static constexpr unsigned int PARAM_TRANSFER = 8;
	static constexpr unsigned int PARAM_USE_ALPHA = 9;
	static constexpr unsigned int PARAM_ALPHA_THRESHOLD = 10;
	static constexpr unsigned int PARAM_OUTPUT_ALPHA = 11;
	static constexpr unsigned int PARAM_EFFECT_MIX = 12;
	static constexpr unsigned int PARAM_INFERENCE_RATE = 13;
	static constexpr unsigned int PARAM_RESET_TEMPORAL = 14;
	static constexpr unsigned int PARAM_OUTPUT_STYLE = 15;
	static constexpr unsigned int PARAM_DEPTH_BANDS = 16;
	static constexpr unsigned int PARAM_SILHOUETTE_THRESHOLD = 17;
	static constexpr unsigned int PARAM_EDGE_GAIN = 18;
	static constexpr unsigned int PARAM_CCTV_SCANLINES = 19;
	static constexpr unsigned int PARAM_CCTV_NOISE = 20;
	static constexpr unsigned int PARAM_AURA_RADIUS = 21;
	static constexpr unsigned int PARAM_AURA_FALLOFF = 22;
	static constexpr unsigned int PARAM_RAY_LENGTH = 23;
	static constexpr unsigned int PARAM_RAY_SPREAD = 24;
	static constexpr unsigned int PARAM_RAY_DENSITY = 25;
	static constexpr unsigned int PARAM_RAY_BRANCHING = 26;
	static constexpr unsigned int PARAM_RAY_FLICKER = 27;
	static constexpr unsigned int PARAM_DEPTH_OCCLUSION = 28;
	static constexpr unsigned int PARAM_ELECTRIC_ENERGY = 29;
	static constexpr unsigned int PARAM_RAY_ORIGIN_X = 30;
	static constexpr unsigned int PARAM_RAY_ORIGIN_Y = 31;
	static constexpr unsigned int PARAM_EMISSION_DEPTH = 32;
	static constexpr unsigned int PARAM_DEPTH_GATE_WIDTH = 33;
	static constexpr unsigned int PARAM_NORMAL_ALIGNMENT = 34;
	static constexpr unsigned int PARAM_ELECTRIC_COLOR = 35;
	static constexpr unsigned int PARAM_ELECTRIC_COLOR_GREEN = 36;
	static constexpr unsigned int PARAM_ELECTRIC_COLOR_BLUE = 37;
	static constexpr unsigned int PARAM_ELECTRIC_COLOR_2 = 38;
	static constexpr unsigned int PARAM_ELECTRIC_COLOR_2_GREEN = 39;
	static constexpr unsigned int PARAM_ELECTRIC_COLOR_2_BLUE = 40;
	static constexpr unsigned int PARAM_RAY_ANGLE = 41;

	void Log(const std::string& message) const;
	bool EnsureDepthTexture(int width, int height);
	void ReleaseDepthTexture();
	bool EnsureReadbackPbos(int width, int height);
	void ReleaseReadbackPbos();
	bool ReadInputTexture(const FFGLTextureStruct& input, std::string* error);
	void UploadDepthTexture();
	lucida_depth::Settings ReadSettings();
	void DrawOutput(const FFGLTextureStruct& input);

	static constexpr int kReadbackPboCount = 3;

	LUCIDA_InferenceWorker inference_worker_;
	GLuint depth_texture_ = 0;
	int depth_width_ = 0;
	int depth_height_ = 0;
	std::vector<unsigned char> readback_rgba_;
	std::vector<unsigned char> texture_readback_rgba_;
	std::vector<float> depth_values_;
	std::vector<float> source_alpha_;
	GLuint readback_pbos_[kReadbackPboCount] = {};
	GLsync readback_pbo_fences_[kReadbackPboCount] = {};
	bool readback_pbo_in_flight_[kReadbackPboCount] = {};
	size_t readback_pbo_bytes_ = 0;
	int readback_pbo_width_ = 0;
	int readback_pbo_height_ = 0;
	int readback_pbo_write_index_ = 0;
	std::int32_t frame_time_ = 0;
	std::int32_t previous_time_ = 0;
	std::uint64_t render_counter_ = 0;
	bool have_time_ = false;
	bool has_depth_ = false;
	bool have_settings_ = false;
	lucida_depth::Settings last_settings_;
	std::uint64_t settings_generation_ = 1;
	bool process_logged_ = false;
	bool render_logged_ = false;
	unsigned int inference_logs_ = 0;
	bool visibility_initialized_ = false;
	bool custom_edge_visible_ = false;
	bool alpha_threshold_visible_ = true;
	bool reset_temporal_requested_ = false;
	int cctv_style_ = -1;
};
