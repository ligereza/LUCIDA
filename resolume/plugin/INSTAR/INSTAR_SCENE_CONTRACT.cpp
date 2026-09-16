#include "INSTAR_SCENE.h"
#include "INSTAR_XML.h"

#include <cstdio>
#include <cmath>
#include <fstream>
#include <string>
#include <vector>

int main()
{
	const char* path = "INSTAR_SCENE_CONTRACT.obj";
	{
		std::ofstream fixture(path, std::ios::out | std::ios::trunc);
		fixture << "o screen_central\n"
			       "v 0 0 0\n"
			       "v 2 0 0\n"
			       "v 2 1 0\n"
			       "v 0 1 0\n"
			       "f 1 2 3 4\n";
	}

	INSTARScene scene;
	std::string error;
	const bool loaded = LoadINSTARObj(path, scene, error);
	std::remove(path);
	if (!loaded || !scene.fromObj || scene.lineVertices.size() != 12U || scene.triangleVertices.size() != 6U || scene.surfaces.size() != 1U || scene.surfaces[0].name != "screen_central")
	{
		std::fprintf(stderr, "load=%d fromObj=%d lines=%zu triangles=%zu surfaces=%zu name=%s\\n", loaded, scene.fromObj, scene.lineVertices.size(), scene.triangleVertices.size(), scene.surfaces.size(), scene.surfaces.empty() ? "" : scene.surfaces[0].name.c_str());
		return 1;
	}
	for (const INSTARVertex& vertex : scene.lineVertices)
	{
		if (vertex.position.x < -1.001f || vertex.position.x > 1.001f ||
			vertex.position.y < -1.001f || vertex.position.y > 1.001f ||
			vertex.position.z < -1.001f || vertex.position.z > 1.001f)
			return 1;
	}
	const std::vector<INSTARProjectedSurface> projected = ProjectINSTARSurfaces(
		scene, 0.0f, -0.15f, 1.5f, 1920, 1080);
	if (projected.empty())
	{
		std::fprintf(stderr, "projection empty\\n");
		return 1;
	}
	std::vector<INSTARSurface> xmlSurfaces;
	for (const INSTARProjectedSurface& source : projected)
	{
		INSTARSurface surface;
		surface.name = source.name;
		surface.x = source.x;
		surface.y = source.y;
		surface.width = source.width;
		surface.height = source.height;
		xmlSurfaces.push_back(surface);
	}
	const std::string xml = BuildINSTARAdvancedOutputXml(1920, 1080, xmlSurfaces);
	if (xml.find("screen_central") == std::string::npos ||
		xml.find("<InputRect ") == std::string::npos ||
		xml.find("<OutputRect ") == std::string::npos)
	{
		std::fprintf(stderr, "xml checks failed: name=%d input=%d output=%d\\n", xml.find("screen_central") != std::string::npos, xml.find("<InputRect ") != std::string::npos, xml.find("<OutputRect ") != std::string::npos);
		return 1;
	}
	const INSTARScene demo = BuildINSTARDemoScene();
	if (demo.surfaces.size() != 3U || demo.triangleVertices.empty())
		return 1;
	const INSTARCamera aerial = SelectINSTARCamera(0, 0.5f, 0.5f, 0.55f);
	const INSTARCamera track = SelectINSTARCamera(1, 0.5f, 0.5f, 0.55f);
	const INSTARCamera free = SelectINSTARCamera(2, 0.25f, 0.75f, 0.4f);
	if (std::fabs(aerial.yaw - track.yaw) < 0.0001f ||
		std::fabs(track.pitch - free.pitch) < 0.0001f ||
		std::fabs(free.zoom - 1.52f) > 0.0001f)
		return 1;
	return 0;
}
