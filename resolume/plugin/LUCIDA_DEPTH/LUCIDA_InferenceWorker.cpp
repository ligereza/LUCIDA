#include "LUCIDA_InferenceWorker.h"

#include <chrono>

LUCIDA_InferenceWorker::~LUCIDA_InferenceWorker() {
	Stop();
}

void LUCIDA_InferenceWorker::Start() {
	std::lock_guard<std::mutex> lock(mutex_);
	if (thread_.joinable()) return;
	stopping_ = false;
	history_ = std::make_unique<depthgen::TemporalHistory>();
	thread_ = std::thread(&LUCIDA_InferenceWorker::Run, this);
}

void LUCIDA_InferenceWorker::Stop() {
	{
		std::lock_guard<std::mutex> lock(mutex_);
		stopping_ = true;
		pending_job_.reset();
	}
	condition_.notify_all();
	if (thread_.joinable()) thread_.join();
	std::lock_guard<std::mutex> lock(mutex_);
	completed_result_.reset();
	history_.reset();
	busy_ = false;
	reset_requested_ = false;
}

void LUCIDA_InferenceWorker::ResetTemporal() {
	std::lock_guard<std::mutex> lock(mutex_);
	reset_requested_ = true;
	completed_result_.reset();
	// The worker clears history at a safe boundary. Clearing from the render
	// thread while ProcessFrame is active could let the old frame repopulate it.
}

bool LUCIDA_InferenceWorker::Submit(LUCIDA_InferenceJob job) {
	std::lock_guard<std::mutex> lock(mutex_);
	if (stopping_ || busy_ || pending_job_.has_value()) return false;
	pending_job_ = std::move(job);
	condition_.notify_one();
	return true;
}

bool LUCIDA_InferenceWorker::TryTake(LUCIDA_InferenceResult* result) {
	if (!result) return false;
	std::lock_guard<std::mutex> lock(mutex_);
	if (!completed_result_) return false;
	*result = std::move(*completed_result_);
	completed_result_.reset();
	return true;
}

void LUCIDA_InferenceWorker::Run() {
	for (;;) {
		LUCIDA_InferenceJob job;
		{
			std::unique_lock<std::mutex> lock(mutex_);
			condition_.wait(lock, [this] { return stopping_ || pending_job_.has_value(); });
			if (stopping_ && !pending_job_) return;
			if (reset_requested_) {
				history_->Clear();
				reset_requested_ = false;
			}
			job = std::move(*pending_job_);
			pending_job_.reset();
			busy_ = true;
		}

		LUCIDA_InferenceResult result;
		result.settings_generation = job.settings_generation;
		result.model = job.settings.model == lucida_depth::ModelDepthAnythingV2Small
			? depthgen::DepthModel::DepthAnythingV2Small : depthgen::DepthModel::ZipDepth;
		const auto started = std::chrono::steady_clock::now();
		result.inference_short_edge = lucida_depth::ShortEdge(job.settings);
		result.success = lucida_depth::ProcessFrame(
			job.rgba,
			job.width,
			job.height,
			job.settings,
			history_.get(),
			job.time,
			job.time_step,
			&result.depth,
			&result.alpha,
			&result.provider,
			&result.error);
		result.elapsed_ms = std::chrono::duration<double, std::milli>(
			std::chrono::steady_clock::now() - started).count();

		{
			std::lock_guard<std::mutex> lock(mutex_);
			busy_ = false;
			if (reset_requested_) {
				history_->Clear();
				reset_requested_ = false;
				continue;
			}
			// Keep only the newest completed result. The render thread should never
			// spend time draining stale depth maps after a long inference.
			completed_result_ = std::move(result);
		}
	}
}
