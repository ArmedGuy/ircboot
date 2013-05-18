__version__ = '0.8'
__author__  = 'ArmedGuy'

import b3, time, threading, re, socket, thread, sys, pyircbot
from pyircbot import IrcEvent, IrcUser
from b3 import clients
import b3.events
import b3.plugin
import datetime, string
from b3 import functions
#--------------------------------------------------------------------------------------------------
class IrcbootPlugin(b3.plugin.Plugin):
    SpawnedPlugin = None
    _reColor = re.compile(r'(\^[0-9a-z])|[\x80-\xff]')
    _settings = { # default settings
        'irc': {
            'nick': "b3ircbot-ircboot",
            'ident': "b3ircboot",
            'realname': "Big Brother",
            'serverpassword': "",
            'nickservpassword': "",
            'host': None,
            'port': 6667,
            'channels': None,
        },
        'relay': {
            'mode': 'rcon',
            'broadcasts': 'true',
            'gamechatmode': 'public',
            'gameeventmode': 'public',
        },
        'commands': {
            'ircadd': 80,
            'ircrem': 80,
            'ircexec': 100,
            'ircon': 80,
        },
        'users': {
            'userfile': None,
        },
    }
    _ircbot = None
    _adminPlugin = None
    def onLoadConfig(self):
        IrcbootPlugin.SpawnedPlugin = self
        if self._adminPlugin == None:
            try:
                self._adminPlugin = self.console.getPlugin('admin')
            except:
                self.error("Could not get admin plugin!")
                return False
                
        #----------------------------------- Bot Settings ---------------------------------------------        
        for section in self.config.sections():
            for setting in self.config.options(section):
                try:
                    if setting == "channels":
                        if "," in self.config.get(section, setting):
                            self._settings[section][setting] = self.config.get(section, setting).split(",")
                        else:
                            self._settings[section][setting] = [1]
                            self._settings[section][setting][0] = self.config.get(section, setting)
                    else:
                        self._settings[section][setting] = self.config.get(section, setting)
                except:
                    print "exception on config load: %s" % sys.exc_info()[0]
                    if setting in ('host', 'channels', 'userfile'):
                        self.error("Could not load setting '%s->%s', plugin cannot start without it!" % (section,setting))
                        return False
                    else:
                        self.warning("Could not load setting '%s->%s', plugin falls back on default!" % (section, setting))
        for cmd in self._settings['commands']:
            self._adminPlugin.registerCommand(self, cmd, self._settings['commands'][cmd], self.getCmd(cmd), "")
        # ------------------------------------------------------ Start IRC Bot -----------------------------------------
        if self._ircbot:
            self._ircbot.exit()
        if "chatprefix" in self._settings['relay']:
            self._settings['relay']['chatprefix'] = self._settings['relay']['chatprefix'].replace("]C","")
            
        IrcAuthSystem.AuthenticationFile = self._settings['users']['userfile']
        
        self.debug("Starting pyircbot with nick=%s, ident=%s, realname=%s, host=%s, port=%i" % (self._settings['irc']['nick'], self._settings['irc']['ident'], self._settings['irc']['realname'], self._settings['irc']['host'], int(self._settings['irc']['port'])))
        
        botsettings = {
            'host': self._settings['irc']['host'],
            'port': int(self._settings['irc']['port']),
            'nick': self._settings['irc']['nick'],
            'ident': self._settings['irc']['ident'],
            'realname': self._settings['irc']['realname'],
        }
        if self._settings['irc']['serverpassword'] != "":
            botsettings['serverpassword'] = self._settings['irc']['serverpassword']
        self._ircbot = pyircbot.create(botsettings)
        
        standard = pyircbot.StandardBotRoutines(self._ircbot, botsettings)
        standard.queueJoinChannels(self._settings['irc']['channels'])
        if self._settings['irc']['nickservpassword'] != "":
            standard.queueNickServAuth(self._settings['irc']['nickservpassword'])
        standard.autoReconnect()
        
        self._ircbot.RegisterEventHandler(IrcEvent.UserJoined, self.onUserJoin)
        self._ircbot.RegisterEventHandler(IrcEvent.ChanmsgRecieved, self.onChanMsg)
        self._ircbot.RegisterEventHandler(IrcEvent.QueryRecieved, self.onQueryMsg)
        self._ircbot.connect()
            
    def startup(self):
        """\
        Initialize plugin settings
        """
        
        # listen for client events
        self.registerEvent(b3.events.EVT_CLIENT_SAY)
        self.registerEvent(b3.events.EVT_CLIENT_TEAM_SAY)
        self.registerEvent(b3.events.EVT_CLIENT_PRIVATE_SAY)
        self.registerEvent(b3.events.EVT_CLIENT_CONNECT)
        self.registerEvent(b3.events.EVT_CLIENT_DISCONNECT)
        
    def getCmd(self, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
        return None
        
    def getIrcBot(self):
        if self._ircbot != None:
            return self._ircbot
        
    def injectClientSay(self, user, msg): # will probably pass user,chan as IrcClient class instead
        # TODO: filter commands so that broken ones wont give errors(!leveltest for example)
        if user.maxLevel > 0 and self._settings['relay']['mode'] == "rcon": # do NOT allow guests to use commands
            self.console.queueEvent(self.console.getEvent('EVT_CLIENT_SAY', msg, user))
        else:
            if self._settings['relay']['mode'] == "rcon":
                self._ircbot.notice(user.name, "You are not authorized to use this B3 Irc Bot")
            else:
                if msg[0] == "!" or msg[0] == "@" and user.maxLevel == 0:
                    msg = msg[1:] # do not let unregistered users use commands
                self.console.queueEvent(self.console.getEvent('EVT_CLIENT_SAY', msg, user))

    

    def onEvent(self, event):
        if not event.client or event.client.cid == None:
            return
        if self._settings['relay']['gamechat'] == "true":
            if self._ircbot:
                if event.type == b3.events.EVT_CLIENT_SAY:
                    for chan in self._settings['irc']['channels']:
                        self._ircbot.msg(chan, "%s%s" % (self._settings['relay']['chatprefix'], re.sub(self._reColor, '', "(ALL)%s: %s" % (event.client.name,event.data))))
                if event.type == b3.events.EVT_CLIENT_TEAM_SAY:
                    for chan in self._settings['irc']['channels']:
                        self._ircbot.msg(chan, "%s%s" % (self._settings['relay']['chatprefix'], re.sub(self._reColor, '', "(TEAM)%s: %s" % (event.client.name,event.data))))
                if event.type == b3.events.EVT_CLIENT_PRIVATE_SAY:
                    for chan in self._settings['irc']['channels']:
                        self._ircbot.msg(chan, "%s%s" % (self._settings['relay']['chatprefix'], re.sub(self._reColor, '', "(PM)%s: %s" % (event.client.name,event.data))))
        if self._settings['relay']['gameevents'] == "true":
            if self._ircbot:
                if event.type == b3.events.EVT_CLIENT_CONNECT:
                    for chan in self._settings['irc']['channels']:
                        self._ircbot.msg(chan, "%s%s" % (self._settings['relay']['chatprefix'], re.sub(self._reColor, '', "Player %s has joined the server" % event.client.name)))
                if event.type == b3.events.EVT_CLIENT_DISCONNECT:
                    for chan in self._settings['irc']['channels']:
                        self._ircbot.msg(chan, "%s%s" % (self._settings['relay']['chatprefix'], re.sub(self._reColor, '', "Player %s has left the server" % event.client.name)))
        self.debug("Got Command: %s" % event.type)
      
    # commands
    def cmd_ircadd(self, data, client, cmd=None):
        m = self._adminPlugin.parseUserCmd(data)
        if not m:
            sclient = client
        else:
            sclient = self._adminPlugin.findClientPrompt(m[0], client)
        if sclient:
            IrcAuthSystem.setLevel("%s!*@*" % sclient.name, sclient.maxLevel, True)
            client.message("Ingame player %s have been added with the level %i" % (str(sclient.name), int(sclient.maxLevel)))
        else:
            if("!" in m[0] and "@" in m[0]):
                try:
                    level = int(m[1])
                    IrcAuthSystem.setLevel(m[0], level, True)
                    client.message("Mask %s added with level %s" % ( m[0], str(m[1])))
                except:
                    client.message("Invalid parameter 'level' for mask")
            else:
                client.message("No client found with that name.")
    def cmd_ircrem(self, data, client, cmd=None):
        pass
    def cmd_ircexec(self, data, client, cmd=None):
        pass
    def cmd_ircon(self, data, client, cmd=None):
        res = self.console.write(data)
        client.message(res)
        
        
    # Handle pyircbot events
    
    def onUserJoin(self, type, data):
        if type == IrcEvent.UserJoined:
            user = IrcClient.GetClient(data.sender)
            if user.maxLevel > 0:
                self._ircbot.notice(user.name, "%s is running with mode '%s%', ready for commands" % (self._settings['irc']['nick'], self._settings['relay']['mode']))
                
    def onChanMsg(self, type, data):
        if type == IrcEvent.ChanmsgRecieved:
            if self._settings['relay']['mode'] == "rcon":
                if data.message[0:len(self._settings['irc']['nick'])] == self._settings['irc']['nick'] and "!" in data.message and (data.message.find("!") < len(self._settings['irc']['nick']) + 4): # highlight command sending
                   b3msg = data.message[data.message.find("!"):]
                   client = IrcClient.GetClient(data.sender)
                   self.injectClientSay(client, b3msg)
                elif data.message[:2] == "@!":
                    b3msg = data.message[1:]
                    client = IrcClient.GetClient(data.sender)
                    self.injectClientSay(client, b3msg)
            else: # full relay
                else:
                    client = IrcClient.GetClient(data.sender)
                    self.injectClientSay(client, data.message)
    def onQueryMsg(self, type, data):
        if type == IrcEvent.QueryRecieved:
            if data.message[0] == "!" or data.message[0] == "@":
                client = IrcClient.GetClient(data.sender)
                self.injectClientSay(client, data.message)
        
class IrcAuthSystem:
    AuthenticationFile = ""
    AuthenticationMap = []
    LastFileLoad = 0
    @staticmethod
    def getLevel(user):
        if(time.time() - IrcAuthSystem.LastFileLoad > 600): IrcAuthSystem.loadUsers()
        for client in IrcAuthSystem.AuthenticationMap:
            if client[2].match(user) != None:
                return int(client[1])
        return 0
    @staticmethod
    def setLevel(user, level, add=False):
        IrcAuthSystem.loadUsers()
        if add == True:
            IrcAuthSystem.AuthenticationMap.append((user, level, re.compile(user.replace("*",".*"))))
        else:
            for client in IrcAuthSystem.AuthenticationMap:
                if client[0].match(user) != None:
                    client[1] = level
        IrcAuthSystem.saveUsers()
        
    @staticmethod
    def loadUsers():
        try:
            IrcAuthSystem.AuthenticationMap = []
            f = open(IrcAuthSystem.AuthenticationFile)
            for line in f.readlines():
                if ":" in line:
                    d = line.split(":", 1)
                    IrcAuthSystem.AuthenticationMap.append((d[0],d[1],re.compile(d[0].replace("*",".*"))))
            IrcAuthSystem.LastFileLoad = time.time()
            f.close()
        except:
            IrcbootPlugin.SpawnedPlugin.error("IrcAuthSystem.loadUsers: could not load users! Exception: %s" % str(sys.exc_info()))
    @staticmethod
    def saveUsers():
        try:
            f = open(IrcAuthSystem.AuthenticationFile, "w")
            for client in IrcAuthSystem.AuthenticationMap:
                IrcbootPlugin.SpawnedPlugin.debug("Writing %s to the authmap" % client[0])
                if(client[1] != 0):
                    f.write("%s:%i\n" % (client[0],int(client[1])))
            f.close()
        except:
            IrcbootPlugin.SpawnedPlugin.error("IrcAuthSystem.saveUsers: could not save users! Exception: %s" % str(sys.exc_info()))
            
        
class IrcClient(b3.clients.Client):
    Clients = []
    _reColor = re.compile(r'(\^[0-9a-z])|[\x80-\xff]')
    maxLevel = 0
    id = 0
    hide = True
    _user = ""
    
    @staticmethod
    def GetClient(user):
        for client in IrcClient.Clients:
            if client._user == user:
                return client
        return IrcClient(IrcbootPlugin.SpawnedPlugin.getIrcBot(), user)
    
    def __init__(self, relaybot, user, channel=""):
        IrcClient.Clients.append(self)
        self._user = user
        self._ircbot = relaybot
        self.maxLevel = IrcAuthSystem.getLevel(user)
        self.name = user.split("!")[0]
        self.authed = True
            
    def getWrap(self, text, length=80, minWrapLen=150): # taken from b3 core, but without any colors, just removing them
        """Returns a sequence of lines for text that fits within the limits"""
        if not text:
            return []

        lines = []
        length = int(length)
        text = text.replace('//', '/ /')
        text = re.sub(self._reColor, '', text)
        if len(text) <= minWrapLen and "\n" not in text:
            return [text]
        #if len(re.sub(REG, '', text)) <= minWrapLen:
        #    return [text]
        for t in text.split("\n"):
            text = re.split(r'\s+', t)


            line = text[0]
            for t in text[1:]:
                if len(re.sub(self._reColor, '', line)) + len(re.sub(self._reColor, '', t)) + 2 <= length:
                    line = '%s %s' % (line, t)
                else:
                    if len(lines) > 0:
                        lines.append(line)
                    else:
                        lines.append(line)

                    m = re.findall(self._reColor, line)
                    if m:
                        color = m[-1]

                    line = t

            if len(line):
                if len(lines) > 0:
                    lines.append(line)
                else:
                    lines.append(line)

        return lines
    def message(self, message):
        lines = self.getWrap(message)
        if len(lines) > 3:
            # run threaded with msg delay to prevent bot from getting its ass handed by netsec
            thread.start_new_thread(self.msg_threaded, (lines,))
        else:
            for line in lines:
                self._ircbot.notice(self.name, "[pm]: %s" % line)
    def msg_threaded(self, lines):
        for line in lines:
            self._ircbot.notice(self.name, "[pm]: %s" % line)
            time.sleep(0.2)
