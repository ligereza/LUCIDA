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
	float u = 0.0f;
	float v = 0.0f;
	float textureEnabled = 0.0f;
};

struct INSTARSurface3D
{
	std::string name;
	INSTARVec3 minimum;
	INSTARVec3 maximum;
};

struct INSTARInputPlane
{
	std::string name;
	float x = 0.0f;
	float y = 0.0f;
	float width = 0.0f;
	float height = 0.0f;
	float depth = 0.0f;
	std::vector<INSTARVec3> corners;
};

struct INSTARPlanShape
{
	std::string name;
	std::string role;
	std::string sliceName;
	std::vector<INSTARVec3> points;
	std::vector<INSTARVec3> mappingCorners;
	unsigned int mappingCanvasWidth = 0;
	unsigned int mappingCanvasHeight = 0;
	bool closed = false;
	bool mapped = false;
	float height = 0.0f;
};

struct INSTARProjectedSurface
{
	std::string name;
	float x = 0.0f;
	float y = 0.0f;
	float width = 0.0f;
	float height = 0.0f;
};

struct INSTARCamera
{
	float yaw = 0.0f;
	float pitch = 0.0f;
	float zoom = 1.8f;
	float distance = 3.5f;
};

struct INSTARScene
{
	std::vector<INSTARVertex> lineVertices;
	std::vector<INSTARVertex> triangleVertices;
	std::vector<INSTARSurface3D> surfaces;
	std::vector<INSTARInputPlane> inputPlanes;
	std::vector<INSTARPlanShape> planShapes;
	unsigned int inputCanvasWidth = 0;
	unsigned int inputCanvasHeight = 0;
	INSTARVec3 renderCentre;
	float renderScale = 1.0f;
	bool hasTextureCoordinates = false;
	bool fromObj = false;
	std::string source;
};

bool LoadINSTARObj(const std::string& path, INSTARScene& scene, std::string& error);
bool LoadINSTARAdvancedOutputPlanes(const std::string& path, INSTARScene& scene, std::string& error);
bool LoadINSTARPlanSvg(
	const std::string& path,
	INSTARScene& scene,
	std::string& error,
	float extrusionHeight = 3.0f,
	float planScale = 1.0f,
	const std::vector<float>& heightOverrides = std::vector<float>(),
	const INSTARScene* mapping = nullptr
);
void ApplyINSTARInputPlaneDepths(INSTARScene& scene, const std::vector<float>& depths);
INSTARScene BuildINSTARFlatPlaneDemoScene();
INSTARScene BuildINSTARModelDemoScene();

INSTARCamera SelectINSTARCamera(
	int view,
	float yaw,
	float pitch,
	float zoom,
	float distance = 3.5f
);

std::vector<INSTARProjectedSurface> ProjectINSTARSurfaces(
	const INSTARScene& scene,
	float yaw,
	float pitch,
	float zoom,
	unsigned int canvasWidth,
	unsigned int canvasHeight
);
