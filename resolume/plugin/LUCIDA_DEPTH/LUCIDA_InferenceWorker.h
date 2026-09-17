#pragma once

#include "LUCIDA_DepthCore.h"

#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

struct LUCIDA_InferenceJob {
	std::vector<unsigned char> rgba;
	int width = 0;
	int height = 0;
	std::uint64_t settings_generation = 0;
	lucida_depth::Settings settings;
	std::int32_t time = 0;
	std::int32_t time_step = 1;
};

struct LUCIDA_InferenceResult {
	bool success = false;
	double elapsed_ms = 0.0;
	int inference_short_edge = 0;
	depthgen::DepthModel model = depthgen::DepthModel::ZipDepth;
	std::uint64_t settings_generation = 0;
	std::vector<float> depth;
	std::vector<float> alpha;
	depthgen::InferenceProvider provider = depthgen::InferenceProvider::Unavailable;
	std::string error;
};

class LUCIDA_InferenceWorker final {
public:
	~LUCIDA_InferenceWorker();

	void Start();
	void Stop();
	void ResetTemporal();
	bool Submit(LUCIDA_InferenceJob job);
	bool TryTake(LUCIDA_InferenceResult* result);

private:
	void Run();

	std::mutex mutex_;
	std::condition_variable condition_;
	std::optional<LUCIDA_InferenceJob> pending_job_;
	std::optional<LUCIDA_InferenceResult> completed_result_;
	std::unique_ptr<depthgen::TemporalHistory> history_;
	std::thread thread_;
	bool stopping_ = false;
	bool busy_ = false;
	bool reset_requested_ = false;
};
