#include "INSTAR_SCENE.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>

namespace
{
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
}

bool LoadINSTARObj(const std::string& path, INSTARScene& scene, std::string& error)
{
	scene = INSTARScene();
	std::ifstream file(path.c_str());
	if (!file.is_open())
	{
		error = "OBJ file could not be opened";
		return false;
	}
	std::vector<INSTARVec3> positions;
	std::map<std::string, std::vector<int>> groupPositions;
	std::string currentGroup = "OBJ";
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
		const float red = 0.35f + static_cast<float>((faceNumber * 37U) % 55U) / 100.0f;
		const float green = 0.45f + static_cast<float>((faceNumber * 19U) % 45U) / 100.0f;
		const float blue = 0.55f + static_cast<float>((faceNumber * 11U) % 35U) / 100.0f;
		for (size_t index = 1; index + 1 < face.size(); ++index)
		{
			const INSTARVec3& first = positions[face[0]];
			const INSTARVec3& second = positions[face[index]];
			const INSTARVec3& third = positions[face[index + 1]];
			AddEdge(scene.lineVertices, first, second, red, green, blue);
			AddEdge(scene.lineVertices, second, third, red, green, blue);
			AddEdge(scene.lineVertices, third, first, red, green, blue);
			AddTriangle(scene.triangleVertices, first, second, third, red, green, blue);
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
