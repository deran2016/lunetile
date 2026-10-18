#pragma once
#include <windows.h>
#include <mmreg.h>
#include <cstdint>
#include <string>
#include <vector>

struct MidiEvent {
    uint64_t microseconds=0;
    DWORD message=0;
    std::vector<unsigned char> sysex;
};
struct AudioData {
    WAVEFORMATEX format{};
    std::vector<unsigned char> pcm;
    std::vector<MidiEvent> midi;
    uint64_t duration_us=0,midi_segment_us=0;
    UINT32 loop_start=0,loop_length=0;
    bool is_midi=false;
    bool ignore_pitch=false;
    std::string decoder;
};
AudioData decode_audio(const std::vector<unsigned char>& bytes);
void init_audio();
void audio_shutdown();
