#include "INSTAR_IMAGE.h"
#include "INSTAR_XML.h"

#include <fstream>
#include <iostream>
#include <iterator>

namespace
{
std::string ReadText(const char* path)
{
	std::ifstream file(path);
	return file.is_open() ? std::string((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>()) : std::string();
}

int VerifySyntheticTemplate()
{
	const std::string templateXml =
		"<XmlState name=\"MOVISTARLOLLA\"><ScreenSetup><CurrentCompositionTextureSize width=\"7680\" height=\"1792\"/>"
		"<screens><Screen name=\"Screen 1\"><layers><Slice uniqueId=\"1773510997554\">"
		"<Params name=\"Common\"><Param name=\"Name\" value=\"old\"/></Params>"
		"<InputRect/><OutputRect/><Warper></Warper></Slice></layers>"
		"<OutputDevice><OutputDeviceDisplay name=\"Display 2\" width=\"3840\" height=\"2160\"/></OutputDevice>"
		"</Screen></screens></ScreenSetup></XmlState>";
	INSTARTemplateInfo info;
	std::string error;
	if (!ReadINSTARAdvancedOutputTemplateInfo(templateXml, info, error) ||
		info.inputWidth != 7680U || info.inputHeight != 1792U ||
		info.outputWidth != 3840U || info.outputHeight != 2160U)
		return 1;
	INSTARSurface source;
	source.name = "CENTRAL";
	source.x = 100.0f;
	source.y = 50.0f;
	source.width = 400.0f;
	source.height = 200.0f;
	const std::vector<INSTARSurfaceMapping> mappings = ScaleINSTARSurfacesToTemplate({source}, 1000, 500, info);
	const std::string output = BuildINSTARAdvancedOutputXmlFromTemplate(templateXml, mappings);
	if (output.empty() || output.find("OutputDeviceDisplay") == std::string::npos ||
		output.find("value=\"CENTRAL\"") == std::string::npos ||
		output.find("1773510997554") == std::string::npos)
		return 1;
	return 0;
}
}

int main(int argc, char** argv)
{
	if (argc == 1)
		return VerifySyntheticTemplate();
	if (argc != 4)
	{
		std::cerr << "usage: INSTAR_TEMPLATE_CONTRACT <template.xml> <pixel-map.png> <output.xml>\n";
		return 2;
	}
	const std::string templateXml = ReadText(argv[1]);
	if (templateXml.empty())
		return 1;
	INSTARTemplateInfo info;
	std::string error;
	if (!ReadINSTARAdvancedOutputTemplateInfo(templateXml, info, error))
	{
		std::cerr << error << "\n";
		return 1;
	}
	INSTARImage image;
	if (!LoadINSTARImage(argv[2], image, error))
	{
		std::cerr << error << "\n";
		return 1;
	}
	const std::vector<INSTARSurface> surfaces = DetectINSTARSurfaces(image, image.width, image.height);
	const std::vector<INSTARSurfaceMapping> mappings = ScaleINSTARSurfacesToTemplate(surfaces, image.width, image.height, info);
	if (mappings.empty())
		return 1;
	const std::string outputXml = BuildINSTARAdvancedOutputXmlFromTemplate(templateXml, mappings);
	if (outputXml.empty())
		return 1;
	std::ofstream output(argv[3], std::ios::out | std::ios::trunc);
	if (!output.is_open())
		return 1;
	output << outputXml;
	if (!output.good())
		return 1;
	std::cout << "template=" << info.inputWidth << "x" << info.inputHeight
		      << " output=" << info.outputWidth << "x" << info.outputHeight
		      << " surfaces=" << mappings.size() << "\n";
	return 0;
}
