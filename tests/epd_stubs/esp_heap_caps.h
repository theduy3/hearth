#pragma once
#include <cstdlib>
constexpr int MALLOC_CAP_DMA=1,MALLOC_CAP_INTERNAL=2;
inline void* heap_caps_malloc(size_t n,int){return std::malloc(n);}
inline void heap_caps_free(void* p){std::free(p);}
