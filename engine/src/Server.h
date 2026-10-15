#pragma once

#include <JuceHeader.h>

class Session;

/** 127.0.0.1 TCP 서버. 한 줄 = JSON 하나.
    요청  {"id":1,"method":"track.add","params":{...},"client":"claude"}
    응답  {"id":1,"ok":true,"result":...} | {"id":1,"ok":false,"error":"..."}
    변경 알림(모든 연결에) {"event":"changed","method":"track.add","client":"claude"}
    Claude 와 화면이 같은 엔진을 동시에 만지는 하이브리드의 통로. */
class Server : private juce::Thread
{
public:
    Server (int port, Session&);
    ~Server() override;

    bool start();
    int getPort() const { return port; }

private:
    struct Client;

    void run() override;
    juce::String dispatchFrom (const juce::String& line, Client* from);
    void broadcast (const juce::String& line, Client* except);

    int port;
    Session& session;
    juce::StreamingSocket listener;
    juce::CriticalSection clientsLock;
    juce::OwnedArray<Client> clients;
};
