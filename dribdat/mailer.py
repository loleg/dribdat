# -*- coding: utf-8 -*-
"""Helper for sending mail."""

from flask import url_for, current_app
from flask_mailman import EmailMessage
from dribdat.utils import random_password  # noqa: I005
import logging


def user_activation_message(user, act_hash):
    """Prepare a message to send to the user."""
    # base_url = url_for("public.home", _external=True)
    act_url = url_for(
        "auth.activate", userid=user.id, userhash=act_hash, _external=True
    )
    fqdn = current_app.config["SERVER_NAME"]
    from_email = current_app.config["MAIL_DEFAULT_SENDER"]
    # Populate message object
    msg = EmailMessage(from_email=from_email)
    msg.subject = "Your dribdat account"
    msg.body = (
        "👋🏾 Hello %s\n\n" % user.name
        + "🗝️ You are 1 click away from signing into Dribdat:"
        + "\n\n%s\n\n" % act_url
        + "🚥 Is the link not working? Try to copy and paste it into your browser.\n"
        + "💡 If you did not expect this e-mail, please change your password!\n"
        + "🏀 Thank you for using the service at %s\n\n" % fqdn
        + "d}}BD{t"
    )
    # --------------------
    logging.debug(act_url)
    return msg


def user_activation(user):
    """Send an activation by e-mail."""
    act_hash = random_password(32)
    user.set_hashword(act_hash)
    user.save()
    msg = user_activation_message(user, act_hash)
    # print(msg.body)
    if "mailman" not in current_app.extensions:
        logging.warning("E-mail extension has not been configured")
        return act_hash
    msg.to = [user.email]
    logging.info("Sending activation mail to user %d" % user.id)
    msg.send(fail_silently=True)
    return act_hash


def user_registration(user_email):
    """Send an invitation by e-mail."""
    msg = user_invitation_message()
    if "mailman" not in current_app.extensions:
        logging.warning("E-mail extension has not been configured")
        return
    msg.to = [user_email]
    logging.info("Sending registration mail")
    msg.send(fail_silently=True)


def user_invitation_message(project=None):
    """Craft an invitation message."""
    # base_url = url_for("public.home", _external=True)
    # login_url = url_for("auth.login", _external=True)
    from_email = current_app.config["MAIL_DEFAULT_SENDER"]
    msg = EmailMessage(from_email=from_email)
    if project:
        act_url = url_for("project.project_star", project_id=project.id, _external=True)
        msg.subject = "Invitation: %s" % project.event.name
        msg.body = (
            "You are personally invited - please join us at %s!\n\n"
            % project.event.name
            + "🏀 We are interested in your contributions to '%s'.\n" % project.name
            + "🤼 Tap here to join the team: %s\n\n" % act_url
            + "-- D}}BD{T --"
        )
    else:
        act_url = url_for("auth.register", _external=True)
        msg.subject = "Invitation to Dribdat"
        msg.body = (
            "You are invited to make a contribution to our sprint!\n\n"
            + "🏀 Tap here to create an account: %s\n\n" % act_url
            + "-- D}}BD{T --"
        )
    return msg


def user_invitation(user_email, project):
    """Send an invitation by e-mail."""
    if "mailman" not in current_app.extensions:
        logging.warning("E-mail extension has not been configured")
        return False
    msg = user_invitation_message(project)
    msg.to = [user_email]
    logging.info("Sending activation mail to %s" % user_email)
    msg.send(fail_silently=True)
    return True
