#include "INSTAR_IMAGE.h"

#include <fstream>
#include <iostream>

int main(int argc, char** argv)
{
	if (argc == 2 || argc == 3)
	{
		INSTARImage image;
		std::string error;
		if (!LoadINSTARImage(argv[1], image, error))
		{
			std::cerr << error << "\n";
			return 1;
		}
		const std::vector<INSTARSurface> surfaces = DetectINSTARSurfaces(image, 4186, 1283);
		std::cout << "decoded=" << image.width << "x" << image.height << " surfaces=" << surfaces.size() << "\n";
		for (const INSTARSurface& surface : surfaces)
			std::cout << surface.name << " " << surface.x << " " << surface.y << " " << surface.width << " " << surface.height << "\n";
		if (argc == 3)
		{
			std::ofstream output(argv[2], std::ios::out | std::ios::trunc);
			if (!output.is_open())
				return 1;
			output << BuildINSTARAdvancedOutputXml(4186, 1283, surfaces);
			if (!output.good())
				return 1;
		}
		return surfaces.empty() ? 1 : 0;
	}

	INSTARImage image;
	image.width = 800;
	image.height = 500;
	image.rgba.resize(static_cast<size_t>(image.width) * image.height * 4U, 0);
	const auto fill = [&image](unsigned int left, unsigned int top, unsigned int right, unsigned int bottom, unsigned char red, unsigned char green, unsigned char blue) {
		for (unsigned int y = top; y <= bottom; ++y)
			for (unsigned int x = left; x <= right; ++x)
			{
				unsigned char* pixel = &image.rgba[(static_cast<size_t>(y) * image.width + x) * 4U];
				pixel[0] = red;
				pixel[1] = green;
				pixel[2] = blue;
				pixel[3] = 255;
			}
	};
	fill(20, 80, 420, 160, 255, 255, 0);
	fill(20, 170, 420, 450, 0, 60, 255);
	fill(20, 460, 420, 490, 255, 120, 0);
	fill(450, 80, 600, 450, 255, 0, 255);
	fill(610, 80, 780, 450, 255, 0, 0);

	const std::vector<INSTARSurface> surfaces = DetectINSTARSurfaces(image, 4186, 1283);
	if (surfaces.size() != 5)
	{
		std::cerr << "expected five surfaces, got " << surfaces.size() << "\n";
		return 1;
	}
	return 0;
}
