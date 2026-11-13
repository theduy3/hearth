#include <cassert>
#include <cstdio>
#include "zectrix_button_logic.h"
int main() {
    struct GestureResult {
        bool click;
        bool long_press;
        uint32_t long_at_ms;
    };
    auto press_gesture = [](uint32_t held_ms, uint32_t bounce_ms) {
        const zectrix::ButtonTiming timing;
        zectrix::ButtonTracker tracker;
        zectrix::ResetButtonTracker(tracker, 0, false);
        GestureResult out = {false, false, 0};
        for (uint32_t ms = 0; ms <= 3000; ms += 20) {
            bool pressed = ms >= 100 && ms < 100 + held_ms;
            // Contact bounce in the middle of a press, shorter than the
            // debounce window.
            if (bounce_ms && ms >= 100 + bounce_ms &&
                ms < 100 + bounce_ms + 20) {
                pressed = false;
            }
            const zectrix::ButtonEvent event = zectrix::TrackButtonPress(
                tracker, timing, ms, pressed);
            if (event == zectrix::ButtonEvent::kClick) out.click = true;
            if (event == zectrix::ButtonEvent::kLongPress) {
                out.long_press = true;
                out.long_at_ms = ms;
            }
        }
        return out;
    };

    assert(press_gesture(120, 0).click);
    assert(!press_gesture(120, 0).long_press);
    // The tail of ordinary human short presses: still a page turn. The old
    // 220 ms threshold, counted after the debounce, turned these into speech.
    assert(press_gesture(300, 0).click);
    assert(!press_gesture(300, 0).long_press);
    assert(press_gesture(420, 0).click);
    assert(!press_gesture(420, 0).long_press);
    // A real hold to speak: long press fires near the threshold, and the
    // release must not also turn the page.
    assert(press_gesture(900, 0).long_press);
    assert(!press_gesture(900, 0).click);
    // Press onset is t=100, so the long press lands on the 450 ms threshold
    // plus at most one 20 ms sample of slack.
    assert(press_gesture(900, 0).long_at_ms >= 550);
    assert(press_gesture(900, 0).long_at_ms <= 580);
    // Bounce shorter than the debounce does not split one press into two.
    assert(press_gesture(200, 60).click);
    assert(!press_gesture(200, 60).long_press);
    // A button already held when the board booted swallows its own release.
    {
        zectrix::ButtonTiming timing;
        zectrix::ButtonTracker tracker;
        zectrix::ResetButtonTracker(tracker, 0, true);
        bool saw_event = false;
        for (uint32_t ms = 0; ms <= 400; ms += 20) {
            if (zectrix::TrackButtonPress(tracker, timing, ms, ms < 200) !=
                zectrix::ButtonEvent::kNone) {
                saw_event = true;
            }
        }
        assert(!saw_event);
        assert(press_gesture(600, 0).long_press);
    }

    std::puts("NOTE4C_BUTTONS_OK");
}
