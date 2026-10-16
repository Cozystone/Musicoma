// Musicoma Engine — 명령 서버(127.0.0.1:47800, 줄 단위 JSON) + 진입점.
// 요청 {id, method, params, client} → 응답 {id, ok, result | error}. 곡을 바꾼 명령은 다른 연결에 {event:"changed", method, client}.
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <list>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include "eng_model.h"
#include "eng_graph.h"
#include "vst3host.h"

namespace mc {

namespace {

struct Client
{
    SOCKET sock = INVALID_SOCKET;
    std::mutex writeLock;
    std::atomic<bool> alive { true };
    std::thread th;

    void send (const std::string& line)
    {
        std::lock_guard<std::mutex> l (writeLock);
        std::string s = line + "\n";
        const char* p = s.data();
        size_t left = s.size();
        while (left > 0)
        {
            int n = ::send (sock, p, (int) std::min<size_t> (left, 1 << 20), 0);
            if (n <= 0) { alive = false; return; }
            p += n; left -= (size_t) n;
        }
    }
};

class Server
{
public:
    Server (Engine& e, int port) : eng (e), port (port) {}

    bool start (std::string& err)
    {
        WSADATA wsa;
        if (WSAStartup (MAKEWORD (2, 2), &wsa) != 0) { err = "WSAStartup failed"; return false; }
        listener = socket (AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (listener == INVALID_SOCKET) { err = "socket failed"; return false; }
        sockaddr_in a {};
        a.sin_family = AF_INET;
        a.sin_port = htons ((u_short) port);
        inet_pton (AF_INET, "127.0.0.1", &a.sin_addr);
        BOOL excl = TRUE;
        setsockopt (listener, SOL_SOCKET, SO_EXCLUSIVEADDRUSE, (const char*) &excl, sizeof excl);
        if (bind (listener, (sockaddr*) &a, sizeof a) != 0) { err = "port " + std::to_string (port) + " is busy (another engine running?)"; return false; }
        if (listen (listener, 16) != 0) { err = "listen failed"; return false; }
        acceptThread = std::thread ([this] { acceptLoop(); });
        return true;
    }

    void acceptLoop()
    {
        while (true)
        {
            SOCKET s = accept (listener, nullptr, nullptr);
            if (s == INVALID_SOCKET) break;
            BOOL nd = TRUE;
            setsockopt (s, IPPROTO_TCP, TCP_NODELAY, (const char*) &nd, sizeof nd);
            auto c = std::make_shared<Client>();
            c->sock = s;
            {
                std::lock_guard<std::mutex> l (clientsLock);
                clients.remove_if ([] (const std::shared_ptr<Client>& x) { if (! x->alive) { if (x->th.joinable()) x->th.detach(); return true; } return false; });
                clients.push_back (c);
            }
            c->th = std::thread ([this, c] { clientLoop (c); });
        }
    }

    void clientLoop (std::shared_ptr<Client> c)
    {
        std::string buf;
        char chunk[16384];
        while (c->alive)
        {
            int n = recv (c->sock, chunk, sizeof chunk, 0);
            if (n <= 0) break;
            buf.append (chunk, (size_t) n);
            size_t nl;
            while ((nl = buf.find ('\n')) != std::string::npos)
            {
                std::string line = buf.substr (0, nl);
                buf.erase (0, nl + 1);
                while (! line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
                if (! line.empty()) c->send (dispatch (line, c.get()));
            }
        }
        c->alive = false;
        closesocket (c->sock);
    }

    std::string dispatch (const std::string& line, Client* from)
    {
        Json reply = Json::object();
        Json req;
        try { req = Json::parse (line); }
        catch (...)
        {
            reply.set ("ok", Json::boolean (false));
            reply.set ("error", Json::string ("invalid JSON"));
            return reply.dump();
        }
        if (! req.isObj())
        {
            reply.set ("ok", Json::boolean (false));
            reply.set ("error", Json::string ("invalid JSON"));
            return reply.dump();
        }
        reply.set ("id", req["id"]);
        std::string method = req.str ("method");
        std::string client = req.str ("client");
        bool mutated = false;
        try
        {
            Json result = eng.handle (method, req["params"], mutated);
            reply.set ("ok", Json::boolean (true));
            reply.set ("result", result);
        }
        catch (const std::exception& e)
        {
            reply.set ("ok", Json::boolean (false));
            reply.set ("error", Json::string (e.what()));
            mutated = false;
        }
        catch (...)
        {
            reply.set ("ok", Json::boolean (false));
            reply.set ("error", Json::string ("unknown error"));
            mutated = false;
        }
        if (mutated)
        {
            Json ev = Json::object();
            ev.set ("event", Json::string ("changed"));
            ev.set ("method", Json::string (method));
            ev.set ("client", Json::string (client));
            std::string s = ev.dump();
            std::lock_guard<std::mutex> l (clientsLock);
            for (auto& c : clients) if (c.get() != from && c->alive) c->send (s);
        }
        return reply.dump();
    }

private:
    Engine& eng;
    int port;
    SOCKET listener = INVALID_SOCKET;
    std::thread acceptThread;
    std::mutex clientsLock;
    std::list<std::shared_ptr<Client>> clients;
};

std::string findRoot (const std::string& exeDir)
{
    if (const char* env = std::getenv ("MUSICOMA_ROOT"); env && *env) return env;
    fs::path p = u8path (exeDir);
    for (int i = 0; i < 8 && ! p.empty(); ++i)
    {
        if (fs::exists (p / "musicoma" / "__init__.py") || (fs::exists (p / "musicoma") && fs::exists (p / "ui")))
            return pathToU8 (p);
        if (p == p.parent_path()) break;
        p = p.parent_path();
    }
    return pathToU8 (fs::current_path());
}

} // namespace

} // namespace mc

int wmain (int argc, wchar_t** argv)
{
    using namespace mc;
    SetConsoleOutputCP (CP_UTF8);
    int port = 47800;
    std::string root;
    for (int i = 1; i < argc; ++i)
    {
        std::wstring a = argv[i];
        if (a == L"--port" && i + 1 < argc) port = _wtoi (argv[++i]);
        else if (a == L"--root" && i + 1 < argc) root = pathToU8 (fs::path (argv[++i]));
    }
    wchar_t exe[MAX_PATH];
    GetModuleFileNameW (nullptr, exe, MAX_PATH);
    if (root.empty()) root = findRoot (pathToU8 (fs::path (exe).parent_path()));

    Engine engine (root);
    engine.prepareAll (48000);
    engine.graph->prepare (48000, 512);
    Server server (engine, port);
    std::string err;
    if (! server.start (err))
    {
        std::fprintf (stderr, "musicoma-engine: %s\n", err.c_str());
        return 1;
    }
    std::printf ("musicoma-engine listening on 127.0.0.1:%d (root %s)\n", port, root.c_str());
    std::fflush (stdout);
    std::string aerr;
    if (! engine.startOutput (aerr)) std::fprintf (stderr, "audio output not available: %s (render still works)\n", aerr.c_str());
    engine.openMidiInputs();   // 연결된 MIDI 키보드·컨트롤러를 바로 연다(녹음 대기 없이도 연주·매핑)
    runVst3WindowThread();     // 플러그인 창 메시지 루프(프로세스 끝까지)
    return 0;
}
