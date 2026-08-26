cmake_minimum_required(VERSION 3.10)
project(SonNativeVision)

set(CMAKE_CXX_STANDARD 17)

# Future: find_package(OpenCV REQUIRED)
# Future: find_package(CUDA REQUIRED)

add_executable(son_vision main.cpp)
# target_link_libraries(son_vision ${OpenCV_LIBS})
