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
    neededDetails = dict(wantProperties=True, wantSteps=True)

    @defer.inlineCallbacks
    def reconfigService(self, endpoint, builder_configs={},
                        ignore_builders=[],
                        icon_url='//buildbot.net/img/nut.png',
                        bot_name='BuildBot', **kwargs):
        yield http.HttpStatusPushBase.reconfigService(self, **kwargs)

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, endpoint)

        self.builder_configs = builder_configs
        self.ignore_builders = ignore_builders
        self.icon_url = icon_url
        self.bot_name = bot_name

    def checkConfig(self, endpoint, builder_configs={},
                    ignore_builders=[],
                    icon_url='//buildbot.net/img/nut.png',
                    bot_name='BuildBot', **kwargs):
        if not isinstance(endpoint, string_types):
            config.error('{name}: endpoint must be a string'.format(
                name=self.name))
        if not isinstance(builder_configs, dict):
            config.error('{name}: builder_configs must be a dictionary'.format(
                name=self.name))
        if not isinstance(ignore_builders, list):
            config.error('{name}: ignore_builders must be a list'.format(
                name=self.name))
        for channel, chconfig in builder_configs.items():
            if not isinstance(chconfig, dict):
                config.error('{name}: configuration for channel {channel} is not a dict'.format(
                    name=self.name, channel=channel))
        if not isinstance(icon_url, string_types):
            config.error('{name}: icon_url must be a string'.format(
                name=self.name))
        if not isinstance(bot_name, string_types):
            config.error('{name}: bot_name must be a string'.format(
                name=self.name))

    def sendMessageToChannel(self, channel, message):
        payload = {
            'username': self.bot_name,
            'icon_url': self.icon_url,
            'text': message
        }

        if channel != 'DEFAULT':
            payload.update({'channel': channel})

        return self._http.post('', json=payload)

    @defer.inlineCallbacks
    def getMessage(self, builder_config, build):
        msg_buildurl = '[#{buildnum}]({buildurl})'.format(
            buildnum=build['number'],
            buildurl=build['url']
        )

        msg_builderinfo = 'build {} for {}'.format(
            msg_buildurl,
            build['builder']['name'])
        msg_body = ''

        if build['properties'].get('project', [''])[0]:
            msg_builderinfo += ' for project {}'.format(build['properties']['project'])

        if not build['complete']:
            return """**Started {msg_builderinfo}!**""".format(
                msg_builderinfo=msg_builderinfo
            )

        msg_result = {SUCCESS: 'successfully',
                      EXCEPTION: 'with an error',
                      FAILURE: 'unsuccessfully',
                      WARNINGS: 'successfully with warnings'}.get(build['results'])

        if build['results'] == FAILURE:
            failed_steps = [step for step in build['steps'].data if step['results'] == FAILURE]
            responsible_users = yield utils.getResponsibleUsersForBuild(self.master, build['buildid'])
            responsible_users = [user for user in responsible_users if user != '']

            msg_body += """Failed step{}: {}.
User{} responsible for this build: {}""".format(
                '' if len(failed_steps) == 1 else 's',
                ', '.join([step['name'] for step in failed_steps]),
                '' if len(responsible_users) == 1 else 's',
                ', '.join(responsible_users) if len(responsible_users) != 0 else '(none found)'
            )

        if build['results'] == EXCEPTION:
            # TODO
            pass

        if build['results'] == WARNINGS:
            # TODO
            pass

        return """**Finished {msg_builderinfo} {msg_result}!**
{msg_body}""".format(msg_builderinfo=msg_builderinfo,
                     msg_result=msg_result,
                     msg_body=msg_body)

    def getBuilderConfig(self, key):
        """
        Return the configuration for builder ``key``

        :param str key: The builder to retrieve the config for
        :return: A dict with the configuration or None is this builder is ignored
        """
        if key in self.ignored_builders:
            return None

        # No builder-specific configs, send all messages to the default channel
        if len(self.builder_configs) == 0:
            return {}

        ret = self.builder_configs.get(key, None)

        if not ret:
            # No channel specific config, is there a default config?
            ret = self.builder_configs.get('DEFAULT', None)

        return ret

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
