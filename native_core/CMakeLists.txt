cmake_minimum_required(VERSION 3.20)
project(son_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(MSVC)
    add_compile_options(/O2 /arch:AVX2 /fp:fast)
else()
    add_compile_options(-O3 -mavx2 -mfma -ffast-math)
endif()

include_directories(include)

# Shared Library
add_library(son_core SHARED
    src/audio_dsp.cpp
    src/vector_engine.cpp
    src/fast_intent.cpp
)
target_compile_definitions(son_core PRIVATE SON_CORE_EXPORTS)

# Standalone Executable
add_executable(son_core_bin
    src/main.cpp
    src/audio_dsp.cpp
    src/vector_engine.cpp
    src/fast_intent.cpp
)
set_target_properties(son_core_bin PROPERTIES OUTPUT_NAME "son_core")
