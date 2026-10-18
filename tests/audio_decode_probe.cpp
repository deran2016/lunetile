#include "audio.h"
#include <array>
#include <cstdio>
#include <stdexcept>

void vlq(std::vector<unsigned char>& bytes,unsigned value){std::array<unsigned char,4> parts{};unsigned count=0;parts[count++]=value&127;while((value>>=7)!=0)parts[count++]=128|(value&127);while(count)bytes.push_back(parts[--count]);}
std::vector<unsigned char> song(unsigned hold,unsigned tempo,unsigned beats){
    std::vector<unsigned char> track={0,255,81,3,static_cast<unsigned char>(tempo>>16),static_cast<unsigned char>(tempo>>8),static_cast<unsigned char>(tempo),0,255,88,4,static_cast<unsigned char>(beats),2,24,8,0,192,19,0,144,71,96};
    vlq(track,hold);track.insert(track.end(),{128,71,0});vlq(track,192);track.insert(track.end(),{255,47,0});
    std::vector<unsigned char> bytes={'M','T','h','d',0,0,0,6,0,0,0,1,1,224,'M','T','r','k',0,0,0,static_cast<unsigned char>(track.size())};bytes.insert(bytes.end(),track.begin(),track.end());return bytes;
}
int main(){
    try {
        struct Case {unsigned hold,tempo,beats;uint64_t end,segment;};
        // Segment lengths measured from the original Windows importer: 3072,6144,2304,3072 music ticks.
        for(const auto& test:std::array<Case,4>{{{576,500000,4,800000,2000000},{2016,500000,4,2300000,4000000},{576,500000,3,800000,1500000},{576,666667,4,1066667,2666668}}}){
            auto data=decode_audio(song(test.hold,test.tempo,test.beats));
            if(!data.is_midi||data.duration_us!=test.end||data.midi_segment_us!=test.segment)throw std::runtime_error("MIDI EOT/whole-measure duration mismatch");
        }
        bool rejected=false;try{decode_audio(song(576,500000,0));}catch(const std::runtime_error&){rejected=true;}
        if(!rejected)throw std::runtime_error("Zero-beat MIDI meter accepted");
        std::puts("MIDI file end, four original segment-length oracles and invalid meter rejection: PASS");return 0;
    }catch(const std::exception& error){std::fprintf(stderr,"%s\n",error.what());return 1;}
}
