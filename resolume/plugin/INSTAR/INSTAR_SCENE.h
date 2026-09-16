#pragma once

#include <string>
#include <vector>

struct INSTARVec3
{
	float x = 0.0f;
	float y = 0.0f;
	float z = 0.0f;
};

struct INSTARVertex
{
	INSTARVec3 position;
	float red = 1.0f;
	float green = 1.0f;
	float blue = 1.0f;
};

struct INSTARSurface3D
{
	std::string name;
	INSTARVec3 minimum;
	INSTARVec3 maximum;
};

struct INSTARProjectedSurface
{
	std::string name;
	float x = 0.0f;
	float y = 0.0f;
	float width = 0.0f;
	float height = 0.0f;
};

struct INSTARScene
{
	std::vector<INSTARVertex> lineVertices;
	std::vector<INSTARSurface3D> surfaces;
	bool fromObj = false;
	std::string source;
};

bool LoadINSTARObj(const std::string& path, INSTARScene& scene, std::string& error);
INSTARScene BuildINSTARDemoScene();

std::vector<INSTARProjectedSurface> ProjectINSTARSurfaces(
	const INSTARScene& scene,
	float yaw,
	float pitch,
	float zoom,
	unsigned int canvasWidth,
	unsigned int canvasHeight
);
