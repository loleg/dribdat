# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, redirect, url_for, make_response, request, flash, jsonify, current_app
from flask_login import login_required, current_user

from sqlalchemy import or_

from ..extensions import db
from ..utils import timesince

from ..user.models import Event, Project, Category, Activity
from ..aggregation import GetProjectData

from flask import Response, stream_with_context
import io, csv, json

blueprint = Blueprint('api', __name__, url_prefix='/api')


# Collect all projects for an event
def project_list(event_id):
    projects = Project.query.filter_by(event_id=event_id, is_hidden=False)
    summaries = [ p.data for p in projects ]
    summaries.sort(key=lambda x: x['score'], reverse=True)
    return summaries

# Generate a CSV file
def gen_csv(csvdata):
    output = io.BytesIO()
    writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
    writer.writerow(csvdata[0].keys())
    for rk in csvdata:
        writer.writerow(rk.values())
    return output.getvalue()


# API: Outputs JSON about an event
@blueprint.route('/event/<int:event_id>/info.json')
def info_event_json(event_id):
    event = Event.query.filter_by(id=event_id).first_or_404()
    return jsonify(event=event.data, timeuntil=timesince(event.countdown, until=True))

# API: Outputs JSON about the current event
@blueprint.route('/event/current/info.json')
def info_current_event_json():
    event = Event.query.filter_by(is_current=True).first()
    return jsonify(event=event.data, timeuntil=timesince(event.countdown, until=True))

# API: Outputs JSON of all projects at a specific event
@blueprint.route('/event/<int:event_id>/projects.json')
def project_list_json(event_id):
    return jsonify(projects=project_list(event_id))

# API: Outputs JSON of projects in the current event, along with its info
@blueprint.route('/event/current/projects.json')
def project_list_current_json():
    event = Event.query.filter_by(is_current=True).first()
    return jsonify(projects=project_list(event.id), event=event.data)

# API: Outputs CSV of all projects in an event
@blueprint.route('/event/<int:event_id>/projects.csv')
def project_list_csv(event_id):
    return Response(stream_with_context(gen_csv(project_list(event_id))),
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=project_list.csv'})

# API: Outputs JSON of all recent activity
@blueprint.route('/project/activity.json')
def projects_activity_json():
    activities = [a.data for a in Activity.query.order_by(Activity.id.desc()).limit(30).all()]
    return jsonify(activities=activities)

# API: Outputs JSON of recent activity of a project
@blueprint.route('/project/<int:project_id>/activity.json')
def project_activity_json(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    query = Activity.query.filter_by(project_id=project.id).order_by(Activity.id.desc()).limit(30).all()
    activities = [a.data for a in query]
    return jsonify(project=project.data, activities=activities)

# API: Full text search projects
@blueprint.route('/project/search.json')
def project_search_json():
    q = request.args.get('q')
    if q is None or len(q) < 3: return jsonify(projects=[])
    q = "%%%s%%" % q
    projects = Project.query.filter(or_(
        Project.name.like(q),
        Project.summary.like(q),
        Project.longtext.like(q),
    )).limit(5).all()
    return jsonify(projects=[p.data for p in projects])

# API: Pushes data into a project
@blueprint.route('/project/push.json', methods=["PUT", "POST"])
def project_push_json():
    data = request.get_json(force=True)
    if not 'key' in data or data['key'] != current_app.config['SODABOT_KEY']:
        return jsonify(error='Invalid key')
    project = Project.query.filter_by(hashtag=data['hashtag']).first()
    if not project:
        project = Project()
        project.user_id = 1
        project.progress = 0
        project.is_autoupdate = True
        project.event = Event.query.filter_by(is_current=True).first()
    elif project.user_id != 1 or project.is_hidden or not project.is_autoupdate:
        return jsonify(error='Access denied')
    project.hashtag = data['hashtag']
    if 'name' in data and len(data['name']) > 0:
        project.name = data['name']
    else:
        project.name = project.hashtag.replace('-', ' ')
    if 'summary' in data and len(data['summary']) > 0:
        project.summary = data['summary']
    if 'longtext' in data and len(data['longtext']) > 0:
        project.longtext = data['longtext']
    if 'autotext_url' in data and data['autotext_url'].startswith('http'):
        project.autotext_url = data['autotext_url']
    if 'levelup' in data and 0 < project.progress + data['levelup'] * 10 < 50: # MAX progress
        project.progress = project.progress + data['levelup'] * 10
    # return jsonify(data=data)
    if project.autotext_url is not None:
        # Now try to autosync
        data = GetProjectData(project.autotext_url)
        if 'name' in data:
            if len(data['name']) > 0:
                project.name = data['name']
            if 'summary' in data and len(data['summary']) > 0:
                project.summary = data['summary']
            if 'description' in data and len(data['description']) > 0:
                project.longtext = data['description']
            if 'homepage_url' in data and len(data['homepage_url']) > 0:
                project.webpage_url = data['homepage_url']
            if 'source_url' in data and len(data['source_url']) > 0:
                project.source_url = data['source_url']
            if 'image_url' in data and len(data['image_url']) > 0:
                project.image_url = data['image_url']
    project.update()
    db.session.add(project)
    db.session.commit()
    return jsonify(success='Updated', project=project.data)
