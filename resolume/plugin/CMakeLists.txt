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

add_library(INSTAR_2 SHARED
    INSTAR_2/INSTAR_2.cpp
    INSTAR_2/INSTAR_2.h
    INSTAR/INSTAR_RENDERER.cpp
    INSTAR/INSTAR_RENDERER.h
    INSTAR/INSTAR_SCENE.cpp
    INSTAR/INSTAR_SCENE.h
    INSTAR/INSTAR_XML.cpp
    INSTAR/INSTAR_XML.h
    ${FFGL_SOURCES}
)
target_include_directories(INSTAR_2 PRIVATE
    "${FFGL_SOURCE_ROOT}"
    "${FFGL_ROOT}/deps/glew-2.1.0/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/INSTAR"
    "${CMAKE_CURRENT_SOURCE_DIR}/INSTAR_2"
)
target_compile_features(INSTAR_2 PRIVATE cxx_std_17)
target_compile_definitions(INSTAR_2 PRIVATE GLEW_STATIC)
set_property(TARGET INSTAR_2 PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)
target_link_libraries(INSTAR_2 PRIVATE
    OpenGL32
    "${FFGL_ROOT}/deps/glew-2.1.0/lib/Release/x64/glew32s.lib"
)
set_target_properties(INSTAR_2 PROPERTIES
    OUTPUT_NAME "INSTAR_2"
    PREFIX ""
    SUFFIX ".dll"
)
add_custom_command(TARGET INSTAR_2 POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:INSTAR_2>"
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/INSTAR_2.dll"
)


set(LUCIDA_DEPTH_ASSET_DIR
    "${CMAKE_CURRENT_SOURCE_DIR}/../../work/resolume-plugin-build/downloads/depthgen-resources"
    CACHE PATH "Directory containing verified DepthGen model and runtime resources")
set(LUCIDA_DEPTH_ORT_ROOT
    "${CMAKE_CURRENT_SOURCE_DIR}/../../work/resolume-plugin-build/deps/ort-dml-1.17.3"
    CACHE PATH "ONNX Runtime 1.17.3 DirectML package root")

set(LUCIDA_DEPTH_ZIP_MODEL "${LUCIDA_DEPTH_ASSET_DIR}/zipdepth_base_npu_dynamic.onnx")
set(LUCIDA_DEPTH_DAV2_MODEL "${LUCIDA_DEPTH_ASSET_DIR}/depth_anything_v2_vits_dml.onnx")
set(LUCIDA_DEPTH_ORT_DLL "${LUCIDA_DEPTH_ASSET_DIR}/DepthGen-onnxruntime.dll")
foreach(required_asset IN ITEMS "${LUCIDA_DEPTH_ZIP_MODEL}" "${LUCIDA_DEPTH_DAV2_MODEL}" "${LUCIDA_DEPTH_ORT_DLL}")
    if(NOT EXISTS "${required_asset}")
        message(FATAL_ERROR "Missing verified DepthGen asset: ${required_asset}")
    endif()
endforeach()
if(NOT EXISTS "${LUCIDA_DEPTH_ORT_ROOT}/build/native/include/onnxruntime_cxx_api.h")
    message(FATAL_ERROR "LUCIDA_DEPTH_ORT_ROOT must point to the ONNX Runtime 1.17.3 DirectML package root")
endif()

configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/LUCIDA_Depth.rc.in"
    "${CMAKE_CURRENT_BINARY_DIR}/LUCIDA_Depth.generated.rc"
    @ONLY
)

add_library(LUCIDA_DEPTH SHARED
    LUCIDA_DEPTH/LUCIDA_Depth.cpp
    LUCIDA_DEPTH/LUCIDA_Depth.h
    LUCIDA_DEPTH/LUCIDA_DepthParamMapping.h
    LUCIDA_DEPTH/LUCIDA_InferenceWorker.cpp
    LUCIDA_DEPTH/LUCIDA_InferenceWorker.h
    LUCIDA_DEPTH/LUCIDA_DepthCore.cpp
    LUCIDA_DEPTH/LUCIDA_DepthCore.h
    LUCIDA_DEPTH/LUCIDA_OrtEmbed.h
    LUCIDA_DEPTH/depthgen/DepthGen_Image.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Image.h
    LUCIDA_DEPTH/depthgen/DepthGen_Temporal.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Temporal.h
    LUCIDA_DEPTH/depthgen/DepthGen_Inference.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Inference.h
    LUCIDA_DEPTH/depthgen/DepthGen_ModelIntegrity.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_ModelIntegrity.h
    LUCIDA_DEPTH/depthgen/DepthGen_EmbeddedModel.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_EmbeddedModel.h
    LUCIDA_DEPTH/depthgen/DepthGen_OrtHost.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_OrtHost.h
    "${CMAKE_CURRENT_BINARY_DIR}/LUCIDA_Depth.generated.rc"
    ${FFGL_SOURCES}
)

target_include_directories(LUCIDA_DEPTH PRIVATE
    "${FFGL_SOURCE_ROOT}"
    "${FFGL_ROOT}/deps/glew-2.1.0/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH"
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/depthgen"
    "${LUCIDA_DEPTH_ORT_ROOT}/build/native/include"
)

target_compile_features(LUCIDA_DEPTH PRIVATE cxx_std_17)
target_compile_definitions(LUCIDA_DEPTH PRIVATE
    GLEW_STATIC
    DEPTHGEN_HAS_ORT
    DEPTHGEN_EMBEDDED_MODEL
    ORT_API_MANUAL_INIT
    DEPTHGEN_ORT_DML
)
set_property(TARGET LUCIDA_DEPTH PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)
target_link_libraries(LUCIDA_DEPTH PRIVATE
    OpenGL32
    "${FFGL_ROOT}/deps/glew-2.1.0/lib/Release/x64/glew32s.lib"
)
set_target_properties(LUCIDA_DEPTH PROPERTIES
    OUTPUT_NAME "LUCIDA_Depth"
    PREFIX ""
    SUFFIX ".dll"
)
add_custom_command(TARGET LUCIDA_DEPTH POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:LUCIDA_DEPTH>"
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/LUCIDA_Depth.dll"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/README.md"
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/LUCIDA_Depth_README.md"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/THIRD_PARTY_NOTICES.md"
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/THIRD_PARTY_NOTICES.md"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/model-manifest.json"
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/model-manifest.json"
)

enable_testing()

add_executable(LUCIDA_DEPTH_CORE_SMOKE
    LUCIDA_DEPTH/LUCIDA_DepthCoreSmoke.cpp
    LUCIDA_DEPTH/LUCIDA_DepthCore.cpp
    LUCIDA_DEPTH/LUCIDA_DepthCore.h
    LUCIDA_DEPTH/depthgen/DepthGen_Image.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Image.h
    LUCIDA_DEPTH/depthgen/DepthGen_Temporal.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Temporal.h
    LUCIDA_DEPTH/depthgen/DepthGen_Inference.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Inference.h
    LUCIDA_DEPTH/depthgen/DepthGen_ModelIntegrity.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_ModelIntegrity.h
    LUCIDA_DEPTH/depthgen/DepthGen_EmbeddedModel.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_EmbeddedModel.h
    LUCIDA_DEPTH/depthgen/DepthGen_OrtHost.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_OrtHost.h
    LUCIDA_DEPTH/LUCIDA_OrtEmbed.h
    "${CMAKE_CURRENT_BINARY_DIR}/LUCIDA_Depth.generated.rc"
)
target_include_directories(LUCIDA_DEPTH_CORE_SMOKE PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH"
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/depthgen"
    "${LUCIDA_DEPTH_ORT_ROOT}/build/native/include"
)
target_compile_features(LUCIDA_DEPTH_CORE_SMOKE PRIVATE cxx_std_17)
target_compile_definitions(LUCIDA_DEPTH_CORE_SMOKE PRIVATE
    DEPTHGEN_HAS_ORT
    DEPTHGEN_EMBEDDED_MODEL
    ORT_API_MANUAL_INIT
    DEPTHGEN_ORT_DML
)
add_test(NAME LUCIDA_DEPTH_CORE_SMOKE COMMAND LUCIDA_DEPTH_CORE_SMOKE)

add_executable(LUCIDA_DEPTH_PARAM_CONTRACT
    LUCIDA_DEPTH/LUCIDA_DepthParamContract.cpp
    LUCIDA_DEPTH/LUCIDA_DepthParamMapping.h
    LUCIDA_DEPTH/LUCIDA_DepthCore.h
)
target_include_directories(LUCIDA_DEPTH_PARAM_CONTRACT PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH"
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/depthgen"
    "${LUCIDA_DEPTH_ORT_ROOT}/build/native/include"
)
target_compile_features(LUCIDA_DEPTH_PARAM_CONTRACT PRIVATE cxx_std_17)
add_test(NAME LUCIDA_DEPTH_PARAM_CONTRACT COMMAND LUCIDA_DEPTH_PARAM_CONTRACT)

add_executable(LUCIDA_DEPTH_SHADER_SMOKE
    LUCIDA_DEPTH/LUCIDA_ShaderSmoke.cpp
)
target_include_directories(LUCIDA_DEPTH_SHADER_SMOKE PRIVATE
    "${FFGL_ROOT}/deps/glew-2.1.0/include"
)
target_compile_features(LUCIDA_DEPTH_SHADER_SMOKE PRIVATE cxx_std_17)
target_compile_definitions(LUCIDA_DEPTH_SHADER_SMOKE PRIVATE GLEW_STATIC FFGL_WINDOWS)
target_link_libraries(LUCIDA_DEPTH_SHADER_SMOKE PRIVATE
    OpenGL32
    "${FFGL_ROOT}/deps/glew-2.1.0/lib/Release/x64/glew32s.lib"
)
add_test(
    NAME LUCIDA_DEPTH_SHADER_SMOKE
    COMMAND LUCIDA_DEPTH_SHADER_SMOKE
        "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/LUCIDA_Depth.cpp"
)

add_executable(LUCIDA_DEPTH_CORE_BENCH
    LUCIDA_DEPTH/LUCIDA_DepthCoreBench.cpp
    LUCIDA_DEPTH/LUCIDA_DepthCore.cpp
    LUCIDA_DEPTH/LUCIDA_DepthCore.h
    LUCIDA_DEPTH/depthgen/DepthGen_Image.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Image.h
    LUCIDA_DEPTH/depthgen/DepthGen_Temporal.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Temporal.h
    LUCIDA_DEPTH/depthgen/DepthGen_Inference.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_Inference.h
    LUCIDA_DEPTH/depthgen/DepthGen_ModelIntegrity.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_ModelIntegrity.h
    LUCIDA_DEPTH/depthgen/DepthGen_EmbeddedModel.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_EmbeddedModel.h
    LUCIDA_DEPTH/depthgen/DepthGen_OrtHost.cpp
    LUCIDA_DEPTH/depthgen/DepthGen_OrtHost.h
    LUCIDA_DEPTH/LUCIDA_OrtEmbed.h
    "${CMAKE_CURRENT_BINARY_DIR}/LUCIDA_Depth.generated.rc"
)
target_include_directories(LUCIDA_DEPTH_CORE_BENCH PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH"
    "${CMAKE_CURRENT_SOURCE_DIR}/LUCIDA_DEPTH/depthgen"
    "${LUCIDA_DEPTH_ORT_ROOT}/build/native/include"
)
target_compile_features(LUCIDA_DEPTH_CORE_BENCH PRIVATE cxx_std_17)
target_compile_definitions(LUCIDA_DEPTH_CORE_BENCH PRIVATE
    DEPTHGEN_HAS_ORT
    DEPTHGEN_EMBEDDED_MODEL
    ORT_API_MANUAL_INIT
    DEPTHGEN_ORT_DML
)

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
