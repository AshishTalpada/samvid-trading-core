#pragma once

#if defined(_WIN32)
#define SOVEREIGN_EXPORT __declspec(dllexport)
#else
#define SOVEREIGN_EXPORT __attribute__((visibility("default")))
#endif
