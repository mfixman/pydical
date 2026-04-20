# modified from https://github.com/pybind/cmake_example/blob/master/setup.py
import os
import sys
import subprocess

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
try:
    from pybind11 import get_cmake_dir as _get_pybind11_cmake_dir
except ModuleNotFoundError:
    _get_pybind11_cmake_dir = None

# Convert distutils Windows platform specifiers to CMake -A arguments
PLAT_TO_CMAKE = {
    "win32": "Win32",
    "win-amd64": "x64",
    "win-arm32": "ARM",
    "win-arm64": "ARM64",
}


# A CMakeExtension needs a sourcedir instead of a file list.
class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    def run(self):
        # This is optional - will print a nicer error if CMake is missing.
        # Since we force CMake via PEP 518 in the pyproject.toml, this should
        # never happen and this whole method can be removed in your code if you
        # want.
        try:
            subprocess.check_output(["cmake", "--version"])
        except OSError:
            msg = "CMake missing - probably upgrade to a newer version of Pip?"
            raise RuntimeError(msg)

        # To support Python 2, we have to avoid super(), since distutils is all
        # old-style classes.
        build_ext.run(self)

    def build_extension(self, ext):
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))

        # required for auto-detection of auxiliary "native" libs
        if not extdir.endswith(os.path.sep):
            extdir += os.path.sep

        cfg = "Debug" if self.debug else "Release"

        # CMake lets you override the generator - we need to check this.
        # Can be set with Conda-Build, for example.
        cmake_generator = os.environ.get("CMAKE_GENERATOR", "")

        # Set Python_EXECUTABLE instead if you use PYBIND11_FINDPYTHON
        # EXAMPLE_VERSION_INFO shows you how to pass a value into the C++ code
        # from Python.
        cmake_args = [
            "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={}".format(extdir),
            "-DPYTHON_EXECUTABLE={}".format(sys.executable),
            "-DPYDICAL_VERSION_INFO={}".format(self.distribution.get_version()),
            "-DCMAKE_BUILD_TYPE={}".format(cfg),  # not used on MSVC, but no harm
        ]
        if _get_pybind11_cmake_dir is not None:
            cmake_args += ["-Dpybind11_ROOT={}".format(_get_pybind11_cmake_dir())]
        build_args = []

        if self.compiler.compiler_type != "msvc":
            # Using Ninja-build since it a) is available as a wheel and b)
            # multithreads automatically. MSVC would require all variables be
            # exported for Ninja to pick it up, which is a little tricky to do.
            # Users can override the generator with CMAKE_GENERATOR in CMake
            # 3.15+.
            if not cmake_generator:
                cmake_args += ["-GUnix Makefiles"]

        else:

            # Single config generators are handled "normally"
            single_config = any(x in cmake_generator for x in {"NMake", "Ninja"})

            # CMake allows an arch-in-generator style for backward compatibility
            contains_arch = any(x in cmake_generator for x in {"ARM", "Win64"})

            # Specify the arch if using MSVC generator, but only if it doesn't
            # contain a backward-compatibility arch spec already in the
            # generator name.
            if not single_config and not contains_arch:
                cmake_args += ["-A", PLAT_TO_CMAKE[self.plat_name]]

            # Multi-config generators have a different way to specify configs
            if not single_config:
                cmake_args += [
                    "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}".format(cfg.upper(), extdir)
                ]
                build_args += ["--config", cfg]

        # Set CMAKE_BUILD_PARALLEL_LEVEL to control the parallel build level
        # across all generators.
        if "CMAKE_BUILD_PARALLEL_LEVEL" not in os.environ:
            # self.parallel is a Python 3 only way to set parallel jobs by hand
            # using -j in the build_ext call, not supported by pip or PyPA-build.
            if hasattr(self, "parallel") and self.parallel:
                # CMake 3.12+ only.
                build_args += ["-j{}".format(self.parallel)]

        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)
        else:
            # Clear stale CMake cache so generator/build-tool changes are respected.
            cmake_cache = os.path.join(self.build_temp, "CMakeCache.txt")
            cmake_files = os.path.join(self.build_temp, "CMakeFiles")
            if os.path.exists(cmake_cache):
                os.remove(cmake_cache)
            if os.path.isdir(cmake_files):
                import shutil
                shutil.rmtree(cmake_files)

        subprocess.check_call(
            ["cmake", "-S", ext.sourcedir, "-B", self.build_temp] + cmake_args
        )
        subprocess.check_call(["cmake", "--build", self.build_temp] + build_args)


setup(
    name="pydical",
    version="0.0.1",
    author="Jannis Harder",
    author_email="me@jix.one",
    description="Python wrapper for the CaDiCaL SAT solver",
    ext_modules=[CMakeExtension("pydical")],
    cmdclass={"build_ext": CMakeBuild},
    zip_safe=False,
)
