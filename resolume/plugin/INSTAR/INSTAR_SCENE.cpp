#include "INSTAR_SCENE.h"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <map>
#include <sstream>

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

void SkipJsonSpace(const std::string& text, size_t& cursor)
{
	while (cursor < text.size() && std::isspace(static_cast<unsigned char>(text[cursor])))
		++cursor;
}

size_t MatchingBracket(const std::string& text, size_t opening, char open, char close)
{
	int depth = 0;
	bool quoted = false;
	bool escaped = false;
	for (size_t cursor = opening; cursor < text.size(); ++cursor)
	{
		const char character = text[cursor];
		if (quoted)
		{
			if (escaped)
				escaped = false;
			else if (character == '\\')
				escaped = true;
			else if (character == '"')
				quoted = false;
			continue;
		}
		if (character == '"')
		{
			quoted = true;
			continue;
		}
		if (character == open)
			++depth;
		else if (character == close && --depth == 0)
			return cursor;
	}
	return std::string::npos;
}

std::vector<INSTARVec3> ParseVenuePoints(const std::string& text, size_t opening, size_t closing)
{
	std::vector<INSTARVec3> points;
	for (size_t cursor = opening + 1; cursor < closing; ++cursor)
	{
		if (text[cursor] != '[')
			continue;
		size_t valueCursor = cursor + 1;
		float values[3] = {};
		bool valid = true;
		for (float& value : values)
		{
			SkipJsonSpace(text, valueCursor);
			if (valueCursor < text.size() && text[valueCursor] == ',')
				++valueCursor;
			SkipJsonSpace(text, valueCursor);
			char* end = nullptr;
			value = std::strtof(text.c_str() + valueCursor, &end);
			if (end == text.c_str() + valueCursor)
			{
				valid = false;
				break;
			}
			valueCursor = static_cast<size_t>(end - text.c_str());
		}
		SkipJsonSpace(text, valueCursor);
		if (valid && valueCursor < text.size() && text[valueCursor] == ']')
		{
			// FLUJO stores [x, depth, height]; the native renderer uses
			// [x, height, depth], so height remains the vertical axis.
			points.push_back({values[0], values[2], values[1]});
			cursor = valueCursor;
		}
	}
	return points;
}

void VenueConfidenceColour(const std::string& confidence, float& red, float& green, float& blue)
{
	if (confidence == "medido")
		red = 0.91f, green = 0.89f, blue = 0.85f;
	else if (confidence == "citado")
		red = 0.56f, green = 0.66f, blue = 0.70f;
	else if (confidence == "ajustado")
		red = 0.73f, green = 0.70f, blue = 0.66f;
	else if (confidence == "aportado")
		red = 0.54f, green = 0.52f, blue = 0.48f;
	else
		red = 0.25f, green = 0.24f, blue = 0.21f;
}

struct INSTARVenueLine
{
	std::vector<INSTARVec3> points;
	std::string confidence;
};

int VenueConfidenceOrder(const std::string& confidence)
{
	if (confidence == "medido")
		return 0;
	if (confidence == "citado")
		return 1;
	if (confidence == "ajustado")
		return 2;
	if (confidence == "aportado")
		return 3;
	return 4;
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

void AddWireRectangle(
	INSTARScene& scene,
	float left,
	float bottom,
	float right,
	float top,
	float z,
	float red,
	float green,
	float blue
)
{
	const INSTARVec3 points[] = {
		{left, top, z}, {right, top, z},
		{right, top, z}, {right, bottom, z},
		{right, bottom, z}, {left, bottom, z},
		{left, bottom, z}, {left, top, z},
	};
	for (size_t index = 0; index < 8U; index += 2U)
		AddEdge(scene.lineVertices, points[index], points[index + 1U], red, green, blue);
}

void AddTiltedWireRectangle(
	INSTARScene& scene,
	float left,
	float bottom,
	float right,
	float top,
	float z,
	float tiltDegrees,
	float red,
	float green,
	float blue
)
{
	// FLUJO's tilt is an orientation control. A sine offset keeps the
	// 0..90-degree range finite and avoids exploding the preview at 90 degrees.
	const float topDepthOffset = std::sin(tiltDegrees * 3.1415926535f / 180.0f) * (top - bottom);
	const INSTARVec3 bottomLeft{left, bottom, z};
	const INSTARVec3 bottomRight{right, bottom, z};
	const INSTARVec3 topLeft{left, top, z + topDepthOffset};
	const INSTARVec3 topRight{right, top, z + topDepthOffset};
	AddEdge(scene.lineVertices, topLeft, topRight, red, green, blue);
	AddEdge(scene.lineVertices, topRight, bottomRight, red, green, blue);
	AddEdge(scene.lineVertices, bottomRight, bottomLeft, red, green, blue);
	AddEdge(scene.lineVertices, bottomLeft, topLeft, red, green, blue);
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

bool LoadINSTARVenueJson(const std::string& path, INSTARScene& scene, std::string& error, unsigned int edgeBudget, int confidenceCeiling)
{
	scene = INSTARScene();
	std::ifstream file = OpenTextFile(path);
	if (!file.is_open())
	{
		error = "venue JSON could not be opened";
		return false;
	}
	const std::string text((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
	const size_t polylinesKey = text.find("\"polilineas\"");
	if (polylinesKey == std::string::npos)
	{
		error = "venue JSON has no geometria.polilineas";
		return false;
	}
	const size_t opening = text.find('[', polylinesKey);
	const size_t closing = opening == std::string::npos ? std::string::npos : MatchingBracket(text, opening, '[', ']');
	if (opening == std::string::npos || closing == std::string::npos)
	{
		error = "venue JSON has an invalid polilineas array";
		return false;
	}

	std::vector<INSTARVenueLine> lines;
	size_t cursor = opening + 1;
	while (cursor < closing)
	{
		const size_t pointsKey = text.find("\"puntos\"", cursor);
		if (pointsKey == std::string::npos || pointsKey >= closing)
			break;
		const size_t pointsOpening = text.find('[', pointsKey);
		const size_t pointsClosing = pointsOpening == std::string::npos ? std::string::npos : MatchingBracket(text, pointsOpening, '[', ']');
		if (pointsOpening == std::string::npos || pointsClosing == std::string::npos || pointsClosing > closing)
		{
			error = "venue JSON has an invalid puntos array";
			return false;
		}
		const size_t confidenceKey = text.find("\"confianza\"", pointsClosing);
		std::string confidence = "no_verificado";
		if (confidenceKey != std::string::npos && confidenceKey < closing)
		{
			const size_t quote = text.find('"', text.find(':', confidenceKey) + 1);
			const size_t endQuote = quote == std::string::npos ? std::string::npos : text.find('"', quote + 1);
			if (quote != std::string::npos && endQuote != std::string::npos)
				confidence = text.substr(quote + 1, endQuote - quote - 1);
		}
		const std::vector<INSTARVec3> points = ParseVenuePoints(text, pointsOpening, pointsClosing);
		if (points.size() >= 2U)
		{
			INSTARVenueLine line;
			line.points = points;
			line.confidence = confidence;
			lines.push_back(line);
		}
		cursor = pointsClosing + 1;
	}
	std::stable_sort(lines.begin(), lines.end(), [](const INSTARVenueLine& left, const INSTARVenueLine& right) {
		return VenueConfidenceOrder(left.confidence) < VenueConfidenceOrder(right.confidence);
	});
	for (const INSTARVenueLine& line : lines)
	{
		const unsigned int edges = static_cast<unsigned int>(line.points.size() - 1U);
		scene.totalEdges += edges;
		if (VenueConfidenceOrder(line.confidence) > confidenceCeiling)
		{
			scene.omittedEdges += edges;
			continue;
		}
		if (edgeBudget != 0 && scene.lineVertices.size() / 2U + edges > edgeBudget)
		{
			scene.omittedEdges += edges;
			continue;
		}
		float red = 0.0f, green = 0.0f, blue = 0.0f;
		VenueConfidenceColour(line.confidence, red, green, blue);
		for (size_t point = 1; point < line.points.size(); ++point)
			AddEdge(scene.lineVertices, line.points[point - 1], line.points[point], red, green, blue);
	}
	if (scene.lineVertices.empty())
	{
		error = "venue JSON contains no renderable polilineas";
		return false;
	}
	SetRenderFit(scene);
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
		const INSTARInputPlane& plane = scene.inputPlanes[index];
		const float depth = index < depths.size() ? depths[index] : 0.0f;
		const float left = plane.x / static_cast<float>(scene.inputCanvasWidth) * 2.0f - 1.0f;
		const float right = (plane.x + plane.width) / static_cast<float>(scene.inputCanvasWidth) * 2.0f - 1.0f;
		const float top = (0.5f - plane.y / static_cast<float>(scene.inputCanvasHeight)) * 2.0f * canvasAspect;
		const float bottom = (0.5f - (plane.y + plane.height) / static_cast<float>(scene.inputCanvasHeight)) * 2.0f * canvasAspect;
		const INSTARVec3 topLeft{left, top, depth};
		const INSTARVec3 topRight{right, top, depth};
		const INSTARVec3 bottomRight{right, bottom, depth};
		const INSTARVec3 bottomLeft{left, bottom, depth};
		const INSTARVec2 topLeftUv{plane.x / static_cast<float>(scene.inputCanvasWidth), plane.y / static_cast<float>(scene.inputCanvasHeight)};
		const INSTARVec2 topRightUv{(plane.x + plane.width) / static_cast<float>(scene.inputCanvasWidth), plane.y / static_cast<float>(scene.inputCanvasHeight)};
		const INSTARVec2 bottomRightUv{(plane.x + plane.width) / static_cast<float>(scene.inputCanvasWidth), (plane.y + plane.height) / static_cast<float>(scene.inputCanvasHeight)};
		const INSTARVec2 bottomLeftUv{plane.x / static_cast<float>(scene.inputCanvasWidth), (plane.y + plane.height) / static_cast<float>(scene.inputCanvasHeight)};
		const float red = 0.20f + static_cast<float>((index * 37U) % 55U) / 100.0f;
		const float green = 0.55f + static_cast<float>((index * 19U) % 35U) / 100.0f;
		const float blue = 0.70f + static_cast<float>((index * 11U) % 25U) / 100.0f;
		AddEdgeTextured(scene.lineVertices, topLeft, topRight, topLeftUv, topRightUv, red, green, blue);
		AddEdgeTextured(scene.lineVertices, topRight, bottomRight, topRightUv, bottomRightUv, red, green, blue);
		AddEdgeTextured(scene.lineVertices, bottomRight, bottomLeft, bottomRightUv, bottomLeftUv, red, green, blue);
		AddEdgeTextured(scene.lineVertices, bottomLeft, topLeft, bottomLeftUv, topLeftUv, red, green, blue);
		AddTriangleTextured(scene.triangleVertices, topLeft, topRight, bottomRight, topLeftUv, topRightUv, bottomRightUv, red, green, blue);
		AddTriangleTextured(scene.triangleVertices, topLeft, bottomRight, bottomLeft, topLeftUv, bottomRightUv, bottomLeftUv, red, green, blue);
	}
	scene.renderCentre = {};
	scene.renderScale = 1.0f;
}

void ApplyINSTARTarima(INSTARScene& scene, const INSTARTarimaConfig& config)
{
	if (scene.inputPlanes.empty() || scene.inputCanvasWidth == 0 || scene.inputCanvasHeight == 0)
		return;

	const float canvasAspect = static_cast<float>(scene.inputCanvasHeight) / static_cast<float>(scene.inputCanvasWidth);
	const auto boundsOf = [canvasAspect, &scene](const INSTARInputPlane& plane) {
		const float canvasWidth = static_cast<float>(scene.inputCanvasWidth);
		const float canvasHeight = static_cast<float>(scene.inputCanvasHeight);
		const float left = plane.x / canvasWidth * 2.0f - 1.0f;
		const float right = (plane.x + plane.width) / canvasWidth * 2.0f - 1.0f;
		const float top = (0.5f - plane.y / canvasHeight) * 2.0f * canvasAspect;
		const float bottom = (0.5f - (plane.y + plane.height) / canvasHeight) * 2.0f * canvasAspect;
		return std::array<float, 4>{left, bottom, right, top};
	};

	// The largest InputRect is the main screen. XML remains authoritative for
	// every plane's XY position and order; this function only adds the stage
	// context behind those planes.
	size_t mainIndex = 0;
	float mainArea = -1.0f;
	for (size_t index = 0; index < scene.inputPlanes.size(); ++index)
	{
		const INSTARInputPlane& plane = scene.inputPlanes[index];
		const float area = plane.width * plane.height;
		if (area > mainArea)
		{
			mainArea = area;
			mainIndex = index;
		}
	}
	const std::array<float, 4> main = boundsOf(scene.inputPlanes[mainIndex]);
	const float mainWidth = std::max(0.25f, main[2] - main[0]);
	const float mainHeight = std::max(0.25f, main[3] - main[1]);
	const float mainCentreX = (main[0] + main[2]) * 0.5f;
	const float mainCentreY = (main[1] + main[3]) * 0.5f;
	const float configuredScreenWidth = std::max(0.25f, static_cast<float>(std::max(1, config.screenColumns)) * config.moduleWidth);
	const float worldPerMetre = mainWidth / configuredScreenWidth;
	const float stageHeight = 0.60f * worldPerMetre;
	const float stageDepth = std::max(0.10f, config.stageDepth * worldPerMetre);
	const float stageZ = scene.lineVertices.empty() ? -config.stageDist * worldPerMetre :
		scene.lineVertices.front().position.z - (config.stageDist * worldPerMetre + stageDepth * 0.5f);
	const float floorY = main[1] - 0.35f * worldPerMetre;

	AddBox(
		scene,
		{mainCentreX, floorY + stageHeight * 0.5f, stageZ},
		{std::max(0.25f, config.stageWidth * worldPerMetre), stageHeight, stageDepth},
		0.12f, 0.07f, 0.20f
	);

	// A thin backing and module grid make the largest screen readable as the
	// main banner without replacing the actual textured InputRect plane.
	const float backingZ = scene.lineVertices.empty() ? stageZ + stageDepth * 0.5f : scene.lineVertices.front().position.z - 0.08f * worldPerMetre;
	AddBox(scene, {mainCentreX, mainCentreY, backingZ}, {mainWidth, mainHeight, 0.08f * worldPerMetre}, 0.04f, 0.35f, 0.55f);
	AddWireRectangle(scene, main[0], main[1], main[2], main[3], backingZ + 0.05f * worldPerMetre, 0.20f, 0.75f, 1.0f);
	const int screenColumns = std::max(1, config.screenColumns);
	const int screenRows = std::max(1, config.screenRows);
	for (int column = 1; column < screenColumns; ++column)
	{
		const float x = main[0] + mainWidth * static_cast<float>(column) / static_cast<float>(screenColumns);
		AddEdge(scene.lineVertices, {x, main[1], backingZ + 0.06f * worldPerMetre}, {x, main[3], backingZ + 0.06f * worldPerMetre}, 0.15f, 0.55f, 0.85f);
	}
	for (int row = 1; row < screenRows; ++row)
	{
		const float y = main[1] + mainHeight * static_cast<float>(row) / static_cast<float>(screenRows);
		AddEdge(scene.lineVertices, {main[0], y, backingZ + 0.06f * worldPerMetre}, {main[2], y, backingZ + 0.06f * worldPerMetre}, 0.15f, 0.55f, 0.85f);
	}

	const int totalTotems = std::max(0, config.totemCount);
	const int pairs = totalTotems / 2;
	const float totemWidth = std::max(0.10f, static_cast<float>(std::max(1, config.totemColumns)) * config.moduleWidth * worldPerMetre);
	const float totemHeight = std::max(0.10f, static_cast<float>(std::max(1, config.totemRows)) * config.moduleHeight * worldPerMetre);
	const float gap = std::max(0.0f, config.totemGap * worldPerMetre);
	const float totemZ = backingZ - 0.16f * worldPerMetre;
	for (int pair = 0; pair < pairs; ++pair)
	{
		const float offset = (static_cast<float>(pair) + 0.5f) * totemWidth + static_cast<float>(pair + 1) * gap;
		const float leftX = main[0] - offset;
		const float rightX = main[2] + offset;
		const float centreY = main[1] + totemHeight * 0.5f;
		AddBox(scene, {leftX, centreY, totemZ}, {totemWidth, totemHeight, 0.12f * worldPerMetre}, 0.75f, 0.35f, 0.05f);
		AddBox(scene, {rightX, centreY, totemZ}, {totemWidth, totemHeight, 0.12f * worldPerMetre}, 0.75f, 0.35f, 0.05f);
		AddTiltedWireRectangle(scene, leftX - totemWidth * 0.5f, main[1], leftX + totemWidth * 0.5f, main[1] + totemHeight, totemZ + 0.08f * worldPerMetre, config.tilt, 1.0f, 0.70f, 0.10f);
		AddTiltedWireRectangle(scene, rightX - totemWidth * 0.5f, main[1], rightX + totemWidth * 0.5f, main[1] + totemHeight, totemZ + 0.08f * worldPerMetre, config.tilt, 1.0f, 0.70f, 0.10f);
	}

	SetRenderFit(scene);
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
	ApplyINSTARInputPlaneDepths(scene, std::vector<float>());
	scene.source = path;
	return true;
}

INSTARScene BuildINSTARDemoScene()
{
	INSTARScene scene;
	// Central screen, side screens, floor and overhead truss: a deterministic
	// venue preview that also makes the camera modes useful before an OBJ exists.
	AddNamedBox(scene, "CENTRAL", {0.0f, 0.0f, 0.0f}, {6.0f, 2.5f, 0.15f}, 0.15f, 0.75f, 1.0f);
	AddNamedBox(scene, "CCTV_L", {-4.0f, 0.4f, 0.25f}, {1.2f, 3.2f, 0.15f}, 0.25f, 1.0f, 0.35f);
	AddNamedBox(scene, "CCTV_R", {4.0f, 0.4f, 0.25f}, {1.2f, 3.2f, 0.15f}, 0.25f, 1.0f, 0.35f);
	AddBox(scene, {0.0f, 2.7f, 0.1f}, {9.5f, 0.15f, 0.15f}, 1.0f, 0.65f, 0.15f);
	AddBox(scene, {0.0f, -1.6f, 0.0f}, {9.5f, 0.15f, 4.0f}, 0.55f, 0.55f, 0.65f);
	Normalise(scene);
	scene.source = "INSTAR demo scene";
	return scene;
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
