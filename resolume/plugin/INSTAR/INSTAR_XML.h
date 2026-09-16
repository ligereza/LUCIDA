#pragma once

#include <string>
#include <vector>

struct INSTARSurface
{
	std::string name;
	float x = 0.0f;
	float y = 0.0f;
	float width = 0.0f;
	float height = 0.0f;
};

// Builds the same Advanced Output document that the native plugin exports.
// The document is a virtual-screen mapping; physical device assignment remains
// a Resolume/operator decision.
std::string BuildINSTARAdvancedOutputXml(
	unsigned int canvasWidth,
	unsigned int canvasHeight,
	const std::vector<INSTARSurface>& surfaces
);
