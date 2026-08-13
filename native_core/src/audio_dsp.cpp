// native_core/src/audio_dsp.cpp — C++20 AVX2 SIMD Real-Time Audio DSP Engine
#include <cmath>
#include <cstring>
#include <algorithm>
#include "../include/son_core.h"

#if defined(__AVX2__) || defined(_MSC_VER)
    #include <immintrin.h>
    #define HAS_AVX2 1
#else
    #define HAS_AVX2 0
#endif

extern "C" {

float son_fast_rms(const float* audio, int length) {
    if (!audio || length <= 0) return 0.0f;

#if HAS_AVX2
    __m256 vsum = _mm256_setzero_ps();
    int i = 0;
    int n8 = length & ~7;

    for (; i < n8; i += 8) {
        __m256 v = _mm256_loadu_ps(&audio[i]);
        vsum = _mm256_fmadd_ps(v, v, vsum);
    }

    // Horizontal sum of 8 float registers
    __m128 hi = _mm256_extractf128_ps(vsum, 1);
    __m128 lo = _mm256_castps256_ps128(vsum);
    __m128 sum128 = _mm_add_ps(lo, hi);
    sum128 = _mm_hadd_ps(sum128, sum128);
    sum128 = _mm_hadd_ps(sum128, sum128);
    float total = _mm_cvtss_f32(sum128);

    for (; i < length; i++) {
        total += audio[i] * audio[i];
    }
    return std::sqrt(total / static_cast<float>(length));
#else
    double total = 0.0;
    for (int i = 0; i < length; i++) {
        total += static_cast<double>(audio[i]) * static_cast<double>(audio[i]);
    }
    return static_cast<float>(std::sqrt(total / static_cast<double>(length)));
#endif
}

void son_fast_resample(const float* src, int src_len, int src_rate, float* dst, int dst_len, int dst_rate) {
    if (!src || !dst || src_len <= 0 || dst_len <= 0) return;
    if (src_rate == dst_rate) {
        std::memcpy(dst, src, std::min(src_len, dst_len) * sizeof(float));
        return;
    }

    float ratio = static_cast<float>(src_len - 1) / static_cast<float>(dst_len - 1);
    for (int i = 0; i < dst_len; i++) {
        float pos = static_cast<float>(i) * ratio;
        int idx = static_cast<int>(pos);
        float frac = pos - static_cast<float>(idx);

        if (idx >= src_len - 1) {
            dst[i] = src[src_len - 1];
        } else {
            dst[i] = src[idx] * (1.0f - frac) + src[idx + 1] * frac;
        }
    }
}

void son_fast_normalize(float* audio, int length, float target_peak, float max_gain) {
    if (!audio || length <= 0) return;

    float peak = 0.0f;
    for (int i = 0; i < length; i++) {
        float v = std::fabs(audio[i]);
        if (v > peak) peak = v;
    }

    if (peak > 0.01f) {
        float gain = std::min(target_peak / peak, max_gain);
        for (int i = 0; i < length; i++) {
            float scaled = audio[i] * gain;
            if (scaled > 1.0f) audio[i] = 1.0f;
            else if (scaled < -1.0f) audio[i] = -1.0f;
            else audio[i] = scaled;
        }
    }
}

}
