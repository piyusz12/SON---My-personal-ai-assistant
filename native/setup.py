# native/setup.py — Build script for SON V3 C acceleration module
"""
Build the _son_accel C extension:
    python native/setup.py build_ext --inplace

The compiled .pyd (Windows) or .so (Linux) will be placed in native/
"""
import os
import sys
from setuptools import setup, Extension

# Compiler flags for Zen 4 (Ryzen 7 7840HS)
extra_compile_args = []
extra_link_args = []

if sys.platform == "win32":
    # MSVC: /O2 = full optimization, /arch:AVX2 = enable AVX2+FMA
    extra_compile_args = ["/O2", "/arch:AVX2", "/GL", "/fp:fast"]
    extra_link_args = ["/LTCG"]
else:
    # GCC/Clang: -O3, AVX2, FMA, march=znver4 for Zen 4
    extra_compile_args = [
        "-O3", "-mavx2", "-mfma", "-march=znver4",
        "-funroll-loops", "-ffast-math",
    ]

son_accel_ext = Extension(
    "_son_accel",
    sources=[os.path.join("native", "son_accel.c")],
    extra_compile_args=extra_compile_args,
    extra_link_args=extra_link_args,
    language="c",
)

setup(
    name="son_accel",
    version="1.0.0",
    description="SON V3 Native Acceleration — AVX2/FMA optimized audio & text processing",
    ext_modules=[son_accel_ext],
)
