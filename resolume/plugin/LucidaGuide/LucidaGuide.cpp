#include "LucidaGuide.h"

using namespace ffglqs;

static CFFGLPluginInfo PluginInfo(
	PluginFactory< LucidaGuide >,
	"LU01",
	"Lucida Guide",
	2,
	1,
	0,
	1,
	FF_EFFECT,
	"A lightweight visual guide that preserves the input and adds an optional composition boundary.",
	"LUCIDA RESOLUME"
);

LucidaGuide::LucidaGuide()
{
	SetFragmentShader(R"(
		in vec2 i_uv;
		uniform sampler2D inputTexture;
		uniform float GuideOpacity;
		uniform float GuideDetail;
		uniform vec4 GuideColor;

		float line(float distanceToLine, float width)
		{
			return 1.0 - smoothstep(width, width + 0.003, distanceToLine);
		}

		void main()
		{
			vec4 base = texture(inputTexture, i_uv);
			vec2 distanceToEdge = min(i_uv, 1.0 - i_uv);
			float border = max(
				line(distanceToEdge.x, 0.018),
				line(distanceToEdge.y, 0.018)
			);

			float gridSpacing = mix(0.25, 0.125, clamp(GuideDetail, 0.0, 1.0));
			vec2 gridCell = abs(fract(i_uv / gridSpacing) - 0.5);
			float grid = max(
				line(gridCell.x * gridSpacing, 0.004),
				line(gridCell.y * gridSpacing, 0.004)
			) * clamp(GuideDetail, 0.0, 1.0);

			float guide = max(border, grid * 0.7);
			float alpha = clamp(GuideOpacity, 0.0, 1.0) * guide;
			fragColor = vec4(mix(base.rgb, GuideColor.rgb, alpha), base.a);
		}
	)");

	AddParam(Param::Create("GuideOpacity", 0.65f));
	AddParam(Param::Create("GuideDetail", 0.0f));
	AddHueColorParam("GuideColor");
}
