// native_core/include/son_core.h — High-Performance Native C/C++ Core Engine for SON V3
#ifndef SON_CORE_H
#define SON_CORE_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN32
    #if defined(SON_CORE_EXPORTS)
        #define SON_API __declspec(dllexport)
    #elif defined(SON_CORE_STATIC)
        #define SON_API
    #else
        #define SON_API __declspec(dllimport)
    #endif
#else
    #define SON_API __attribute__((visibility("default")))
#endif

// ── Audio DSP & Voice Activity Detection ──────────────────────────
SON_API float son_fast_rms(const float* audio, int length);
SON_API void son_fast_resample(const float* src, int src_len, int src_rate, float* dst, int dst_len, int dst_rate);
SON_API void son_fast_normalize(float* audio, int length, float target_peak, float max_gain);

// ── Vector Search & SIMD Math ────────────────────────────────────
SON_API float son_cosine_similarity(const float* a, const float* b, int dim);
SON_API void son_batch_cosine_similarity(const float* query, const float* matrix, int num_vectors, int dim, float* scores_out);

// ── Optical Motion & Frame Difference ────────────────────────────
SON_API float son_frame_motion_sad(const unsigned char* frame1, const unsigned char* frame2, int total_pixels);

// ── Fast Trie Intent Router ──────────────────────────────────────
SON_API int son_match_intent_fast(const char* text);

#ifdef __cplusplus
}
#endif

#endif // SON_CORE_H
