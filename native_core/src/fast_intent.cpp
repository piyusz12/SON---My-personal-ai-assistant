// native_core/src/fast_intent.cpp — C++20 Fast Trie & Keyword Matcher
#include <string>
#include <vector>
#include <cstring>
#include <algorithm>
#include "../include/son_core.h"

enum NativeIntentType {
    INTENT_UNKNOWN = 0,
    INTENT_APP_OPEN = 1,
    INTENT_WEBSITE_OPEN = 2,
    INTENT_WEB_SEARCH = 3,
    INTENT_CAMERA_QUERY = 4,
    INTENT_SCREEN_QUERY = 5,
    INTENT_SYSTEM_QUERY = 6,
    INTENT_MEDIA_CONTROL = 7,
    INTENT_CHAT = 8
};

extern "C" {

int son_match_intent_fast(const char* text) {
    if (!text) return INTENT_UNKNOWN;

    std::string s(text);
    std::transform(s.begin(), s.end(), s.begin(), ::tolower);

    // Fast keyword / prefix routing in C++
    if (s.find("open ") == 0 || s.find("launch ") == 0 || s.find("start ") == 0) {
        if (s.find(".com") != std::string::npos || s.find(".org") != std::string::npos ||
            s.find("youtube") != std::string::npos || s.find("github") != std::string::npos ||
            s.find("google") != std::string::npos || s.find("reddit") != std::string::npos) {
            return INTENT_WEBSITE_OPEN;
        }
        return INTENT_APP_OPEN;
    }

    if (s.find("search ") == 0 || s.find("google ") == 0 || s.find("look up ") == 0) {
        return INTENT_WEB_SEARCH;
    }

    if (s.find("see me") != std::string::npos || s.find("who is in front") != std::string::npos ||
        s.find("look at me") != std::string::npos || s.find("camera") != std::string::npos) {
        return INTENT_CAMERA_QUERY;
    }

    if (s.find("what's on my screen") != std::string::npos || s.find("look at screen") != std::string::npos ||
        s.find("screenshot") != std::string::npos) {
        return INTENT_SCREEN_QUERY;
    }

    if (s.find("system status") != std::string::npos || s.find("cpu") != std::string::npos ||
        s.find("gpu") != std::string::npos || s.find("vram") != std::string::npos ||
        s.find("battery") != std::string::npos) {
        return INTENT_SYSTEM_QUERY;
    }

    return INTENT_CHAT;
}

}
