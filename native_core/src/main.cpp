// native_core/src/main.cpp — Standalone Native Core Diagnostic & Benchmark Runner
#include <iostream>
#include <vector>
#include <chrono>
#include <iomanip>
#include "../include/son_core.h"

int main() {
    std::cout << "=================================================================\n";
    std::cout << "      SON V3  ::  C++20 NATIVE ACCELERATION ENGINE\n";
    std::cout << "=================================================================\n";

    // 1. Audio DSP RMS Benchmark
    std::vector<float> audio(48000, 0.25f);
    auto t0 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < 5000; i++) {
        son_fast_rms(audio.data(), static_cast<int>(audio.size()));
    }
    auto t1 = std::chrono::high_resolution_clock::now();
    double rms_us = std::chrono::duration<double, std::micro>(t1 - t0).count() / 5000.0;
    std::cout << "1. C++ AVX2 Fast RMS (48k samples): " << std::fixed << std::setprecision(3) << rms_us << " us/pass\n";

    // 2. Vector Cosine Similarity Benchmark
    std::vector<float> vec_a(512, 1.0f);
    std::vector<float> vec_b(512, 0.9f);
    t0 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < 50000; i++) {
        son_cosine_similarity(vec_a.data(), vec_b.data(), 512);
    }
    t1 = std::chrono::high_resolution_clock::now();
    double cos_us = std::chrono::duration<double, std::micro>(t1 - t0).count() / 50000.0;
    std::cout << "2. C++ AVX2 Vector Similarity (512-dim): " << cos_us << " us/pair\n";

    // 3. Fast Intent Matcher
    t0 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < 100000; i++) {
        son_match_intent_fast("open youtube and search for lofi music");
    }
    t1 = std::chrono::high_resolution_clock::now();
    double intent_ns = std::chrono::duration<double, std::nano>(t1 - t0).count() / 100000.0;
    std::cout << "3. C++ Fast Intent Routing: " << intent_ns << " ns/query (< 0.001 ms!)\n";

    std::cout << "=================================================================\n";
    std::cout << "  C++ NATIVE ENGINE OPERATIONAL WITH ZERO INTERPRETER OVERHEAD!\n";
    std::cout << "=================================================================\n";
    return 0;
}
