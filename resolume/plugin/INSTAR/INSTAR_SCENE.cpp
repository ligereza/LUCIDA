#include "INSTAR_SCENE.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>

namespace
{
void AddEdge(std::vector<INSTARVertex>& output, const INSTARVec3& first, const INSTARVec3& second, float red, float green, float blue)
{
	output.push_back({first, red, green, blue});
	output.push_back({second, red, green, blue});
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
		}
		++faceNumber;
	}
	if (positions.empty() || scene.lineVertices.empty())
	{
		error = "OBJ contains no renderable faces";
		return false;
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
	AddBox(scene, {0.0f, 0.0f, 0.0f}, {6.0f, 2.5f, 0.15f}, 0.15f, 0.75f, 1.0f);
	AddBox(scene, {-4.0f, 0.4f, 0.25f}, {1.2f, 3.2f, 0.15f}, 0.25f, 1.0f, 0.35f);
	AddBox(scene, {4.0f, 0.4f, 0.25f}, {1.2f, 3.2f, 0.15f}, 0.25f, 1.0f, 0.35f);
	AddBox(scene, {0.0f, 2.7f, 0.1f}, {9.5f, 0.15f, 0.15f}, 1.0f, 0.65f, 0.15f);
	AddBox(scene, {0.0f, -1.6f, 0.0f}, {9.5f, 0.15f, 4.0f}, 0.55f, 0.55f, 0.65f);
	Normalise(scene);
	scene.source = "INSTAR demo scene";
	return scene;
}
