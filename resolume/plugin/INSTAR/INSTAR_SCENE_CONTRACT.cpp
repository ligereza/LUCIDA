#include "INSTAR_SCENE.h"
#include "INSTAR_XML.h"

#include <cstdio>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace
{
bool HasSuffix(const std::string& value, const char* suffix)
{
	if (value.size() < std::strlen(suffix))
		return false;
	return value.compare(value.size() - std::strlen(suffix), std::strlen(suffix), suffix) == 0;
}
}

int main(int argc, char** argv)
{
	if (argc == 2)
	{
		INSTARScene scene;
		std::string error;
		const std::string path = argv[1];
		const bool loaded = HasSuffix(path, ".json") ? LoadINSTARVenueJson(path, scene, error) : LoadINSTARObj(path, scene, error);
		if (!loaded)
		{
			std::cerr << error << "\n";
			return 1;
		}
		std::cout << (HasSuffix(path, ".json") ? "venue_lines=" : "obj_lines=") << scene.lineVertices.size()
			      << " surfaces=" << scene.surfaces.size()
			      << " triangles=" << scene.triangleVertices.size() << "\n";
		return scene.lineVertices.empty() ? 1 : 0;
	}
	if (argc > 2)
		return 2;
	const char* path = "INSTAR_SCENE_CONTRACT.obj";
	const char* materialPath = "INSTAR_SCENE_CONTRACT.mtl";
	{
		std::ofstream material(materialPath, std::ios::out | std::ios::trunc);
		material << "newmtl central_red\nKd 0.8 0.2 0.1\n";
	}
	{
		std::ofstream fixture(path, std::ios::out | std::ios::trunc);
		fixture << "mtllib INSTAR_SCENE_CONTRACT.mtl\n"
		       << "o screen_central\n"
		       "v 0 0 0\n"
		       "v 2 0 0\n"
		       "v 2 1 0\n"
		       "v 0 1 0\n"
		       "usemtl central_red\n"
		       "f 1 2 3 4\n";
	}

	INSTARScene scene;
	std::string error;
	const bool loaded = LoadINSTARObj(path, scene, error);
	std::remove(path);
	std::remove(materialPath);
	if (!loaded || !scene.fromObj || scene.lineVertices.size() != 12U || scene.triangleVertices.size() != 6U || scene.surfaces.size() != 1U || scene.surfaces[0].name != "screen_central")
	{
		std::fprintf(stderr, "load=%d fromObj=%d lines=%zu triangles=%zu surfaces=%zu name=%s\\n", loaded, scene.fromObj, scene.lineVertices.size(), scene.triangleVertices.size(), scene.surfaces.size(), scene.surfaces.empty() ? "" : scene.surfaces[0].name.c_str());
		return 1;
	}
	if (scene.triangleVertices[0].red < 0.79f || scene.triangleVertices[0].green > 0.21f || scene.triangleVertices[0].blue > 0.11f)
		return 1;
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
	const char* venuePath = "INSTAR_SCENE_CONTRACT_VENUE.json";
	{
		std::ofstream venue(venuePath, std::ios::out | std::ios::trunc);
		venue << "{\"geometria\":{\"polilineas\":["
		      << "{\"puntos\":[[0,0,0],[2,0,0],[2,1,0]],\"confianza\":\"medido\"},"
		      << "{\"puntos\":[[0,0,0],[0,2,0]],\"confianza\":\"no_verificado\"}]}}";
	}
	INSTARScene venue;
	std::string venueError;
	const bool venueLoaded = LoadINSTARVenueJson(venuePath, venue, venueError);
	if (!venueLoaded || venue.fromObj || !venue.surfaces.empty() || venue.lineVertices.size() != 6U ||
		venue.totalEdges != 3U || venue.omittedEdges != 0U ||
		venue.lineVertices[0].red < 0.90f || venue.lineVertices.back().red > 0.26f)
		return 1;
	INSTARScene budgetedVenue;
	std::string budgetError;
	const bool budgetLoaded = LoadINSTARVenueJson(venuePath, budgetedVenue, budgetError, 2);
	INSTARScene measuredOnlyVenue;
	std::string confidenceError;
	const bool confidenceLoaded = LoadINSTARVenueJson(venuePath, measuredOnlyVenue, confidenceError, 0, 0);
	std::remove(venuePath);
	if (!budgetLoaded || budgetedVenue.totalEdges != 3U || budgetedVenue.omittedEdges != 1U || budgetedVenue.lineVertices.size() != 4U)
		return 1;
	if (!confidenceLoaded || measuredOnlyVenue.totalEdges != 3U || measuredOnlyVenue.omittedEdges != 1U || measuredOnlyVenue.lineVertices.size() != 4U)
		return 1;
	return 0;
}
