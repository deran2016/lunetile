#pragma once

namespace rgss_render {
struct Constants { float position[4], source[4], transform[4], origin[4], color[4], tone[4], extra[4], resolution[4] = {640,480,0,0}; };
inline constexpr char shader[]=R"HLSL(
cbuffer State:register(b0){float4 position;float4 source;float4 transform;float4 origin;float4 color;float4 tone;float4 extra;float4 resolution;};
Texture2D image:register(t0);Texture2D old_image:register(t1);Texture2D mask_image:register(t2);SamplerState nearest:register(s0);
struct Vertex{float4 position:SV_POSITION;float2 uv:TEXCOORD0;float2 local:TEXCOORD1;};
// Convert only the final SDR image; RGSS blending and transitions remain in their original encoded space.
// Final passes use color.x for SDR white scale; extra.y remains the vertex mirror flag.
float4 output_color(float4 value){float3 low=value.rgb/12.92;float3 high=pow((value.rgb+0.055)/1.055,2.4);return float4(lerp(high,low,step(value.rgb,0.04045))*color.x,value.a);}
Vertex vs(uint id:SV_VertexID){
 float2 corners[6]={float2(0,0),float2(1,0),float2(0,1),float2(0,1),float2(1,0),float2(1,1)};
 float2 base=corners[id];float2 local=(base*position.zw-origin.xy)*transform.xy;
 float2 rotated=float2(local.x*transform.z-local.y*transform.w,local.x*transform.w+local.y*transform.z);
 Vertex v;v.position=float4((position.x+rotated.x)*2/resolution.x-1,1-(position.y+rotated.y)*2/resolution.y,0,1);
 v.uv=source.xy+float2(extra.y>0?1-base.x:base.x,base.y)*source.zw;v.local=base*position.zw;return v;
}
float4 ps(Vertex v):SV_TARGET{
 if(extra.x==3)return color;
 float4 value=image.Sample(nearest,v.uv);
 if(extra.x==4)return output_color(value);
 if(extra.x==2){float p=extra.z;if(extra.w>=0){float m=mask_image.Sample(nearest,v.uv).r;p=saturate((p*(1+extra.w)-m)/max(extra.w,0.0001));}return output_color(lerp(old_image.Sample(nearest,v.uv),value,p));}
 if(extra.x==1&&value.a>0)value.rgb/=value.a;
 float gray=dot(value.rgb,float3(0.299,0.587,0.114));
 value.rgb=saturate(lerp(value.rgb,gray.xxx,tone.w)+tone.xyz);
 value.rgb=lerp(value.rgb,color.rgb,color.a);value.a*=origin.z;
 if(origin.w>0&&v.local.y>=position.w-origin.w)value.a*=0.5;
 return value;
})HLSL";
}
