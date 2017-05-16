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

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.reporters.mattermost import MattermostStatusPush
from buildbot.process.results import SUCCESS
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestMattermostStatusPush(unittest.TestCase, ReporterTestMixin, LoggingMixin):

    def setUp(self):
        self.patch(config, '_errors', Mock)
        self.master = fakemaster.make_master(
            testcase=self, wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def tearDown(self):
        if self.master.running:
            yield self.master.stopService()

    @defer.inlineCallbacks
    def createReporter(self, **kwargs):
        kwargs['endpoint'] = kwargs.get('endpoint', 'http://localhost/hooks/aabbccddeeffgghh')
        self.mm = MattermostStatusPush(**kwargs)
        self._http = yield fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, kwargs.get('endpoint'))
        yield self.mm.setServiceParent(self.master)
        yield self.master.startService()

    @defer.inlineCallbacks
    def setupBuildResults(self):
        self.insertTestData([SUCCESS], SUCCESS)
        build = yield self.master.data.get(("builds", 20))
        defer.returnValue(build)

    @defer.inlineCallbacks
    def test_build_finished_defaults(self):
        yield self.createReporter()
        build = yield self.setupBuildResults()
        self._http.expect(
            'post',
            '',
            json={'username': 'BuildBot',
                  'text': 'Finished build Builder0 with result success (http://localhost:8080/#builders/79/builds/0)',
                  'icon_url': '//buildbot.net/img/nut.png',
                  'username': 'BuildBot'})
        build['complete'] = True
        self.mm.buildFinished(('build', 20, 'finished'), build)

    @defer.inlineCallbacks
    def test_build_started_defaults(self):
        yield self.createReporter()
        build = yield self.setupBuildResults()
        build['state_string'] = 'starting'
        self._http.expect(
            'post',
            '',
            json={'username': 'BuildBot',
                  'text': 'Started build Builder0 (http://localhost:8080/#builders/79/builds/0)',
                  'icon_url': '//buildbot.net/img/nut.png',
                  'username': 'BuildBot'})
        self.mm.buildStarted(('build', 20, 'new'), build)
