# Author: Zhang Huangbin <zhb _at_ iredmail.org>
#
# Purpose: Reject sender login mismatch (addresses in 'From:' and SASL username).
#
# How to use this plugin:
#
# *) You must remove "sender_login_mismatch" restriction rule in Postfix
#    setting "smtpd_sender_restrictions" (/etc/postfix/main.cf). this plugin
#    will do the same and additonal restrictions for you.
#
# *) Enable this plugin in iRedAPD config file /opt/iredapd/settings.py:
#
#       plugins = ['reject_sender_login_mismatch', ...]
#
#    Note: please check suggested order of plugins in `settings.py.sample`.
#
# *) Optional settings (set in iRedAPD config file /opt/iredapd/settings.py):
#
#   Settings applied on message sent by not-authenticated user:
#
#   1) Check whether sender address is forged. If sender domain is hosted
#      locally, smtp authentication is required, so sender will be considered
#      as forged address. Default value is True.
#
#       CHECK_FORGED_SENDER = True
#
#   2) If you want to allow someone to send email as forged address, e.g.
#      salesforce.com, you can bypass these addresses in this setting.
#      Default value is empty (no allowed forged sender).
#
#       ALLOWED_FORGED_SENDERS = ['user@domain1.com', 'domain2.com', 'support@*']
#
#      With above setting, if sender is 'user@domain1.com', or any user under
#      'domain2.com', or any user with username 'support' in the email address,
#      this plugin won't reject it.
#
#   Settings applied on message sent by authenticated user:
#
#   1) List senders who are allowed to send email as different
#      users in iRedAPD config file (/opt/iredapd/settings.py).
#      Valid sender format:
#
#       - full email address. e.g. `user@domain.ltd`.
#
#           Allow this sender to send email as ANY sender address.
#
#       - domain name. e.g. `domain.ltd`.
#
#           Allow all users under this domain to send email as ANY sender address.
#
#       - @ + domain name. e.g. `@domain.ltd`.
#
#           Allow all users under this domain to send email as sender address
#           under the same domain.
#
#       - catch-all address: '@.'
#
#           All all users hosted on this server to send email as sender address
#           under the same domain.
#
#      Sample setting:
#
#       ALLOWED_LOGIN_MISMATCH_SENDERS = ['domain.com', 'user2@here.com']
#
#      If no sender spcified, no users are allowed to send as different users,
#      except you have other optional settings (listed below) enabled.
#
#      Note: this setting doesn't need to be used together with optional
#      settings listed below.
#
#  2) Set whether or not strictly allow sender to send as one of user alias
#     addresses. Default is True.
#
#       ALLOWED_LOGIN_MISMATCH_STRICTLY = True
#       ALLOWED_LOGIN_MISMATCH_STRICTLY = False
#
#     - With OpenLDAP backend, user alias address is stored in attribute
#       `shadowAddress` of user object.
#
#     - With MySQL/PostgreSQL backends, user alias address is username part +
#       alias domain name. For example, if primary domain `primary.com` has
#       two alias domains: `alias-1.com`, `alias-2.com`. User `user@primary.com`
#       is allowed to send email as:
#
#       + user@primary.com
#       + user@alias-1.com
#       + user@alias-2.com
#
#  3) set whether or not allow member of mail lists/alias account to send email
#     as mail list/alias ('From: <list@domain.ltd>' in mail header). Default is
#     False. Sample setting:
#
#       ALLOWED_LOGIN_MISMATCH_LIST_MEMBER = True
#
# *) Restart iRedAPD service.

import requests
from web import sqlquote
from libs.logger import logger
from libs import SMTP_ACTIONS, dnsspf
from libs.utils import is_trusted_client
import settings

if settings.backend == 'ldap':
    from libs.ldaplib.conn_utils import is_local_domain
else:
    from libs.sql import is_local_domain


check_forged_sender = settings.CHECK_FORGED_SENDER
allowed_forged_senders = settings.ALLOWED_FORGED_SENDERS
allowed_senders = settings.ALLOWED_LOGIN_MISMATCH_SENDERS
is_strict = settings.ALLOWED_LOGIN_MISMATCH_STRICTLY
allow_list_member = settings.ALLOWED_LOGIN_MISMATCH_LIST_MEMBER

if is_strict or allow_list_member:
    if settings.backend == 'ldap':
        from libs.ldaplib import conn_utils

action_reject = SMTP_ACTIONS['reject_sender_login_mismatch']


def restriction(**kwargs):
    sasl_username = kwargs['sasl_username']

    sasl_username_user = sasl_username.split('@', 1)[0]
    sasl_username_domain = kwargs['sasl_username_domain']

    sender = kwargs['sender_without_ext']
    sender_name = ''
    sender_domain = ''
    if sender:
        (sender_name, sender_domain) = sender.split('@', 1)

    # Leave this to plugin `reject_null_sender`.
    if sasl_username and not sender:
        return SMTP_ACTIONS['default']

    recipient_domain = kwargs['recipient_domain']
    client_address = kwargs['client_address']

    real_sasl_username = sasl_username
    real_sasl_username_user = sasl_username_user
    real_sender = sender

    conn = kwargs['conn_vmail']

    # Check emails sent from external network.
    if not sasl_username:
        logger.debug('Not an authenticated sender (no sasl_username).')

        # Bypass trusted networks.
        # NOTE: if sender sent email through SOGo, smtp session may not
        #       have `sasl_username`.
        if is_trusted_client(client_address):
            logger.debug('Bypass trusted client.')
            return SMTP_ACTIONS['default']

        if not check_forged_sender:
            logger.debug('Skip forged sender checks.')
            return SMTP_ACTIONS['default']

        # Bypass allowed forged sender.
        if sender in allowed_forged_senders or \
           sender_domain in allowed_forged_senders or \
           sender_name + '@*' in allowed_forged_senders:
            logger.debug('Bypass allowed forged sender.')
            return SMTP_ACTIONS['default']

        _is_local_sender_domain = False
        if sender_domain == recipient_domain:
            logger.debug('Sender domain is same as recipient domain.')
            _is_local_sender_domain = True
        else:
            if is_local_domain(conn=conn, domain=sender_domain, include_backupmx=False):
                logger.debug('Sender domain is hosted locally, smtp authentication is required.')
                _is_local_sender_domain = True
            else:
                logger.debug('Sender domain is NOT hosted locally.')

        if _is_local_sender_domain:
            if settings.CHECK_SPF_IF_LOGIN_MISMATCH:
                logger.debug('Check whether client is allowed smtp server against DNS SPF record.')

                # Query DNS to get IP addresses/networks listed in SPF
                # record of sender domain, reject if not match.
                if dnsspf.is_allowed_server_in_spf(sender_domain=sender_domain, ip=client_address):
                    logger.debug('Sender server is listed in DNS SPF record, bypassed.')
                    return SMTP_ACTIONS['default']
                else:
                    logger.debug('Sender server is NOT listed in DNS SPF record.')

            logger.debug('Sender is considered as forged, rejecting')
            return SMTP_ACTIONS['reject_forged_sender']
        else:
            return SMTP_ACTIONS['default']

    # Check emails sent by authenticated users.
    logger.debug('Sender: {}, SASL username: {}'.format(sender, sasl_username))

    if sender == sasl_username:
        logger.debug('SKIP: sender == sasl username.')
        return SMTP_ACTIONS['default']

    #
    # sender != sasl_username
    #
    # If no access settings available, reject directly.
    if not (allowed_senders or is_strict or allow_list_member):
        logger.debug('No allowed senders in config file.')
        return action_reject

    # Check explicitly allowed senders
    if allowed_senders:
        logger.debug('Allowed SASL senders: %s' % ', '.join(allowed_senders))
        if sasl_username in allowed_senders:
            logger.debug('Sender SASL username is explicitly allowed.')
            return SMTP_ACTIONS['default']
        elif sasl_username_domain in allowed_senders:
            logger.debug('Sender domain name is explicitly allowed.')
            return SMTP_ACTIONS['default']
        elif ('@' + sasl_username_domain in allowed_senders) or ('@.' in allowed_senders):
            # Restrict to send as users under SAME domain
            if sasl_username_domain == sender_domain:
                return SMTP_ACTIONS['default']
        else:
            # Note: not reject email here, still need to check other access settings.
            logger.debug('Sender is not allowed to send email as other user (ALLOWED_LOGIN_MISMATCH_SENDERS).')

    # Check whether sender is a member of mlmmj mailing list.
    _check_mlmmj_ml = False

    # Check alias domains and user alias addresses
    if is_strict or allow_list_member:
        if is_strict:
            logger.debug('Apply strict restriction (ALLOWED_LOGIN_MISMATCH_STRICTLY=True).')

        if allow_list_member:
            logger.debug('Apply list/alias member restriction (ALLOWED_LOGIN_MISMATCH_LIST_MEMBER=True).')

        if settings.backend == 'ldap':
            filter_user_alias = '(&(objectClass=mailUser)(mail={})(shadowAddress={}))'.format(sasl_username, sender)
            filter_list_member = '(&(objectClass=mailUser)(|(mail={})(shadowAddress={}))(memberOfGroup={}))'.format(sasl_username, sasl_username, sender)
            filter_alias_member = '(&(objectClass=mailAlias)(|(mail={})(shadowAddress={}))(mailForwardingAddress={}))'.format(sender, sender, sasl_username)

            if is_strict and (not allow_list_member):
                # Query mail account directly
                query_filter = filter_user_alias
                success_msg = 'Sender is an user alias address.'
            elif (not is_strict) and allow_list_member:
                query_filter = '(|' + filter_list_member + filter_alias_member + ')'
                success_msg = 'Sender ({}) is member of mail list/alias ({}).'.format(sasl_username, sender)
            else:
                # (is_strict and allow_list_member)
                query_filter = '(|' + filter_user_alias + filter_list_member + filter_alias_member + ')'
                success_msg = 'Sender ({}) is an user alias address or list/alias member ({}).'.format(sasl_username, sender)

            qr = conn_utils.get_account_ldif(conn=conn,
                                             account=sasl_username,
                                             query_filter=query_filter,
                                             attrs=['dn'])
            (_dn, _ldif) = qr
            if _dn:
                logger.debug(success_msg)
                return SMTP_ACTIONS['default']
            else:
                logger.debug('Sender is neither user alias address nor member of list/alias.')

            # Check mlmmj
            query_filter = "(&(objectClass=mailList)(enabledService=mlmmj)(accountStatus=active))"
            qr = conn_utils.get_account_ldif(conn=conn,
                                             account=sender,
                                             query_filter=query_filter,
                                             attrs=['dn'])
            (_dn, _ldif) = qr
            if _dn:
                _check_mlmmj_ml = True

        elif settings.backend in ['mysql', 'pgsql']:
            if is_strict:
                # Get per-user alias addresses
                sql = """SELECT address
                           FROM forwardings
                          WHERE address=%s AND (forwarding=%s OR forwarding LIKE %s) AND is_alias=1
                          LIMIT 1""" % (sqlquote(sender),
                                        sqlquote(real_sasl_username),
                                        sqlquote(real_sasl_username_user + '+%%@' + sasl_username_domain))
                logger.debug('[SQL] query per-user alias address: \n%s' % sql)

                qr = conn.execute(sql)
                sql_record = qr.fetchone()
                logger.debug('SQL query result: %s' % str(sql_record))

                if sql_record:
                    logger.debug('Sender {} is an alias address of smtp auth username {}.'.format(sender, real_sasl_username))
                    return SMTP_ACTIONS['default']
                else:
                    logger.debug('No per-user alias address found.')

                # Get alias domains
                if sender_domain != sasl_username_domain:
                    sql = """SELECT alias_domain
                               FROM alias_domain
                              WHERE alias_domain=%s AND target_domain=%s
                              LIMIT 1""" % (sqlquote(sender_domain), sqlquote(sasl_username_domain))
                    logger.debug('[SQL] query alias domains: \n%s' % sql)

                    qr = conn.execute(sql)
                    sql_record = qr.fetchone()
                    logger.debug('SQL query result: %s' % str(sql_record))

                    if not sql_record:
                        logger.debug('No alias domain found.')
                    else:
                        logger.debug('Sender domain {} is an alias domain of {}.'.format(sender_domain, sasl_username_domain))

                        real_sasl_username = sasl_username_user + '@' + sasl_username_domain
                        real_sender = sender_name + '@' + sasl_username_domain

                        # sender_domain is one of alias domains
                        if sender_name != sasl_username_user:
                            logger.debug('Sender is not an user alias address.')
                        else:
                            logger.debug('Sender is an alias address of sasl username.')
                            return SMTP_ACTIONS['default']

            if allow_list_member:
                # Get alias members
                sql = """SELECT forwarding
                           FROM forwardings
                          WHERE address=%s AND forwarding=%s AND is_list=1 AND active=1
                          LIMIT 1""" % (sqlquote(real_sender), sqlquote(real_sasl_username))
                logger.debug('[SQL] query members of mail alias account ({}): \n{}'.format(real_sender, sql))

                qr = conn.execute(sql)
                sql_record = qr.fetchone()
                logger.debug('SQL query result: %s' % str(sql_record))

                if sql_record:
                    logger.debug('SASL username ({}) is a member of mail alias ({}).'.format(sasl_username, sender))
                    return SMTP_ACTIONS['default']
                else:
                    logger.debug('No such mail alias account.')

                # Check subscribeable (mlmmj) mailing list.
                sql = """SELECT id FROM maillists WHERE address=%s AND active=1 LIMIT 1""" % sqlquote(real_sender)
                logger.debug('[SQL] query mailing list account ({}): \n{}'.format(real_sender, sql))

                qr = conn.execute(sql)
                sql_record = qr.fetchone()
                logger.debug('SQL query result: %s' % str(sql_record))

                if sql_record:
                    _check_mlmmj_ml = True
                else:
                    logger.debug('No such mailing list account.')

    if _check_mlmmj_ml:
        # Perform mlmmjadmin query.
        api_auth_token = settings.mlmmjadmin_api_auth_token
        if api_auth_token and settings.mlmmjadmin_api_endpoint:
            _api_endpoint = '/'.join([settings.mlmmjadmin_api_endpoint, real_sender, 'has_subscriber', sasl_username])
            api_headers = {settings.MLMMJADMIN_API_AUTH_TOKEN_HEADER_NAME: api_auth_token}
            logger.debug('mlmmjadmin api endpoint: {}'.format(_api_endpoint))
            logger.debug('mlmmjadmin api headers: {}'.format(api_headers))

            try:
                r = requests.get(_api_endpoint, headers=api_headers, verify=False)
                _json = r.json()
                if _json['_success']:
                    logger.debug('SASL username ({}) is a member of mailing list ({}).'.format(sasl_username, sender))
                    return SMTP_ACTIONS['default']
            except Exception as e:
                logger.error("Error while querying mlmmjadmin api: {}".format(e))

    return action_reject
