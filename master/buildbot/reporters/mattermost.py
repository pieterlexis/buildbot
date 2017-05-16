# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot.reporters import http
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger
from buildbot.reporters import utils
from buildbot.process.results import statusToString

log = Logger()


class MattermostStatusPush(http.HttpStatusPushBase):
    name = "MattermostStatusPush"
    neededDetails = dict(wantProperties=True)

    @defer.inlineCallbacks
    def reconfigService(self, endpoint, builder_channel_map={},
                        icon_url='//buildbot.net/img/nut.png',
                        bot_name='BuildBot', **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, endpoint)

        self.icon_url = icon_url
        self.bot_name = bot_name
        self.builder_channel_map = builder_channel_map

    def getChannelForBuild(self, key):
        res = self.builder_channel_map.get(key, [])
        if not isinstance(res, list):
            return [res]
        return res

    def sendMessageToChannel(self, channel, message):
        payload = {
            'username': self.bot_name,
            'icon_url': self.icon_url,
            'text': message
        }

        if channel != 'DEFAULT':
            payload.update({'channel': channel})

        return self._http.post('', json=payload)

    def getMessage(self, build):
        if build['complete']:
            return 'Finished build {} with result {} ({})'.format(
                build['builder']['name'], statusToString(build['results']), build['url'])
        if build['state_string'] == 'starting':
            return 'Started build {} ({})'.format(
                build['builder']['name'], build['url'])
        return None

    @defer.inlineCallbacks
    def send(self, build):
        message = yield self.getMessage(build)

        if not message:
            return

        channels = yield self.getChannelForBuild(build['builder']['name'])

        if not channels:
            res = yield self.sendMessageToChannel('DEFAULT', message)
            if res.code != 200:
                content = yield res.content()
                log.error("{code}: Unable to push status: {content}".format(
                    code=res.code, content=content))
            return
        for channel in channels:
            res = yield self.sendMessageToChannel(channel, message)
            if res.code != 200:
                content = yield res.content()
                log.error("{code}: Unable to push status: {content}".format(
                    code=res.code, content=content))
