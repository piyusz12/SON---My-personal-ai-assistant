// native_core/src/vector_engine.cpp — C++ AVX2 SIMD Vector Search & Cosine Distance Engine
#ifndef SON_CORE_EXPORTS
#define SON_CORE_EXPORTS 1
#endif

#include <cmath>
#include "../include/son_core.h"

#if defined(__AVX2__) || defined(_MSC_VER)
    #include <immintrin.h>
    #define HAS_AVX2 1
#else
    #define HAS_AVX2 0
#endif

extern "C" {

SON_API float son_cosine_similarity(const float* a, const float* b, int dim) {
    if (!a || !b || dim <= 0) return 0.0f;

#if HAS_AVX2
    __m256 vdot = _mm256_setzero_ps();
    __m256 vnorm_a = _mm256_setzero_ps();
    __m256 vnorm_b = _mm256_setzero_ps();

    int i = 0;
    int n8 = dim & ~7;

    for (; i < n8; i += 8) {
        __m256 va = _mm256_loadu_ps(&a[i]);
        __m256 vb = _mm256_loadu_ps(&b[i]);
        vdot = _mm256_fmadd_ps(va, vb, vdot);
        vnorm_a = _mm256_fmadd_ps(va, va, vnorm_a);
        vnorm_b = _mm256_fmadd_ps(vb, vb, vnorm_b);
    }

    // Horizontal sums
    auto hsum8 = [](__m256 v) -> float {
        __m128 hi = _mm256_extractf128_ps(v, 1);
        __m128 lo = _mm256_castps256_ps128(v);
        __m128 s = _mm_add_ps(lo, hi);
        s = _mm_hadd_ps(s, s);
        s = _mm_hadd_ps(s, s);
        return _mm_cvtss_f32(s);
    };

    float dot = hsum8(vdot);
    float norm_a = hsum8(vnorm_a);
    float norm_b = hsum8(vnorm_b);

    for (; i < dim; i++) {
        dot += a[i] * b[i];
        norm_a += a[i] * a[i];
        norm_b += b[i] * b[i];
    }

    float denom = std::sqrt(norm_a) * std::sqrt(norm_b);
    return (denom > 1e-7f) ? (dot / denom) : 0.0f;
#else
    double dot = 0.0, norm_a = 0.0, norm_b = 0.0;
    for (int i = 0; i < dim; i++) {
        dot += static_cast<double>(a[i]) * static_cast<double>(b[i]);
        norm_a += static_cast<double>(a[i]) * static_cast<double>(a[i]);
        norm_b += static_cast<double>(b[i]) * static_cast<double>(b[i]);
    }
    double denom = std::sqrt(norm_a) * std::sqrt(norm_b);
    return (denom > 1e-7) ? static_cast<float>(dot / denom) : 0.0f;
#endif
}

SON_API void son_batch_cosine_similarity(const float* query, const float* matrix, int num_vectors, int dim, float* scores_out) {
    if (!query || !matrix || !scores_out || num_vectors <= 0 || dim <= 0) return;

    for (int v = 0; v < num_vectors; v++) {
        const float* row = &matrix[v * dim];
        scores_out[v] = son_cosine_similarity(query, row, dim);
    }
}

SON_API float son_frame_motion_sad(const unsigned char* frame1, const unsigned char* frame2, int total_pixels) {
    if (!frame1 || !frame2 || total_pixels <= 0) return 0.0f;

    double diff_sum = 0.0;
    for (int i = 0; i < total_pixels; i++) {
        diff_sum += std::abs(static_cast<int>(frame1[i]) - static_cast<int>(frame2[i]));
    }
    return static_cast<float>(diff_sum / (static_cast<double>(total_pixels) * 255.0));
}

}
