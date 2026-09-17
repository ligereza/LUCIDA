#include "DEPTH_FX_CUDA.h"

#ifdef _WIN32
#include <windows.h>
#endif

#include <cuda_fp16.h>
#include <cuda_gl_interop.h>
#include <cuda_runtime.h>

#include <NvInfer.h>

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace
{
constexpr unsigned int kGLTexture2D = 0x0DE1;

void SetError(char* destination, size_t destinationSize, const std::string& message)
{
	if (destination == nullptr || destinationSize == 0)
		return;
	const size_t length = std::min(destinationSize - 1, message.size());
	std::memcpy(destination, message.data(), length);
	destination[length] = '\0';
}

std::string CudaError(const char* operation, cudaError_t error)
{
	std::ostringstream message;
	message << operation << ": " << cudaGetErrorString(error) << " (" << static_cast<int>(error) << ")";
	return message.str();
}

int64_t DimsVolume(const nvinfer1::Dims& dims)
{
	int64_t result = 1;
	for (int index = 0; index < dims.nbDims; ++index)
	{
		if (dims.d[index] <= 0)
			return 0;
		result *= dims.d[index];
	}
	return result;
}

template <typename T>
__device__ T StoreValue(float value);

template <>
__device__ float StoreValue<float>(float value)
{
	return value;
}

template <>
__device__ __half StoreValue<__half>(float value)
{
	return __float2half(value);
}

template <typename T>
__global__ void PreprocessKernel(
	cudaTextureObject_t source,
	T* destination,
	int width,
	int height,
	int inputWidth,
	int inputHeight)
{
	const int x = blockIdx.x * blockDim.x + threadIdx.x;
	const int y = blockIdx.y * blockDim.y + threadIdx.y;
	if (x >= width || y >= height)
		return;

	const float u = (static_cast<float>(x) + 0.5f) / static_cast<float>(width);
	const float v = (static_cast<float>(y) + 0.5f) / static_cast<float>(height);
	const float4 rgba = tex2D<float4>(source, u, v);
	const float channels[3] = {rgba.x, rgba.y, rgba.z};
	const float mean[3] = {0.485f, 0.456f, 0.406f};
	const float standardDeviation[3] = {0.229f, 0.224f, 0.225f};
	const int plane = width * height;
	const int pixel = y * width + x;

	for (int channel = 0; channel < 3; ++channel)
	{
		const float normalized = (channels[channel] - mean[channel]) / standardDeviation[channel];
		destination[channel * plane + pixel] = StoreValue<T>(normalized);
	}
}

template <typename T>
__global__ void PreprocessHostKernel(
	const uchar4* source,
	T* destination,
	int width,
	int height,
	int sourceWidth,
	int sourceHeight)
{
	const int x = blockIdx.x * blockDim.x + threadIdx.x;
	const int y = blockIdx.y * blockDim.y + threadIdx.y;
	if (x >= width || y >= height)
		return;

	const int sourceX = min(sourceWidth - 1, static_cast<int>((static_cast<float>(x) + 0.5f) * sourceWidth / width));
	const int sourceY = min(sourceHeight - 1, static_cast<int>((static_cast<float>(y) + 0.5f) * sourceHeight / height));
	const uchar4 pixel = source[sourceY * sourceWidth + sourceX];
	const float channels[3] = {
		static_cast<float>(pixel.x) / 255.0f,
		static_cast<float>(pixel.y) / 255.0f,
		static_cast<float>(pixel.z) / 255.0f
	};
	const float mean[3] = {0.485f, 0.456f, 0.406f};
	const float standardDeviation[3] = {0.229f, 0.224f, 0.225f};
	const int plane = width * height;
	const int index = y * width + x;
	for (int channel = 0; channel < 3; ++channel)
		destination[channel * plane + index] = StoreValue<T>((channels[channel] - mean[channel]) / standardDeviation[channel]);
}

__global__ void ConvertFloatKernel(const float* source, float* destination, int count)
{
	const int index = blockIdx.x * blockDim.x + threadIdx.x;
	if (index < count)
		destination[index] = source[index];
}

__global__ void ConvertHalfKernel(const __half* source, float* destination, int count)
{
	const int index = blockIdx.x * blockDim.x + threadIdx.x;
	if (index < count)
		destination[index] = __half2float(source[index]);
}

__global__ void WriteDepthTextureKernel(
	cudaSurfaceObject_t destination,
	const float* source,
	int sourceWidth,
	int sourceHeight,
	int destinationWidth,
	int destinationHeight,
	const float* minimum,
	const float* maximum)
{
	const int x = blockIdx.x * blockDim.x + threadIdx.x;
	const int y = blockIdx.y * blockDim.y + threadIdx.y;
	if (x >= destinationWidth || y >= destinationHeight)
		return;

	const int sourceX = min(sourceWidth - 1, static_cast<int>((static_cast<float>(x) + 0.5f) * sourceWidth / destinationWidth));
	const int sourceY = min(sourceHeight - 1, static_cast<int>((static_cast<float>(y) + 0.5f) * sourceHeight / destinationHeight));
	const float low = *minimum;
	const float high = *maximum;
	const float value = source[sourceY * sourceWidth + sourceX];
	const float range = high - low;
	float normalized = 0.5f;
	if (isfinite(value) && isfinite(low) && isfinite(high) && range > 1.0e-6f)
		normalized = (value - low) / range;
	const float clamped = fminf(1.0f, fmaxf(0.0f, normalized));
	surf2Dwrite(make_float4(clamped, clamped, clamped, 1.0f), destination, x * static_cast<int>(sizeof(float4)), y);
}

__global__ void ReduceMinMaxKernel(
	const float* source,
	float* blockMinimum,
	float* blockMaximum,
	int count)
{
	__shared__ float minimumValues[256];
	__shared__ float maximumValues[256];
	const int thread = threadIdx.x;
	const int index = blockIdx.x * blockDim.x + thread;
	minimumValues[thread] = index < count ? source[index] : FLT_MAX;
	maximumValues[thread] = index < count ? source[index] : -FLT_MAX;
	__syncthreads();
	for (int stride = blockDim.x / 2; stride > 0; stride >>= 1)
	{
		if (thread < stride)
		{
			minimumValues[thread] = fminf(minimumValues[thread], minimumValues[thread + stride]);
			maximumValues[thread] = fmaxf(maximumValues[thread], maximumValues[thread + stride]);
		}
		__syncthreads();
	}
	if (thread == 0)
	{
		blockMinimum[blockIdx.x] = minimumValues[0];
		blockMaximum[blockIdx.x] = maximumValues[0];
	}
}

class TensorRTLogger final : public nvinfer1::ILogger
{
public:
	void log(Severity severity, const char* message) noexcept override
	{
		if (severity <= Severity::kWARNING && message != nullptr)
			lastMessage = message;
	}

	std::string lastMessage;
};
}

struct DEPTHFX_CUDA
{
	TensorRTLogger logger;
	nvinfer1::IRuntime* runtime = nullptr;
	nvinfer1::ICudaEngine* engine = nullptr;
	nvinfer1::IExecutionContext* context = nullptr;

	cudaStream_t stream = nullptr;
	void* inputDevice = nullptr;
	uchar4* sourceDevice = nullptr;
	size_t sourceCapacity = 0;
	void* outputDevice = nullptr;
	float* outputFloatDevice = nullptr;
	float* minimumDevice = nullptr;
	float* maximumDevice = nullptr;
	float* blockMinimumDevice = nullptr;
	float* blockMaximumDevice = nullptr;
	int reductionBlocks = 0;

	cudaGraphicsResource_t inputResource = nullptr;
	cudaGraphicsResource_t outputResource = nullptr;
	unsigned int registeredInputTexture = 0;
	unsigned int registeredOutputTexture = 0;

	int inputBinding = -1;
	int outputBinding = -1;
	int inputWidth = 0;
	int inputHeight = 0;
	int modelWidth = 0;
	int modelHeight = 0;
	int64_t inputElements = 0;
	int64_t outputElements = 0;
	nvinfer1::DataType inputType = nvinfer1::DataType::kFLOAT;
	nvinfer1::DataType outputType = nvinfer1::DataType::kFLOAT;
	std::string loadedEnginePath;
	std::string lastError;
	bool ready = false;

	~DEPTHFX_CUDA()
	{
		Shutdown();
	}

	void Shutdown()
	{
		UnregisterGraphicsResources();
		FreeBuffers();
		if (context != nullptr)
			context->destroy();
		if (engine != nullptr)
			engine->destroy();
		if (runtime != nullptr)
			runtime->destroy();
		context = nullptr;
		engine = nullptr;
		runtime = nullptr;
		inputBinding = -1;
		outputBinding = -1;
		inputWidth = 0;
		inputHeight = 0;
		modelWidth = 0;
		modelHeight = 0;
		inputElements = 0;
		outputElements = 0;
		logger.lastMessage.clear();
		loadedEnginePath.clear();
		ready = false;
	}

	void FreeBuffers()
	{
		if (blockMaximumDevice != nullptr)
			cudaFree(blockMaximumDevice);
		if (blockMinimumDevice != nullptr)
			cudaFree(blockMinimumDevice);
		if (maximumDevice != nullptr)
			cudaFree(maximumDevice);
		if (minimumDevice != nullptr)
			cudaFree(minimumDevice);
		if (outputFloatDevice != nullptr)
			cudaFree(outputFloatDevice);
		if (outputDevice != nullptr)
			cudaFree(outputDevice);
		if (inputDevice != nullptr)
			cudaFree(inputDevice);
		if (sourceDevice != nullptr)
			cudaFree(sourceDevice);
		if (stream != nullptr)
			cudaStreamDestroy(stream);
		blockMaximumDevice = nullptr;
		blockMinimumDevice = nullptr;
		maximumDevice = nullptr;
		minimumDevice = nullptr;
		outputFloatDevice = nullptr;
		outputDevice = nullptr;
		inputDevice = nullptr;
		sourceDevice = nullptr;
		sourceCapacity = 0;
		stream = nullptr;
		reductionBlocks = 0;
	}

	void UnregisterGraphicsResources()
	{
		if (inputResource != nullptr)
			cudaGraphicsUnregisterResource(inputResource);
		if (outputResource != nullptr)
			cudaGraphicsUnregisterResource(outputResource);
		inputResource = nullptr;
		outputResource = nullptr;
		registeredInputTexture = 0;
		registeredOutputTexture = 0;
	}

	bool Fail(const std::string& message)
	{
		lastError = message;
		return false;
	}

	bool AllocateBuffers()
	{
		FreeBuffers();
		if (cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking) != cudaSuccess)
			return Fail(CudaError("cudaStreamCreateWithFlags", cudaGetLastError()));

		const size_t inputBytes = static_cast<size_t>(inputElements) * (inputType == nvinfer1::DataType::kHALF ? sizeof(__half) : sizeof(float));
		const size_t outputBytes = static_cast<size_t>(outputElements) * (outputType == nvinfer1::DataType::kHALF ? sizeof(__half) : sizeof(float));
		if (cudaMalloc(&inputDevice, inputBytes) != cudaSuccess)
			return Fail(CudaError("cudaMalloc(input)", cudaGetLastError()));
		if (cudaMalloc(&outputDevice, outputBytes) != cudaSuccess)
			return Fail(CudaError("cudaMalloc(output)", cudaGetLastError()));
		if (cudaMalloc(reinterpret_cast<void**>(&outputFloatDevice), static_cast<size_t>(outputElements) * sizeof(float)) != cudaSuccess)
			return Fail(CudaError("cudaMalloc(output float)", cudaGetLastError()));
		if (cudaMalloc(reinterpret_cast<void**>(&minimumDevice), sizeof(float)) != cudaSuccess)
			return Fail(CudaError("cudaMalloc(minimum)", cudaGetLastError()));
		if (cudaMalloc(reinterpret_cast<void**>(&maximumDevice), sizeof(float)) != cudaSuccess)
			return Fail(CudaError("cudaMalloc(maximum)", cudaGetLastError()));

		reductionBlocks = (modelWidth * modelHeight + 255) / 256;
		if (cudaMalloc(reinterpret_cast<void**>(&blockMinimumDevice), static_cast<size_t>(reductionBlocks) * sizeof(float)) != cudaSuccess)
			return Fail(CudaError("cudaMalloc(block minimum)", cudaGetLastError()));
		if (cudaMalloc(reinterpret_cast<void**>(&blockMaximumDevice), static_cast<size_t>(reductionBlocks) * sizeof(float)) != cudaSuccess)
			return Fail(CudaError("cudaMalloc(block maximum)", cudaGetLastError()));
		return true;
	}

	bool EnsureSourceBuffer(int width, int height)
	{
		const size_t required = static_cast<size_t>(width) * static_cast<size_t>(height) * sizeof(uchar4);
		if (sourceDevice != nullptr && sourceCapacity >= required)
			return true;
		if (sourceDevice != nullptr)
			cudaFree(sourceDevice);
		sourceDevice = nullptr;
		sourceCapacity = 0;
		const cudaError_t error = cudaMalloc(reinterpret_cast<void**>(&sourceDevice), required);
		if (error != cudaSuccess)
			return Fail(CudaError("cudaMalloc(source)", error));
		sourceCapacity = required;
		return true;
	}

	bool LoadEngine(const char* path)
	{
		lastError.clear();
		if (path == nullptr || path[0] == '\0')
			return Fail("no se seleccionó un archivo TensorRT .engine");
		if (ready && loadedEnginePath == path)
			return true;

		Shutdown();
		std::ifstream input(path, std::ios::binary | std::ios::ate);
		if (!input)
			return Fail(std::string("no se pudo abrir el engine: ") + path);
		const std::streamsize size = input.tellg();
		if (size <= 0)
			return Fail("el archivo TensorRT está vacío");
		input.seekg(0, std::ios::beg);
		std::vector<char> serialized(static_cast<size_t>(size));
		if (!input.read(serialized.data(), size))
			return Fail("no se pudo leer completamente el engine TensorRT");

		runtime = nvinfer1::createInferRuntime(logger);
		if (runtime == nullptr)
			return Fail("TensorRT no pudo crear IRuntime");
		engine = runtime->deserializeCudaEngine(serialized.data(), serialized.size());
		if (engine == nullptr)
		{
			const std::string detail = logger.lastMessage.empty() ? std::string() : std::string(" — ") + logger.lastMessage;
			return Fail("TensorRT no pudo deserializar el engine" + detail);
		}
		context = engine->createExecutionContext();
		if (context == nullptr)
			return Fail("TensorRT no pudo crear IExecutionContext");

		for (int binding = 0; binding < engine->getNbBindings(); ++binding)
		{
			if (engine->bindingIsInput(binding) && inputBinding < 0)
				inputBinding = binding;
			if (!engine->bindingIsInput(binding) && outputBinding < 0)
				outputBinding = binding;
		}
		if (inputBinding < 0 || outputBinding < 0)
			return Fail("el engine debe tener una entrada y una salida");

		nvinfer1::Dims inputDims = engine->getBindingDimensions(inputBinding);
		if (inputDims.nbDims != 4)
			return Fail("la entrada del engine no tiene forma NCHW de 4 dimensiones");
		for (int dimension = 0; dimension < inputDims.nbDims; ++dimension)
		{
			if (inputDims.d[dimension] <= 0)
			{
				if (dimension == 0)
					inputDims.d[dimension] = 1;
				else if (dimension == 1)
					inputDims.d[dimension] = 3;
				else
					inputDims.d[dimension] = 518;
			}
		}
		if (!context->setBindingDimensions(inputBinding, inputDims))
			return Fail("TensorRT rechazó las dimensiones de entrada");
		if (!context->allInputDimensionsSpecified())
			return Fail("TensorRT dejó dimensiones de entrada sin especificar");

		const nvinfer1::Dims outputDims = context->getBindingDimensions(outputBinding);
		if (outputDims.nbDims < 2 || outputDims.d[outputDims.nbDims - 1] <= 0 || outputDims.d[outputDims.nbDims - 2] <= 0)
			return Fail("la salida del engine no tiene resolución espacial válida");
		inputWidth = inputDims.d[3];
		inputHeight = inputDims.d[2];
		modelWidth = outputDims.d[outputDims.nbDims - 1];
		modelHeight = outputDims.d[outputDims.nbDims - 2];
		inputElements = DimsVolume(inputDims);
		outputElements = DimsVolume(outputDims);
		if (inputElements != static_cast<int64_t>(inputWidth) * inputHeight * 3 || outputElements < static_cast<int64_t>(modelWidth) * modelHeight)
			return Fail("las dimensiones del engine no corresponden a una imagen RGB y un mapa de profundidad");

		inputType = engine->getBindingDataType(inputBinding);
		outputType = engine->getBindingDataType(outputBinding);
		if ((inputType != nvinfer1::DataType::kFLOAT && inputType != nvinfer1::DataType::kHALF) ||
			(outputType != nvinfer1::DataType::kFLOAT && outputType != nvinfer1::DataType::kHALF))
			return Fail("el engine requiere tipos TensorRT FLOAT o HALF");
		if (!AllocateBuffers())
			return false;

		loadedEnginePath = path;
		ready = true;
		return true;
	}

	bool EnsureGraphicsResources(unsigned int inputTexture, unsigned int outputTexture)
	{
		if (registeredInputTexture != inputTexture || registeredOutputTexture != outputTexture)
		{
			UnregisterGraphicsResources();
			cudaError_t inputRegistration = cudaGraphicsGLRegisterImage(
				&inputResource,
				inputTexture,
				kGLTexture2D,
				cudaGraphicsRegisterFlagsReadOnly
			);
			if (inputRegistration != cudaSuccess)
				return Fail(CudaError("cudaGraphicsGLRegisterImage(input)", inputRegistration));
			cudaError_t outputRegistration = cudaGraphicsGLRegisterImage(
				&outputResource,
				outputTexture,
				kGLTexture2D,
				cudaGraphicsRegisterFlagsWriteDiscard | cudaGraphicsRegisterFlagsSurfaceLoadStore
			);
			if (outputRegistration != cudaSuccess)
			{
				UnregisterGraphicsResources();
				return Fail(CudaError("cudaGraphicsGLRegisterImage(output)", outputRegistration));
			}
			registeredInputTexture = inputTexture;
			registeredOutputTexture = outputTexture;
		}
		return true;
	}

	bool Process(
		unsigned int inputTexture,
		int sourceWidth,
		int sourceHeight,
		unsigned int outputTexture,
		int destinationWidth,
		int destinationHeight)
	{
		lastError.clear();
		if (!ready)
			return Fail("el engine TensorRT no está cargado");
		if (sourceWidth <= 0 || sourceHeight <= 0 || destinationWidth <= 0 || destinationHeight <= 0)
			return Fail("la textura de entrada o salida no tiene resolución válida");
		if (!EnsureGraphicsResources(inputTexture, outputTexture))
			return false;

		cudaGraphicsResource_t resources[2] = {inputResource, outputResource};
		cudaError_t error = cudaGraphicsMapResources(2, resources, stream);
		if (error != cudaSuccess)
			return Fail(CudaError("cudaGraphicsMapResources", error));
		bool mapped = true;
		cudaArray_t inputArray = nullptr;
		cudaArray_t outputArray = nullptr;
		cudaTextureObject_t sourceObject = 0;
		cudaSurfaceObject_t destinationObject = 0;

		auto failMapped = [&](const std::string& message) {
			cudaStreamSynchronize(stream);
			if (destinationObject != 0)
				cudaDestroySurfaceObject(destinationObject);
			if (sourceObject != 0)
				cudaDestroyTextureObject(sourceObject);
			if (mapped)
				cudaGraphicsUnmapResources(2, resources, stream);
			return Fail(message);
		};

		error = cudaGraphicsSubResourceGetMappedArray(&inputArray, inputResource, 0, 0);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaGraphicsSubResourceGetMappedArray(input)", error));
		error = cudaGraphicsSubResourceGetMappedArray(&outputArray, outputResource, 0, 0);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaGraphicsSubResourceGetMappedArray(output)", error));

		cudaResourceDesc sourceDescription{};
		sourceDescription.resType = cudaResourceTypeArray;
		sourceDescription.res.array.array = inputArray;
		cudaTextureDesc sourceTextureDescription{};
		sourceTextureDescription.addressMode[0] = cudaAddressModeClamp;
		sourceTextureDescription.addressMode[1] = cudaAddressModeClamp;
		sourceTextureDescription.filterMode = cudaFilterModeLinear;
		sourceTextureDescription.readMode = cudaReadModeNormalizedFloat;
		sourceTextureDescription.normalizedCoords = 1;
		error = cudaCreateTextureObject(&sourceObject, &sourceDescription, &sourceTextureDescription, nullptr);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaCreateTextureObject", error));

		cudaResourceDesc destinationDescription{};
		destinationDescription.resType = cudaResourceTypeArray;
		destinationDescription.res.array.array = outputArray;
		error = cudaCreateSurfaceObject(&destinationObject, &destinationDescription);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaCreateSurfaceObject", error));

		const dim3 block2D(16, 16);
		const dim3 grid2D(
			static_cast<unsigned int>((inputWidth + block2D.x - 1) / block2D.x),
			static_cast<unsigned int>((inputHeight + block2D.y - 1) / block2D.y)
		);
		if (inputType == nvinfer1::DataType::kHALF)
			PreprocessKernel<<<grid2D, block2D, 0, stream>>>(sourceObject, reinterpret_cast<__half*>(inputDevice), inputWidth, inputHeight, sourceWidth, sourceHeight);
		else
			PreprocessKernel<<<grid2D, block2D, 0, stream>>>(sourceObject, reinterpret_cast<float*>(inputDevice), inputWidth, inputHeight, sourceWidth, sourceHeight);
		error = cudaGetLastError();
		if (error != cudaSuccess)
			return failMapped(CudaError("PreprocessKernel", error));

		std::vector<void*> bindings(static_cast<size_t>(engine->getNbBindings()), nullptr);
		bindings[static_cast<size_t>(inputBinding)] = inputDevice;
		bindings[static_cast<size_t>(outputBinding)] = outputDevice;
		if (!context->enqueueV2(bindings.data(), stream, nullptr))
			return failMapped("TensorRT rechazó enqueueV2 para el frame de Resolume");

		const int outputCount = static_cast<int>(outputElements);
		const int blocks = (outputCount + 255) / 256;
		if (outputType == nvinfer1::DataType::kHALF)
			ConvertHalfKernel<<<blocks, 256, 0, stream>>>(reinterpret_cast<const __half*>(outputDevice), outputFloatDevice, outputCount);
		else
			ConvertFloatKernel<<<blocks, 256, 0, stream>>>(reinterpret_cast<const float*>(outputDevice), outputFloatDevice, outputCount);
		error = cudaGetLastError();
		if (error != cudaSuccess)
			return failMapped(CudaError("ConvertOutputKernel", error));

		const int pixels = modelWidth * modelHeight;
		ReduceMinMaxKernel<<<reductionBlocks, 256, 0, stream>>>(
			outputFloatDevice,
			blockMinimumDevice,
			blockMaximumDevice,
			pixels
		);
		error = cudaGetLastError();
		if (error != cudaSuccess)
			return failMapped(CudaError("ReduceMinMaxKernel", error));
		std::vector<float> blockMinimum(static_cast<size_t>(reductionBlocks));
		std::vector<float> blockMaximum(static_cast<size_t>(reductionBlocks));
		error = cudaMemcpyAsync(
			blockMinimum.data(),
			blockMinimumDevice,
			blockMinimum.size() * sizeof(float),
			cudaMemcpyDeviceToHost,
			stream
		);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaMemcpyAsync(minimum)", error));
		error = cudaMemcpyAsync(
			blockMaximum.data(),
			blockMaximumDevice,
			blockMaximum.size() * sizeof(float),
			cudaMemcpyDeviceToHost,
			stream
		);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaMemcpyAsync(maximum)", error));
		error = cudaStreamSynchronize(stream);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaStreamSynchronize(reduction)", error));
		float minimum = FLT_MAX;
		float maximum = -FLT_MAX;
		for (int block = 0; block < reductionBlocks; ++block)
		{
			minimum = std::min(minimum, blockMinimum[static_cast<size_t>(block)]);
			maximum = std::max(maximum, blockMaximum[static_cast<size_t>(block)]);
		}
		if (!std::isfinite(minimum) || !std::isfinite(maximum) || maximum - minimum <= 1.0e-6f)
		{
			minimum = 0.0f;
			maximum = 1.0f;
		}
		error = cudaMemcpyAsync(&minimumDevice[0], &minimum, sizeof(float), cudaMemcpyHostToDevice, stream);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaMemcpyAsync(minimum device)", error));
		error = cudaMemcpyAsync(&maximumDevice[0], &maximum, sizeof(float), cudaMemcpyHostToDevice, stream);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaMemcpyAsync(maximum device)", error));
		const dim3 depthGrid(
			static_cast<unsigned int>((destinationWidth + block2D.x - 1) / block2D.x),
			static_cast<unsigned int>((destinationHeight + block2D.y - 1) / block2D.y)
		);
		WriteDepthTextureKernel<<<depthGrid, block2D, 0, stream>>>(
			destinationObject,
			outputFloatDevice,
			modelWidth,
			modelHeight,
			destinationWidth,
			destinationHeight,
			minimumDevice,
			maximumDevice
		);
		error = cudaGetLastError();
		if (error != cudaSuccess)
			return failMapped(CudaError("WriteDepthTextureKernel", error));

		error = cudaStreamSynchronize(stream);
		if (error != cudaSuccess)
			return failMapped(CudaError("cudaStreamSynchronize", error));
		cudaDestroySurfaceObject(destinationObject);
		cudaDestroyTextureObject(sourceObject);
		destinationObject = 0;
		sourceObject = 0;
		error = cudaGraphicsUnmapResources(2, resources, stream);
		mapped = false;
		if (error != cudaSuccess)
			return Fail(CudaError("cudaGraphicsUnmapResources", error));
		return true;
	}

	bool ProcessHost(
		const unsigned char* rgbaPixels,
		int sourceWidth,
		int sourceHeight,
		int destinationWidth,
		int destinationHeight,
		float* destination,
		size_t destinationCount)
	{
		lastError.clear();
		if (!ready)
			return Fail("el engine TensorRT no está cargado");
		if (rgbaPixels == nullptr || destination == nullptr)
			return Fail("la entrada o la salida host es nula");
		if (sourceWidth <= 0 || sourceHeight <= 0 || destinationWidth <= 0 || destinationHeight <= 0)
			return Fail("la textura host no tiene resolución válida");
		if (destinationCount < static_cast<size_t>(destinationWidth) * static_cast<size_t>(destinationHeight) * 4)
			return Fail("la salida host no tiene espacio suficiente");
		if (!EnsureSourceBuffer(sourceWidth, sourceHeight))
			return false;

		const size_t sourceBytes = static_cast<size_t>(sourceWidth) * static_cast<size_t>(sourceHeight) * sizeof(uchar4);
		cudaError_t error = cudaMemcpyAsync(sourceDevice, rgbaPixels, sourceBytes, cudaMemcpyHostToDevice, stream);
		if (error != cudaSuccess)
			return Fail(CudaError("cudaMemcpyAsync(source)", error));

		const dim3 block2D(16, 16);
		const dim3 grid2D(
			static_cast<unsigned int>((inputWidth + block2D.x - 1) / block2D.x),
			static_cast<unsigned int>((inputHeight + block2D.y - 1) / block2D.y)
		);
		if (inputType == nvinfer1::DataType::kHALF)
			PreprocessHostKernel<<<grid2D, block2D, 0, stream>>>(sourceDevice, reinterpret_cast<__half*>(inputDevice), inputWidth, inputHeight, sourceWidth, sourceHeight);
		else
			PreprocessHostKernel<<<grid2D, block2D, 0, stream>>>(sourceDevice, reinterpret_cast<float*>(inputDevice), inputWidth, inputHeight, sourceWidth, sourceHeight);
		error = cudaGetLastError();
		if (error != cudaSuccess)
			return Fail(CudaError("PreprocessHostKernel", error));

		std::vector<void*> bindings(static_cast<size_t>(engine->getNbBindings()), nullptr);
		bindings[static_cast<size_t>(inputBinding)] = inputDevice;
		bindings[static_cast<size_t>(outputBinding)] = outputDevice;
		if (!context->enqueueV2(bindings.data(), stream, nullptr))
			return Fail("TensorRT rechazó enqueueV2 para la entrada host");

		const int outputCount = static_cast<int>(outputElements);
		const int blocks = (outputCount + 255) / 256;
		if (outputType == nvinfer1::DataType::kHALF)
			ConvertHalfKernel<<<blocks, 256, 0, stream>>>(reinterpret_cast<const __half*>(outputDevice), outputFloatDevice, outputCount);
		else
			ConvertFloatKernel<<<blocks, 256, 0, stream>>>(reinterpret_cast<const float*>(outputDevice), outputFloatDevice, outputCount);
		error = cudaGetLastError();
		if (error != cudaSuccess)
			return Fail(CudaError("ConvertOutputHostKernel", error));

		const int pixels = modelWidth * modelHeight;
		std::vector<float> rawDepth(static_cast<size_t>(pixels));
		error = cudaMemcpyAsync(rawDepth.data(), outputFloatDevice, rawDepth.size() * sizeof(float), cudaMemcpyDeviceToHost, stream);
		if (error != cudaSuccess)
			return Fail(CudaError("cudaMemcpyAsync(depth)", error));
		error = cudaStreamSynchronize(stream);
		if (error != cudaSuccess)
			return Fail(CudaError("cudaStreamSynchronize(host)", error));

		float minimum = FLT_MAX;
		float maximum = -FLT_MAX;
		for (const float value : rawDepth)
		{
			if (std::isfinite(value))
			{
				minimum = std::min(minimum, value);
				maximum = std::max(maximum, value);
			}
		}
		if (!std::isfinite(minimum) || !std::isfinite(maximum) || maximum - minimum <= 1.0e-6f)
		{
			minimum = 0.0f;
			maximum = 1.0f;
		}
		const float range = maximum - minimum;
		for (int y = 0; y < destinationHeight; ++y)
		{
			const int sourceY = min(modelHeight - 1, static_cast<int>((static_cast<float>(y) + 0.5f) * modelHeight / destinationHeight));
			for (int x = 0; x < destinationWidth; ++x)
			{
				const int sourceX = min(modelWidth - 1, static_cast<int>((static_cast<float>(x) + 0.5f) * modelWidth / destinationWidth));
				const float value = rawDepth[static_cast<size_t>(sourceY) * modelWidth + sourceX];
				const float normalized = std::isfinite(value) ? std::max(0.0f, std::min(1.0f, (value - minimum) / range)) : 0.5f;
				const size_t index = (static_cast<size_t>(y) * destinationWidth + x) * 4;
				destination[index + 0] = normalized;
				destination[index + 1] = normalized;
				destination[index + 2] = normalized;
				destination[index + 3] = 1.0f;
			}
		}
		return true;
	}
};

extern "C"
{
DEPTHFX_CUDA* DEPTHFX_CUDA_Create()
{
	return new DEPTHFX_CUDA();
}

void DEPTHFX_CUDA_Destroy(DEPTHFX_CUDA* bridge)
{
	delete bridge;
}

bool DEPTHFX_CUDA_LoadEngine(DEPTHFX_CUDA* bridge, const char* enginePath, char* errorMessage, size_t errorMessageSize)
{
	if (bridge == nullptr)
	{
		SetError(errorMessage, errorMessageSize, "bridge CUDA nulo");
		return false;
	}
	const bool success = bridge->LoadEngine(enginePath);
	if (!success)
		SetError(errorMessage, errorMessageSize, bridge->lastError);
	return success;
}

bool DEPTHFX_CUDA_Process(
	DEPTHFX_CUDA* bridge,
	unsigned int inputTexture,
	int inputWidth,
	int inputHeight,
	unsigned int outputTexture,
	int outputWidth,
	int outputHeight,
	char* errorMessage,
	size_t errorMessageSize)
{
	if (bridge == nullptr)
	{
		SetError(errorMessage, errorMessageSize, "bridge CUDA nulo");
		return false;
	}
	const bool success = bridge->Process(inputTexture, inputWidth, inputHeight, outputTexture, outputWidth, outputHeight);
	if (!success)
		SetError(errorMessage, errorMessageSize, bridge->lastError);
	return success;
}

bool DEPTHFX_CUDA_ProcessHost(
	DEPTHFX_CUDA* bridge,
	const unsigned char* rgbaPixels,
	int inputWidth,
	int inputHeight,
	int outputWidth,
	int outputHeight,
	float* outputPixels,
	size_t outputPixelCount,
	char* errorMessage,
	size_t errorMessageSize)
{
	if (bridge == nullptr)
	{
		SetError(errorMessage, errorMessageSize, "bridge CUDA nulo");
		return false;
	}
	const bool success = bridge->ProcessHost(rgbaPixels, inputWidth, inputHeight, outputWidth, outputHeight, outputPixels, outputPixelCount);
	if (!success)
		SetError(errorMessage, errorMessageSize, bridge->lastError);
	return success;
}
}
