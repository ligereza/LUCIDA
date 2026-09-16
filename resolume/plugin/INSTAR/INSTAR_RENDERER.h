#pragma once

#include <FFGLSDK.h>

#include "INSTAR_SCENE.h"

class INSTARSceneRenderer final
{
public:
	FFResult Init();
	void Clean();
	void Upload(const INSTARScene& scene);
	FFResult Render(
		const INSTARScene& scene,
		const INSTARCamera& camera,
		float brightness,
		unsigned int viewportWidth,
		unsigned int viewportHeight,
		GLuint textureId,
		bool useTexture
	);

private:
	ffglex::FFGLShader sceneShader;
	GLuint lineVao = 0;
	GLuint lineVbo = 0;
	GLuint triangleVao = 0;
	GLuint triangleVbo = 0;
};
