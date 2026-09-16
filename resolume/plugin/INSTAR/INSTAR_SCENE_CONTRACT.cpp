#include "INSTAR_SCENE.h"

#include <cstdio>
#include <fstream>

int main()
{
	const char* path = "INSTAR_SCENE_CONTRACT.obj";
	{
		std::ofstream fixture(path, std::ios::out | std::ios::trunc);
		fixture << "v 0 0 0\n"
			       "v 2 0 0\n"
			       "v 2 1 0\n"
			       "v 0 1 0\n"
			       "f 1 2 3 4\n";
	}

	INSTARScene scene;
	std::string error;
	const bool loaded = LoadINSTARObj(path, scene, error);
	std::remove(path);
	if (!loaded || !scene.fromObj || scene.lineVertices.size() != 12U)
		return 1;
	for (const INSTARVertex& vertex : scene.lineVertices)
	{
		if (vertex.position.x < -1.001f || vertex.position.x > 1.001f ||
			vertex.position.y < -1.001f || vertex.position.y > 1.001f ||
			vertex.position.z < -1.001f || vertex.position.z > 1.001f)
			return 1;
	}
	return 0;
}
