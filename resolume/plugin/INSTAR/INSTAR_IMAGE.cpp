#include "INSTAR_IMAGE.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <gdiplus.h>

#include <algorithm>
#include <cmath>
#include <memory>
#include <queue>

namespace
{
std::wstring Utf8ToWide(const std::string& value)
{
	if (value.empty())
		return std::wstring();
	int length = MultiByteToWideChar(CP_UTF8, 0, value.c_str(), -1, nullptr, 0);
	if (length <= 0)
		return std::wstring();
	std::wstring result(static_cast<size_t>(length), L'\0');
	MultiByteToWideChar(CP_UTF8, 0, value.c_str(), -1, &result[0], length);
	result.resize(static_cast<size_t>(length - 1));
	return result;
}

struct HueBand
{
	const char* name;
	bool redWrap = false;
	float low = 0.0f;
	float high = 0.0f;
};

const HueBand BANDS[] = {
	{"RED", true, 0.0f, 10.0f},
	{"ORANGE", false, 10.0f, 22.0f},
	{"YELLOW", false, 22.0f, 42.0f},
	{"GREEN", false, 42.0f, 90.0f},
	{"BLUE", false, 90.0f, 135.0f},
	{"MAGENTA", false, 135.0f, 170.0f},
};

bool IsBand(unsigned char red, unsigned char green, unsigned char blue, const HueBand& band)
{
	const float r = red / 255.0f;
	const float g = green / 255.0f;
	const float b = blue / 255.0f;
	const float maximum = std::max(r, std::max(g, b));
	const float minimum = std::min(r, std::min(g, b));
	const float delta = maximum - minimum;
	if (maximum < 0.18f || delta < 0.08f)
		return false;

	float hue = 0.0f;
	if (delta > 0.0f)
	{
		if (maximum == r)
			hue = 60.0f * std::fmod((g - b) / delta, 6.0f);
		else if (maximum == g)
			hue = 60.0f * (((b - r) / delta) + 2.0f);
		else
			hue = 60.0f * (((r - g) / delta) + 4.0f);
	}
	if (hue < 0.0f)
		hue += 360.0f;
	// The detector bands below use the same 0..180 hue scale as OpenCV.
	hue /= 2.0f;
	const float saturation = delta / maximum;
	if (saturation < 0.22f)
		return false;
	return band.redWrap ? (hue < band.high || hue >= 170.0f) : (hue >= band.low && hue < band.high);
}

void CloseMask(std::vector<unsigned char>& mask, int width, int height)
{
	std::vector<unsigned char> dilated(mask.size(), 0);
	for (int y = 0; y < height; ++y)
	{
		for (int x = 0; x < width; ++x)
		{
			bool found = false;
			for (int dy = -1; dy <= 1 && !found; ++dy)
			{
				for (int dx = -1; dx <= 1; ++dx)
				{
					const int nx = x + dx;
					const int ny = y + dy;
					if (nx >= 0 && nx < width && ny >= 0 && ny < height && mask[ny * width + nx])
					{
						found = true;
						break;
					}
				}
			}
			dilated[y * width + x] = found ? 1 : 0;
		}
	}

	std::vector<unsigned char> eroded(mask.size(), 0);
	for (int y = 0; y < height; ++y)
	{
		for (int x = 0; x < width; ++x)
		{
			bool filled = true;
			for (int dy = -1; dy <= 1 && filled; ++dy)
			{
				for (int dx = -1; dx <= 1; ++dx)
				{
					const int nx = x + dx;
					const int ny = y + dy;
					if (nx < 0 || nx >= width || ny < 0 || ny >= height || !dilated[ny * width + nx])
					{
						filled = false;
						break;
					}
				}
			}
			eroded[y * width + x] = filled ? 1 : 0;
		}
	}
	mask.swap(eroded);
}
}

bool LoadINSTARImage(const std::string& path, INSTARImage& image, std::string& error)
{
	image = INSTARImage();
	const std::wstring widePath = Utf8ToWide(path);
	if (widePath.empty())
	{
		error = "path is not valid UTF-8";
		return false;
	}

	Gdiplus::GdiplusStartupInput startupInput;
	ULONG_PTR token = 0;
	if (Gdiplus::GdiplusStartup(&token, &startupInput, nullptr) != Gdiplus::Ok)
	{
		error = "GDI+ startup failed";
		return false;
	}
	std::unique_ptr<Gdiplus::Bitmap> bitmap(new Gdiplus::Bitmap(widePath.c_str(), FALSE));
	if (bitmap->GetLastStatus() != Gdiplus::Ok || bitmap->GetWidth() == 0 || bitmap->GetHeight() == 0)
	{
		error = "GDI+ could not decode the map image";
		bitmap.reset();
		Gdiplus::GdiplusShutdown(token);
		return false;
	}

	const unsigned int width = bitmap->GetWidth();
	const unsigned int height = bitmap->GetHeight();
	const size_t pixelCount = static_cast<size_t>(width) * static_cast<size_t>(height);
	if (pixelCount > 64U * 1024U * 1024U)
	{
		error = "map image is too large";
		bitmap.reset();
		Gdiplus::GdiplusShutdown(token);
		return false;
	}

	Gdiplus::Rect rect(0, 0, static_cast<INT>(width), static_cast<INT>(height));
	Gdiplus::BitmapData data;
	const Gdiplus::Status locked = bitmap->LockBits(
		&rect,
		Gdiplus::ImageLockModeRead,
		PixelFormat32bppARGB,
		&data
	);
	if (locked != Gdiplus::Ok || data.Scan0 == nullptr)
	{
		error = "GDI+ could not expose bitmap pixels";
		bitmap.reset();
		Gdiplus::GdiplusShutdown(token);
		return false;
	}

	image.width = width;
	image.height = height;
	image.rgba.resize(pixelCount * 4U);
	for (unsigned int y = 0; y < height; ++y)
	{
		const unsigned char* row = static_cast<const unsigned char*>(data.Scan0) + static_cast<ptrdiff_t>(y) * data.Stride;
		for (unsigned int x = 0; x < width; ++x)
		{
			const unsigned char* source = row + static_cast<size_t>(x) * 4U;
			unsigned char* destination = &image.rgba[(static_cast<size_t>(y) * width + x) * 4U];
			destination[0] = source[2];
			destination[1] = source[1];
			destination[2] = source[0];
			destination[3] = source[3];
		}
	}
	bitmap->UnlockBits(&data);
	bitmap.reset();
	Gdiplus::GdiplusShutdown(token);
	return true;
}

std::vector<INSTARSurface> DetectINSTARSurfaces(
	const INSTARImage& image,
	unsigned int canvasWidth,
	unsigned int canvasHeight
)
{
	std::vector<INSTARSurface> result;
	if (image.width == 0 || image.height == 0 || image.rgba.size() < static_cast<size_t>(image.width) * image.height * 4U)
		return result;
	// The plugin runs this only on ExportMapXML, but maps can be several megapixels.
	// A 320-cell long side preserves venue-scale regions while keeping the
	// morphology bounded and responsive on the VJ machine.
	const unsigned int maxSamples = 320;
	const unsigned int stepX = std::max(1U, (image.width + maxSamples - 1U) / maxSamples);
	const unsigned int stepY = std::max(1U, (image.height + maxSamples - 1U) / maxSamples);
	const int gridWidth = static_cast<int>((image.width + stepX - 1U) / stepX);
	const int gridHeight = static_cast<int>((image.height + stepY - 1U) / stepY);
	const size_t gridCells = static_cast<size_t>(gridWidth) * gridHeight;
	const size_t minimumArea = std::max<size_t>(20, gridCells / 500);

	struct Detected
	{
		const HueBand* band;
		int x;
		int y;
		int width;
		int height;
		size_t area;
	};
	std::vector<Detected> detected;
	for (const HueBand& band : BANDS)
	{
		std::vector<unsigned char> mask(gridCells, 0);
		for (int gy = 0; gy < gridHeight; ++gy)
		{
			const unsigned int sourceY = std::min(image.height - 1U, static_cast<unsigned int>(gy) * stepY + stepY / 2U);
			for (int gx = 0; gx < gridWidth; ++gx)
			{
				const unsigned int sourceX = std::min(image.width - 1U, static_cast<unsigned int>(gx) * stepX + stepX / 2U);
				const unsigned char* pixel = &image.rgba[(static_cast<size_t>(sourceY) * image.width + sourceX) * 4U];
				mask[static_cast<size_t>(gy) * gridWidth + gx] = IsBand(pixel[0], pixel[1], pixel[2], band) ? 1 : 0;
			}
		}
		CloseMask(mask, gridWidth, gridHeight);
		std::vector<unsigned char> visited(gridCells, 0);
		for (int gy = 0; gy < gridHeight; ++gy)
		{
			for (int gx = 0; gx < gridWidth; ++gx)
			{
				const size_t start = static_cast<size_t>(gy) * gridWidth + gx;
				if (!mask[start] || visited[start])
					continue;
				std::queue<std::pair<int, int>> pending;
				pending.push({gx, gy});
				visited[start] = 1;
				int minX = gx, maxX = gx, minY = gy, maxY = gy;
				size_t area = 0;
				while (!pending.empty())
				{
					const auto point = pending.front();
					pending.pop();
					++area;
					minX = std::min(minX, point.first);
					maxX = std::max(maxX, point.first);
					minY = std::min(minY, point.second);
					maxY = std::max(maxY, point.second);
					for (int dy = -1; dy <= 1; ++dy)
					{
						for (int dx = -1; dx <= 1; ++dx)
						{
							const int nx = point.first + dx;
							const int ny = point.second + dy;
							if (nx < 0 || nx >= gridWidth || ny < 0 || ny >= gridHeight)
								continue;
							const size_t index = static_cast<size_t>(ny) * gridWidth + nx;
							if (mask[index] && !visited[index])
							{
								visited[index] = 1;
								pending.push({nx, ny});
							}
						}
					}
				}
				const int componentWidth = maxX - minX + 1;
				const int componentHeight = maxY - minY + 1;
				const float rectangularity = static_cast<float>(area) / static_cast<float>(componentWidth * componentHeight);
				if (area >= minimumArea && rectangularity >= 0.20f)
					detected.push_back({&band, minX, minY, componentWidth, componentHeight, area});
			}
		}
	}

	if (detected.empty() || canvasWidth == 0 || canvasHeight == 0)
		return result;
	std::sort(detected.begin(), detected.end(), [](const Detected& first, const Detected& second) {
		return first.area > second.area;
	});
	const auto overlaps = [](const Detected& first, const Detected& second) {
		const int left = std::max(first.x, second.x);
		const int top = std::max(first.y, second.y);
		const int right = std::min(first.x + first.width, second.x + second.width);
		const int bottom = std::min(first.y + first.height, second.y + second.height);
		const int area = std::max(0, right - left) * std::max(0, bottom - top);
		return static_cast<float>(area) / static_cast<float>(std::max<size_t>(1, std::min(first.area, second.area))) >= 0.80f;
	};
	std::vector<Detected> unique;
	for (const Detected& candidate : detected)
	{
		if (std::none_of(unique.begin(), unique.end(), [&](const Detected& existing) { return overlaps(candidate, existing); }))
			unique.push_back(candidate);
	}

	const int minX = std::min_element(unique.begin(), unique.end(), [](const Detected& first, const Detected& second) { return first.x < second.x; })->x;
	const int minY = std::min_element(unique.begin(), unique.end(), [](const Detected& first, const Detected& second) { return first.y < second.y; })->y;
	const int maxX = std::max_element(unique.begin(), unique.end(), [](const Detected& first, const Detected& second) { return first.x + first.width < second.x + second.width; })->x + std::max_element(unique.begin(), unique.end(), [](const Detected& first, const Detected& second) { return first.x + first.width < second.x + second.width; })->width;
	const int maxY = std::max_element(unique.begin(), unique.end(), [](const Detected& first, const Detected& second) { return first.y + first.height < second.y + second.height; })->y + std::max_element(unique.begin(), unique.end(), [](const Detected& first, const Detected& second) { return first.y + first.height < second.y + second.height; })->height;
	const float sourceWidth = static_cast<float>(std::max(1, maxX - minX));
	const float sourceHeight = static_cast<float>(std::max(1, maxY - minY));
	unsigned int sequence = 1;
	for (const Detected& item : unique)
	{
		INSTARSurface surface;
		surface.name = std::string("INSTAR_") + item.band->name + "_" + (sequence < 10 ? "00" : sequence < 100 ? "0" : "") + std::to_string(sequence++);
		surface.x = (static_cast<float>(item.x - minX) / sourceWidth) * canvasWidth;
		surface.y = (static_cast<float>(item.y - minY) / sourceHeight) * canvasHeight;
		surface.width = (static_cast<float>(item.width) / sourceWidth) * canvasWidth;
		surface.height = (static_cast<float>(item.height) / sourceHeight) * canvasHeight;
		result.push_back(surface);
	}
	std::sort(result.begin(), result.end(), [](const INSTARSurface& first, const INSTARSurface& second) {
		return first.y == second.y ? first.x < second.x : first.y < second.y;
	});
	return result;
}
