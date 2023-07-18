# -*- coding: utf-8 -*-
"""Dribdat data aggregation tests."""

from dribdat.aggregation import GetProjectData
from requests.exceptions import ReadTimeout
import warnings

class TestRepository:
    """Here be dataragons."""

    def test_datapackage_dribdat(self):
        """Test parsing a dribdat Data Package."""
        test_url = 'https://raw.githubusercontent.com/dribdat/dribdat/main/tests/mock/datapackage.json'
        try:
            test_obj = GetProjectData(test_url)
        except ReadTimeout:
            return warnings.warn("GitHub is not accessible")
        assert 'name' in test_obj
        assert test_obj['type'] == 'Data Package'
        assert 'dribdat' in test_obj['description']
        assert test_url == test_obj['source_url']

    def test_datapackage(self):
        """Test parsing a dribdat Data Package."""
        test_url = 'https://raw.githubusercontent.com/OpenEnergyData/energy-data-ch/master/datapackage.json'
        try:
            test_obj = GetProjectData(test_url)
        except ReadTimeout:
            return warnings.warn("GitHub is not accessible")
        assert 'name' in test_obj
        assert test_obj['type'] == 'Data Package'
        assert 'Datasets' in test_obj['summary']
        assert test_url == test_obj['source_url']

    def test_gitea(self):
        """Test parsing a Codeberg readme."""
        test_url = 'https://codeberg.org/dribdat/dribdat'
        try:
            test_obj = GetProjectData(test_url)
        except ReadTimeout:
            return warnings.warn("Codeberg is not accessible")
        assert 'name' in test_obj
        assert test_obj['name'] == 'dribdat'
        assert test_obj['type'] == 'Gitea'
        assert 'commits' in test_obj
        assert len(test_obj['commits']) > 5

    def test_github(self):
        """Test parsing a GitHub readme."""
        test_url = 'https://github.com/dribdat/dribdat/blob/main/README.md'
        try:
            test_obj = GetProjectData(test_url)
        except ReadTimeout:
            return warnings.warn("GitHub is not accessible")
        assert 'name' in test_obj
        assert test_obj['name'] == 'dribdat'
        assert test_obj['type'] == 'GitHub'
        assert 'commits' in test_obj
        assert len(test_obj['commits']) > 5

    def test_gitlab(self):
        """Test parsing a GitLab readme."""
        test_url = 'https://gitlab.com/seismist/dribdat'
        try:
            test_obj = GetProjectData(test_url)
        except ReadTimeout:
            return warnings.warn("GitLab is not accessible")
        assert 'name' in test_obj
        assert test_obj['name'] == 'dribdat'
        assert test_obj['type'] == 'GitLab'
        assert 'commits' in test_obj
        assert len(test_obj['commits']) > 5

    def test_bitbucket(self):
        """Test parsing a Bitbucket readme."""
        test_url = 'https://bitbucket.org/dribdat/dribdat/src/master/'
        try:
            test_obj = GetProjectData(test_url)
        except ReadTimeout:
            return warnings.warn("Bitbucket is not accessible")
        assert 'name' in test_obj
        assert test_obj['name'] == 'dribdat'
        assert test_obj['type'] == 'Bitbucket'
        # TODO: support for commits
