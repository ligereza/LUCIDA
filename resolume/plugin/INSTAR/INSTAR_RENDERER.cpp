#include "INSTAR_RENDERER.h"

FFResult INSTARSceneRenderer::Init()
{
	const char* vertexShader = R"(
		#version 410 core
		layout(location = 0) in vec3 position;
		layout(location = 1) in vec3 colour;
		layout(location = 2) in vec2 texCoord;
		uniform float u_yaw;
		uniform float u_pitch;
		uniform float u_zoom;
		uniform float u_aspect;
		uniform vec3 u_scene_centre;
		uniform float u_scene_scale;
		out vec3 v_colour;
		out vec2 v_texcoord;
		void main()
		{
			float cy = cos(u_yaw);
			float sy = sin(u_yaw);
			vec3 fitted = (position - u_scene_centre) * u_scene_scale;
			vec3 p = vec3(cy * fitted.x - sy * fitted.z, fitted.y, sy * fitted.x + cy * fitted.z);
			float cp = cos(u_pitch);
			float sp = sin(u_pitch);
			p = vec3(p.x, cp * p.y - sp * p.z, sp * p.y + cp * p.z);
			p.z += 3.5;
			float perspective = u_zoom / max(0.5, p.z);
			float depth = clamp((p.z - 0.5) / 6.0 * 2.0 - 1.0, -1.0, 1.0);
			gl_Position = vec4(p.x * perspective / max(0.1, u_aspect), p.y * perspective, depth, 1.0);
			v_colour = colour;
			v_texcoord = texCoord;
		}
	)";
	const char* fragmentShader = R"(
		#version 410 core
		in vec3 v_colour;
		in vec2 v_texcoord;
		uniform float u_brightness;
		uniform sampler2D modelTexture;
		uniform float u_texture_enabled;
		out vec4 fragColor;
		void main()
		{
			vec4 textured = texture(modelTexture, vec2(v_texcoord.x, 1.0 - v_texcoord.y));
			vec3 base = u_texture_enabled > 0.5 ? textured.rgb : v_colour;
			float alpha = u_texture_enabled > 0.5 ? textured.a : 1.0;
			fragColor = vec4(base * u_brightness, alpha);
		}
	)";
	if (!sceneShader.Compile(vertexShader, fragmentShader))
		return FF_FAIL;
	glGenVertexArrays(1, &lineVao);
	glGenBuffers(1, &lineVbo);
	glGenVertexArrays(1, &triangleVao);
	glGenBuffers(1, &triangleVbo);
	if (lineVao == 0 || lineVbo == 0 || triangleVao == 0 || triangleVbo == 0)
		return FF_FAIL;
	return FF_SUCCESS;
}

void INSTARSceneRenderer::Clean()
{
	if (lineVbo != 0)
		glDeleteBuffers(1, &lineVbo);
	if (lineVao != 0)
		glDeleteVertexArrays(1, &lineVao);
	if (triangleVbo != 0)
		glDeleteBuffers(1, &triangleVbo);
	if (triangleVao != 0)
		glDeleteVertexArrays(1, &triangleVao);
	lineVbo = 0;
	lineVao = 0;
	triangleVbo = 0;
	triangleVao = 0;
	sceneShader.FreeGLResources();
}

void INSTARSceneRenderer::Upload(const INSTARScene& scene)
{
	if (lineVao == 0 || lineVbo == 0 || triangleVao == 0 || triangleVbo == 0)
		return;
	ffglex::ScopedShaderBinding binding(sceneShader.GetGLID());
	glBindVertexArray(lineVao);
	glBindBuffer(GL_ARRAY_BUFFER, lineVbo);
	glBufferData(GL_ARRAY_BUFFER, static_cast<GLsizeiptr>(scene.lineVertices.size() * sizeof(INSTARVertex)), scene.lineVertices.data(), GL_STATIC_DRAW);
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(0));
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(sizeof(INSTARVec3)));
	glEnableVertexAttribArray(2);
	glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(sizeof(INSTARVec3) + 3 * sizeof(float)));
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glBindVertexArray(0);

	glBindVertexArray(triangleVao);
	glBindBuffer(GL_ARRAY_BUFFER, triangleVbo);
	glBufferData(GL_ARRAY_BUFFER, static_cast<GLsizeiptr>(scene.triangleVertices.size() * sizeof(INSTARVertex)), scene.triangleVertices.data(), GL_STATIC_DRAW);
	glEnableVertexAttribArray(0);
	glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(0));
	glEnableVertexAttribArray(1);
	glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(sizeof(INSTARVec3)));
	glEnableVertexAttribArray(2);
	glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, sizeof(INSTARVertex), reinterpret_cast<const void*>(sizeof(INSTARVec3) + 3 * sizeof(float)));
	glBindBuffer(GL_ARRAY_BUFFER, 0);
	glBindVertexArray(0);
}

FFResult INSTARSceneRenderer::Render(
	const INSTARScene& scene,
	const INSTARCamera& camera,
	float brightness,
	unsigned int viewportWidth,
	unsigned int viewportHeight,
	GLuint textureId,
	bool useTexture
)
{
	glEnable(GL_DEPTH_TEST);
	glEnable(GL_BLEND);
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
	glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
	glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
	if (!sceneShader.IsReady() || (scene.lineVertices.empty() && scene.triangleVertices.empty()))
		return FF_SUCCESS;
	const float aspect = viewportHeight > 0 ? static_cast<float>(viewportWidth) / static_cast<float>(viewportHeight) : 1.777f;
	ffglex::ScopedShaderBinding binding(sceneShader.GetGLID());
	sceneShader.Set("u_yaw", camera.yaw);
	sceneShader.Set("u_pitch", camera.pitch);
	sceneShader.Set("u_zoom", camera.zoom);
	sceneShader.Set("u_aspect", aspect);
	sceneShader.Set("u_scene_centre", scene.renderCentre.x, scene.renderCentre.y, scene.renderCentre.z);
	sceneShader.Set("u_scene_scale", scene.renderScale);
	sceneShader.Set("u_brightness", 0.2f + brightness * 1.2f);
	sceneShader.Set("modelTexture", 0);
	sceneShader.Set("u_texture_enabled", useTexture ? 1.0f : 0.0f);
	glActiveTexture(GL_TEXTURE0);
	glBindTexture(GL_TEXTURE_2D, useTexture ? textureId : 0);
	glBindVertexArray(triangleVao);
	if (!scene.triangleVertices.empty())
		glDrawArrays(GL_TRIANGLES, 0, static_cast<GLsizei>(scene.triangleVertices.size()));
	glBindVertexArray(lineVao);
	if (!scene.lineVertices.empty())
		glDrawArrays(GL_LINES, 0, static_cast<GLsizei>(scene.lineVertices.size()));
	glBindVertexArray(0);
	glBindTexture(GL_TEXTURE_2D, 0);
	glDisable(GL_BLEND);
	glDisable(GL_DEPTH_TEST);
	return FF_SUCCESS;
}
