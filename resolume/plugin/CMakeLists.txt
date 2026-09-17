cmake_minimum_required(VERSION 3.15)

project(LucidaResolumePlugins LANGUAGES CXX)

set(CUDA_ROOT "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v11.8" CACHE PATH "CUDA toolkit used by the Depth Anything FFGL effect")
set(DEPTH_CUDA_ARCHITECTURE "89" CACHE STRING "CUDA architecture for the Depth Anything effect")
set(NVCC_EXECUTABLE "${CUDA_ROOT}/bin/nvcc.exe" CACHE FILEPATH "nvcc used to compile the Depth Anything bridge")
find_path(TENSORRT_INCLUDE_DIR NvInfer.h HINTS "${CUDA_ROOT}/include" REQUIRED)
find_library(TENSORRT_LIBRARY NAMES nvinfer HINTS "${CUDA_ROOT}/lib/x64" REQUIRED)
set(CUDART_LIBRARY "${CUDA_ROOT}/lib/x64/cudart.lib")
if(NOT EXISTS "${NVCC_EXECUTABLE}" OR NOT EXISTS "${CUDART_LIBRARY}")
    message(FATAL_ERROR "CUDA toolkit incompleto: se requieren nvcc.exe y cudart.lib")
endif()

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

set(DEPTH_CUDA_OBJECT "${CMAKE_CURRENT_BINARY_DIR}/DEPTH_FX_CUDA.obj")
add_custom_command(
    OUTPUT "${DEPTH_CUDA_OBJECT}"
    COMMAND "${NVCC_EXECUTABLE}"
        -allow-unsupported-compiler
        -D__NV_NO_HOST_COMPILER_CHECK
        -D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH
        -arch=sm_${DEPTH_CUDA_ARCHITECTURE}
        -std=c++17
        -Xcompiler=/MT
        -I"${CUDA_ROOT}/include"
        -I"${TENSORRT_INCLUDE_DIR}"
        -c "${CMAKE_CURRENT_SOURCE_DIR}/DEPTH_FX/DEPTH_FX_CUDA.cu"
        -o "${DEPTH_CUDA_OBJECT}"
    DEPENDS
        DEPTH_FX/DEPTH_FX_CUDA.cu
        DEPTH_FX/DEPTH_FX_CUDA.h
    VERBATIM
)
add_custom_target(DEPTH_FX_CUDA_OBJECT DEPENDS "${DEPTH_CUDA_OBJECT}")

add_library(DEPTH_FX SHARED
    DEPTH_FX/DEPTH_FX.cpp
    DEPTH_FX/DEPTH_FX.h
    DEPTH_FX/DEPTH_FX_CUDA.h
    "${DEPTH_CUDA_OBJECT}"
    ${FFGL_SOURCES}
)
add_dependencies(DEPTH_FX DEPTH_FX_CUDA_OBJECT)
target_include_directories(DEPTH_FX PRIVATE
    "${FFGL_SOURCE_ROOT}"
    "${FFGL_ROOT}/deps/glew-2.1.0/include"
    "${CUDA_ROOT}/include"
    "${TENSORRT_INCLUDE_DIR}"
)
target_compile_features(DEPTH_FX PRIVATE cxx_std_17)
target_compile_definitions(DEPTH_FX PRIVATE GLEW_STATIC)
set_property(TARGET DEPTH_FX PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)
target_link_libraries(DEPTH_FX PRIVATE
    OpenGL32
    "${CUDART_LIBRARY}"
    "${TENSORRT_LIBRARY}"
    "${FFGL_ROOT}/deps/glew-2.1.0/lib/Release/x64/glew32s.lib"
)
set_target_properties(DEPTH_FX PROPERTIES
    OUTPUT_NAME "DEPTH_FX"
    PREFIX ""
    SUFFIX ".dll"
)
add_custom_command(TARGET DEPTH_FX POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:DEPTH_FX>"
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/DEPTH_FX.dll"
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
