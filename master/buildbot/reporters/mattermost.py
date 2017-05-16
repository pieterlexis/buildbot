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
from future.utils import string_types

from twisted.internet import defer

from buildbot import config
from buildbot.reporters import http
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger
from buildbot.reporters import utils
from buildbot.process.results import statusToString
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS

log = Logger()


class MattermostStatusPush(http.HttpStatusPushBase):
    name = "MattermostStatusPush"
    neededDetails = dict(wantProperties=True)

    @defer.inlineCallbacks
    def reconfigService(self, endpoint, builder_configs={},
                        icon_url='//buildbot.net/img/nut.png',
                        bot_name='BuildBot', **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, endpoint)

        self.builder_configs = builder_configs
        self.icon_url = icon_url
        self.bot_name = bot_name

    def checkConfig(self, endpoint, builder_configs={},
                    icon_url='//buildbot.net/img/nut.png',
                    bot_name='BuildBot', **kwargs):
        if not isinstance(endpoint, string_types):
            config.error('endpoint must be a string')
        if not isinstance(builder_configs, dict):
            config.error('builder_configs must be a dictionary')
        if not isinstance(icon_url, string_types):
            config.error('icon_url must be a string')
        if not isinstance(bot_name, string_types):
            config.error('bot_name must be a string')

    def sendMessageToChannel(self, channel, message):
        payload = {
            'username': self.bot_name,
            'icon_url': self.icon_url,
            'text': message
        }

        if channel != 'DEFAULT':
            payload.update({'channel': channel})

        return self._http.post('', json=payload)

    def getMessage(self, builder_config, build):
        msg_header = 'Builder {}'.format(build['builder']['name'])
        msg_buildurl = '[#{buildnum}]({buildurl})'.format(
            buildnum=build['number'],
            buildurl=build['url']
        )

        if build['properties'].get('project', [''])[0]:
            msg_header += ' for project {}'.format(build['properties']['project'])

        if build['complete']:
            msg_header += ' finished {} {}!'.format(
                msg_buildurl,
                {
                    SUCCESS: 'successfully',
                    EXCEPTION: 'with an error',
                    FAILURE: 'unsuccessfully',
                    WARNINGS: 'successfully with warnings'
                }.get(build['results'])
            )
        else:
            msg_header += ' started {}!'.format(msg_buildurl)

        return """{msg_header}""".format(msg_header=msg_header)

    def getBuilderConfig(self, key):
        if len(self.builder_configs) == 0:
            return {}

        return self.builder_configs.get(key, None)

    @defer.inlineCallbacks
    def send(self, build):
        builder_name = build['builder']['name']
        builder_config = yield self.getBuilderConfig(builder_name)
        if builder_config is None:
            return
        message = yield self.getMessage(builder_config, build)

        channels = builder_config.get('channels', ['DEFAULT'])
        if not isinstance(channels, list):
            channels = [channels]

        for channel in channels:
            res = yield self.sendMessageToChannel(channel, message)
            if res.code != 200:
                content = yield res.content()
                log.error("{code}: Unable to push status: {content}".format(
                    code=res.code, content=content))
