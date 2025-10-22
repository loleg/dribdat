# -*- coding: utf-8 -*-
"""Dribdat admin configuration."""

from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from dribdat.user.models import User, Role, Event, Project, Category
from dribdat.extensions import db

class UserAdmin(ModelView):
    """User administration."""

    column_searchable_list = ('username', 'email')
    column_filters = ('active', 'is_admin')
    column_list = ('username', 'email', 'active', 'is_admin')

admin = Admin(name='sudo dribdat', template_mode='bootstrap3')

# Add administration views
admin.add_view(UserAdmin(User, db.session))
admin.add_view(ModelView(Role, db.session))
admin.add_view(ModelView(Event, db.session))
admin.add_view(ModelView(Project, db.session))
admin.add_view(ModelView(Category, db.session))
