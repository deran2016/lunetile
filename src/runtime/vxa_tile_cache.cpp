#include <array>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <cstring>
#include <climits>
#include <cmath>
#include <utility>
#include "graphics.h"
#include "table_data.h"
#include "vxa_tile_cache.h"

namespace {
constexpr size_t memory_limit=32*1024*1024;
struct Part { int dx,dy,sx,sy,w,h; };
struct Shape { int sheet=0,count=0; int64_t phase=-1; Part parts[8]{}; };
struct Piece { int sheet,layer; Part part; };
struct Cell {
    int64_t wx=INT64_MIN,wy=INT64_MIN;
    int mx=0,my=0,ids[4]{},flags[3]{},edge=0,count=0;
    bool animated=false;
    Piece pieces[30]{};
};
int mod(int64_t value,int size){int result=static_cast<int>(value%size);return result<0?result+size:result;}
int flag(const TableData* table,int id){return table&&id>=0&&static_cast<size_t>(id)<table->count?table->cells[id]:0;}
bool valid_id(int id){return id>0&&id<8192;}
bool animated(int id){return id>=2048&&id<2816;}
int key(int id,int flags){return id+(id>=2816&&id<4352&&(flags&128)?8192:0);}

struct Cache {
    std::array<int,16384> index;
    std::array<bool,16384> requested{};
    std::vector<Shape> shapes;
    std::vector<Cell> cells;
    std::vector<int> pending,missing;
    uint64_t map_id=0,map_revision=0,flags_id=0,flags_revision=0,reads=0,builds=0;
    int columns=0,rows=0,levels=0;
    int64_t first_x=0,first_y=0,phase=-1;
    size_t counts[2][10]{};
    bool ready=false,disposed=false;
    Cache(){index.fill(-1);}
    size_t bytes()const{return sizeof(*this)+shapes.capacity()*sizeof(Shape)+cells.capacity()*sizeof(Cell)+(pending.capacity()+missing.capacity())*sizeof(int);}
    template<class T> void reserve(std::vector<T>& items,size_t count){
        if(count<=items.capacity())return;
        if(count>memory_limit/sizeof(T)||bytes()+(count-items.capacity())*sizeof(T)>memory_limit)throw std::length_error("Tile cache exceeds 32 MiB");
        items.reserve(count);
        if(bytes()>memory_limit)throw std::length_error("Tile cache exceeds 32 MiB");
    }
    Cell& at(int64_t x,int64_t y){return cells[mod(y,rows)*columns+mod(x,columns)];}
    void need(int id,int flags=0){
        if(!valid_id(id))return;
        int k=key(id,flags),n=index[k];
        if(n>=0&&(!animated(id)||shapes[n].phase==phase))return;
        if(!requested[k]){requested[k]=true;missing.push_back(k);}
    }
    void read_cell(Cell& cell,const TableData* map,const TableData* flags,int64_t x,int64_t y){
        cell.wx=x;cell.wy=y;cell.mx=mod(x,map->x);cell.my=mod(y,map->y);
        cell.animated=false;cell.edge=0;
        for(int z=0;z<4;++z)cell.ids[z]=z<map->z?map->cells[(static_cast<size_t>(z)*map->y+cell.my)*map->x+cell.mx]:0;
        for(int z=0;z<3;++z){cell.flags[z]=flag(flags,cell.ids[z]);cell.animated|=z<levels&&animated(cell.ids[z]);}
        if(levels>1&&flags){
            int above=map->cells[(static_cast<size_t>(map->y)+mod(cell.my-1,map->y))*map->x+cell.mx];
            bool current=cell.ids[1]>=2816&&cell.ids[1]<4352&&(cell.flags[1]&128);
            if(above>=2816&&above<4352&&(flag(flags,above)&128)&&!current&&cell.ids[0]<4352)cell.edge=above;
        }
        ++reads;
    }
    void prepare(const TableData* map,const TableData* flags,int64_t x,int64_t y,int cols,int lines,int64_t animation){
        if(disposed)throw std::invalid_argument("Disposed tile cache");
        if(!map||map->dimensions!=3||map->x<=0||map->y<=0||map->z<1||(flags&&flags->dimensions!=1))
            throw std::invalid_argument("Unsupported tile tables");
        if(cols<=0||lines<=0||static_cast<uint64_t>(cols)*lines>memory_limit/sizeof(Cell))
            throw std::length_error("Tile cache exceeds 32 MiB");
        bool full=!ready||map_id!=map->identity||flags_id!=(flags?flags->identity:0)||
            flags_revision!=(flags?flags->revision:0)||columns!=cols||rows!=lines;
        if(map_revision>map->revision||map->revision-map_revision>64)full=true;
        if(!full)for(uint64_t r=map_revision+1;r<=map->revision;++r){
            const auto& change=map->history[r%64];
            if(change.revision!=r||change.all){full=true;break;}
        }
        bool moved=first_x!=x||first_y!=y;
        bool animation_changed=phase!=animation;
        bool changed=map_revision!=map->revision;
        for(int k:missing)requested[k]=false;
        missing.clear();pending.clear();
        if(!full&&!moved&&!animation_changed&&!changed)return;
        ready=false;
        size_t count=static_cast<size_t>(cols)*lines;
        reserve(cells,count);reserve(pending,count);reserve(missing,16384);
        cells.resize(count);
        columns=cols;rows=lines;levels=std::min(map->z,3);first_x=x;first_y=y;phase=animation;
        for(int j=0;j<rows;++j)for(int i=0;i<columns;++i){
            int64_t wx=x+i,wy=y+j;Cell& cell=at(wx,wy);
            bool reload=full||cell.wx!=wx||cell.wy!=wy;
            if(!reload&&changed){
                for(uint64_t r=map_revision+1;r<=map->revision;++r){
                    const auto& change=map->history[r%64];
                    if(change.x==cell.mx&&(change.y==cell.my||(change.z==1&&mod(change.y+1,map->y)==cell.my))){reload=true;break;}
                }
            }
            if(reload)read_cell(cell,map,flags,wx,wy);
            if(reload||(animation_changed&&cell.animated)){
                int n=static_cast<int>(&cell-cells.data());pending.push_back(n);
                for(int z=0;z<levels;++z)need(cell.ids[z],cell.flags[z]);
                need(cell.edge);
            }
        }
        map_id=map->identity;map_revision=map->revision;flags_id=flags?flags->identity:0;flags_revision=flags?flags->revision:0;
    }
    void define(int k,const Shape& shape){
        int n=index[k];
        if(n<0){if(shapes.size()==shapes.capacity())reserve(shapes,std::max<size_t>(16,shapes.size()*2));n=static_cast<int>(shapes.size());shapes.push_back(shape);index[k]=n;}
        else shapes[n]=shape;
    }
    const Shape& shape(int id,int flags=0)const{
        int n=index[key(id,flags)];
        if(n<0||(animated(id)&&shapes[n].phase!=phase))throw std::invalid_argument("Missing tile shape");
        return shapes[n];
    }
    void push(Cell& cell,int sheet,int layer,const Part& part){
        if(cell.count>=30)throw std::length_error("Too many cell pieces");
        cell.pieces[cell.count++]={sheet,layer,part};
    }
    void commit(){
        if(disposed)throw std::invalid_argument("Disposed tile cache");
        if(ready)return;
        for(int k:missing){int n=index[k];if(n<0||(animated(k%8192)&&shapes[n].phase!=phase))throw std::invalid_argument("Missing tile shape");}
        for(int n:pending){
            Cell& cell=cells[n];cell.count=0;
            for(int z=0;z<levels;++z){
                int id=cell.ids[z];
                if(valid_id(id)){const auto& s=shape(id,cell.flags[z]);for(int q=0;q<s.count;++q)push(cell,s.sheet,(cell.flags[z]&16)?1:0,s.parts[q]);}
                if(z==1){
                    if(cell.edge){
                        const auto& s=shape(cell.edge);
                        if(s.count!=4)throw std::invalid_argument("Invalid table edge shape");
                        for(int q=2;q<4;++q){Part p=s.parts[q];p.dy=0;p.sy+=8;p.h=8;push(cell,1,0,p);}
                    }
                    for(int q=0;q<4;++q)if(cell.ids[3]&(1<<q))push(cell,9,0,{q%2*16,q/2*16,0,0,16,16});
                }
            }
            ++builds;
        }
        memset(counts,0,sizeof(counts));
        for(const auto& cell:cells)for(int q=0;q<cell.count;++q)++counts[cell.pieces[q].layer][cell.pieces[q].sheet];
        ready=true;
    }
    void release(){std::vector<Shape>().swap(shapes);std::vector<Cell>().swap(cells);std::vector<int>().swap(pending);std::vector<int>().swap(missing);ready=false;disposed=true;}
};
void free_cache(void* value){if(!value)return;auto* c=static_cast<Cache*>(value);rb_gc_adjust_memory_usage(-static_cast<ssize_t>(c->bytes()));delete c;}
size_t cache_size(const void* value){return value?static_cast<const Cache*>(value)->bytes():0;}
const rb_data_type_t cache_type={"LunetileVXA::TileCache",{nullptr,free_cache,cache_size},nullptr,nullptr,RUBY_TYPED_FREE_IMMEDIATELY};
Cache* cache(VALUE object){Cache* c;TypedData_Get_Struct(object,Cache,&cache_type,c);return c;}
void account(Cache* c,size_t before){rb_gc_adjust_memory_usage(static_cast<ssize_t>(c->bytes())-static_cast<ssize_t>(before));}
VALUE allocate(VALUE klass){
    VALUE result=TypedData_Wrap_Struct(klass,&cache_type,nullptr);
    Cache* c=nullptr;try{c=new Cache;}catch(const std::bad_alloc&){rb_memerror();}
    RTYPEDDATA_DATA(result)=c;rb_gc_adjust_memory_usage(c->bytes());return result;
}
VALUE prepare(VALUE self,VALUE map,VALUE flags,VALUE x,VALUE y,VALUE cols,VALUE rows,VALUE phase){
    const auto* m=vxa_table_view(map);const auto* f=NIL_P(flags)?nullptr:vxa_table_view(flags);
    if(!m||(!NIL_P(flags)&&!f))rb_raise(rb_eTypeError,"Tile cache requires native Table objects");
    if(m->dimensions!=3||m->x<=0||m->y<=0||m->z<1||(f&&f->dimensions!=1))return Qfalse;
    int64_t wx=NUM2LL(x),wy=NUM2LL(y),animation=NUM2LL(phase);
    int width=NUM2INT(cols),height=NUM2INT(rows);
    if(wx<INT_MIN||wx>INT_MAX||wy<INT_MIN||wy>INT_MAX)rb_raise(rb_eRangeError,"Tile origin out of range");
    auto* c=cache(self);size_t before=c->bytes();char error[192]{};
    try{c->prepare(m,f,wx,wy,width,height,animation);}catch(const std::exception& e){strncpy_s(error,e.what(),_TRUNCATE);}
    account(c,before);if(*error)rb_raise(rb_eArgError,"%s",error);
    VALUE keys=rb_ary_new_capa(static_cast<long>(c->missing.size()));
    for(int key:c->missing)rb_ary_push(keys,INT2NUM(key));
    return keys;
}
VALUE define_shape(VALUE self,VALUE key_value,VALUE sheet_value,VALUE parts){
    int k=NUM2INT(key_value),sheet=NUM2INT(sheet_value);
    Check_Type(parts,T_ARRAY);
    if(k<=0||k>=16384||sheet<0||sheet>8||RARRAY_LEN(parts)>8)rb_raise(rb_eArgError,"Invalid tile shape");
    auto* c=cache(self);if(c->disposed)rb_raise(rb_eArgError,"Disposed tile cache");
    Shape s;s.sheet=sheet;s.count=static_cast<int>(RARRAY_LEN(parts));s.phase=animated(k%8192)?c->phase:-1;
    for(int i=0;i<s.count;++i){
        VALUE p=rb_ary_entry(parts,i);Check_Type(p,T_ARRAY);if(RARRAY_LEN(p)!=6)rb_raise(rb_eArgError,"Invalid tile quarter");
        auto& d=s.parts[i];d={NUM2INT(rb_ary_entry(p,0)),NUM2INT(rb_ary_entry(p,1)),NUM2INT(rb_ary_entry(p,2)),NUM2INT(rb_ary_entry(p,3)),NUM2INT(rb_ary_entry(p,4)),NUM2INT(rb_ary_entry(p,5))};
        if(d.dx<0||d.dx>16||d.dy<0||d.dy>24||d.sx<0||d.sx>16384||d.sy<0||d.sy>16384||d.w<1||d.w>32||d.h<1||d.h>32)
            rb_raise(rb_eArgError,"Tile quarter out of range");
    }
    size_t before=c->bytes();char error[192]{};
    try{c->define(k,s);}catch(const std::exception& e){strncpy_s(error,e.what(),_TRUNCATE);}
    account(c,before);if(*error)rb_raise(rb_eArgError,"%s",error);return Qnil;
}
VALUE commit(VALUE self){char error[192]{};try{cache(self)->commit();}catch(const std::exception& e){strncpy_s(error,e.what(),_TRUNCATE);}if(*error)rb_raise(rb_eArgError,"%s",error);return Qnil;}
VALUE dispose(VALUE self){auto* c=cache(self);size_t before=c->bytes();c->release();account(c,before);return Qnil;}
VALUE stats(VALUE self){auto* c=cache(self);return rb_ary_new_from_args(5,ULL2NUM(c->reads),ULL2NUM(c->builds),SIZET2NUM(c->bytes()),SIZET2NUM(c->cells.size()),SIZET2NUM(c->shapes.size()));}
struct Batch { Cache* c; int layer; Canvas* images[10]{}; VALUE objects; double x,y; };
Batch batch(VALUE command){
    Check_Type(command,T_ARRAY);if(RARRAY_LEN(command)!=6)rb_raise(rb_eArgError,"Invalid tile batch command");
    VALUE layer=rb_ary_entry(command,2),x=rb_ary_entry(command,4),y=rb_ary_entry(command,5);
    if(!RB_INTEGER_TYPE_P(layer)||(!RB_INTEGER_TYPE_P(x)&&!RB_FLOAT_TYPE_P(x))||(!RB_INTEGER_TYPE_P(y)&&!RB_FLOAT_TYPE_P(y)))
        rb_raise(rb_eTypeError,"Tile batch metadata must be numeric primitives");
    Batch b{};b.c=cache(rb_ary_entry(command,1));b.layer=NUM2INT(rb_ary_entry(command,2));b.objects=rb_ary_entry(command,3);
    Check_Type(b.objects,T_ARRAY);
    if(!b.c->ready||b.c->disposed||b.layer<0||b.layer>1||RARRAY_LEN(b.objects)!=10)rb_raise(rb_eArgError,"Invalid tile batch state");
    b.x=NUM2DBL(x);b.y=NUM2DBL(y);
    if(!std::isfinite(b.x)||!std::isfinite(b.y)||std::abs(b.x)>static_cast<double>(INT64_MAX)||std::abs(b.y)>static_cast<double>(INT64_MAX))
        rb_raise(rb_eArgError,"Invalid tile batch origin");
    for(int i=0;i<10;++i)b.images[i]=canvas_optional(rb_ary_entry(b.objects,i));
    return b;
}
void ruby_emit(void* target,Canvas*,double x,double y,int sx,int sy,int w,int h){
    auto* state=static_cast<std::pair<VALUE,VALUE>*>(target);
    VALUE values[22]={INT2FIX(0),state->second,DBL2NUM(x),DBL2NUM(y),INT2NUM(w),INT2NUM(h),INT2NUM(sx),INT2NUM(sy),INT2NUM(w),INT2NUM(h),
        INT2FIX(1),INT2FIX(1),INT2FIX(0),INT2FIX(0),INT2FIX(0),INT2FIX(255),INT2FIX(0),Qnil,Qnil,INT2FIX(0),Qnil,Qfalse};
    rb_ary_push(state->first,rb_ary_new_from_values(22,values));
}
VALUE inspect_batch(VALUE,VALUE command){
    size_t count=vxa_batch_count(command);
    if(count>100000)rb_raise(rb_eArgError,"Too many rendering commands");
    struct Entry { int sheet; double x,y; Part part; };
    VALUE storage=rb_str_new(nullptr,static_cast<long>(count*sizeof(Entry)));
    auto* entries=reinterpret_cast<Entry*>(RSTRING_PTR(storage));
    auto b=batch(command);size_t used=0;
    for(int j=0;j<b.c->rows;++j)for(int i=0;i<b.c->columns;++i){
        const auto& cell=b.c->at(b.c->first_x+i,b.c->first_y+j);
        for(int q=0;q<cell.count;++q){const auto& d=cell.pieces[q];if(d.layer!=b.layer||!b.images[d.sheet])continue;
            if(used>=count)rb_raise(rb_eArgError,"Tile batch changed while inspecting");
            entries[used++]={d.sheet,cell.wx*32+b.x+d.part.dx,cell.wy*32+b.y+d.part.dy,d.part};
        }
    }
    std::pair<VALUE,VALUE> state{rb_ary_new(),Qnil};
    for(size_t i=0;i<used;++i){
        const auto& d=entries[i];state.second=rb_ary_entry(b.objects,d.sheet);
        ruby_emit(&state,nullptr,d.x,d.y,d.part.sx,d.part.sy,d.part.w,d.part.h);
    }
    RB_GC_GUARD(storage);RB_GC_GUARD(command);
    return state.first;
}
}
size_t vxa_batch_count(VALUE command){auto b=batch(command);size_t count=0;for(int i=0;i<10;++i)if(b.images[i])count+=b.c->counts[b.layer][i];return count;}
void vxa_batch_expand(VALUE command,void* target,TileEmit emit){
    auto b=batch(command);
    for(int j=0;j<b.c->rows;++j)for(int i=0;i<b.c->columns;++i){
        const auto& cell=b.c->at(b.c->first_x+i,b.c->first_y+j);
        for(int q=0;q<cell.count;++q){const auto& d=cell.pieces[q];if(d.layer!=b.layer||!b.images[d.sheet])continue;
            emit(target,b.images[d.sheet],cell.wx*32+b.x+d.part.dx,cell.wy*32+b.y+d.part.dy,d.part.sx,d.part.sy,d.part.w,d.part.h);
        }
    }
}
void init_vxa_tile_cache(){
    VALUE module=rb_define_module("RGSSXP"),klass=rb_define_class_under(module,"TileCache",rb_cObject);
    rb_define_alloc_func(klass,allocate);
    rb_define_method(klass,"prepare",RUBY_METHOD_FUNC(prepare),7);
    rb_define_method(klass,"shape",RUBY_METHOD_FUNC(define_shape),3);
    rb_define_method(klass,"commit",RUBY_METHOD_FUNC(commit),0);
    rb_define_method(klass,"dispose",RUBY_METHOD_FUNC(dispose),0);
    rb_define_method(klass,"stats",RUBY_METHOD_FUNC(stats),0);
    rb_define_singleton_method(module,"__expand_tile_batch",RUBY_METHOD_FUNC(inspect_batch),1);
}
