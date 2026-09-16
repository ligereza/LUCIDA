#include "INSTAR_XML.h"

#include <fstream>
#include <iostream>

int main(int argc, char** argv)
{
	if (argc != 2)
	{
		std::cerr << "usage: INSTAR_XML_CONTRACT <output.xml>\n";
		return 2;
	}

	INSTARSurface central;
	central.name = "CENTRAL";
	central.x = 0.0f;
	central.y = 128.0f;
	central.width = 2560.0f;
	central.height = 1024.0f;

	INSTARSurface right;
	right.name = "CCTV_R";
	right.x = 2644.0f;
	right.y = 0.0f;
	right.width = 768.0f;
	right.height = 1280.0f;

	INSTARSurface left;
	left.name = "CCTV_L";
	left.x = 3414.0f;
	left.y = 0.0f;
	left.width = 768.0f;
	left.height = 1280.0f;

	INSTARSurface front;
	front.name = "BANNER_FRONTAL";
	front.x = 0.0f;
	front.y = 0.0f;
	front.width = 2560.0f;
	front.height = 128.0f;

	INSTARSurface floor;
	floor.name = "BANNER_PISO";
	floor.x = 0.0f;
	floor.y = 1152.0f;
	floor.width = 2560.0f;
	floor.height = 128.0f;

	std::vector<INSTARSurface> surfaces;
	surfaces.push_back(front);
	surfaces.push_back(central);
	surfaces.push_back(right);
	surfaces.push_back(left);
	surfaces.push_back(floor);
	const std::string xml = BuildINSTARAdvancedOutputXml(4186, 1283, surfaces);
	if (xml.find("<XmlState name=\"INSTAR\">") == std::string::npos ||
		xml.find("<Slice uniqueId=\"1800000000001\">") == std::string::npos ||
		xml.find("<OutputDeviceVirtual name=\"INSTAR\"") == std::string::npos ||
		xml.find("value=\"CENTRAL\"") == std::string::npos ||
		xml.find("value=\"CCTV_L\"") == std::string::npos ||
		xml.find("value=\"BANNER_PISO\"") == std::string::npos)
	{
		std::cerr << "INSTAR XML contract markers missing\n";
		return 1;
	}

	std::ofstream output(argv[1], std::ios::out | std::ios::trunc);
	if (!output.is_open())
	{
		std::cerr << "could not write contract XML\n";
		return 1;
	}
	output << xml;
	return output.good() ? 0 : 1;
}
