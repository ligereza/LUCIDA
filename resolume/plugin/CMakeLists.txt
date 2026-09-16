cmake_minimum_required(VERSION 3.15)

project(LucidaResolumePlugins LANGUAGES CXX)

set(FFGL_ROOT "" CACHE PATH "Path to the official Resolume FFGL checkout")
if(NOT FFGL_ROOT OR NOT EXISTS "${FFGL_ROOT}/source/lib/FFGLSDK.h")
    message(FATAL_ERROR "Set FFGL_ROOT to the official resolume/ffgl checkout")
endif()

set(FFGL_SOURCE_ROOT "${FFGL_ROOT}/source/lib")
set(FFGL_SOURCES
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLFBO.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLScopedBufferBinding.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLScopedFBOBinding.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLScopedRenderBufferBinding.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLScopedSamplerActivation.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLScopedShaderBinding.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLScopedTextureBinding.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLScopedVAOBinding.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLScreenQuad.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLShader.cpp"
    "${FFGL_SOURCE_ROOT}/ffglex/FFGLUtilities.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLAudio.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLEffect.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLMixer.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLParam.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLParamBool.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLParamEvent.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLParamFFT.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLParamOption.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLParamRange.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLParamText.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLParamTrigger.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLPlugin.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLRandom.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLSmoothValue.cpp"
    "${FFGL_SOURCE_ROOT}/ffglquickstart/FFGLSource.cpp"
    "${FFGL_SOURCE_ROOT}/ffgl/FFGL.cpp"
    "${FFGL_SOURCE_ROOT}/ffgl/FFGLLog.cpp"
    "${FFGL_SOURCE_ROOT}/ffgl/FFGLPluginInfo.cpp"
    "${FFGL_SOURCE_ROOT}/ffgl/FFGLPluginInfoData.cpp"
    "${FFGL_SOURCE_ROOT}/ffgl/FFGLPluginManager.cpp"
    "${FFGL_SOURCE_ROOT}/ffgl/FFGLPluginSDK.cpp"
    "${FFGL_SOURCE_ROOT}/ffgl/FFGLThumbnailInfo.cpp"
)

add_library(INSTAR SHARED
    INSTAR/INSTAR.cpp
    INSTAR/INSTAR.h
    INSTAR/INSTAR_RENDERER.cpp
    INSTAR/INSTAR_RENDERER.h
    INSTAR/INSTAR_SCENE.cpp
    INSTAR/INSTAR_SCENE.h
    INSTAR/INSTAR_XML.cpp
    INSTAR/INSTAR_XML.h
    INSTAR/INSTAR_IMAGE.cpp
    INSTAR/INSTAR_IMAGE.h
    ${FFGL_SOURCES}
)

target_include_directories(INSTAR PRIVATE
    "${FFGL_SOURCE_ROOT}"
    "${FFGL_ROOT}/deps/glew-2.1.0/include"
)

target_compile_features(INSTAR PRIVATE cxx_std_11)
target_compile_definitions(INSTAR PRIVATE GLEW_STATIC)
set_property(TARGET INSTAR PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)
target_link_libraries(INSTAR PRIVATE
    OpenGL32
    Gdiplus
    "${FFGL_ROOT}/deps/glew-2.1.0/lib/Release/x64/glew32s.lib"
)

set_target_properties(INSTAR PROPERTIES
    OUTPUT_NAME "INSTAR"
    PREFIX ""
    SUFFIX ".dll"
)

add_custom_command(TARGET INSTAR POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:INSTAR>"
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/INSTAR.dll"
)

add_library(INSTAR_3D SHARED
	INSTAR/INSTAR_3D.cpp
	INSTAR/INSTAR_3D.h
	INSTAR/INSTAR_RENDERER.cpp
	INSTAR/INSTAR_RENDERER.h
	INSTAR/INSTAR_SCENE.cpp
	INSTAR/INSTAR_SCENE.h
	INSTAR/INSTAR_IMAGE.cpp
	INSTAR/INSTAR_IMAGE.h
	${FFGL_SOURCES}
)
target_include_directories(INSTAR_3D PRIVATE
	"${FFGL_SOURCE_ROOT}"
	"${FFGL_ROOT}/deps/glew-2.1.0/include"
)
target_compile_features(INSTAR_3D PRIVATE cxx_std_11)
target_compile_definitions(INSTAR_3D PRIVATE GLEW_STATIC)
set_property(TARGET INSTAR_3D PROPERTY
	MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)
target_link_libraries(INSTAR_3D PRIVATE
	OpenGL32
	Gdiplus
	"${FFGL_ROOT}/deps/glew-2.1.0/lib/Release/x64/glew32s.lib"
)
set_target_properties(INSTAR_3D PROPERTIES
	OUTPUT_NAME "INSTAR_3D"
	PREFIX ""
	SUFFIX ".dll"
)
add_custom_command(TARGET INSTAR_3D POST_BUILD
	COMMAND ${CMAKE_COMMAND} -E make_directory
		"${CMAKE_CURRENT_BINARY_DIR}/Extra Effects"
	COMMAND ${CMAKE_COMMAND} -E copy_if_different
		"$<TARGET_FILE:INSTAR_3D>"
		"${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/INSTAR_3D.dll"
)

enable_testing()
add_executable(INSTAR_XML_CONTRACT
    INSTAR/INSTAR_XML.cpp
    INSTAR/INSTAR_XML.h
    INSTAR/INSTAR_XML_CONTRACT.cpp
)
target_compile_features(INSTAR_XML_CONTRACT PRIVATE cxx_std_11)
add_test(
    NAME INSTAR_XML_CONTRACT
    COMMAND INSTAR_XML_CONTRACT "${CMAKE_CURRENT_BINARY_DIR}/INSTAR_AdvancedOutput.xml"
)

add_executable(INSTAR_IMAGE_CONTRACT
    INSTAR/INSTAR_IMAGE.cpp
    INSTAR/INSTAR_IMAGE.h
    INSTAR/INSTAR_XML.cpp
    INSTAR/INSTAR_XML.h
    INSTAR/INSTAR_IMAGE_CONTRACT.cpp
)
target_compile_features(INSTAR_IMAGE_CONTRACT PRIVATE cxx_std_11)
target_link_libraries(INSTAR_IMAGE_CONTRACT PRIVATE Gdiplus)
add_test(NAME INSTAR_IMAGE_CONTRACT COMMAND INSTAR_IMAGE_CONTRACT)

add_executable(INSTAR_TEMPLATE_CONTRACT
    INSTAR/INSTAR_IMAGE.cpp
    INSTAR/INSTAR_IMAGE.h
    INSTAR/INSTAR_XML.cpp
    INSTAR/INSTAR_XML.h
    INSTAR/INSTAR_TEMPLATE_CONTRACT.cpp
)
target_compile_features(INSTAR_TEMPLATE_CONTRACT PRIVATE cxx_std_11)
target_link_libraries(INSTAR_TEMPLATE_CONTRACT PRIVATE Gdiplus)
add_test(NAME INSTAR_TEMPLATE_CONTRACT COMMAND INSTAR_TEMPLATE_CONTRACT)

add_executable(INSTAR_SCENE_CONTRACT
    INSTAR/INSTAR_SCENE.cpp
    INSTAR/INSTAR_SCENE.h
    INSTAR/INSTAR_XML.cpp
    INSTAR/INSTAR_XML.h
    INSTAR/INSTAR_SCENE_CONTRACT.cpp
)
target_compile_features(INSTAR_SCENE_CONTRACT PRIVATE cxx_std_11)
add_test(NAME INSTAR_SCENE_CONTRACT COMMAND INSTAR_SCENE_CONTRACT)
