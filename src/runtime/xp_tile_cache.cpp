#include <vector>
#include <array>
#include <algorithm>
#include <stdexcept>
#include <cstring>
#include <cmath>
#include <climits>
#include "graphics.h"
#include "table_data.h"
#include "xp_tile_cache.h"

namespace {
constexpr size_t limit=32*1024*1024;
struct Part {int dx,dy,sx,sy,w,h;};
struct Shape {int sheet=0,count=0;int64_t phase=-1;Part parts[4]{};};
struct Cell {int64_t wx=INT64_MIN,wy=INT64_MIN;int mx=0,my=0,ids[3]{},priority[3]{},flash=0;};
struct Entry {int cell,level;};
struct Group {int64_t depth;std::vector<Entry> entries;};
int mod(int64_t value,int size){int n=static_cast<int>(value%size);return n<0?n+size:n;}
struct Cache {
    std::array<int,32768> indices;
    std::array<bool,32768> requested{};
    std::vector<Shape> shapes;
    std::vector<Cell> cells;
    std::vector<int> missing;
    std::vector<Group> groups;
    size_t group_count=0;
    uint64_t ids[3]{},revisions[3]{},reads=0,builds=0;
    int dimensions[8]{},columns=0,rows=0,levels=0;
    int64_t first_x=0,first_y=0,phase=-1;
    bool ready=false,disposed=false;
    Cache(){indices.fill(-1);}
    size_t bytes()const {
        size_t n=sizeof(*this)+shapes.capacity()*sizeof(Shape)+cells.capacity()*sizeof(Cell)+missing.capacity()*sizeof(int)+groups.capacity()*sizeof(Group);
        for(const auto& g:groups)n+=g.entries.capacity()*sizeof(Entry);
        return n;
    }
    template<class T> void reserve(std::vector<T>& v,size_t count){
        if(count<=v.capacity())return;
        if(count>limit/sizeof(T)||bytes()+(count-v.capacity())*sizeof(T)>limit)throw std::length_error("Tile cache exceeds 32 MiB");
        v.reserve(count);
        if(bytes()>limit)throw std::length_error("Tile cache exceeds 32 MiB");
    }
    Cell& at(int64_t x,int64_t y){return cells[mod(y,rows)*columns+mod(x,columns)];}
    void prepare(TableData** tables,int64_t x,int64_t y,int cols,int lines,int64_t animation,const int* sizes){
        if(disposed)throw std::invalid_argument("Disposed tile cache");
        auto* map=tables[0];
        if(cols<=0||lines<=0||static_cast<uint64_t>(cols)*lines>limit/sizeof(Cell))throw std::length_error("Tile cache exceeds 32 MiB");
        bool full=!ready||columns!=cols||rows!=lines;
        for(int t=0;t<3;++t){
            auto* table=tables[t];
            if(ids[t]!=(table?table->identity:0))full=true;
            if(table&&(revisions[t]>table->revision||table->revision-revisions[t]>64))full=true;
            if(table&&!full)for(uint64_t r=revisions[t]+1;r<=table->revision;++r){
                auto c=table->history[r%64];if(c.revision!=r||c.all||t==1){full=true;break;}
            }
        }
        bool geometry=memcmp(dimensions,sizes,sizeof(dimensions))!=0;
        bool changed=full||first_x!=x||first_y!=y;
        for(int t=0;t<3;++t)changed|=tables[t]&&revisions[t]!=tables[t]->revision;
        bool animated=phase!=animation;
        for(int id:missing)requested[id]=false;
        missing.clear();ready=false;
        reserve(cells,static_cast<size_t>(cols)*lines);cells.resize(static_cast<size_t>(cols)*lines);
        columns=cols;rows=lines;levels=map->z;first_x=x;first_y=y;phase=animation;
        if(geometry){indices.fill(-1);shapes.clear();memcpy(dimensions,sizes,sizeof(dimensions));}
        if(changed||animated||geometry)for(int j=0;j<rows;++j)for(int i=0;i<columns;++i){
            int64_t wx=x+i,wy=y+j;auto& c=at(wx,wy);
            bool reload=full||c.wx!=wx||c.wy!=wy;
            if(!reload)for(int t:{0,2})if(auto* table=tables[t]){
                for(uint64_t r=revisions[t]+1;r<=table->revision;++r){auto change=table->history[r%64];if(change.x==c.mx&&change.y==c.my){reload=true;break;}}
            }
            if(reload){
                c.wx=wx;c.wy=wy;c.mx=mod(wx,map->x);c.my=mod(wy,map->y);
                for(int z=0;z<levels;++z){
                    c.ids[z]=map->cells[(static_cast<size_t>(z)*map->y+c.my)*map->x+c.mx];
                    auto* p=tables[1];int id=c.ids[z];c.priority[z]=p&&id>=0&&static_cast<size_t>(id)<p->count?p->cells[id]:0;
                }
                auto* f=tables[2];c.flash=f&&c.mx<f->x&&c.my<f->y?f->cells[static_cast<size_t>(c.my)*f->x+c.mx]:0;
                ++reads;
            }
            for(int z=0;z<levels;++z){int id=c.ids[z];if(id<48)continue;
                int n=indices[id];if((n<0||(id<384&&shapes[n].phase!=phase))&&!requested[id]){reserve(missing,missing.size()+1);missing.push_back(id);requested[id]=true;}
            }
        }
        for(int t=0;t<3;++t){ids[t]=tables[t]?tables[t]->identity:0;revisions[t]=tables[t]?tables[t]->revision:0;}
    }
    void define(int id,const Shape& shape){
        int n=indices[id];
        if(n<0){if(shapes.size()==shapes.capacity())reserve(shapes,std::max<size_t>(16,shapes.size()*2));indices[id]=static_cast<int>(shapes.size());shapes.push_back(shape);}
        else shapes[n]=shape;
        ++builds;
    }
    void commit(){
        if(disposed)throw std::invalid_argument("Disposed tile cache");
        for(int id:missing)if(indices[id]<0||(id<384&&shapes[indices[id]].phase!=phase))throw std::invalid_argument("Missing tile shape");
        ready=true;
    }
    void push(int64_t depth,int cell,int level){
        size_t n=0;for(;n<group_count;++n)if(groups[n].depth==depth)break;
        if(n==group_count){
            if(n==groups.size()){if(groups.size()==groups.capacity())reserve(groups,std::max<size_t>(8,groups.size()*2));groups.emplace_back();}
            groups[n].depth=depth;groups[n].entries.clear();++group_count;
        }
        auto& list=groups[n].entries;
        if(list.size()==list.capacity())reserve(list,std::max<size_t>(32,list.size()*2));
        list.push_back({cell,level});
    }
    void group(int64_t oy){
        if(!ready||disposed)throw std::invalid_argument("Invalid tile cache state");
        group_count=0;
        for(int j=0;j<rows;++j)for(int i=0;i<columns;++i){
            auto& c=at(first_x+i,first_y+j);int index=static_cast<int>(&c-cells.data());
            for(int z=0;z<levels;++z)if(c.ids[z]>=48)push(c.priority[z]>0?c.wy*32-oy+(c.priority[z]+1)*32:0,index,z);
            if(c.flash)push(1000,index,3);
        }
    }
    void release(){
        std::vector<Shape>().swap(shapes);std::vector<Cell>().swap(cells);std::vector<int>().swap(missing);std::vector<Group>().swap(groups);
        group_count=0;ready=false;disposed=true;
    }
};
void free_cache(void* value){if(!value)return;auto* c=static_cast<Cache*>(value);rb_gc_adjust_memory_usage(-static_cast<ssize_t>(c->bytes()));delete c;}
size_t size(const void* value){return value?static_cast<const Cache*>(value)->bytes():0;}
const rb_data_type_t type={"Lunetile::XPTileCache",{nullptr,free_cache,size},nullptr,nullptr,RUBY_TYPED_FREE_IMMEDIATELY};
Cache* cache(VALUE v){Cache* c;TypedData_Get_Struct(v,Cache,&type,c);return c;}
void account(Cache* c,size_t before){rb_gc_adjust_memory_usage(static_cast<ssize_t>(c->bytes())-static_cast<ssize_t>(before));}
VALUE allocate(VALUE klass){VALUE result=TypedData_Wrap_Struct(klass,&type,nullptr);Cache* c=nullptr;try{c=new Cache;}catch(const std::bad_alloc&){rb_memerror();}RTYPEDDATA_DATA(result)=c;rb_gc_adjust_memory_usage(c->bytes());return result;}
VALUE prepare(VALUE self,VALUE objects,VALUE x,VALUE y,VALUE width,VALUE height,VALUE phase,VALUE images){
    Check_Type(objects,T_ARRAY);Check_Type(images,T_ARRAY);
    if(RARRAY_LEN(objects)!=3||RARRAY_LEN(images)!=8)rb_raise(rb_eArgError,"Invalid tile cache metadata");
    TableData* tables[3]{};
    for(int t=0;t<3;++t){VALUE v=rb_ary_entry(objects,t);if(t&&NIL_P(v))continue;tables[t]=native_table_view(v);if(!tables[t])rb_raise(rb_eTypeError,"Expected native Table");}
    if(tables[0]->dimensions!=3||tables[0]->z>3||tables[0]->z<1||tables[0]->x<1||tables[0]->y<1||
        (tables[1]&&tables[1]->dimensions!=1)||(tables[2]&&tables[2]->dimensions!=2))return Qfalse;
    int sizes[8]{};for(int i=1;i<8;++i){auto* image=canvas_optional(rb_ary_entry(images,i));sizes[i]=image?image->width+(image->height==32?0:65536):0;}
    int64_t wx=NUM2LL(x),wy=NUM2LL(y),animation=NUM2LL(phase);int cols=NUM2INT(width),rows=NUM2INT(height);
    if(wx<INT_MIN||wx>INT_MAX||wy<INT_MIN||wy>INT_MAX)rb_raise(rb_eRangeError,"Tile origin out of range");
    for(auto* t:tables)observe_table(t);
    auto* c=cache(self);size_t before=c->bytes();char error[192]{};
    try{c->prepare(tables,wx,wy,cols,rows,animation,sizes);}catch(const std::exception& e){strncpy_s(error,e.what(),_TRUNCATE);}
    account(c,before);if(*error)rb_raise(rb_eArgError,"%s",error);
    VALUE result=rb_ary_new_capa(static_cast<long>(c->missing.size()));for(int id:c->missing)rb_ary_push(result,INT2NUM(id));return result;
}
VALUE define(VALUE self,VALUE id_value,VALUE sheet_value,VALUE parts){
    int id=NUM2INT(id_value),sheet=NUM2INT(sheet_value);Check_Type(parts,T_ARRAY);
    if(id<48||id>=32768||sheet<0||sheet>7||RARRAY_LEN(parts)>4)rb_raise(rb_eArgError,"Invalid XP tile shape");
    auto* c=cache(self);if(c->disposed)rb_raise(rb_eArgError,"Disposed tile cache");
    Shape shape;shape.sheet=sheet;shape.phase=c->phase;shape.count=static_cast<int>(RARRAY_LEN(parts));
    for(int q=0;q<shape.count;++q){VALUE p=rb_ary_entry(parts,q);Check_Type(p,T_ARRAY);if(RARRAY_LEN(p)!=6)rb_raise(rb_eArgError,"Invalid tile quarter");
        int a[6];for(int k=0;k<6;++k)a[k]=NUM2INT(rb_ary_entry(p,k));
        if(a[0]<0||a[0]>16||a[1]<0||a[1]>16||a[2]<0||a[2]>1048576||a[3]<0||a[3]>131072||a[4]<1||a[4]>32||a[5]<1||a[5]>32)rb_raise(rb_eArgError,"Invalid tile quarter range");
        shape.parts[q]={a[0],a[1],a[2],a[3],a[4],a[5]};
    }
    size_t before=c->bytes();char error[192]{};try{c->define(id,shape);}catch(const std::exception& e){strncpy_s(error,e.what(),_TRUNCATE);}account(c,before);if(*error)rb_raise(rb_eArgError,"%s",error);return Qnil;
}
VALUE commit(VALUE self){char error[192]{};try{cache(self)->commit();}catch(const std::exception& e){strncpy_s(error,e.what(),_TRUNCATE);}if(*error)rb_raise(rb_eArgError,"%s",error);return Qnil;}
VALUE groups(VALUE self,VALUE origin){auto* c=cache(self);int64_t oy=NUM2LL(origin);size_t before=c->bytes();char error[192]{};try{c->group(oy);}catch(const std::exception& e){strncpy_s(error,e.what(),_TRUNCATE);}account(c,before);if(*error)rb_raise(rb_eArgError,"%s",error);
    VALUE list=rb_ary_new_capa(static_cast<long>(c->group_count));for(size_t i=0;i<c->group_count;++i)rb_ary_push(list,rb_ary_new_from_args(2,SIZET2NUM(i),LL2NUM(c->groups[i].depth)));return list;}
VALUE dispose(VALUE self){auto* c=cache(self);size_t before=c->bytes();c->release();account(c,before);return Qnil;}
VALUE stats(VALUE self){auto* c=cache(self);return rb_ary_new_from_args(5,ULL2NUM(c->reads),ULL2NUM(c->builds),SIZET2NUM(c->bytes()),SIZET2NUM(c->cells.size()),SIZET2NUM(c->shapes.size()));}
struct Batch {Cache* c;size_t group;Canvas* images[9]{};VALUE objects;double x,y;int opacity;};
Batch batch(VALUE command){
    Check_Type(command,T_ARRAY);if(RARRAY_LEN(command)!=7)rb_raise(rb_eArgError,"Invalid XP tile batch");
    for(int i:{2,4,5,6})if(!RB_INTEGER_TYPE_P(rb_ary_entry(command,i)))rb_raise(rb_eTypeError,"Tile batch metadata must be integer primitives");
    Batch b{};b.c=cache(rb_ary_entry(command,1));b.group=NUM2SIZET(rb_ary_entry(command,2));b.objects=rb_ary_entry(command,3);
    Check_Type(b.objects,T_ARRAY);
    if(!b.c->ready||b.c->disposed||b.group>=b.c->group_count||RARRAY_LEN(b.objects)!=9)rb_raise(rb_eArgError,"Invalid XP tile batch state");
    b.x=NUM2DBL(rb_ary_entry(command,4));b.y=NUM2DBL(rb_ary_entry(command,5));b.opacity=NUM2INT(rb_ary_entry(command,6));
    if(!std::isfinite(b.x)||!std::isfinite(b.y)||std::abs(b.x)>1e12||std::abs(b.y)>1e12||b.opacity<0||b.opacity>255)rb_raise(rb_eArgError,"Invalid XP tile batch origin or opacity");
    for(int i=0;i<9;++i)b.images[i]=canvas_optional(rb_ary_entry(b.objects,i));return b;
}
}
size_t xp_batch_count(VALUE command,size_t* flashes){auto b=batch(command);size_t count=0;if(flashes)*flashes=0;for(const auto& e:b.c->groups[b.group].entries){const auto& cell=b.c->cells[e.cell];if(e.level==3){if(b.images[8]){++count;if(flashes)++*flashes;}}else{const auto& s=b.c->shapes[b.c->indices[cell.ids[e.level]]];if(b.images[s.sheet])count+=s.count;}}return count;}
void xp_batch_expand(VALUE command,void* target,XPTileEmit emit){
    auto b=batch(command);for(const auto& e:b.c->groups[b.group].entries){const auto& cell=b.c->cells[e.cell];double x=cell.wx*32+b.x,y=cell.wy*32+b.y;
        if(e.level==3){if(b.images[8])emit(target,b.images[8],x,y,0,0,32,32,cell.flash,b.opacity);}
        else {const auto& s=b.c->shapes[b.c->indices[cell.ids[e.level]]];if(b.images[s.sheet])for(int q=0;q<s.count;++q){const auto& p=s.parts[q];emit(target,b.images[s.sheet],x+p.dx,y+p.dy,p.sx,p.sy,p.w,p.h,0,255);}}
    }
}
namespace {
VALUE expand(VALUE,VALUE command){
    size_t count=xp_batch_count(command);if(count>100000)rb_raise(rb_eArgError,"Too many rendering commands");
    struct Item {Canvas* bitmap;double x,y;int sx,sy,w,h,flash,opacity;};
    VALUE storage=rb_str_new(nullptr,static_cast<long>(count*sizeof(Item)));auto* items=reinterpret_cast<Item*>(RSTRING_PTR(storage));
    struct Sink {Item* items;size_t used,count;} sink{items,0,count};
    xp_batch_expand(command,&sink,[](void* v,Canvas* b,double x,double y,int sx,int sy,int w,int h,int flash,int opacity){auto& s=*static_cast<Sink*>(v);if(s.used>=s.count)rb_raise(rb_eArgError,"Tile batch changed");s.items[s.used++]={b,x,y,sx,sy,w,h,flash,opacity};});
    VALUE result=rb_ary_new();VALUE objects=rb_ary_entry(command,3);
    for(size_t i=0;i<sink.used;++i){auto d=items[i];VALUE bitmap=Qnil;for(int k=0;k<9;++k){VALUE v=rb_ary_entry(objects,k);if(canvas_optional(v)==d.bitmap){bitmap=v;break;}}
        VALUE color=Qnil;if(d.flash)color=rb_funcall(rb_path2class("Color"),rb_intern("new"),4,INT2NUM((d.flash>>8&15)*17),INT2NUM((d.flash>>4&15)*17),INT2NUM((d.flash&15)*17),INT2FIX(255));
        VALUE a[22]={INT2FIX(0),bitmap,DBL2NUM(d.x),DBL2NUM(d.y),INT2NUM(d.w),INT2NUM(d.h),INT2NUM(d.sx),INT2NUM(d.sy),INT2NUM(d.w),INT2NUM(d.h),INT2FIX(1),INT2FIX(1),INT2FIX(0),INT2FIX(0),INT2FIX(0),INT2NUM(d.opacity),INT2NUM(d.flash?1:0),color,Qnil,INT2FIX(0),Qnil,Qfalse};rb_ary_push(result,rb_ary_new_from_values(22,a));
    }RB_GC_GUARD(storage);RB_GC_GUARD(command);return result;
}
}
void init_xp_tile_cache(){
    VALUE module=rb_define_module("RGSSXP"),klass=rb_define_class_under(module,"XPTileCache",rb_cObject);
    rb_define_alloc_func(klass,allocate);rb_define_method(klass,"prepare",RUBY_METHOD_FUNC(prepare),7);rb_define_method(klass,"shape",RUBY_METHOD_FUNC(define),3);
    rb_define_method(klass,"commit",RUBY_METHOD_FUNC(commit),0);rb_define_method(klass,"groups",RUBY_METHOD_FUNC(groups),1);rb_define_method(klass,"dispose",RUBY_METHOD_FUNC(dispose),0);rb_define_method(klass,"stats",RUBY_METHOD_FUNC(stats),0);
    rb_define_singleton_method(module,"__expand_xp_tile_batch",RUBY_METHOD_FUNC(expand),1);
}
