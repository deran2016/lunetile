#pragma once
struct TextSubmit {
    bool down=false,pending=false,waiting=false,triggered=false;
    void press(bool editing,bool composing,bool repeat) {
        if(down||repeat)return;
        down=true;
        if(editing){pending=true;waiting=composing;}
    }
    void release(){down=false;}
    void committed(){waiting=false;}
    void cancel(){pending=waiting=triggered=false;}
    void reset(){cancel();down=false;}
    void update(bool editing,bool composing) {
        triggered=editing&&pending&&(!waiting||!composing);
        if(triggered)pending=false;
    }
};
