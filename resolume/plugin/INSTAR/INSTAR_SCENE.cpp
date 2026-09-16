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
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <map>
#include <sstream>

namespace
{
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
		std::string token;
		while (input >> token)
		{
			const int index = ObjIndex(token, static_cast<int>(positions.size()));
			if (index >= 0)
				face.push_back(index);
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
			AddEdge(scene.lineVertices, first, second, colour.red, colour.green, colour.blue);
			AddEdge(scene.lineVertices, second, third, colour.red, colour.green, colour.blue);
			AddEdge(scene.lineVertices, third, first, colour.red, colour.green, colour.blue);
			AddTriangle(scene.triangleVertices, first, second, third, colour.red, colour.green, colour.blue);
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

INSTARScene BuildINSTARModelDemoScene()
{
	INSTARScene scene;
	AddNamedBox(scene, "MODEL_DEMO", {0.0f, 0.0f, 0.0f}, {1.4f, 1.4f, 1.4f}, 0.95f, 0.20f, 0.75f);
	Normalise(scene);
	scene.source = "INSTAR 3D model demo";
	return scene;
}

INSTARCamera SelectINSTARCamera(int view, float yaw, float pitch, float zoom)
{
	INSTARCamera camera;
	camera.yaw = (yaw - 0.5f) * 6.2831853f;
	camera.pitch = (pitch - 0.5f) * 2.2f;
	camera.zoom = 0.8f + zoom * 1.8f;
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
