#pragma once

#include "INSTAR_XML.h"

#include <string>
#include <vector>

struct INSTARImage
{
	unsigned int width = 0;
	unsigned int height = 0;
	std::vector<unsigned char> rgba;
};

bool LoadINSTARImage(const std::string& path, INSTARImage& image, std::string& error);

std::vector<INSTARSurface> DetectINSTARSurfaces(
	const INSTARImage& image,
	unsigned int canvasWidth,
	unsigned int canvasHeight
);
