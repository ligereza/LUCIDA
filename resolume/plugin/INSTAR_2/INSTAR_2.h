#pragma once

#include <ffglquickstart/FFGLEffect.h>
#include <ffglquickstart/FFGLParamBool.h>
#include <ffglquickstart/FFGLParamOption.h>
#include <ffglquickstart/FFGLParamRange.h>
#include <ffglquickstart/FFGLParamTrigger.h>

#include "../INSTAR/INSTAR_RENDERER.h"
#include "../INSTAR/INSTAR_SCENE.h"

#include <string>
#include <utility>
#include <vector>

class INSTAR_2 final : public ffglqs::Effect
{
public:
	INSTAR_2();
	~INSTAR_2() override = default;

	const char* GetShortName() override
	{
		static const char* shortName = "INSTAR 2";
		return shortName;
	}

	FFResult SetFloatParameter(unsigned int index, float value) override;
	FFResult SetTextParameter(unsigned int index, const char* value) override;
	char* GetTextParameter(unsigned int index) override;
	FFResult Render(ProcessOpenGLStruct* inputTextures) override;

protected:
	FFResult Init() override;
	void Update() override;
	void Clean() override;

private:
	using FileSignature = std::pair<long long, long long>;

	static constexpr unsigned int PARAM_TEMPLATE_XML = 0;
	static constexpr unsigned int PARAM_FOLLOW_ACTIVE_XML = 1;
	static constexpr unsigned int PARAM_VIEW = 2;
	static constexpr unsigned int PARAM_YAW = 3;
	static constexpr unsigned int PARAM_PITCH = 4;
	static constexpr unsigned int PARAM_ZOOM = 5;
	static constexpr unsigned int PARAM_BRIGHTNESS = 6;
	static constexpr unsigned int PARAM_DEPTH = 7;
	static constexpr unsigned int PARAM_SLICE_ENABLED_01 = 8;
	static constexpr unsigned int PARAM_SLICE_ENABLED_32 = 39;
	static constexpr unsigned int PARAM_SLICE_DEPTH_01 = 40;
	static constexpr unsigned int PARAM_SLICE_DEPTH_32 = 71;
	static constexpr unsigned int PARAM_CAMERA_DISTANCE = 72;
	static constexpr unsigned int PARAM_USE_ACTIVE_XML = 73;
	static constexpr unsigned int PARAM_RELOAD_XML = 74;

	static FileSignature GetFileSignature(const std::string& path);
	static std::string ResolveActivePresetPath();
	void ConfigureSliceDepthParams(size_t sliceCount, const std::vector<std::string>& names);
	void FollowActivePresetIfNeeded();
	bool ReloadSceneIfNeeded(bool force);
	void Log(const std::string& message) const;

	INSTARSceneRenderer renderer_;
	INSTARScene scene_;
	std::string templatePath_;
	FileSignature activeSignature_ = {0, 0};
	FileSignature lastAttemptSignature_ = {0, 0};
	std::string activePath_;
	std::string lastAttemptPath_;
	float yaw_ = 0.5f;
	float pitch_ = 0.5f;
	float zoom_ = 0.55f;
	float brightness_ = 0.85f;
	float depth_ = 0.0f;
	float cameraDistance_ = 3.5f;
	bool sliceEnabled_[32] = {};
	float sliceDepths_[32] = {};
	bool sceneDirty_ = true;
	bool reloadRequested_ = false;
	unsigned int visibleSliceCount_ = 0;
	unsigned int selectedSliceCount_ = 0;
	bool followActivePreset_ = true;
	unsigned int activePresetPollCounter_ = 0;
};
