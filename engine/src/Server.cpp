#include "Server.h"
#include "Session.h"

#include <future>

//==============================================================================
struct Server::Client : public juce::Thread
{
    Client (Server& s, std::unique_ptr<juce::StreamingSocket> sock)
        : juce::Thread ("musicoma-client"), server (s), socket (std::move (sock)) {}

    ~Client() override
    {
        signalThreadShouldExit();
        socket->close();
        stopThread (2000);
    }

    void send (const juce::String& line)
    {
        const juce::ScopedLock sl (writeLock);
        auto utf8 = (line + "\n").toStdString();
        socket->write (utf8.data(), (int) utf8.size());
    }

    void run() override
    {
        std::string buffer;
        char chunk[8192];

        while (! threadShouldExit() && socket->isConnected())
        {
            auto ready = socket->waitUntilReady (true, 200);

            if (ready < 0)
                break;

            if (ready == 0)
                continue;

            auto n = socket->read (chunk, sizeof (chunk), false);

            if (n <= 0)
                break;

            buffer.append (chunk, (size_t) n);
            size_t nl;

            while ((nl = buffer.find ('\n')) != std::string::npos)
            {
                auto line = juce::String::fromUTF8 (buffer.data(), (int) nl).trim();
                buffer.erase (0, nl + 1);

                if (line.isNotEmpty())
                    send (server.dispatchFrom (line, this));
            }
        }

        finished = true;
    }

    Server& server;
    std::unique_ptr<juce::StreamingSocket> socket;
    juce::CriticalSection writeLock;
    std::atomic<bool> finished { false };
};

//==============================================================================
Server::Server (int p, Session& s) : juce::Thread ("musicoma-server"), port (p), session (s) {}

Server::~Server()
{
    signalThreadShouldExit();
    listener.close();
    stopThread (3000);

    const juce::ScopedLock sl (clientsLock);
    clients.clear();
}

bool Server::start()
{
    if (! listener.createListener (port, "127.0.0.1"))
        return false;

    startThread();
    return true;
}

void Server::run()
{
    while (! threadShouldExit())
    {
        std::unique_ptr<juce::StreamingSocket> sock (listener.waitForNextConnection());

        if (sock == nullptr)
            continue;

        const juce::ScopedLock sl (clientsLock);

        for (int i = clients.size(); --i >= 0;)
            if (clients[i]->finished)
                clients.remove (i);

        clients.add (new Client (*this, std::move (sock)))->startThread();
    }
}

void Server::broadcast (const juce::String& line, Client* except)
{
    const juce::ScopedLock sl (clientsLock);

    for (auto c : clients)
        if (c != except && ! c->finished)
            c->send (line);
}

juce::String Server::dispatchFrom (const juce::String& line, Client* from)
{
    auto request = juce::JSON::parse (line);
    auto reply = new juce::DynamicObject();
    juce::var replyVar (reply);

    if (! request.isObject())
    {
        reply->setProperty ("ok", false);
        reply->setProperty ("error", "invalid JSON");
        return juce::JSON::toString (replyVar, true);
    }

    reply->setProperty ("id", request["id"]);
    auto method = request["method"].toString();
    auto params = request["params"];
    auto client = request["client"].toString();

    // Tracktion 은 메시지 스레드에서만 만진다.
    std::promise<std::pair<juce::var, juce::String>> promise;
    auto future = promise.get_future();
    bool mutated = false;

    juce::MessageManager::callAsync ([&]
    {
        try
        {
            auto result = session.handle (method, params, mutated);
            promise.set_value ({ result, {} });
        }
        catch (const std::exception& e)
        {
            promise.set_value ({ {}, juce::String::fromUTF8 (e.what()) });
        }
        catch (...)
        {
            promise.set_value ({ {}, "unknown error" });
        }
    });

    auto [result, error] = future.get();

    if (error.isEmpty())
    {
        reply->setProperty ("ok", true);
        reply->setProperty ("result", result);

        if (mutated)
        {
            auto ev = new juce::DynamicObject();
            juce::var evVar (ev);
            ev->setProperty ("event", "changed");
            ev->setProperty ("method", method);
            ev->setProperty ("client", client);
            broadcast (juce::JSON::toString (evVar, true), from);
        }
    }
    else
    {
        reply->setProperty ("ok", false);
        reply->setProperty ("error", error);
    }

    return juce::JSON::toString (replyVar, true);
}
