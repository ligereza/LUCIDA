#include "INSTAR_XML.h"

#include <cmath>
#include <cstdlib>
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

std::string AttributeValue(const std::string& text, size_t start, const char* name)
{
	const std::string marker = std::string(name) + "=\"";
	const size_t valueStart = text.find(marker, start);
	if (valueStart == std::string::npos)
		return std::string();
	const size_t contentStart = valueStart + marker.size();
	const size_t contentEnd = text.find('"', contentStart);
	return contentEnd == std::string::npos ? std::string() : text.substr(contentStart, contentEnd - contentStart);
}

bool ParseUnsigned(const std::string& value, unsigned int& result)
{
	if (value.empty())
		return false;
	char* end = nullptr;
	const unsigned long parsed = std::strtoul(value.c_str(), &end, 10);
	if (end == value.c_str() || *end != '\0' || parsed == 0 || parsed > 4294967295UL)
		return false;
	result = static_cast<unsigned int>(parsed);
	return true;
}

bool ParseUnsignedLongLong(const std::string& value, unsigned long long& result)
{
	if (value.empty())
		return false;
	char* end = nullptr;
	const unsigned long long parsed = std::strtoull(value.c_str(), &end, 10);
	if (end == value.c_str() || *end != '\0' || parsed == 0)
		return false;
	result = parsed;
	return true;
}

std::string ReplaceAttribute(const std::string& text, const char* name, const std::string& value)
{
	const std::string marker = std::string(name) + "=\"";
	const size_t valueStart = text.find(marker);
	if (valueStart == std::string::npos)
		return text;
	const size_t contentStart = valueStart + marker.size();
	const size_t contentEnd = text.find('"', contentStart);
	if (contentEnd == std::string::npos)
		return text;
	std::string result = text;
	result.replace(contentStart, contentEnd - contentStart, value);
	return result;
}

std::string ReplaceSliceName(const std::string& text, const std::string& name)
{
	const size_t common = text.find("<Params name=\"Common\"");
	const size_t nameParam = common == std::string::npos ? std::string::npos : text.find("<Param name=\"Name\"", common);
	if (nameParam == std::string::npos)
		return text;
	const size_t valueStart = text.find("value=\"", nameParam);
	if (valueStart == std::string::npos)
		return text;
	const size_t contentStart = valueStart + 7;
	const size_t contentEnd = text.find('"', contentStart);
	if (contentEnd == std::string::npos)
		return text;
	std::string result = text;
	result.replace(contentStart, contentEnd - contentStart, XmlEscape(name));
	return result;
}

std::string TemplateSlice(
	const std::string& templateSlice,
	unsigned long long uniqueId,
	const INSTARSurfaceMapping& mapping
)
{
	const size_t sliceOpenEnd = templateSlice.find('>');
	const size_t inputStart = sliceOpenEnd == std::string::npos ? std::string::npos : templateSlice.find("<InputRect", sliceOpenEnd);
	const size_t warperEnd = inputStart == std::string::npos ? std::string::npos : templateSlice.find("</Warper>", inputStart);
	const size_t sliceClose = templateSlice.rfind("</Slice>");
	if (sliceOpenEnd == std::string::npos || inputStart == std::string::npos || warperEnd == std::string::npos || sliceClose == std::string::npos)
		return std::string();
	std::string head = templateSlice.substr(0, inputStart);
	head = ReplaceAttribute(head, "uniqueId", std::to_string(uniqueId));
	head = ReplaceSliceName(head, mapping.name);
	const std::string tail = templateSlice.substr(warperEnd + std::string("</Warper>").size(), sliceClose - warperEnd - std::string("</Warper>").size());
	const std::string indent = "\t\t\t\t\t\t";
	return head + RectXml("InputRect", mapping.input, indent) + "\n" +
		RectXml("OutputRect", mapping.output, indent) + "\n" +
		WarperXml(mapping.output, indent) + tail + "</Slice>";
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

bool ReadINSTARAdvancedOutputTemplateInfo(
	const std::string& templateXml,
	INSTARTemplateInfo& info,
	std::string& error
)
{
	info = INSTARTemplateInfo();
	if (templateXml.find("<XmlState") == std::string::npos ||
		templateXml.find("<ScreenSetup") == std::string::npos ||
		templateXml.find("<Screen ") == std::string::npos ||
		templateXml.find("<layers>") == std::string::npos ||
		templateXml.find("</layers>") == std::string::npos)
	{
		error = "template is not a Resolume Advanced Output document";
		return false;
	}
	const size_t texture = templateXml.find("<CurrentCompositionTextureSize");
	const size_t display = templateXml.find("<OutputDeviceDisplay");
	const size_t virtualDevice = templateXml.find("<OutputDeviceVirtual");
	if (texture == std::string::npos)
	{
		error = "template has no composition texture size";
		return false;
	}
	if (!ParseUnsigned(AttributeValue(templateXml, texture, "width"), info.inputWidth) ||
		!ParseUnsigned(AttributeValue(templateXml, texture, "height"), info.inputHeight))
	{
		error = "template composition texture size is invalid";
		return false;
	}
	const size_t outputTag = display != std::string::npos ? display : virtualDevice;
	if (outputTag != std::string::npos)
	{
		ParseUnsigned(AttributeValue(templateXml, outputTag, "width"), info.outputWidth);
		ParseUnsigned(AttributeValue(templateXml, outputTag, "height"), info.outputHeight);
	}
	if (info.outputWidth == 0 || info.outputHeight == 0)
	{
		info.outputWidth = info.inputWidth;
		info.outputHeight = info.inputHeight;
	}
	const size_t slice = templateXml.find("<Slice");
	if (slice != std::string::npos)
		ParseUnsignedLongLong(AttributeValue(templateXml, slice, "uniqueId"), info.firstSliceId);
	if (info.firstSliceId == 0)
		info.firstSliceId = 1800000000001ULL;
	return true;
}

std::vector<INSTARSurfaceMapping> ScaleINSTARSurfacesToTemplate(
	const std::vector<INSTARSurface>& surfaces,
	unsigned int sourceWidth,
	unsigned int sourceHeight,
	const INSTARTemplateInfo& templateInfo
)
{
	std::vector<INSTARSurfaceMapping> mappings;
	if (sourceWidth == 0 || sourceHeight == 0 || templateInfo.inputWidth == 0 || templateInfo.inputHeight == 0 || templateInfo.outputWidth == 0 || templateInfo.outputHeight == 0)
		return mappings;
	for (const INSTARSurface& surface : surfaces)
	{
		INSTARSurfaceMapping mapping;
		mapping.name = surface.name;
		mapping.input.x = surface.x / static_cast<float>(sourceWidth) * templateInfo.inputWidth;
		mapping.input.y = surface.y / static_cast<float>(sourceHeight) * templateInfo.inputHeight;
		mapping.input.width = surface.width / static_cast<float>(sourceWidth) * templateInfo.inputWidth;
		mapping.input.height = surface.height / static_cast<float>(sourceHeight) * templateInfo.inputHeight;
		mapping.output.x = surface.x / static_cast<float>(sourceWidth) * templateInfo.outputWidth;
		mapping.output.y = surface.y / static_cast<float>(sourceHeight) * templateInfo.outputHeight;
		mapping.output.width = surface.width / static_cast<float>(sourceWidth) * templateInfo.outputWidth;
		mapping.output.height = surface.height / static_cast<float>(sourceHeight) * templateInfo.outputHeight;
		mappings.push_back(mapping);
	}
	return mappings;
}

std::string BuildINSTARAdvancedOutputXmlFromTemplate(
	const std::string& templateXml,
	const std::vector<INSTARSurfaceMapping>& mappings
)
{
	INSTARTemplateInfo info;
	std::string error;
	if (!ReadINSTARAdvancedOutputTemplateInfo(templateXml, info, error))
		return std::string();
	const size_t layersOpen = templateXml.find("<layers>");
	const size_t layersClose = templateXml.find("</layers>", layersOpen);
	const size_t sliceOpen = templateXml.find("<Slice", layersOpen);
	const size_t sliceClose = sliceOpen == std::string::npos ? std::string::npos : templateXml.find("</Slice>", sliceOpen);
	if (layersOpen == std::string::npos || layersClose == std::string::npos || sliceOpen == std::string::npos || sliceClose == std::string::npos)
		return std::string();
	const std::string templateSlice = templateXml.substr(sliceOpen, sliceClose + std::string("</Slice>").size() - sliceOpen);
	std::ostringstream output;
	output << templateXml.substr(0, layersOpen + std::string("<layers>").size()) << "\n";
	unsigned long long nextId = info.firstSliceId;
	for (const INSTARSurfaceMapping& mapping : mappings)
	{
		const std::string slice = TemplateSlice(templateSlice, nextId++, mapping);
		if (slice.empty())
			return std::string();
		output << slice << "\n";
	}
	output << templateXml.substr(layersClose);
	return output.str();
}
