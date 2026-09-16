#include "INSTAR_XML.h"

#include <cmath>
#include <iomanip>
#include <sstream>

namespace
{
std::string XmlEscape(const std::string& value)
{
	std::string escaped;
	for (const char character : value)
	{
		switch (character)
		{
		case '&': escaped += "&amp;"; break;
		case '<': escaped += "&lt;"; break;
		case '>': escaped += "&gt;"; break;
		case '\"': escaped += "&quot;"; break;
		case '\'': escaped += "&apos;"; break;
		default: escaped += character; break;
		}
	}
	return escaped;
}

std::string Number(float value)
{
	if (std::fabs(value) < 0.000001f)
		return "0";
	std::ostringstream output;
	output << std::fixed << std::setprecision(6) << value;
	std::string result = output.str();
	while (!result.empty() && result.back() == '0')
		result.pop_back();
	if (!result.empty() && result.back() == '.')
		result.pop_back();
	return result;
}

std::string RectXml(const char* tag, const INSTARSurface& surface, const std::string& indent)
{
	const float right = surface.x + surface.width;
	const float bottom = surface.y + surface.height;
	std::ostringstream xml;
	xml << indent << '<' << tag << " orientation=\"0\">\n"
		<< indent << "\t<v x=\"" << Number(surface.x) << "\" y=\"" << Number(surface.y) << "\"/>\n"
		<< indent << "\t<v x=\"" << Number(right) << "\" y=\"" << Number(surface.y) << "\"/>\n"
		<< indent << "\t<v x=\"" << Number(right) << "\" y=\"" << Number(bottom) << "\"/>\n"
		<< indent << "\t<v x=\"" << Number(surface.x) << "\" y=\"" << Number(bottom) << "\"/>\n"
		<< indent << "</" << tag << ">";
	return xml.str();
}

std::string WarperXml(const INSTARSurface& surface, const std::string& indent)
{
	const float right = surface.x + surface.width;
	const float bottom = surface.y + surface.height;
	std::ostringstream xml;
	xml << indent << "<Warper>\n"
		<< indent << "\t<Params name=\"Warper\">\n"
		<< indent << "\t\t<ParamChoice name=\"Point Mode\" default=\"PM_LINEAR\" value=\"PM_LINEAR\" storeChoices=\"0\"/>\n"
		<< indent << "\t\t<Param name=\"Flip\" T=\"UINT8\" default=\"0\" value=\"0\"/>\n"
		<< indent << "\t</Params>\n"
		<< indent << "\t<BezierWarper controlWidth=\"4\" controlHeight=\"4\">\n"
		<< indent << "\t\t<vertices>\n";
	for (int row = 0; row < 4; ++row)
	{
		for (int column = 0; column < 4; ++column)
		{
			const float x = surface.x + surface.width * static_cast<float>(column) / 3.0f;
			const float y = surface.y + surface.height * static_cast<float>(row) / 3.0f;
			xml << indent << "\t\t\t<v x=\"" << Number(x) << "\" y=\"" << Number(y) << "\"/>\n";
		}
	}
	xml << indent << "\t\t</vertices>\n"
		<< indent << "\t</BezierWarper>\n"
		<< indent << "\t<Homography>\n"
		<< indent << "\t\t<src>\n"
		<< indent << "\t\t\t<v x=\"" << Number(surface.x) << "\" y=\"" << Number(surface.y) << "\"/>\n"
		<< indent << "\t\t\t<v x=\"" << Number(right) << "\" y=\"" << Number(surface.y) << "\"/>\n"
		<< indent << "\t\t\t<v x=\"" << Number(right) << "\" y=\"" << Number(bottom) << "\"/>\n"
		<< indent << "\t\t\t<v x=\"" << Number(surface.x) << "\" y=\"" << Number(bottom) << "\"/>\n"
		<< indent << "\t\t</src>\n"
		<< indent << "\t\t<dst>\n"
		<< indent << "\t\t\t<v x=\"" << Number(surface.x) << "\" y=\"" << Number(surface.y) << "\"/>\n"
		<< indent << "\t\t\t<v x=\"" << Number(right) << "\" y=\"" << Number(surface.y) << "\"/>\n"
		<< indent << "\t\t\t<v x=\"" << Number(right) << "\" y=\"" << Number(bottom) << "\"/>\n"
		<< indent << "\t\t\t<v x=\"" << Number(surface.x) << "\" y=\"" << Number(bottom) << "\"/>\n"
		<< indent << "\t\t</dst>\n"
		<< indent << "\t</Homography>\n"
		<< indent << "</Warper>";
	return xml.str();
}
}

std::string BuildINSTARAdvancedOutputXml(
	unsigned int canvasWidth,
	unsigned int canvasHeight,
	const std::vector<INSTARSurface>& surfaces
)
{
	const unsigned int width = canvasWidth > 0 ? canvasWidth : 1920;
	const unsigned int height = canvasHeight > 0 ? canvasHeight : 1080;

	std::ostringstream file;
	file << "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
		 << "<XmlState name=\"INSTAR\">\n"
		 << "\t<versionInfo name=\"Resolume Arena\" majorVersion=\"7\" minorVersion=\"27\" microVersion=\"0\" revision=\"14395\"/>\n"
		 << "\t<ScreenSetup name=\"ScreenSetup\">\n"
		 << "\t\t<Params name=\"ScreenSetupParams\"/>\n"
		 << "\t\t<CurrentCompositionTextureSize width=\"" << width << "\" height=\"" << height << "\"/>\n"
		 << "\t\t<screens>\n"
		 << "\t\t\t<Screen name=\"INSTAR\" uniqueId=\"1800000000000\">\n"
		 << "\t\t\t\t<Params name=\"Params\">\n"
		 << "\t\t\t\t\t<Param name=\"Name\" T=\"STRING\" default=\"INSTAR\" value=\"INSTAR\"/>\n"
		 << "\t\t\t\t\t<Param name=\"Enabled\" T=\"BOOL\" default=\"1\" value=\"1\"/>\n"
		 << "\t\t\t\t\t<Param name=\"Hidden\" T=\"BOOL\" default=\"0\" value=\"0\"/>\n"
		 << "\t\t\t\t</Params>\n"
		 << "\t\t\t\t<guides>\n"
		 << "\t\t\t\t\t<ScreenGuide name=\"ScreenGuide\" type=\"0\"/>\n"
		 << "\t\t\t\t\t<ScreenGuide name=\"ScreenGuide\" type=\"1\"/>\n"
		 << "\t\t\t\t</guides>\n"
		 << "\t\t\t\t<layers>\n";

	unsigned long long sliceId = 1800000000001ULL;
	for (const INSTARSurface& surface : surfaces)
	{
		file << "\t\t\t\t\t<Slice uniqueId=\"" << sliceId++ << "\">\n"
			 << "\t\t\t\t\t\t<Params name=\"Common\">\n"
			 << "\t\t\t\t\t\t\t<Param name=\"Name\" T=\"STRING\" default=\"Layer\" value=\"" << XmlEscape(surface.name) << "\"/>\n"
			 << "\t\t\t\t\t\t\t<Param name=\"Enabled\" T=\"BOOL\" default=\"1\" value=\"1\"/>\n"
			 << "\t\t\t\t\t\t</Params>\n"
			 << "\t\t\t\t\t\t<Params name=\"Input\">\n"
			 << "\t\t\t\t\t\t\t<ParamChoice name=\"Input Source\" default=\"0:1\" value=\"0:1\" storeChoices=\"0\"/>\n"
			 << "\t\t\t\t\t\t</Params>\n"
			 << "\t\t\t\t\t\t<Params name=\"Output\"><Param name=\"Flip\" T=\"UINT8\" default=\"0\" value=\"0\"/></Params>\n"
			 << RectXml("InputRect", surface, "\t\t\t\t\t\t") << "\n"
			 << RectXml("OutputRect", surface, "\t\t\t\t\t\t") << "\n"
			 << WarperXml(surface, "\t\t\t\t\t\t") << "\n"
			 << "\t\t\t\t\t</Slice>\n";
	}

	file << "\t\t\t\t</layers>\n"
		 << "\t\t\t\t<OutputDevice>\n"
		 << "\t\t\t\t\t<OutputDeviceVirtual name=\"INSTAR\" deviceId=\"VirtualINSTAR\" width=\"" << width << "\" height=\"" << height << "\"/>\n"
		 << "\t\t\t\t</OutputDevice>\n"
		 << "\t\t\t</Screen>\n"
		 << "\t\t</screens>\n"
		 << "\t</ScreenSetup>\n"
		 << "</XmlState>\n";
	return file.str();
}
