#include <JuceHeader.h>
#include "Session.h"
#include "Server.h"

#include <iostream>

namespace te = tracktion;

/** musicoma-engine [--port 47800] [--root D:\0.Musicoma]
    창 없이 떠 있는 엔진. 플러그인 창은 device.show 로 연다. */
class MusicomaEngineApp : public juce::JUCEApplication
{
public:
    const juce::String getApplicationName() override       { return "Musicoma Engine"; }
    const juce::String getApplicationVersion() override    { return "0.1.0"; }
    bool moreThanOneInstanceAllowed() override             { return true; }

    void initialise (const juce::String& commandLine) override
    {
        std::cout << "init: " << commandLine << std::endl;
        if (te::PluginManager::startChildProcessPluginScan (commandLine))
            return;

        auto args = juce::StringArray::fromTokens (commandLine, true);
        int port = 47800;
        auto root = juce::File::getSpecialLocation (juce::File::currentExecutableFile)
                        .getParentDirectory().getChildFile ("../../../..");

        for (int i = 0; i < args.size() - 1; ++i)
        {
            if (args[i] == "--port") port = args[i + 1].getIntValue();
            if (args[i] == "--root") root = juce::File (args[i + 1].unquoted());
        }

        if (! root.getChildFile ("BRIEF.md").existsAsFile())
            root = juce::File ("D:/0.Musicoma");

        std::cout << "starting engine..." << std::endl;
        session = std::make_unique<Session> (root);
        std::cout << "engine ok" << std::endl;
        server = std::make_unique<Server> (port, *session);

        if (! server->start())
        {
            std::cout << "ERROR could not listen on 127.0.0.1:" << port << std::endl;
            setApplicationReturnValue (1);
            quit();
            return;
        }

        std::cout << "READY musicoma-engine 127.0.0.1:" << port
                  << " root=" << root.getFullPathName() << std::endl;
    }

    void shutdown() override
    {
        server.reset();
        session.reset();
    }

    void systemRequestedQuit() override    { quit(); }

private:
    std::unique_ptr<Session> session;
    std::unique_ptr<Server> server;
};

START_JUCE_APPLICATION (MusicomaEngineApp)
