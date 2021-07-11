 # -*- coding: utf-8 -*-

from flask import (
    Blueprint,
    current_app
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    Response,
    send_file,
    stream_with_context,
    url_for,
)
from flask_login import login_required, current_user
from flask_restx import fields, Api

from datetime import datetime
from sqlalchemy import or_

import json, tempfile

from ..extensions import db
from ..utils import timesince, random_password, format_date
from ..decorators import admin_required

from ..user.models import Event, Project, Category, Activity
from ..aggregation import GetProjectData, GetEventUsers

from ..apiutils import *

blueprint = Blueprint('api', __name__, url_prefix='/api')
api = Api(blueprint, doc='/doc/')

ns = api.namespace('projects', description='Interact with projects')
project = api.model('Project', {
    'name': fields.String,
    'summary': fields.String,
    'hashtag': fields.String,
})

# ------ EVENT INFORMATION ---------

# API: Outputs JSON about the current event
@blueprint.route('/event/current/info.json')
def info_current_event_json():
    event = Event.query.filter_by(is_current=True).first() or \
            Event.query.order_by(Event.id.desc()).first_or_404()
    return jsonify(event=event.data, timeuntil=timesince(event.countdown, until=True))

# API: Outputs JSON about an event
@blueprint.route('/event/<int:event_id>/info.json')
def info_event_json(event_id):
    event = Event.query.filter_by(id=event_id).first_or_404()
    return jsonify(event=event.data, timeuntil=timesince(event.countdown, until=True))

# API: Outputs JSON-LD about an Event according to https://schema.org/Hackathon
@blueprint.route('/event/<int:event_id>/hackathon.json')
def info_event_hackathon_json(event_id):
    event = Event.query.filter_by(id=event_id).first_or_404()
    return jsonify(event.get_schema(request.host_url))

# ------ EVENT PROJECTS ---------

def project_list(event_id, full_data=False):
    """ Collect all projects and challenges for an event """
    is_moar = bool(request.args.get('moar', type=bool)) or full_data
    projects = get_projects_by_event(event_id)
    host_url = request.host_url
    return get_project_summaries(projects, host_url, is_moar)

@blueprint.route('/event/current/projects.json')
def project_list_current_json():
    """ API: Outputs JSON of projects in the current event, along with its info """
    event = Event.query.filter_by(is_current=True).first() or \
            Event.query.order_by(Event.id.desc()).first_or_404()
    return jsonify(projects=project_list(event.id), event=event.data)

@blueprint.route('/event/<int:event_id>/projects.json')
def project_list_json(event_id):
    """ API: Outputs JSON of all projects at a specific event """
    return jsonify(projects=project_list(event_id))

def project_list_csv(event_id, event_name):
    return Response(stream_with_context(gen_csv(project_list(event_id))),
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=' + event_name + '_dribdat.csv'})

# API: Outputs CSV of all projects in an event
@blueprint.route('/event/<int:event_id>/projects.csv')
def project_list_event_csv(event_id):
    event = Event.query.filter_by(id=event_id).first_or_404()
    return project_list_csv(event.id, event.name)

# API: Outputs CSV of projects and challenges in the current event
@blueprint.route('/event/current/projects.csv')
def project_list_current_csv():
    event = Event.query.filter_by(is_current=True).first() or \
            Event.query.order_by(Event.id.desc()).first_or_404()
    return project_list_csv(event.id, event.name)

# API: Outputs JSON of categories in the current event
@blueprint.route('/event/current/categories.json')
def categories_list_current_json():
    event = Event.query.filter_by(is_current=True).first()
    return jsonify(categories=[ c.data for c in event.categories_for_event() ], event=event.data)

# ------ ACTIVITY FEEDS ---------

# API: Outputs JSON of recent activity in an event
@blueprint.route('/event/<int:event_id>/activity.json')
def event_activity_json(event_id):
    limit = request.args.get('limit') or 50
    return jsonify(activities=get_event_activities(event_id, limit))

# API: Outputs JSON of categories in the current event
@blueprint.route('/event/current/activity.json')
def event_activity_current_json():
    event = Event.query.filter_by(is_current=True).first()
    if not event: return jsonify(activities=[])
    return event_activity_json(event.id)

# API: Outputs CSV of an event activity
@blueprint.route('/event/<int:event_id>/activity.csv')
def event_activity_csv(event_id):
    limit = request.args.get('limit') or 50
    return Response(stream_with_context(gen_csv(get_event_activities(event_id, limit))),
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=activity_list.csv'})

# API: Outputs JSON of recent activity across all projects
@blueprint.route('/project/activity.json')
def projects_activity_json():
    limit = request.args.get('limit') or 10
    recent = Activity.query.order_by(Activity.id.desc()).limit(limit).all()
    return jsonify(activities=[a.data for a in recent])

# API: Outputs JSON of recent posts (a type of activity) across projects
@blueprint.route('/project/posts.json')
def projects_posts_json():
    limit = request.args.get('limit') or 10
    recent = Activity.query.filter(Activity.action=="post")
    recent = recent.order_by(Activity.id.desc())
    recent = recent.limit(limit).all()
    return jsonify(activities=[a.data for a in recent])

# API: Outputs JSON of recent activity of a project
@blueprint.route('/project/<int:project_id>/activity.json')
def project_activity_json(project_id):
    limit = request.args.get('limit') or 10
    project = Project.query.filter_by(id=project_id).first_or_404()
    query = Activity.query.filter_by(project_id=project.id).order_by(Activity.id.desc()).limit(limit).all()
    activities = [a.data for a in query]
    return jsonify(project=project.data, activities=activities)

# API: Outputs JSON info for a specific project
@blueprint.route('/project/<int:project_id>/info.json')
def project_info_json(project_id):
    project = Project.query.filter_by(id=project_id).first_or_404()
    activities = []
    for user in project.team():
        activities.append({
            'id': user.id,
            'name': user.username,
            'link': user.webpage_url
        })

    data = {
        'project': project.data,
        'phase': project.phase,
        'pitch': project.webembed,
        'is_webembed': project.is_webembed,
        'event': project.event.data,
        'creator': {
            'id': project.user.id,
            'username': project.user.username
        },
        'team': activities
    }

    return jsonify(data)

# ------ USERS ----------

@blueprint.route('/event/<int:event_id>/participants.csv')
@admin_required
def event_participants_csv(event_id):
    event = Event.query.filter_by(id=event_id).first_or_404()
    userlist = [u.data for u in GetEventUsers(event)]
    return Response(stream_with_context(gen_csv(userlist)),
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=user_list_%d.csv' % event.id})



# ------ SEARCH ---------

# API: Full text search projects
@blueprint.route('/project/search.json')
def project_search_json():
    q = request.args.get('q')
    if q is None or len(q) < 3: return jsonify(projects=[])
    limit = request.args.get('limit') or 10
    q = "%%%s%%" % q
    projects = Project.query.filter(or_(
        Project.name.like(q),
        Project.summary.like(q),
        Project.longtext.like(q),
        Project.autotext.like(q),
    )).limit(limit).all()
    projects = expand_project_urls(
        [p.data for p in projects],
        request.host_url
    )
    return jsonify(projects=projects)

# ------ UPDATE ---------

# API: Pushes data into a project
@blueprint.route('/project/push.json', methods=["PUT", "POST"])
def project_push_json():
    data = request.get_json(force=True)
    if not 'key' in data or data['key'] != current_app.config['SECRET_API']:
        return jsonify(error='Invalid key')
    project = Project.query.filter_by(hashtag=data['hashtag']).first()
    if not project:
        project = Project()
        project.user_id = 1
        project.progress = 0
        # project.autotext_url = "#bot"
        # project.is_autoupdate = True
        project.event = Event.query.filter_by(is_current=True).first()
    elif project.user_id != 1 or project.is_hidden:
        return jsonify(error='Access denied')
    project.hashtag = data['hashtag']
    if 'name' in data and len(data['name']) > 0:
        project.name = data['name']
    else:
        project.name = project.hashtag.replace('-', ' ')
    if 'summary' in data and len(data['summary']) > 0:
        project.summary = data['summary']
    hasLongtext = 'longtext' in data and len(data['longtext']) > 0
    if hasLongtext:
        project.longtext = data['longtext']
    if 'autotext_url' in data and data['autotext_url'].startswith('http'):
        project.autotext_url = data['autotext_url']
        if not project.source_url or project.source_url == '':
            project.source_url = data['autotext_url']
    if 'levelup' in data and 0 < project.progress + data['levelup'] * 10 < 50: # MAX progress
        project.progress = project.progress + data['levelup'] * 10
    # return jsonify(data=data)
    if project.autotext_url is not None and not hasLongtext:
        # Now try to autosync
        data = GetProjectData(project.autotext_url)
        if 'name' in data:
            if len(data['name']) > 0:
                project.name = data['name'][0:80]
            if 'summary' in data and len(data['summary']) > 0:
                project.summary = data['summary'][0:140]
            if 'description' in data and len(data['description']) > 0:
                project.longtext = data['description']
            if 'homepage_url' in data and len(data['homepage_url']) > 0:
                project.webpage_url = data['homepage_url'][0:2048]
            if 'source_url' in data and len(data['source_url']) > 0:
                project.source_url = data['source_url'][0:255]
            if 'image_url' in data and len(data['image_url']) > 0:
                project.image_url = data['image_url'][0:255]
    project.update()
    db.session.add(project)
    db.session.commit()
    return jsonify(success='Updated', project=project.data)

# ------ FRONTEND -------

# API routine used to help sync project data
@blueprint.route('/project/autofill', methods=['GET', 'POST'])
@login_required
def project_autofill():
    url = request.args.get('url')
    data = GetProjectData(url)
    return jsonify(data)

# TODO: move to separate upload.py ?
import boto3, botocore
from botocore.exceptions import ClientError
from botocore.client import Config

# API: Enables uploading images into a project
@blueprint.route('/project/uploader', methods=["POST"])
@login_required
def project_uploader():
    if not current_app.config['S3_KEY']: return ''
    if len(request.files) == 0: return 'No files selected'
    img = request.files['file']
    if not img or img.filename == '': return 'No filename'
    ext = img.filename.split('.')[-1].lower()
    if not ext in ['png','jpg','jpeg','gif']: return 'Invalid format'
    filename = random_password(24) + '.' + ext
    # with tempfile.TemporaryDirectory() as tmpdir:
        # img.save(path.join(tmpdir, filename))
    if 'S3_FOLDER' in current_app.config:
        s3_filepath = '/'.join([current_app.config['S3_FOLDER'], filename])
    else:
        s3_filepath = filename
    # print('Uploading to %s' % s3_filepath)
    if 'S3_ENDPOINT' in current_app.config:
        s3_obj = boto3.client(service_name='s3',
            endpoint_url=current_app.config['S3_ENDPOINT'],
            aws_access_key_id=current_app.config['S3_KEY'],
            aws_secret_access_key=current_app.config['S3_SECRET'],
        )
    else:
        s3_obj = boto3.client(service_name='s3',
            region_name=current_app.config['S3_REGION'],
            aws_access_key_id=current_app.config['S3_KEY'],
            aws_secret_access_key=current_app.config['S3_SECRET'],
        )
    # Commence upload
    s3_obj.upload_fileobj(img,
        current_app.config['S3_BUCKET'],
        s3_filepath,
        ExtraArgs={ 'ContentType': img.content_type, 'ACL': 'public-read' }
      )
    return '/'.join([current_app.config['S3_HTTPS'], s3_filepath])


# TODO: move to packager.py ?

from frictionless import Package, Resource

@blueprint.route('/event/current/datapackage.<format>', methods=["GET"])
@login_required
def package_current_event(format):
    event = Event.query.filter_by(is_current=True).first() or \
            Event.query.order_by(Event.id.desc()).first_or_404()
    return package_event(event, format)

@blueprint.route('/event/<int:event_id>/datapackage.<format>', methods=["GET"])
@login_required
def package_specific_event(event_id, format):
    event = Event.query.filter_by(id=event_id).first_or_404()
    return package_event(event, format)

def package_event(event, format):
    if format not in ['zip', 'json']:
        return "Format not supported"
    # Set up a data package
    package = Package(
        name='event-%d' % event.id,
        title=event.name,
        description="This is a Data Package containing event and project details",
        keywords=["dribdat", "hackathon", "co-creation"],
        sources=[{
            "title": "dribdat", "path": "https://dribdat.cc"
        }],
        licenses=[{
            "name": "ODC-PDDL-1.0", "path": "http://opendatacommons.org/licenses/pddl/",
            "title": "Open Data Commons Public Domain Dedication and License v1.0"
        }],
        contributors=[{
            "title": current_user.username,
            "path": current_user.webpage_url or '',
            "role": "author"
        }],
        homepage=request.host_url,
        created=format_date(datetime.now(), '%Y-%m-%dT%H:%M'),
        version="0.1.0"
    )

    if False: # as CSV
        fp_projects = tempfile.NamedTemporaryFile(mode='w+t', prefix='projects-', suffix='.csv')
        print("Writing to temp CSV file", fp_projects.name)
        fp_projects.write(gen_csv(project_list(event.id)))
        resource = Resource(fp_projects.name)
    if False:
        print("Generating in-memory rowset")
        project_rows = gen_rows(project_list(event.id))
        resource = Resource(
            name='projects',
            data=project_rows,
        )

    # Generate resources
    print("Generating in-memory JSON of event")
    package.add_resource(Resource(
            name='event',
            data=[event.get_full_data()],
        ))
    print("Generating in-memory JSON of projects")
    package.add_resource(Resource(
            name='projects',
            data=project_list(event.id, True),
        ))

    # Generate data package
    fp_package = tempfile.NamedTemporaryFile(prefix='datapackage-', suffix='.zip')
    print("Saving at", fp_package.name)
    if format == 'json':
        return jsonify(package)
    elif format == 'zip':
        package.to_zip(fp_package.name)
        return send_file(fp_package.name, as_attachment=True)
