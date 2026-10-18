#include <windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <shlwapi.h>
#include <wrl/client.h>
#include <vorbis/vorbisfile.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include "audio.h"

namespace {
constexpr size_t limit=128*1024*1024;
uint16_t le16(const unsigned char* p){return p[0]|p[1]<<8;}
uint32_t le32(const unsigned char* p){return p[0]|p[1]<<8|p[2]<<16|static_cast<uint32_t>(p[3])<<24;}
uint32_t be32(const unsigned char* p){return static_cast<uint32_t>(p[0])<<24|p[1]<<16|p[2]<<8|p[3];}
void require(bool yes,const char* error){if(!yes)throw std::runtime_error(error);}
void checked(HRESULT hr,const char* error){if(FAILED(hr))throw std::runtime_error(std::string(error)+" (HRESULT "+std::to_string(static_cast<unsigned long>(hr))+")");}
void shape(AudioData& result,unsigned channels,unsigned rate){
    require(channels>=1&&channels<=8&&rate>=8000&&rate<=192000,"Unsupported audio channel count or sample rate");
    result.format.wFormatTag=WAVE_FORMAT_PCM;result.format.nChannels=static_cast<WORD>(channels);
    result.format.nSamplesPerSec=rate;result.format.wBitsPerSample=16;
    result.format.nBlockAlign=static_cast<WORD>(channels*2);result.format.nAvgBytesPerSec=rate*channels*2;
}
void append(AudioData& result,const unsigned char* bytes,size_t count){require(count<=limit-result.pcm.size(),"Decoded audio exceeds 128 MiB");result.pcm.insert(result.pcm.end(),bytes,bytes+count);}
AudioData wave(const std::vector<unsigned char>& bytes){
    require(bytes.size()>=12&&memcmp(bytes.data()+8,"WAVE",4)==0,"Invalid RIFF WAVE header");
    size_t end=static_cast<size_t>(le32(bytes.data()+4))+8;require(end<=bytes.size()&&end>=12,"Truncated RIFF WAVE");
    const unsigned char *format=nullptr,*samples=nullptr,*sampler=nullptr;size_t fmt_size=0,count=0,smpl_size=0;
    for(size_t pos=12;pos<end;){
        require(end-pos>=8,"Truncated WAVE chunk header");auto* chunk=bytes.data()+pos;size_t size=le32(chunk+4);pos+=8;
        require(size<=end-pos,"WAVE chunk exceeds RIFF bounds");
        if(!memcmp(chunk,"fmt ",4)){format=bytes.data()+pos;fmt_size=size;}
        if(!memcmp(chunk,"data",4)){samples=bytes.data()+pos;count=size;}
        if(!memcmp(chunk,"smpl",4)){sampler=bytes.data()+pos;smpl_size=size;}
        pos+=size;if(size&1){require(pos<end,"Missing WAVE padding");++pos;}
    }
    require(format&&fmt_size>=16&&samples,"WAVE requires fmt and data chunks");
    unsigned tag=le16(format),channels=le16(format+2),rate=le32(format+4),block=le16(format+12),bits=le16(format+14);
    if(tag==WAVE_FORMAT_EXTENSIBLE){require(fmt_size>=40&&le16(format+16)>=22,"Truncated extensible WAVE");tag=le16(format+24);}
    require((tag==WAVE_FORMAT_PCM&&(bits==8||bits==16||bits==24||bits==32))||(tag==WAVE_FORMAT_IEEE_FLOAT&&bits==32),"Only PCM/float WAVE is supported");
    require(block==channels*(bits/8)&&block&&count%block==0,"Invalid WAVE block alignment");
    AudioData result;shape(result,channels,rate);result.decoder="wav";
    size_t values=count/(bits/8);require(values<=limit/2,"Decoded WAVE exceeds 128 MiB");result.pcm.resize(values*2);
    for(size_t i=0;i<values;++i){
        auto* p=samples+i*(bits/8);int value=0;
        if(tag==WAVE_FORMAT_IEEE_FLOAT){float f;memcpy(&f,p,4);require(std::isfinite(f),"Non-finite WAVE sample");value=static_cast<int>(std::clamp(f,-1.0f,1.0f)*32767);}
        else if(bits==8)value=(static_cast<int>(*p)-128)*256;
        else if(bits==16)value=static_cast<int16_t>(le16(p));
        else if(bits==24)value=static_cast<int16_t>(le16(p+1));
        else value=static_cast<int16_t>(le16(p+2));
        result.pcm[i*2]=static_cast<unsigned char>(value);result.pcm[i*2+1]=static_cast<unsigned char>(value>>8);
    }
    if(sampler&&smpl_size>=60&&le32(sampler+28)>0){
        require(le32(sampler+40)==0,"Unsupported WAVE ping-pong/reverse loop");
        result.loop_start=le32(sampler+44);uint64_t stop=static_cast<uint64_t>(le32(sampler+48))+1;
        require(stop>result.loop_start&&stop<=count/block,"Invalid WAVE loop bounds");result.loop_length=static_cast<UINT32>(stop-result.loop_start);
    }
    return result;
}
struct Memory {const std::vector<unsigned char>& bytes;size_t pos=0;};
size_t read_ogg(void* target,size_t unit,size_t count,void* source){auto& m=*static_cast<Memory*>(source);if(!unit)return 0;size_t items=std::min(count,(m.bytes.size()-m.pos)/unit);memcpy(target,m.bytes.data()+m.pos,items*unit);m.pos+=items*unit;return items;}
int seek_ogg(void* source,ogg_int64_t offset,int origin){auto& m=*static_cast<Memory*>(source);int64_t base=origin==SEEK_SET?0:origin==SEEK_CUR?static_cast<int64_t>(m.pos):origin==SEEK_END?static_cast<int64_t>(m.bytes.size()):-1;if(base<0||offset< -base||offset>static_cast<int64_t>(m.bytes.size())-base)return -1;m.pos=static_cast<size_t>(base+offset);return 0;}
long tell_ogg(void* source){return static_cast<long>(static_cast<Memory*>(source)->pos);}
AudioData ogg(const std::vector<unsigned char>& bytes){
    Memory memory{bytes};OggVorbis_File file{};require(ov_open_callbacks(&memory,&file,nullptr,0,{read_ogg,seek_ogg,nullptr,tell_ogg})==0,"Invalid Ogg Vorbis stream");
    struct Close {OggVorbis_File* p;~Close(){ov_clear(p);}} close{&file};
    auto* info=ov_info(&file,0);require(info!=nullptr,"Missing Vorbis information");AudioData result;shape(result,info->channels,info->rate);result.decoder="vorbis";
    char buffer[16384];int stream=0;long count=0;
    while((count=ov_read(&file,buffer,sizeof(buffer),0,2,1,&stream))!=0){
        require(count>0,"Corrupt Vorbis packet");auto* current=ov_info(&file,stream);
        require(current&&current->channels==result.format.nChannels&&current->rate==result.format.nSamplesPerSec,"Chained Vorbis changes format");
        append(result,reinterpret_cast<unsigned char*>(buffer),count);
    }
    auto* comments=ov_comment(&file,0);uint64_t start=0,length=0,finish=0;bool has_start=false,has_length=false,has_end=false;
    if(comments)for(int i=0;i<comments->comments;++i){
        std::string item(comments->user_comments[i],comments->comment_lengths[i]);auto split=item.find('=');if(split==std::string::npos)continue;
        std::string key=item.substr(0,split);std::transform(key.begin(),key.end(),key.begin(),[](unsigned char c){return static_cast<char>(std::toupper(c));});
        if(key!="LOOPSTART"&&key!="LOOPLENGTH"&&key!="LOOPEND")continue;
        std::string number=item.substr(split+1);require(!number.empty()&&number.size()<=10&&number.find_first_not_of("0123456789")==std::string::npos,"Invalid Vorbis loop tag");
        uint64_t value=std::stoull(number);
        if(key=="LOOPSTART"){start=value;has_start=true;}else if(key=="LOOPLENGTH"){length=value;has_length=true;}else{finish=value;has_end=true;}
    }
    uint64_t frames=result.pcm.size()/result.format.nBlockAlign;
    if(has_start||has_length||has_end){if(!has_length)length=has_end&&finish>=start?finish-start:frames-start;require(start<frames&&length>0&&length<=frames-start,"Invalid Vorbis loop bounds");result.loop_start=static_cast<UINT32>(start);result.loop_length=static_cast<UINT32>(length);}
    return result;
}
AudioData media(const std::vector<unsigned char>& bytes){
    using Microsoft::WRL::ComPtr;
    ComPtr<IStream> stream;stream.Attach(SHCreateMemStream(bytes.data(),static_cast<UINT>(bytes.size())));require(stream!=nullptr,"Cannot allocate audio byte stream");
    ComPtr<IMFByteStream> source;checked(MFCreateMFByteStreamOnStream(stream.Get(),&source),"MF byte stream");
    ComPtr<IMFSourceReader> reader;checked(MFCreateSourceReaderFromByteStream(source.Get(),nullptr,&reader),"MF audio reader");
    checked(reader->SetStreamSelection(MF_SOURCE_READER_ALL_STREAMS,FALSE),"MF deselect streams");
    checked(reader->SetStreamSelection(MF_SOURCE_READER_FIRST_AUDIO_STREAM,TRUE),"MF audio stream");
    ComPtr<IMFMediaType> encoded;checked(reader->GetNativeMediaType(MF_SOURCE_READER_FIRST_AUDIO_STREAM,0,&encoded),"MF encoded audio type");
    GUID codec{};checked(encoded->GetGUID(MF_MT_SUBTYPE,&codec),"MF encoded audio codec");
    ComPtr<IMFMediaType> requested;checked(MFCreateMediaType(&requested),"MF media type");
    checked(requested->SetGUID(MF_MT_MAJOR_TYPE,MFMediaType_Audio),"MF audio type");checked(requested->SetGUID(MF_MT_SUBTYPE,MFAudioFormat_PCM),"MF PCM type");
    checked(requested->SetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE,16),"MF sample width");
    checked(reader->SetCurrentMediaType(MF_SOURCE_READER_FIRST_AUDIO_STREAM,nullptr,requested.Get()),"MF decoder format");
    ComPtr<IMFMediaType> actual;checked(reader->GetCurrentMediaType(MF_SOURCE_READER_FIRST_AUDIO_STREAM,&actual),"MF decoded type");
    UINT32 channels=0,rate=0,bits=0;checked(actual->GetUINT32(MF_MT_AUDIO_NUM_CHANNELS,&channels),"MF channel count");checked(actual->GetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND,&rate),"MF sample rate");checked(actual->GetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE,&bits),"MF sample size");require(bits==16,"MF decoder did not provide 16-bit PCM");
    AudioData result;shape(result,channels,rate);result.decoder="media-foundation";
    result.ignore_pitch=codec==MFAudioFormat_WMAudioV8||codec==MFAudioFormat_WMAudioV9||codec==MFAudioFormat_WMAudio_Lossless||codec==MFAudioFormat_WMASPDIF;
    for(;;){DWORD flags=0;ComPtr<IMFSample> sample;checked(reader->ReadSample(MF_SOURCE_READER_FIRST_AUDIO_STREAM,0,nullptr,&flags,nullptr,&sample),"MF decode sample");require(!(flags&MF_SOURCE_READERF_CURRENTMEDIATYPECHANGED),"Audio stream changes format");
        if(sample){ComPtr<IMFMediaBuffer> buffer;checked(sample->ConvertToContiguousBuffer(&buffer),"MF contiguous audio");BYTE* data=nullptr;DWORD count=0;checked(buffer->Lock(&data,nullptr,&count),"MF audio lock");if(count>limit-result.pcm.size()){buffer->Unlock();throw std::runtime_error("Decoded audio exceeds 128 MiB");}result.pcm.insert(result.pcm.end(),data,data+count);buffer->Unlock();}
        if(flags&MF_SOURCE_READERF_ENDOFSTREAM)break;
    }
    return result;
}
struct TickEvent {uint64_t tick;DWORD message;std::vector<unsigned char> sysex;unsigned tempo=0,beats=0,denominator=2;};
AudioData midi(const std::vector<unsigned char>& bytes){
    require(bytes.size()>=14&&be32(bytes.data()+4)>=6&&be32(bytes.data()+4)<=bytes.size()-8,"Invalid MIDI header");
    unsigned format=(bytes[8]<<8)|bytes[9],tracks=(bytes[10]<<8)|bytes[11],division=(bytes[12]<<8)|bytes[13];
    require(format<=1&&tracks>0&&tracks<=256&&(format!=0||tracks==1)&&division&&!(division&0x8000),"MIDI requires SMF 0/1 with PPQ time division");
    size_t pos=8+be32(bytes.data()+4);std::vector<TickEvent> events;
    for(unsigned track=0;track<tracks;++track){require(bytes.size()-pos>=8&&!memcmp(bytes.data()+pos,"MTrk",4),"Missing MIDI track");size_t length=be32(bytes.data()+pos+4);pos+=8;require(length<=bytes.size()-pos,"Truncated MIDI track");size_t end=pos+length;uint64_t tick=0;unsigned running=0;
        auto byte=[&](){require(pos<end,"Truncated MIDI event");return static_cast<unsigned>(bytes[pos++]);};
        auto vlq=[&](){uint32_t value=0;for(int i=0;i<4;++i){unsigned part=byte();value=(value<<7)|(part&127);if(!(part&128))return value;}throw std::runtime_error("MIDI variable-length integer exceeds four bytes");};
        while(pos<end){tick+=vlq();require(tick<=0xffffffffull,"MIDI timeline exceeds supported range");unsigned status=byte();if(status<128){require(running>=128,"MIDI running status is missing");--pos;status=running;}
            require(events.size()<1000000,"MIDI exceeds one million events");
            if(status==255){running=0;unsigned type=byte();size_t size=vlq();require(size<=end-pos,"Truncated MIDI meta event");if(type==81){require(size==3,"Invalid MIDI tempo event");unsigned tempo=bytes[pos]<<16|bytes[pos+1]<<8|bytes[pos+2];require(tempo>0,"Zero MIDI tempo");events.push_back({tick,0,{},tempo});}if(type==88){require(size==4&&bytes[pos]>0&&bytes[pos+1]<=7,"Invalid MIDI time signature");events.push_back({tick,0,{},0,bytes[pos],bytes[pos+1]});}if(type==47)events.push_back({tick,0,{},0});pos+=size;}
            else if(status==240||status==247){running=0;size_t size=vlq();require(size<=end-pos&&size<=65536,"Invalid MIDI SysEx length");std::vector<unsigned char> packet;if(status==240)packet.push_back(240);packet.insert(packet.end(),bytes.begin()+pos,bytes.begin()+pos+size);events.push_back({tick,0,std::move(packet),0});pos+=size;}
            else{require(status>=128&&status<240,"Unsupported MIDI system event");running=status;unsigned first=byte();require(first<128,"Invalid MIDI channel data");unsigned second=0;if((status&240)!=192&&(status&240)!=208){second=byte();require(second<128,"Invalid MIDI channel data");}events.push_back({tick,status|(first<<8)|(second<<16),{},0});}
        }
    }
    std::stable_sort(events.begin(),events.end(),[](const auto& a,const auto& b){return a.tick<b.tick;});
    AudioData result;result.is_midi=true;result.decoder="windows-midi-port";uint64_t tick=0,microseconds=0,remainder=0,meter_origin=0;unsigned tempo=500000,beats=4,denominator=2;
    for(auto& event:events){uint64_t delta=(event.tick-tick)*tempo+remainder;microseconds+=delta/division;remainder=delta%division;tick=event.tick;require(microseconds<=24ull*60*60*1000000,"MIDI exceeds 24 hours");if(event.tempo)tempo=event.tempo;else if(event.beats){meter_origin=tick;beats=event.beats;denominator=event.denominator;}else if(event.message||!event.sysex.empty())result.midi.push_back({microseconds,event.message,std::move(event.sysex)});}
    result.duration_us=microseconds;require(result.duration_us>0&&!result.midi.empty(),"Empty MIDI song");
    // Windows imports one-shot SMF segments through the final whole measure; BGM loops retain the file end.
    uint64_t unit=1ull<<denominator,measure=static_cast<uint64_t>(division)*4*beats;
    uint64_t measures=std::max<uint64_t>(1,((tick-meter_origin)*unit+measure-1)/measure);
    uint64_t segment_tick=meter_origin+(measures*measure+unit-1)/unit;
    result.midi_segment_us=microseconds+((segment_tick-tick)*tempo+remainder)/division;
    require(result.midi_segment_us<=24ull*60*60*1000000,"MIDI segment exceeds 24 hours");return result;
}
}
AudioData decode_audio(const std::vector<unsigned char>& bytes){
    require(bytes.size()>=4&&bytes.size()<=limit,"Encoded audio must be 4 bytes..128 MiB");AudioData result;
    if(!memcmp(bytes.data(),"RIFF",4))result=wave(bytes);
    else if(!memcmp(bytes.data(),"OggS",4))result=ogg(bytes);
    else if(!memcmp(bytes.data(),"MThd",4))return midi(bytes);
    else result=media(bytes);
    require(!result.pcm.empty()&&result.pcm.size()%result.format.nBlockAlign==0,"Empty or unaligned audio samples");
    result.duration_us=result.pcm.size()/result.format.nBlockAlign*1000000ull/result.format.nSamplesPerSec;return result;
}
