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

add_library(LucidaGuide SHARED
    LucidaGuide/LucidaGuide.cpp
    LucidaGuide/LucidaGuide.h
    ${FFGL_SOURCES}
)

target_include_directories(LucidaGuide PRIVATE
    "${FFGL_SOURCE_ROOT}"
    "${FFGL_ROOT}/deps/glew-2.1.0/include"
)

target_compile_features(LucidaGuide PRIVATE cxx_std_11)
target_compile_definitions(LucidaGuide PRIVATE GLEW_STATIC)
set_property(TARGET LucidaGuide PROPERTY
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>"
)
target_link_libraries(LucidaGuide PRIVATE
    OpenGL32
    "${FFGL_ROOT}/deps/glew-2.1.0/lib/Release/x64/glew32s.lib"
)

set_target_properties(LucidaGuide PROPERTIES
    OUTPUT_NAME "LucidaGuide"
    PREFIX ""
    SUFFIX ".dll"
)

add_custom_command(TARGET LucidaGuide POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:LucidaGuide>"
        "${CMAKE_CURRENT_BINARY_DIR}/Extra Effects/LucidaGuide.dll"
)
