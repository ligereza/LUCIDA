#include "INSTAR_SCENE.h"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <map>
#include <sstream>
#include <utility>

namespace
{
struct INSTARVec2
{
	float u = 0.0f;
	float v = 0.0f;
};

std::ifstream OpenTextFile(const std::string& path)
{
#ifdef _WIN32
	const int wideLength = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path.c_str(), -1, nullptr, 0);
	if (wideLength > 0)
	{
		std::wstring widePath(static_cast<size_t>(wideLength), L'\0');
		if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path.c_str(), -1, &widePath[0], wideLength) > 0)
		{
			std::ifstream unicodeFile(widePath.c_str());
			if (unicodeFile.is_open())
				return unicodeFile;
		}
	}
#endif
	return std::ifstream(path.c_str());
}

struct INSTARMaterialColour
{
	float red = 1.0f;
	float green = 1.0f;
	float blue = 1.0f;
};

void AddEdge(std::vector<INSTARVertex>& output, const INSTARVec3& first, const INSTARVec3& second, float red, float green, float blue)
{
	output.push_back({first, red, green, blue});
	output.push_back({second, red, green, blue});
}

void AddTriangle(std::vector<INSTARVertex>& output, const INSTARVec3& first, const INSTARVec3& second, const INSTARVec3& third, float red, float green, float blue)
{
	output.push_back({first, red, green, blue});
	output.push_back({second, red, green, blue});
	output.push_back({third, red, green, blue});
}

void AddEdgeTextured(
	std::vector<INSTARVertex>& output,
	const INSTARVec3& first,
	const INSTARVec3& second,
	const INSTARVec2& firstUv,
	const INSTARVec2& secondUv,
	float red,
	float green,
	float blue
)
{
	output.push_back({first, red, green, blue, firstUv.u, firstUv.v, 1.0f});
	output.push_back({second, red, green, blue, secondUv.u, secondUv.v, 1.0f});
}

void AddTriangleTextured(
	std::vector<INSTARVertex>& output,
	const INSTARVec3& first,
	const INSTARVec3& second,
	const INSTARVec3& third,
	const INSTARVec2& firstUv,
	const INSTARVec2& secondUv,
	const INSTARVec2& thirdUv,
	float red,
	float green,
	float blue
)
{
	output.push_back({first, red, green, blue, firstUv.u, firstUv.v, 1.0f});
	output.push_back({second, red, green, blue, secondUv.u, secondUv.v, 1.0f});
	output.push_back({third, red, green, blue, thirdUv.u, thirdUv.v, 1.0f});
}

void Normalise(INSTARScene& scene)
{
	if (scene.lineVertices.empty())
		return;
	INSTARVec3 minimum = scene.lineVertices.front().position;
	INSTARVec3 maximum = minimum;
	for (const INSTARVertex& vertex : scene.lineVertices)
	{
		minimum.x = std::min(minimum.x, vertex.position.x);
		minimum.y = std::min(minimum.y, vertex.position.y);
		minimum.z = std::min(minimum.z, vertex.position.z);
		maximum.x = std::max(maximum.x, vertex.position.x);
		maximum.y = std::max(maximum.y, vertex.position.y);
		maximum.z = std::max(maximum.z, vertex.position.z);
	}
	const INSTARVec3 centre{
		(minimum.x + maximum.x) * 0.5f,
		(minimum.y + maximum.y) * 0.5f,
		(minimum.z + maximum.z) * 0.5f,
	};
	const float extent = std::max(maximum.x - minimum.x, std::max(maximum.y - minimum.y, maximum.z - minimum.z));
	const float scale = extent > 0.000001f ? 2.0f / extent : 1.0f;
	for (INSTARVertex& vertex : scene.lineVertices)
	{
		vertex.position.x = (vertex.position.x - centre.x) * scale;
		vertex.position.y = (vertex.position.y - centre.y) * scale;
		vertex.position.z = (vertex.position.z - centre.z) * scale;
	}
	for (INSTARVertex& vertex : scene.triangleVertices)
	{
		vertex.position.x = (vertex.position.x - centre.x) * scale;
		vertex.position.y = (vertex.position.y - centre.y) * scale;
		vertex.position.z = (vertex.position.z - centre.z) * scale;
	}
	for (INSTARSurface3D& surface : scene.surfaces)
	{
		surface.minimum.x = (surface.minimum.x - centre.x) * scale;
		surface.minimum.y = (surface.minimum.y - centre.y) * scale;
		surface.minimum.z = (surface.minimum.z - centre.z) * scale;
		surface.maximum.x = (surface.maximum.x - centre.x) * scale;
		surface.maximum.y = (surface.maximum.y - centre.y) * scale;
		surface.maximum.z = (surface.maximum.z - centre.z) * scale;
	}
	if (!scene.hasTextureCoordinates)
	{
		const auto generateUv = [](INSTARVertex& vertex) {
			vertex.u = vertex.position.x * 0.5f + 0.5f;
			vertex.v = vertex.position.y * 0.5f + 0.5f;
		};
		for (INSTARVertex& vertex : scene.lineVertices)
			generateUv(vertex);
		for (INSTARVertex& vertex : scene.triangleVertices)
			generateUv(vertex);
	}
	scene.renderCentre = {};
	scene.renderScale = 1.0f;
}

void SetRenderFit(INSTARScene& scene)
{
	if (scene.lineVertices.empty())
		return;
	INSTARVec3 minimum = scene.lineVertices.front().position;
	INSTARVec3 maximum = minimum;
	for (const INSTARVertex& vertex : scene.lineVertices)
	{
		minimum.x = std::min(minimum.x, vertex.position.x);
		minimum.y = std::min(minimum.y, vertex.position.y);
		minimum.z = std::min(minimum.z, vertex.position.z);
		maximum.x = std::max(maximum.x, vertex.position.x);
		maximum.y = std::max(maximum.y, vertex.position.y);
		maximum.z = std::max(maximum.z, vertex.position.z);
	}
	scene.renderCentre = {
		(minimum.x + maximum.x) * 0.5f,
		(minimum.y + maximum.y) * 0.5f,
		(minimum.z + maximum.z) * 0.5f,
	};
	const float extent = std::max(maximum.x - minimum.x, std::max(maximum.y - minimum.y, maximum.z - minimum.z));
	scene.renderScale = extent > 0.000001f ? 2.0f / extent : 1.0f;
}

int ObjIndex(const std::string& token, int positionCount)
{
	const size_t slash = token.find('/');
	const std::string raw = token.substr(0, slash);
	if (raw.empty())
		return -1;
	char* end = nullptr;
	const long value = std::strtol(raw.c_str(), &end, 10);
	if (end == raw.c_str() || value == 0)
		return -1;
	const long index = value > 0 ? value - 1 : positionCount + value;
	return index >= 0 && index < positionCount ? static_cast<int>(index) : -1;
}

int ObjTexcoordIndex(const std::string& token, int texcoordCount)
{
	const size_t firstSlash = token.find('/');
	if (firstSlash == std::string::npos)
		return -1;
	const size_t secondSlash = token.find('/', firstSlash + 1);
	const size_t end = secondSlash == std::string::npos ? token.size() : secondSlash;
	const std::string raw = token.substr(firstSlash + 1, end - firstSlash - 1);
	if (raw.empty())
		return -1;
	char* endPointer = nullptr;
	const long value = std::strtol(raw.c_str(), &endPointer, 10);
	if (endPointer == raw.c_str() || value == 0)
		return -1;
	const long index = value > 0 ? value - 1 : texcoordCount + value;
	return index >= 0 && index < texcoordCount ? static_cast<int>(index) : -1;
}

std::string DirectoryOf(const std::string& path)
{
	const size_t slash = path.find_last_of("/\\");
	return slash == std::string::npos ? std::string() : path.substr(0, slash + 1);
}

void LoadMtlFile(
	const std::string& objPath,
	const std::string& mtlName,
	std::map<std::string, INSTARMaterialColour>& materials
)
{
	std::ifstream file = OpenTextFile(DirectoryOf(objPath) + mtlName);
	if (!file.is_open())
		return;
	std::string currentMaterial;
	std::string line;
	while (std::getline(file, line))
	{
		std::istringstream input(line);
		std::string command;
		input >> command;
		if (command == "newmtl")
		{
			input >> currentMaterial;
			if (!currentMaterial.empty())
				materials[currentMaterial] = INSTARMaterialColour();
		}
		else if (command == "Kd" && !currentMaterial.empty())
		{
			INSTARMaterialColour colour;
			if (input >> colour.red >> colour.green >> colour.blue)
			{
				colour.red = std::max(0.0f, std::min(1.0f, colour.red));
				colour.green = std::max(0.0f, std::min(1.0f, colour.green));
				colour.blue = std::max(0.0f, std::min(1.0f, colour.blue));
				materials[currentMaterial] = colour;
			}
		}
	}
}

void AddBox(INSTARScene& scene, const INSTARVec3& centre, const INSTARVec3& size, float red, float green, float blue)
{
	const float x = size.x * 0.5f;
	const float y = size.y * 0.5f;
	const float z = size.z * 0.5f;
	const INSTARVec3 p[] = {
		{centre.x - x, centre.y - y, centre.z - z}, {centre.x + x, centre.y - y, centre.z - z},
		{centre.x + x, centre.y + y, centre.z - z}, {centre.x - x, centre.y + y, centre.z - z},
		{centre.x - x, centre.y - y, centre.z + z}, {centre.x + x, centre.y - y, centre.z + z},
		{centre.x + x, centre.y + y, centre.z + z}, {centre.x - x, centre.y + y, centre.z + z},
	};
	const int edges[][2] = {{0,1},{1,2},{2,3},{3,0},{4,5},{5,6},{6,7},{7,4},{0,4},{1,5},{2,6},{3,7}};
	for (const auto& edge : edges)
		AddEdge(scene.lineVertices, p[edge[0]], p[edge[1]], red, green, blue);
	const int faces[][4] = {{0,3,2,1},{4,5,6,7},{0,1,5,4},{3,7,6,2},{0,4,7,3},{1,2,6,5}};
	for (const auto& face : faces)
	{
		AddTriangle(scene.triangleVertices, p[face[0]], p[face[1]], p[face[2]], red, green, blue);
		AddTriangle(scene.triangleVertices, p[face[0]], p[face[2]], p[face[3]], red, green, blue);
	}
}

void AddNamedBox(INSTARScene& scene, const std::string& name, const INSTARVec3& centre, const INSTARVec3& size, float red, float green, float blue)
{
	INSTARSurface3D surface;
	surface.name = name;
	surface.minimum = {centre.x - size.x * 0.5f, centre.y - size.y * 0.5f, centre.z - size.z * 0.5f};
	surface.maximum = {centre.x + size.x * 0.5f, centre.y + size.y * 0.5f, centre.z + size.z * 0.5f};
	scene.surfaces.push_back(surface);
	AddBox(scene, centre, size, red, green, blue);
}

bool IsSurfaceGroup(const std::string& value)
{
	std::string lower;
	for (const char character : value)
		lower += static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
	for (const char* token : {"screen", "led", "banner", "cctv", "display", "surface", "panel"})
	{
		if (lower.find(token) != std::string::npos)
			return true;
	}
	return false;
}

bool ParseUnsignedValue(const std::string& value, unsigned int& result)
{
	if (value.empty())
		return false;
	char* end = nullptr;
	const unsigned long parsed = std::strtoul(value.c_str(), &end, 10);
	if (end == value.c_str() || *end != '\0' || parsed == 0 || parsed > 4294967295UL)
		return false;
	result = static_cast<unsigned int>(parsed);
	return true;
}

std::string XmlAttributeValue(const std::string& text, const char* name, size_t start = 0)
{
	const std::string marker = std::string(name) + "=\"";
	const size_t valueStart = text.find(marker, start);
	if (valueStart == std::string::npos)
		return std::string();
	const size_t contentStart = valueStart + marker.size();
	const size_t contentEnd = text.find('"', contentStart);
	return contentEnd == std::string::npos ? std::string() : text.substr(contentStart, contentEnd - contentStart);
}

bool ParseFloatValue(const std::string& value, float& result)
{
	if (value.empty())
		return false;
	char* end = nullptr;
	result = std::strtof(value.c_str(), &end);
	return end != value.c_str() && *end == '\0';
}

std::vector<INSTARVec3> ParseXmlRectPoints(const std::string& text, size_t start, size_t end)
{
	std::vector<INSTARVec3> points;
	size_t cursor = start;
	while (cursor < end)
	{
		const size_t vertex = text.find("<v ", cursor);
		if (vertex == std::string::npos || vertex >= end)
			break;
		float x = 0.0f;
		float y = 0.0f;
		if (ParseFloatValue(XmlAttributeValue(text, "x", vertex), x) &&
			ParseFloatValue(XmlAttributeValue(text, "y", vertex), y))
			points.push_back({x, y, 0.0f});
		cursor = vertex + 3;
	}
	return points;
}

}

namespace
{
std::string PlanLocalName(const std::string& tag)
{
	const size_t separator = tag.find_last_of(':');
	return separator == std::string::npos ? tag : tag.substr(separator + 1U);
}

size_t FindPlanSvgRoot(const std::string& xml)
{
	size_t cursor = 0;
	while (cursor < xml.size())
	{
		const size_t open = xml.find('<', cursor);
		if (open == std::string::npos || open + 1U >= xml.size())
			return std::string::npos;
		if (xml[open + 1U] == '/' || xml[open + 1U] == '!' || xml[open + 1U] == '?')
		{
			cursor = open + 1U;
			continue;
		}
		size_t nameEnd = open + 1U;
		while (nameEnd < xml.size() && !std::isspace(static_cast<unsigned char>(xml[nameEnd])) && xml[nameEnd] != '>' && xml[nameEnd] != '/')
			++nameEnd;
		if (PlanLocalName(xml.substr(open + 1U, nameEnd - open - 1U)) == "svg")
			return open;
		cursor = nameEnd;
	}
	return std::string::npos;
}

std::vector<float> PlanSvgNumbers(const std::string& value);

struct PlanTransform
{
	float a = 1.0f;
	float b = 0.0f;
	float c = 0.0f;
	float d = 1.0f;
	float e = 0.0f;
	float f = 0.0f;
};

PlanTransform ComposePlanTransforms(const PlanTransform& first, const PlanTransform& second)
{
	return {
		first.a * second.a + first.c * second.b,
		first.b * second.a + first.d * second.b,
		first.a * second.c + first.c * second.d,
		first.b * second.c + first.d * second.d,
		first.a * second.e + first.c * second.f + first.e,
		first.b * second.e + first.d * second.f + first.f,
	};
}

INSTARVec3 ApplyPlanTransform(const PlanTransform& transform, const INSTARVec3& point)
{
	return {
		transform.a * point.x + transform.c * point.y + transform.e,
		transform.b * point.x + transform.d * point.y + transform.f,
		0.0f,
	};
}

PlanTransform ParsePlanTransform(const std::string& value)
{
	PlanTransform result;
	size_t cursor = 0;
	while (cursor < value.size())
	{
		while (cursor < value.size() && std::isspace(static_cast<unsigned char>(value[cursor])) != 0)
			++cursor;
		const size_t nameStart = cursor;
		while (cursor < value.size() && std::isalpha(static_cast<unsigned char>(value[cursor])) != 0)
			++cursor;
		if (nameStart == cursor)
			break;
		const std::string operation = value.substr(nameStart, cursor - nameStart);
		while (cursor < value.size() && (std::isspace(static_cast<unsigned char>(value[cursor])) != 0 || value[cursor] == '('))
			++cursor;
		const size_t argumentStart = cursor;
		const size_t argumentEnd = value.find(')', argumentStart);
		if (argumentEnd == std::string::npos)
			break;
		const std::vector<float> arguments = PlanSvgNumbers(value.substr(argumentStart, argumentEnd - argumentStart));
		PlanTransform current;
		if (operation == "matrix" && arguments.size() >= 6U)
			current = {arguments[0], arguments[1], arguments[2], arguments[3], arguments[4], arguments[5]};
		else if (operation == "translate")
			current = {1.0f, 0.0f, 0.0f, 1.0f, arguments.empty() ? 0.0f : arguments[0], arguments.size() > 1U ? arguments[1] : 0.0f};
		else if (operation == "scale" && !arguments.empty())
		{
			const float sy = arguments.size() > 1U ? arguments[1] : arguments[0];
			current = {arguments[0], 0.0f, 0.0f, sy, 0.0f, 0.0f};
		}
		else if (operation == "rotate" && !arguments.empty())
		{
			const float angle = arguments[0] * 0.017453292519943295f;
			const float cosine = std::cos(angle);
			const float sine = std::sin(angle);
			const PlanTransform rotation{cosine, sine, -sine, cosine, 0.0f, 0.0f};
			if (arguments.size() >= 3U)
			{
				const PlanTransform toCentre{1.0f, 0.0f, 0.0f, 1.0f, arguments[1], arguments[2]};
				const PlanTransform fromCentre{1.0f, 0.0f, 0.0f, 1.0f, -arguments[1], -arguments[2]};
				current = ComposePlanTransforms(ComposePlanTransforms(toCentre, rotation), fromCentre);
			}
			else
				current = rotation;
		}
		else if (operation == "skewX" && !arguments.empty())
			current = {1.0f, 0.0f, std::tan(arguments[0] * 0.017453292519943295f), 1.0f, 0.0f, 0.0f};
		else if (operation == "skewY" && !arguments.empty())
			current = {1.0f, std::tan(arguments[0] * 0.017453292519943295f), 0.0f, 1.0f, 0.0f, 0.0f};
		result = ComposePlanTransforms(result, current);
		cursor = argumentEnd + 1U;
	}
	return result;
}

std::vector<float> PlanSvgNumbers(const std::string& value)
{
	std::vector<float> numbers;
	const char* cursor = value.c_str();
	while (*cursor != '\0')
	{
		while (*cursor != '\0' && (std::isspace(static_cast<unsigned char>(*cursor)) || *cursor == ','))
			++cursor;
		if (*cursor == '\0')
			break;
		char* end = nullptr;
		const float number = std::strtof(cursor, &end);
		if (end == cursor)
			return std::vector<float>();
		numbers.push_back(number);
		cursor = end;
	}
	return numbers;
}

bool ParsePlanLength(const std::string& value, float& result)
{
	if (value.empty())
		return false;
	char* end = nullptr;
	result = std::strtof(value.c_str(), &end);
	return end != value.c_str() && std::isfinite(result);
}

std::string PlanXmlAttributeValue(const std::string& text, const char* name, size_t start)
{
	const size_t tagEnd = text.find('>', start);
	if (tagEnd == std::string::npos)
		return std::string();
	const std::string attribute(name);
	size_t cursor = start + 1U;
	while (cursor < tagEnd)
	{
		const size_t valueStart = text.find(attribute, cursor);
		if (valueStart == std::string::npos || valueStart >= tagEnd)
			return std::string();
		const bool boundary = valueStart == start + 1U ||
			std::isspace(static_cast<unsigned char>(text[valueStart - 1U])) != 0;
		if (!boundary)
		{
			cursor = valueStart + attribute.size();
			continue;
		}
		size_t equal = valueStart + attribute.size();
		while (equal < tagEnd && std::isspace(static_cast<unsigned char>(text[equal])) != 0)
			++equal;
		if (equal >= tagEnd || text[equal] != '=')
		{
			cursor = valueStart + attribute.size();
			continue;
		}
		++equal;
		while (equal < tagEnd && std::isspace(static_cast<unsigned char>(text[equal])) != 0)
			++equal;
		if (equal >= tagEnd || (text[equal] != '"' && text[equal] != '\''))
			return std::string();
		const char quote = text[equal++];
		const size_t contentEnd = text.find(quote, equal);
		if (contentEnd == std::string::npos || contentEnd > tagEnd)
			return std::string();
		return text.substr(equal, contentEnd - equal);
	}
	return std::string();
}

bool ParsePlanSvgPath(const std::string& value, std::vector<INSTARVec3>& points, bool& closed, std::string& error)
{
	points.clear();
	closed = false;
	const char* cursor = value.c_str();
	char command = 0;
	INSTARVec3 current;
	INSTARVec3 start;
	INSTARVec3 lastCubicControl;
	INSTARVec3 lastQuadraticControl;
	bool hasLastCubicControl = false;
	bool hasLastQuadraticControl = false;
	const auto appendCubic = [&points](const INSTARVec3& first, const INSTARVec3& controlFirst, const INSTARVec3& controlSecond, const INSTARVec3& second) {
		constexpr unsigned int samples = 12U;
		for (unsigned int sample = 1U; sample <= samples; ++sample)
		{
			const float t = static_cast<float>(sample) / static_cast<float>(samples);
			const float inverse = 1.0f - t;
			points.push_back({
				inverse * inverse * inverse * first.x + 3.0f * inverse * inverse * t * controlFirst.x + 3.0f * inverse * t * t * controlSecond.x + t * t * t * second.x,
				inverse * inverse * inverse * first.y + 3.0f * inverse * inverse * t * controlFirst.y + 3.0f * inverse * t * t * controlSecond.y + t * t * t * second.y,
				0.0f,
			});
		}
	};
	const auto appendArc = [&points](const INSTARVec3& first, float radiusX, float radiusY, float rotationDegrees, bool largeArc, bool sweep, const INSTARVec3& second) {
		radiusX = std::fabs(radiusX);
		radiusY = std::fabs(radiusY);
		if (radiusX < 0.000001f || radiusY < 0.000001f ||
			(std::fabs(first.x - second.x) < 0.000001f && std::fabs(first.y - second.y) < 0.000001f))
		{
			points.push_back(second);
			return;
		}
		const float radians = rotationDegrees * 0.017453292519943295f;
		const float cosine = std::cos(radians);
		const float sine = std::sin(radians);
		const float halfDeltaX = (first.x - second.x) * 0.5f;
		const float halfDeltaY = (first.y - second.y) * 0.5f;
		const float primeX = cosine * halfDeltaX + sine * halfDeltaY;
		const float primeY = -sine * halfDeltaX + cosine * halfDeltaY;
		const float radiusRatio = (primeX * primeX) / (radiusX * radiusX) + (primeY * primeY) / (radiusY * radiusY);
		if (radiusRatio > 1.0f)
		{
			const float correction = std::sqrt(radiusRatio);
			radiusX *= correction;
			radiusY *= correction;
		}
		const float numerator = radiusX * radiusX * radiusY * radiusY - radiusX * radiusX * primeY * primeY - radiusY * radiusY * primeX * primeX;
		const float denominator = radiusX * radiusX * primeY * primeY + radiusY * radiusY * primeX * primeX;
		const float factor = denominator > 0.000001f ? ((largeArc == sweep) ? -1.0f : 1.0f) * std::sqrt(std::max(0.0f, numerator / denominator)) : 0.0f;
		const float centrePrimeX = factor * radiusX * primeY / radiusY;
		const float centrePrimeY = factor * -radiusY * primeX / radiusX;
		const float centreX = cosine * centrePrimeX - sine * centrePrimeY + (first.x + second.x) * 0.5f;
		const float centreY = sine * centrePrimeX + cosine * centrePrimeY + (first.y + second.y) * 0.5f;
		const auto angleBetween = [](float ux, float uy, float vx, float vy) {
			return std::atan2(ux * vy - uy * vx, ux * vx + uy * vy);
		};
		const float unitStartX = (primeX - centrePrimeX) / radiusX;
		const float unitStartY = (primeY - centrePrimeY) / radiusY;
		const float unitEndX = (-primeX - centrePrimeX) / radiusX;
		const float unitEndY = (-primeY - centrePrimeY) / radiusY;
		const float startAngle = angleBetween(1.0f, 0.0f, unitStartX, unitStartY);
		float sweepAngle = angleBetween(unitStartX, unitStartY, unitEndX, unitEndY);
		if (!sweep && sweepAngle > 0.0f)
			sweepAngle -= 6.2831853071795864769f;
		else if (sweep && sweepAngle < 0.0f)
			sweepAngle += 6.2831853071795864769f;
		const unsigned int samples = std::max(4U, std::min(128U, static_cast<unsigned int>(std::ceil(std::fabs(sweepAngle) / 0.2617993877991494f))));
		for (unsigned int sample = 1U; sample <= samples; ++sample)
		{
			const float angle = startAngle + sweepAngle * static_cast<float>(sample) / static_cast<float>(samples);
			const float localX = radiusX * std::cos(angle);
			const float localY = radiusY * std::sin(angle);
			points.push_back({
				cosine * localX - sine * localY + centreX,
				sine * localX + cosine * localY + centreY,
				0.0f,
			});
		}
	};
	while (*cursor != '\0')
	{
		while (*cursor != '\0' && (std::isspace(static_cast<unsigned char>(*cursor)) || *cursor == ','))
			++cursor;
		if (*cursor == '\0')
			break;
		if (std::isalpha(static_cast<unsigned char>(*cursor)))
		{
			command = *cursor++;
			if (std::toupper(static_cast<unsigned char>(command)) == 'Z')
			{
				closed = true;
				current = start;
				command = 0;
				hasLastCubicControl = false;
				hasLastQuadraticControl = false;
			}
			continue;
		}
		if (command == 0)
		{
			error = "SVG path has coordinates without a command";
			return false;
		}
		const bool relative = std::islower(static_cast<unsigned char>(command)) != 0;
		const char operation = static_cast<char>(std::toupper(static_cast<unsigned char>(command)));
		if (operation != 'M' && operation != 'L' && operation != 'H' && operation != 'V' &&
			operation != 'C' && operation != 'S' && operation != 'Q' && operation != 'T' && operation != 'A')
		{
			error = "SVG path uses an unsupported command";
			return false;
		}
		const size_t required = operation == 'H' || operation == 'V' ? 1U :
			(operation == 'C' ? 6U : operation == 'S' ? 4U : operation == 'Q' ? 4U : operation == 'A' ? 7U : 2U);
		std::vector<float> group;
		while (group.size() < required)
		{
			while (*cursor != '\0' && (std::isspace(static_cast<unsigned char>(*cursor)) || *cursor == ','))
				++cursor;
			if (*cursor == '\0' || std::isalpha(static_cast<unsigned char>(*cursor)))
			{
				error = "SVG path has an incomplete coordinate group";
				return false;
			}
			char* end = nullptr;
			const float number = std::strtof(cursor, &end);
			if (end == cursor)
			{
				error = "SVG path contains invalid coordinates";
				return false;
			}
			group.push_back(number);
			cursor = end;
		}
		INSTARVec3 next = current;
		if (operation == 'H')
			next.x = relative ? current.x + group[0] : group[0];
		else if (operation == 'V')
			next.y = relative ? current.y + group[0] : group[0];
		else if (operation == 'A')
		{
			next.x = relative ? current.x + group[5] : group[5];
			next.y = relative ? current.y + group[6] : group[6];
		}
		else
		{
			next.x = relative ? current.x + group[0] : group[0];
			next.y = relative ? current.y + group[1] : group[1];
		}
		if (operation == 'M')
		{
			if (!points.empty())
			{
				error = "SVG path contains multiple subpaths; split them into separate elements";
				return false;
			}
			start = next;
			command = relative ? 'l' : 'L';
			hasLastCubicControl = false;
			hasLastQuadraticControl = false;
		}
		if (operation == 'C')
		{
			INSTARVec3 controlFirst{group[0], group[1], 0.0f};
			INSTARVec3 controlSecond{group[2], group[3], 0.0f};
			if (relative)
			{
				controlFirst.x += current.x;
				controlFirst.y += current.y;
				controlSecond.x += current.x;
				controlSecond.y += current.y;
			}
			appendCubic(current, controlFirst, controlSecond, next);
			lastCubicControl = controlSecond;
			hasLastCubicControl = true;
			hasLastQuadraticControl = false;
		}
		else if (operation == 'S')
		{
			const INSTARVec3 controlFirst = hasLastCubicControl ?
				INSTARVec3{2.0f * current.x - lastCubicControl.x, 2.0f * current.y - lastCubicControl.y, 0.0f} : current;
			INSTARVec3 controlSecond{group[0], group[1], 0.0f};
			if (relative)
			{
				controlSecond.x += current.x;
				controlSecond.y += current.y;
			}
			appendCubic(current, controlFirst, controlSecond, next);
			lastCubicControl = controlSecond;
			hasLastCubicControl = true;
			hasLastQuadraticControl = false;
		}
		else if (operation == 'Q' || operation == 'T')
		{
			INSTARVec3 control;
			if (operation == 'Q')
			{
				control = {group[0], group[1], 0.0f};
				if (relative)
				{
					control.x += current.x;
					control.y += current.y;
				}
			}
			else
				control = hasLastQuadraticControl ? INSTARVec3{2.0f * current.x - lastQuadraticControl.x, 2.0f * current.y - lastQuadraticControl.y, 0.0f} : current;
			const INSTARVec3 controlFirst{
				current.x + (2.0f / 3.0f) * (control.x - current.x),
				current.y + (2.0f / 3.0f) * (control.y - current.y),
				0.0f,
			};
			const INSTARVec3 controlSecond{
				next.x + (2.0f / 3.0f) * (control.x - next.x),
				next.y + (2.0f / 3.0f) * (control.y - next.y),
				0.0f,
			};
			appendCubic(current, controlFirst, controlSecond, next);
			lastQuadraticControl = control;
			hasLastQuadraticControl = true;
			hasLastCubicControl = false;
		}
		else if (operation == 'A')
		{
			appendArc(current, group[0], group[1], group[2], group[3] != 0.0f, group[4] != 0.0f, next);
			hasLastCubicControl = false;
			hasLastQuadraticControl = false;
		}
		else
		{
			points.push_back(next);
			hasLastCubicControl = false;
			hasLastQuadraticControl = false;
		}
		current = next;
	}
	if (points.size() < 2U)
	{
		error = "SVG path has fewer than two points";
		return false;
	}
	return true;
}

float PlanShapeHeight(const std::string& xml, size_t start, float fallback)
{
	float result = fallback;
	float parsed = 0.0f;
	if (ParsePlanLength(PlanXmlAttributeValue(xml, "data-height", start), parsed) ||
		ParsePlanLength(PlanXmlAttributeValue(xml, "data-extrusion-height", start), parsed))
		result = parsed;
	return std::max(0.0f, result);
}

std::string PlanShapeName(const std::string& xml, size_t start, const std::string& tag, unsigned int index)
{
	for (const char* attribute : {"id", "data-name", "aria-label"})
	{
		const std::string value = PlanXmlAttributeValue(xml, attribute, start);
		if (!value.empty())
			return value;
	}
	return tag + "_" + std::to_string(index);
}

std::string PlanShapeRole(const std::string& xml, size_t start)
{
	return PlanXmlAttributeValue(xml, "data-role", start);
}

std::string PlanShapeSliceName(const std::string& xml, size_t start)
{
	return PlanXmlAttributeValue(xml, "data-slice", start);
}

bool PlanElementHidden(const std::string& xml, size_t start, const std::string& localTag)
{
	if (localTag == "defs")
		return true;
	const auto lower = [](std::string value) {
		for (char& character : value)
			character = static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
		return value;
	};
	const std::string display = lower(PlanXmlAttributeValue(xml, "display", start));
	const std::string visibility = lower(PlanXmlAttributeValue(xml, "visibility", start));
	std::string style = lower(PlanXmlAttributeValue(xml, "style", start));
	style.erase(std::remove_if(style.begin(), style.end(), [](char character) {
		return std::isspace(static_cast<unsigned char>(character)) != 0;
	}), style.end());
	return display == "none" || visibility == "hidden" || visibility == "collapse" ||
		style.find("display:none") != std::string::npos || style.find("visibility:hidden") != std::string::npos;
}

std::string PlanNameKey(const std::string& value)
{
	std::string result;
	for (const char character : value)
	{
		if (std::isspace(static_cast<unsigned char>(character)) != 0)
			continue;
		result += static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
	}
	return result;
}

const INSTARInputPlane* FindPlanMapping(const INSTARScene* mapping, const INSTARPlanShape& shape)
{
	if (mapping == nullptr || PlanNameKey(shape.role) != "screen")
		return nullptr;
	const std::string requested = PlanNameKey(shape.sliceName.empty() ? shape.name : shape.sliceName);
	if (requested.empty())
		return nullptr;
	for (const INSTARInputPlane& plane : mapping->inputPlanes)
	{
		if (PlanNameKey(plane.name) == requested)
			return &plane;
	}
	return nullptr;
}

void PlanShapeColour(const std::string& name, float& red, float& green, float& blue)
{
	std::string lower;
	for (const char character : name)
		lower += static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
	if (lower.find("muro") != std::string::npos || lower.find("wall") != std::string::npos || lower.find("pared") != std::string::npos)
		red = 0.70f, green = 0.70f, blue = 0.72f;
	else if (lower.find("tarima") != std::string::npos || lower.find("stage") != std::string::npos || lower.find("escenario") != std::string::npos)
		red = 0.12f, green = 0.78f, blue = 0.86f;
	else if (lower.find("grader") != std::string::npos || lower.find("butaca") != std::string::npos)
		red = 0.90f, green = 0.42f, blue = 0.12f;
	else
		red = 0.30f, green = 0.58f, blue = 0.82f;
}

INSTARVec3 PlanPointToWorld(const INSTARVec3& point, float width, float height, float scale, float vertical)
{
	return {
		(point.x - static_cast<float>(width) * 0.5f) * scale,
		vertical,
		(static_cast<float>(height) * 0.5f - point.y) * scale,
	};
}

void AddPlanWall(INSTARScene& scene, const INSTARVec3& first, const INSTARVec3& second, float height, float red, float green, float blue)
{
	const INSTARVec3 bottomFirst{first.x, 0.0f, first.z};
	const INSTARVec3 bottomSecond{second.x, 0.0f, second.z};
	const INSTARVec3 topFirst{first.x, height, first.z};
	const INSTARVec3 topSecond{second.x, height, second.z};
	AddEdge(scene.lineVertices, bottomFirst, bottomSecond, red, green, blue);
	AddEdge(scene.lineVertices, topFirst, topSecond, red, green, blue);
	AddEdge(scene.lineVertices, bottomFirst, topFirst, red, green, blue);
	AddEdge(scene.lineVertices, bottomSecond, topSecond, red, green, blue);
	AddTriangle(scene.triangleVertices, bottomFirst, bottomSecond, topSecond, red * 0.55f, green * 0.55f, blue * 0.55f);
	AddTriangle(scene.triangleVertices, bottomFirst, topSecond, topFirst, red, green, blue);
}

void AddPlanScreen(
	INSTARScene& scene,
	const INSTARVec3& first,
	const INSTARVec3& second,
	float height,
	float red,
	float green,
	float blue,
	const INSTARPlanShape& shape
)
{
	const INSTARVec3 bottomFirst{first.x, 0.0f, first.z};
	const INSTARVec3 bottomSecond{second.x, 0.0f, second.z};
	const INSTARVec3 topFirst{first.x, height, first.z};
	const INSTARVec3 topSecond{second.x, height, second.z};
	AddEdge(scene.lineVertices, bottomFirst, bottomSecond, red, green, blue);
	AddEdge(scene.lineVertices, topFirst, topSecond, red, green, blue);
	AddEdge(scene.lineVertices, bottomFirst, topFirst, red, green, blue);
	AddEdge(scene.lineVertices, bottomSecond, topSecond, red, green, blue);
	if (shape.mapped && shape.mappingCorners.size() >= 4U && shape.mappingCanvasWidth > 0U && shape.mappingCanvasHeight > 0U)
	{
		const auto toUv = [&shape](const INSTARVec3& point) {
			return INSTARVec2{
				point.x / static_cast<float>(shape.mappingCanvasWidth),
				point.y / static_cast<float>(shape.mappingCanvasHeight),
			};
		};
		const INSTARVec2 firstUv = toUv(shape.mappingCorners[0]);
		const INSTARVec2 secondUv = toUv(shape.mappingCorners[1]);
		const INSTARVec2 thirdUv = toUv(shape.mappingCorners[2]);
		const INSTARVec2 fourthUv = toUv(shape.mappingCorners[3]);
		AddTriangleTextured(scene.triangleVertices, bottomFirst, bottomSecond, topSecond, firstUv, secondUv, thirdUv, red, green, blue);
		AddTriangleTextured(scene.triangleVertices, bottomFirst, topSecond, topFirst, firstUv, thirdUv, fourthUv, red, green, blue);
		scene.hasTextureCoordinates = true;
	}
	else
	{
		AddTriangle(scene.triangleVertices, bottomFirst, bottomSecond, topSecond, red, green, blue);
		AddTriangle(scene.triangleVertices, bottomFirst, topSecond, topFirst, red, green, blue);
	}
}

std::pair<INSTARVec3, INSTARVec3> SelectPlanScreenEdge(const std::vector<INSTARVec3>& points, bool closed)
{
	if (points.size() < 2U)
		return {INSTARVec3(), INSTARVec3()};
	const size_t segmentCount = closed && points.size() >= 3U ? points.size() : points.size() - 1U;
	size_t selected = 0U;
	float longest = -1.0f;
	for (size_t index = 0; index < segmentCount; ++index)
	{
		const INSTARVec3& first = points[index];
		const INSTARVec3& second = points[(index + 1U) % points.size()];
		const float dx = second.x - first.x;
		const float dz = second.z - first.z;
		const float lengthSquared = dx * dx + dz * dz;
		if (lengthSquared > longest)
		{
			longest = lengthSquared;
			selected = index;
		}
	}
	return {points[selected], points[(selected + 1U) % points.size()]};
}

float PlanCross(const INSTARVec3& first, const INSTARVec3& second, const INSTARVec3& third)
{
	return (second.x - first.x) * (third.z - first.z) - (second.z - first.z) * (third.x - first.x);
}

bool PlanPointInTriangle(const INSTARVec3& point, const INSTARVec3& first, const INSTARVec3& second, const INSTARVec3& third, bool counterClockwise)
{
	const float firstCross = PlanCross(first, second, point);
	const float secondCross = PlanCross(second, third, point);
	const float thirdCross = PlanCross(third, first, point);
	const float epsilon = 0.000001f;
	if (counterClockwise)
		return firstCross >= -epsilon && secondCross >= -epsilon && thirdCross >= -epsilon;
	return firstCross <= epsilon && secondCross <= epsilon && thirdCross <= epsilon;
}

void AddPlanCap(INSTARScene& scene, const std::vector<INSTARVec3>& points, float height, float red, float green, float blue)
{
	if (points.size() < 3U)
		return;
	float area = 0.0f;
	for (size_t index = 0; index < points.size(); ++index)
	{
		const INSTARVec3& first = points[index];
		const INSTARVec3& second = points[(index + 1U) % points.size()];
		area += first.x * second.z - second.x * first.z;
	}
	if (std::fabs(area) < 0.000001f)
		return;
	const bool counterClockwise = area > 0.0f;
	std::vector<size_t> remaining;
	for (size_t index = 0; index < points.size(); ++index)
		remaining.push_back(index);
	const size_t maximumIterations = points.size() * points.size();
	for (size_t iteration = 0; remaining.size() > 3U && iteration < maximumIterations; ++iteration)
	{
		bool clipped = false;
		for (size_t index = 0; index < remaining.size(); ++index)
		{
			const size_t previousIndex = remaining[(index + remaining.size() - 1U) % remaining.size()];
			const size_t currentIndex = remaining[index];
			const size_t nextIndex = remaining[(index + 1U) % remaining.size()];
			const float cross = PlanCross(points[previousIndex], points[currentIndex], points[nextIndex]);
			if ((counterClockwise && cross <= 0.000001f) || (!counterClockwise && cross >= -0.000001f))
				continue;
			bool containsPoint = false;
			for (const size_t candidate : remaining)
			{
				if (candidate == previousIndex || candidate == currentIndex || candidate == nextIndex)
					continue;
				if (PlanPointInTriangle(points[candidate], points[previousIndex], points[currentIndex], points[nextIndex], counterClockwise))
				{
					containsPoint = true;
					break;
				}
			}
			if (containsPoint)
				continue;
			const INSTARVec3 first{points[previousIndex].x, height, points[previousIndex].z};
			const INSTARVec3 second{points[currentIndex].x, height, points[currentIndex].z};
			const INSTARVec3 third{points[nextIndex].x, height, points[nextIndex].z};
			if (counterClockwise)
				AddTriangle(scene.triangleVertices, first, second, third, red, green, blue);
			else
				AddTriangle(scene.triangleVertices, first, third, second, red, green, blue);
			remaining.erase(remaining.begin() + static_cast<std::ptrdiff_t>(index));
			clipped = true;
			break;
		}
		if (!clipped)
			return;
	}
	if (remaining.size() == 3U)
	{
		const INSTARVec3 first{points[remaining[0]].x, height, points[remaining[0]].z};
		const INSTARVec3 second{points[remaining[1]].x, height, points[remaining[1]].z};
		const INSTARVec3 third{points[remaining[2]].x, height, points[remaining[2]].z};
		if (counterClockwise)
			AddTriangle(scene.triangleVertices, first, second, third, red, green, blue);
		else
			AddTriangle(scene.triangleVertices, first, third, second, red, green, blue);
	}
}
}

bool LoadINSTARObj(const std::string& path, INSTARScene& scene, std::string& error)
{
	scene = INSTARScene();
	std::ifstream file = OpenTextFile(path);
	if (!file.is_open())
	{
		error = "OBJ file could not be opened";
		return false;
	}
	std::vector<INSTARVec3> positions;
	std::vector<INSTARVec2> texcoords;
	std::map<std::string, std::vector<int>> groupPositions;
	std::map<std::string, INSTARMaterialColour> materials;
	std::string currentGroup = "OBJ";
	std::string currentMaterial;
	std::string line;
	unsigned int faceNumber = 0;
	while (std::getline(file, line))
	{
		std::istringstream input(line);
		std::string command;
		input >> command;
		if (command.empty() || command[0] == '#')
			continue;
		if (command == "v")
		{
			INSTARVec3 position;
			if (input >> position.x >> position.y >> position.z)
				positions.push_back(position);
			continue;
		}
		if (command == "vt")
		{
			INSTARVec2 texcoord;
			if (input >> texcoord.u >> texcoord.v)
				texcoords.push_back(texcoord);
			continue;
		}
		if (command == "o" || command == "g")
		{
			input >> currentGroup;
			if (currentGroup.empty())
				currentGroup = "OBJ";
			continue;
		}
		if (command == "mtllib")
		{
			std::string materialLibrary;
			while (input >> materialLibrary)
				LoadMtlFile(path, materialLibrary, materials);
			continue;
		}
		if (command == "usemtl")
		{
			input >> currentMaterial;
			continue;
		}
		if (command != "f")
			continue;

		std::vector<int> face;
		std::vector<int> faceTexcoords;
		std::string token;
		while (input >> token)
		{
			const int index = ObjIndex(token, static_cast<int>(positions.size()));
			if (index >= 0)
			{
				face.push_back(index);
				faceTexcoords.push_back(ObjTexcoordIndex(token, static_cast<int>(texcoords.size())));
			}
		}
		if (face.size() < 3)
			continue;
		groupPositions[currentGroup].insert(groupPositions[currentGroup].end(), face.begin(), face.end());
		INSTARMaterialColour colour;
		const auto material = materials.find(currentMaterial);
		if (material != materials.end())
			colour = material->second;
		else
		{
			colour.red = 0.35f + static_cast<float>((faceNumber * 37U) % 55U) / 100.0f;
			colour.green = 0.45f + static_cast<float>((faceNumber * 19U) % 45U) / 100.0f;
			colour.blue = 0.55f + static_cast<float>((faceNumber * 11U) % 35U) / 100.0f;
		}
		for (size_t index = 1; index + 1 < face.size(); ++index)
		{
			const INSTARVec3& first = positions[face[0]];
			const INSTARVec3& second = positions[face[index]];
			const INSTARVec3& third = positions[face[index + 1]];
			const auto fallbackUv = [](const INSTARVec3& vertex) {
				return INSTARVec2{vertex.x * 0.5f + 0.5f, vertex.y * 0.5f + 0.5f};
			};
			const auto uvFor = [&texcoords, &faceTexcoords, index, &fallbackUv](size_t faceIndex, const INSTARVec3& vertex) {
				const int uvIndex = faceTexcoords[faceIndex];
				return uvIndex >= 0 ? texcoords[uvIndex] : fallbackUv(vertex);
			};
			const INSTARVec2 firstUv = uvFor(0, first);
			const INSTARVec2 secondUv = uvFor(index, second);
			const INSTARVec2 thirdUv = uvFor(index + 1, third);
			if (faceTexcoords[0] >= 0 || faceTexcoords[index] >= 0 || faceTexcoords[index + 1] >= 0)
				scene.hasTextureCoordinates = true;
			AddEdgeTextured(scene.lineVertices, first, second, firstUv, secondUv, colour.red, colour.green, colour.blue);
			AddEdgeTextured(scene.lineVertices, second, third, secondUv, thirdUv, colour.red, colour.green, colour.blue);
			AddEdgeTextured(scene.lineVertices, third, first, thirdUv, firstUv, colour.red, colour.green, colour.blue);
			AddTriangleTextured(scene.triangleVertices, first, second, third, firstUv, secondUv, thirdUv, colour.red, colour.green, colour.blue);
		}
		++faceNumber;
	}
	if (positions.empty() || scene.lineVertices.empty())
	{
		error = "OBJ contains no renderable faces";
		return false;
	}
	for (const auto& group : groupPositions)
	{
		if (!IsSurfaceGroup(group.first))
			continue;
		std::vector<int> indices = group.second;
		std::sort(indices.begin(), indices.end());
		indices.erase(std::unique(indices.begin(), indices.end()), indices.end());
		if (indices.empty())
			continue;
		INSTARSurface3D surface;
		surface.name = group.first;
		surface.minimum = positions[indices.front()];
		surface.maximum = positions[indices.front()];
		for (const int index : indices)
		{
			const INSTARVec3& position = positions[index];
			surface.minimum.x = std::min(surface.minimum.x, position.x);
			surface.minimum.y = std::min(surface.minimum.y, position.y);
			surface.minimum.z = std::min(surface.minimum.z, position.z);
			surface.maximum.x = std::max(surface.maximum.x, position.x);
			surface.maximum.y = std::max(surface.maximum.y, position.y);
			surface.maximum.z = std::max(surface.maximum.z, position.z);
		}
		scene.surfaces.push_back(surface);
	}
	Normalise(scene);
	scene.fromObj = true;
	scene.source = path;
	return true;
}

void ApplyINSTARInputPlaneDepths(INSTARScene& scene, const std::vector<float>& depths)
{
	scene.lineVertices.clear();
	scene.triangleVertices.clear();
	scene.surfaces.clear();
	scene.hasTextureCoordinates = true;
	if (scene.inputCanvasWidth == 0 || scene.inputCanvasHeight == 0)
		return;
	const float canvasAspect = static_cast<float>(scene.inputCanvasHeight) / static_cast<float>(scene.inputCanvasWidth);
	for (size_t index = 0; index < scene.inputPlanes.size(); ++index)
	{
		INSTARInputPlane& plane = scene.inputPlanes[index];
		const float depth = index < depths.size() ? depths[index] : 0.0f;
		plane.depth = depth;
		std::vector<INSTARVec3> corners = plane.corners;
		if (corners.size() < 4U)
		{
			corners = {
				{plane.x, plane.y, 0.0f},
				{plane.x + plane.width, plane.y, 0.0f},
				{plane.x + plane.width, plane.y + plane.height, 0.0f},
				{plane.x, plane.y + plane.height, 0.0f},
			};
		}
		const auto toWorld = [canvasAspect, &scene, depth](const INSTARVec3& point) {
			return INSTARVec3{
				point.x / static_cast<float>(scene.inputCanvasWidth) * 2.0f - 1.0f,
				(0.5f - point.y / static_cast<float>(scene.inputCanvasHeight)) * 2.0f * canvasAspect,
				depth,
			};
		};
		const auto toUv = [&scene](const INSTARVec3& point) {
			return INSTARVec2{
				point.x / static_cast<float>(scene.inputCanvasWidth),
				point.y / static_cast<float>(scene.inputCanvasHeight),
			};
		};
		const INSTARVec3 first = toWorld(corners[0]);
		const INSTARVec3 second = toWorld(corners[1]);
		const INSTARVec3 third = toWorld(corners[2]);
		const INSTARVec3 fourth = toWorld(corners[3]);
		const INSTARVec2 firstUv = toUv(corners[0]);
		const INSTARVec2 secondUv = toUv(corners[1]);
		const INSTARVec2 thirdUv = toUv(corners[2]);
		const INSTARVec2 fourthUv = toUv(corners[3]);
		const float red = 0.20f + static_cast<float>((index * 37U) % 55U) / 100.0f;
		const float green = 0.55f + static_cast<float>((index * 19U) % 35U) / 100.0f;
		const float blue = 0.70f + static_cast<float>((index * 11U) % 25U) / 100.0f;
		AddEdgeTextured(scene.lineVertices, first, second, firstUv, secondUv, red, green, blue);
		AddEdgeTextured(scene.lineVertices, second, third, secondUv, thirdUv, red, green, blue);
		AddEdgeTextured(scene.lineVertices, third, fourth, thirdUv, fourthUv, red, green, blue);
		AddEdgeTextured(scene.lineVertices, fourth, first, fourthUv, firstUv, red, green, blue);
		AddTriangleTextured(scene.triangleVertices, first, second, third, firstUv, secondUv, thirdUv, red, green, blue);
		AddTriangleTextured(scene.triangleVertices, first, third, fourth, firstUv, thirdUv, fourthUv, red, green, blue);
	}
	scene.renderCentre = {};
	scene.renderScale = 1.0f;
}

bool LoadINSTARAdvancedOutputPlanes(const std::string& path, INSTARScene& scene, std::string& error)
{
	scene = INSTARScene();
	std::ifstream file = OpenTextFile(path);
	if (!file.is_open())
	{
		error = "Advanced Output XML could not be opened";
		return false;
	}
	const std::string xml((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
	const size_t texture = xml.find("<CurrentCompositionTextureSize");
	if (texture == std::string::npos ||
		!ParseUnsignedValue(XmlAttributeValue(xml, "width", texture), scene.inputCanvasWidth) ||
		!ParseUnsignedValue(XmlAttributeValue(xml, "height", texture), scene.inputCanvasHeight))
	{
		error = "Advanced Output XML has no valid composition texture size";
		return false;
	}
	size_t cursor = xml.find("<Slice");
	while (cursor != std::string::npos)
	{
		const size_t close = xml.find("</Slice>", cursor);
		if (close == std::string::npos)
		{
			error = "Advanced Output XML has an unterminated Slice";
			return false;
		}
		const size_t inputRect = xml.find("<InputRect", cursor);
		const size_t inputRectClose = inputRect == std::string::npos ? std::string::npos : xml.find("</InputRect>", inputRect);
		if (inputRect == std::string::npos || inputRect >= close || inputRectClose == std::string::npos || inputRectClose > close)
		{
			cursor = xml.find("<Slice", close + 8);
			continue;
		}
		const std::vector<INSTARVec3> points = ParseXmlRectPoints(xml, inputRect, inputRectClose);
		if (points.size() >= 4U)
		{
			INSTARInputPlane plane;
			plane.corners.assign(points.begin(), points.begin() + 4U);
			const size_t nameParam = xml.find("<Param name=\"Name\"", cursor);
			if (nameParam != std::string::npos && nameParam < close)
				plane.name = XmlAttributeValue(xml, "value", nameParam);
			if (plane.name.empty())
				plane.name = "SLICE_" + std::to_string(scene.inputPlanes.size() + 1U);
			float minX = points.front().x;
			float maxX = points.front().x;
			float minY = points.front().y;
			float maxY = points.front().y;
			for (const INSTARVec3& point : points)
			{
				minX = std::min(minX, point.x);
				maxX = std::max(maxX, point.x);
				minY = std::min(minY, point.y);
				maxY = std::max(maxY, point.y);
			}
			plane.x = minX;
			plane.y = minY;
			plane.width = maxX - minX;
			plane.height = maxY - minY;
			if (plane.width > 0.0f && plane.height > 0.0f)
				scene.inputPlanes.push_back(plane);
		}
		cursor = xml.find("<Slice", close + 8);
	}
	if (scene.inputPlanes.empty())
	{
		error = "Advanced Output XML contains no rectangular InputRect slices";
		return false;
	}
	scene.textureCanvasWidth = scene.inputCanvasWidth;
	scene.textureCanvasHeight = scene.inputCanvasHeight;
	ApplyINSTARInputPlaneDepths(scene, std::vector<float>());
	scene.source = path;
	return true;
}

bool LoadINSTARPlanSvg(const std::string& path, INSTARScene& scene, std::string& error, float extrusionHeight, float planScale, const std::vector<float>& heightOverrides, const INSTARScene* mapping, bool useGlobalHeight)
{
	scene = INSTARScene();
	std::ifstream file = OpenTextFile(path);
	if (!file.is_open())
	{
		error = "plan SVG could not be opened";
		return false;
	}
	const std::string xml((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
	const size_t root = FindPlanSvgRoot(xml);
	if (root == std::string::npos)
	{
		error = "plan file has no SVG root";
		return false;
	}
	const std::vector<float> viewBox = PlanSvgNumbers(XmlAttributeValue(xml, "viewBox", root));
	float viewMinX = 0.0f;
	float viewMinY = 0.0f;
	float viewWidth = 0.0f;
	float viewHeight = 0.0f;
	if (viewBox.size() == 4U && viewBox[2] > 0.0f && viewBox[3] > 0.0f)
	{
		viewMinX = viewBox[0];
		viewMinY = viewBox[1];
		viewWidth = viewBox[2];
		viewHeight = viewBox[3];
	}
	else
	{
		const auto scalarAttribute = [&xml, root](const char* name) {
			const std::string value = PlanXmlAttributeValue(xml, name, root);
			char* end = nullptr;
			const float parsed = std::strtof(value.c_str(), &end);
			return end != value.c_str() && std::isfinite(parsed) ? parsed : 0.0f;
		};
		viewWidth = scalarAttribute("width");
		viewHeight = scalarAttribute("height");
	}
	if (!(viewWidth > 0.0f && viewHeight > 0.0f))
	{
		error = "plan SVG needs a positive viewBox or width/height";
		return false;
	}
	scene.inputCanvasWidth = static_cast<unsigned int>(std::max(1.0f, viewWidth));
	scene.inputCanvasHeight = static_cast<unsigned int>(std::max(1.0f, viewHeight));
	if (mapping != nullptr)
	{
		scene.textureCanvasWidth = mapping->inputCanvasWidth;
		scene.textureCanvasHeight = mapping->inputCanvasHeight;
	}
	const float safeHeight = std::isfinite(extrusionHeight) ? std::max(0.0f, extrusionHeight) : 3.0f;
	const float safeScale = std::isfinite(planScale) ? std::max(0.000001f, planScale) : 1.0f;
	// SVG viewBox units are arbitrary. Normalize the plan footprint to a
	// stable preview reference, then use PlanScale as a proportion control.
	const float planReference = 48.0f / std::max(viewWidth, viewHeight);
	const float effectivePlanScale = planReference * safeScale;

	const auto isShapeTag = [](const std::string& tag) {
		const std::string localName = PlanLocalName(tag);
		return localName == "rect" || localName == "polygon" || localName == "polyline" || localName == "line" ||
			localName == "circle" || localName == "ellipse" || localName == "path";
	};
	size_t cursor = root;
	unsigned int shapeIndex = 1;
	bool unsupportedPathFound = false;
	std::vector<std::string> elementStack;
	std::vector<PlanTransform> transformStack;
	std::vector<bool> visibilityStack;
	while (cursor < xml.size())
	{
		const size_t open = xml.find('<', cursor);
		if (open == std::string::npos)
			break;
		if (open + 1U >= xml.size())
			break;
		if (xml[open + 1U] == '/')
		{
			const size_t close = xml.find('>', open + 2U);
			if (close == std::string::npos)
			{
				error = "plan SVG has an unterminated closing element";
				return false;
			}
			if (!elementStack.empty())
			{
				elementStack.pop_back();
				transformStack.pop_back();
				visibilityStack.pop_back();
			}
			cursor = close + 1U;
			continue;
		}
		if (xml[open + 1U] == '!' || xml[open + 1U] == '?')
		{
			cursor = open + 1U;
			continue;
		}
		size_t nameEnd = open + 1U;
		while (nameEnd < xml.size() && !std::isspace(static_cast<unsigned char>(xml[nameEnd])) && xml[nameEnd] != '>' && xml[nameEnd] != '/')
			++nameEnd;
		const std::string tag = xml.substr(open + 1U, nameEnd - open - 1U);
		const size_t close = xml.find('>', nameEnd);
		if (close == std::string::npos)
		{
			error = "plan SVG has an unterminated element";
			return false;
		}
		const PlanTransform parentTransform = transformStack.empty() ? PlanTransform() : transformStack.back();
		const PlanTransform elementTransform = ComposePlanTransforms(
			parentTransform,
			ParsePlanTransform(PlanXmlAttributeValue(xml, "transform", open))
		);
		const std::string localTag = PlanLocalName(tag);
		const bool parentVisible = visibilityStack.empty() ? true : visibilityStack.back();
		const bool elementVisible = parentVisible && !PlanElementHidden(xml, open, localTag);
		if (isShapeTag(tag) && elementVisible)
		{
			INSTARPlanShape shape;
			const unsigned int shapeNumber = shapeIndex++;
			shape.name = PlanShapeName(xml, open, tag, shapeNumber);
			shape.role = PlanShapeRole(xml, open);
			shape.sliceName = PlanShapeSliceName(xml, open);
			shape.height = PlanShapeHeight(xml, open, safeHeight);
			if (useGlobalHeight)
				shape.height = safeHeight;
			if (shapeNumber > 0U && shapeNumber <= heightOverrides.size() && heightOverrides[shapeNumber - 1U] != 0.0f)
				shape.height = std::max(0.0f, heightOverrides[shapeNumber - 1U]);
			if (localTag == "rect")
			{
				float x = 0.0f, y = 0.0f, width = 0.0f, height = 0.0f;
				if (ParsePlanLength(PlanXmlAttributeValue(xml, "x", open), x) &&
					ParsePlanLength(PlanXmlAttributeValue(xml, "y", open), y) &&
					ParsePlanLength(PlanXmlAttributeValue(xml, "width", open), width) &&
					ParsePlanLength(PlanXmlAttributeValue(xml, "height", open), height) &&
					width > 0.0f && height > 0.0f)
				{
					shape.points = {{x, y, 0.0f}, {x + width, y, 0.0f}, {x + width, y + height, 0.0f}, {x, y + height, 0.0f}};
					shape.closed = true;
				}
			}
			else if (localTag == "line")
			{
				float x1 = 0.0f, y1 = 0.0f, x2 = 0.0f, y2 = 0.0f;
				if (ParsePlanLength(PlanXmlAttributeValue(xml, "x1", open), x1) &&
					ParsePlanLength(PlanXmlAttributeValue(xml, "y1", open), y1) &&
					ParsePlanLength(PlanXmlAttributeValue(xml, "x2", open), x2) &&
					ParsePlanLength(PlanXmlAttributeValue(xml, "y2", open), y2))
					shape.points = {{x1, y1, 0.0f}, {x2, y2, 0.0f}};
			}
			else if (localTag == "polygon" || localTag == "polyline")
			{
				const std::vector<float> values = PlanSvgNumbers(PlanXmlAttributeValue(xml, "points", open));
				const size_t minimumValues = localTag == "polygon" ? 6U : 4U;
				if (values.size() >= minimumValues && values.size() % 2U == 0U)
				{
					for (size_t index = 0; index < values.size(); index += 2U)
						shape.points.push_back({values[index], values[index + 1U], 0.0f});
					shape.closed = localTag == "polygon";
				}
			}
			else if (localTag == "circle" || localTag == "ellipse")
			{
				float centreX = 0.0f, centreY = 0.0f, radiusX = 0.0f, radiusY = 0.0f;
				ParsePlanLength(PlanXmlAttributeValue(xml, "cx", open), centreX);
				ParsePlanLength(PlanXmlAttributeValue(xml, "cy", open), centreY);
				bool validRadius = false;
				if (localTag == "circle")
				{
					validRadius = ParsePlanLength(PlanXmlAttributeValue(xml, "r", open), radiusX);
					radiusY = radiusX;
				}
				else
					validRadius = ParsePlanLength(PlanXmlAttributeValue(xml, "rx", open), radiusX) && ParsePlanLength(PlanXmlAttributeValue(xml, "ry", open), radiusY);
				if (validRadius && radiusX > 0.0f && radiusY > 0.0f)
				{
					constexpr unsigned int samples = 32U;
					for (unsigned int sample = 0U; sample < samples; ++sample)
					{
						const float angle = 6.2831853071795864769f * static_cast<float>(sample) / static_cast<float>(samples);
						shape.points.push_back({centreX + radiusX * std::cos(angle), centreY + radiusY * std::sin(angle), 0.0f});
					}
					shape.closed = true;
				}
			}
			else if (localTag == "path")
			{
				std::string pathError;
				if (!ParsePlanSvgPath(PlanXmlAttributeValue(xml, "d", open), shape.points, shape.closed, pathError))
				{
					// SVG exports commonly include decorative/text paths with Bézier
					// curves. They are not plan geometry; ignore them and keep
					// reading the line/polygon geometry that can be extruded.
					unsupportedPathFound = true;
					shape.points.clear();
				}
			}
			if (shape.points.size() >= 2U)
			{
				for (INSTARVec3& point : shape.points)
				{
					point = ApplyPlanTransform(elementTransform, point);
					point.x -= viewMinX;
					point.y -= viewMinY;
				}
				if (const INSTARInputPlane* matchedPlane = FindPlanMapping(mapping, shape))
				{
					shape.mapped = true;
					shape.mappingCorners = matchedPlane->corners;
					if (shape.mappingCorners.size() < 4U)
						shape.mappingCorners = {
							{matchedPlane->x, matchedPlane->y, 0.0f},
							{matchedPlane->x + matchedPlane->width, matchedPlane->y, 0.0f},
							{matchedPlane->x + matchedPlane->width, matchedPlane->y + matchedPlane->height, 0.0f},
							{matchedPlane->x, matchedPlane->y + matchedPlane->height, 0.0f},
						};
					shape.mappingCanvasWidth = mapping->inputCanvasWidth;
					shape.mappingCanvasHeight = mapping->inputCanvasHeight;
				}
				scene.planShapes.push_back(shape);
			}
		}
		size_t nonWhitespace = close;
		while (nonWhitespace > open && std::isspace(static_cast<unsigned char>(xml[nonWhitespace - 1U])) != 0)
			--nonWhitespace;
		if (xml[nonWhitespace - 1U] != '/')
		{
			elementStack.push_back(tag);
			transformStack.push_back(elementTransform);
			visibilityStack.push_back(elementVisible);
		}
		cursor = close + 1U;
	}
	if (scene.planShapes.empty())
	{
		error = unsupportedPathFound ?
			"plan SVG contains no supported geometry; split unsupported paths into simple elements" :
			"plan SVG contains no supported geometry";
		return false;
	}
	for (const INSTARPlanShape& shape : scene.planShapes)
	{
		float red = 0.0f, green = 0.0f, blue = 0.0f;
		PlanShapeColour(shape.name, red, green, blue);
		std::vector<INSTARVec3> world;
		for (const INSTARVec3& point : shape.points)
			world.push_back(PlanPointToWorld(point, viewWidth, viewHeight, effectivePlanScale, 0.0f));
		INSTARSurface3D surface;
		surface.name = shape.name;
		surface.minimum = {world.front().x, 0.0f, world.front().z};
		surface.maximum = {world.front().x, shape.height, world.front().z};
		for (const INSTARVec3& point : world)
		{
			surface.minimum.x = std::min(surface.minimum.x, point.x);
			surface.minimum.z = std::min(surface.minimum.z, point.z);
			surface.maximum.x = std::max(surface.maximum.x, point.x);
			surface.maximum.z = std::max(surface.maximum.z, point.z);
		}
		scene.surfaces.push_back(surface);
		const size_t segmentCount = shape.closed && world.size() >= 3U ? world.size() : world.size() - 1U;
		if (PlanNameKey(shape.role) == "screen" && world.size() >= 2U)
		{
			// A screen uses its longest plan edge as the bottom of a vertical
			// display surface, not as a solid venue wall.
			const std::pair<INSTARVec3, INSTARVec3> screenEdge = SelectPlanScreenEdge(world, shape.closed);
			AddPlanScreen(scene, screenEdge.first, screenEdge.second, shape.height, red, green, blue, shape);
		}
		else
		{
			for (size_t index = 0; index < segmentCount; ++index)
				AddPlanWall(scene, world[index], world[(index + 1U) % world.size()], shape.height, red, green, blue);
		}
		if (PlanNameKey(shape.role) != "screen" && shape.closed)
			AddPlanCap(scene, world, shape.height, red, green, blue);
	}
	Normalise(scene);
	scene.source = path;
	return true;
}

INSTARScene BuildINSTARFlatPlaneDemoScene()
{
	INSTARScene scene;
	scene.inputCanvasWidth = 1920;
	scene.inputCanvasHeight = 1080;
	INSTARInputPlane plane;
	plane.name = "INPUT_PLANE_DEMO";
	plane.x = 0.0f;
	plane.y = 0.0f;
	plane.width = 1920.0f;
	plane.height = 1080.0f;
	plane.corners = {
		{0.0f, 0.0f, 0.0f},
		{1920.0f, 0.0f, 0.0f},
		{1920.0f, 1080.0f, 0.0f},
		{0.0f, 1080.0f, 0.0f},
	};
	scene.inputPlanes.push_back(plane);
	ApplyINSTARInputPlaneDepths(scene, std::vector<float>());
	scene.source = "INSTAR flat plane demo";
	return scene;
}

INSTARScene BuildINSTARModelDemoScene()
{
	INSTARScene scene;
	AddNamedBox(scene, "MODEL_DEMO", {0.0f, 0.0f, 0.0f}, {1.4f, 1.4f, 1.4f}, 0.95f, 0.20f, 0.75f);
	Normalise(scene);
	scene.source = "INSTAR 3D model demo";
	return scene;
}

INSTARCamera SelectINSTARCamera(int view, float yaw, float pitch, float zoom, float distance)
{
	INSTARCamera camera;
	camera.yaw = (yaw - 0.5f) * 6.2831853f;
	camera.pitch = (pitch - 0.5f) * 2.2f;
	camera.zoom = 0.8f + zoom * 1.8f;
	camera.distance = std::max(0.5f, distance);
	if (view == 0)
	{
		camera.yaw = 0.75f;
		camera.pitch = -0.75f;
	}
	else if (view == 1)
	{
		camera.yaw = 0.0f;
		camera.pitch = -0.15f;
	}
	return camera;
}

std::vector<INSTARProjectedSurface> ProjectINSTARSurfaces(
	const INSTARScene& scene,
	float yaw,
	float pitch,
	float zoom,
	unsigned int canvasWidth,
	unsigned int canvasHeight
)
{
	std::vector<INSTARProjectedSurface> result;
	if (canvasWidth == 0 || canvasHeight == 0)
		return result;
	const float aspect = static_cast<float>(canvasWidth) / static_cast<float>(canvasHeight);
	for (const INSTARSurface3D& surface : scene.surfaces)
	{
		float minX = 1.0f, maxX = -1.0f, minY = 1.0f, maxY = -1.0f;
		bool visible = false;
		for (int corner = 0; corner < 8; ++corner)
		{
			const float x = (corner & 1) ? surface.maximum.x : surface.minimum.x;
			const float y = (corner & 2) ? surface.maximum.y : surface.minimum.y;
			const float z = (corner & 4) ? surface.maximum.z : surface.minimum.z;
			const float cy = std::cos(yaw);
			const float sy = std::sin(yaw);
			INSTARVec3 p{cy * x - sy * z, y, sy * x + cy * z};
			const float cp = std::cos(pitch);
			const float sp = std::sin(pitch);
			p = {p.x, cp * p.y - sp * p.z, sp * p.y + cp * p.z};
			p.z += 3.5f;
			if (p.z <= 0.1f)
				continue;
			const float perspective = zoom / p.z;
			const float projectedX = p.x * perspective / std::max(0.1f, aspect);
			const float projectedY = p.y * perspective;
			minX = std::min(minX, projectedX);
			maxX = std::max(maxX, projectedX);
			minY = std::min(minY, projectedY);
			maxY = std::max(maxY, projectedY);
			visible = true;
		}
		if (!visible)
			continue;
		const float left = std::max(0.0f, std::min(1.0f, (minX + 1.0f) * 0.5f));
		const float right = std::max(0.0f, std::min(1.0f, (maxX + 1.0f) * 0.5f));
		const float top = std::max(0.0f, std::min(1.0f, (1.0f - maxY) * 0.5f));
		const float bottom = std::max(0.0f, std::min(1.0f, (1.0f - minY) * 0.5f));
		if (right - left <= 0.0001f || bottom - top <= 0.0001f)
			continue;
		INSTARProjectedSurface projected;
		projected.name = surface.name;
		projected.x = left * canvasWidth;
		projected.y = top * canvasHeight;
		projected.width = (right - left) * canvasWidth;
		projected.height = (bottom - top) * canvasHeight;
		result.push_back(projected);
	}
	return result;
}
