<?php

// SQL DATABASE
$config['db_dsnw'] = 'mysqli://roundcube:Vwr0S23hr0uLfZwxJLnlkY342SVZltgr@127.0.0.1:3306/roundcubemail';

// LOGGING
$config['log_driver'] = 'syslog';
$config['syslog_facility'] = LOG_MAIL;
$config['log_logins'] = true;

// IMAP
$config['imap_host'] = 'tls://127.0.0.1:143';
$config['imap_auth_type'] = 'LOGIN';
$config['imap_delimiter'] = '/';
// Required if you're running PHP 5.6 or later
$config['imap_conn_options'] = array(
    'ssl' => array(
        'verify_peer'  => false,
        'verify_peer_name' => false,
    ),
);

// SMTP
$config['smtp_host'] = 'tls://127.0.0.1:587';
$config['smtp_user'] = '%u';
$config['smtp_pass'] = '%p';
$config['smtp_auth_type'] = 'LOGIN';
// Required if you're running PHP 5.6 or later
$config['smtp_conn_options'] = array(
    'ssl' => array(
        'verify_peer'      => false,
        'verify_peer_name' => false,
    ),
);

// Use user's identity as envelope sender for 'return receipt' responses,
// otherwise it will be rejected by iRedAPD plugin `reject_null_sender`.
$config['mdn_use_from'] = true;

// SYSTEM
$config['auto_create_user'] = true;
$config['force_https'] = true;
$config['login_autocomplete'] = 2;
$config['ip_check'] = false;
$config['des_key'] = 'lbRCCFMauM6DLVFI0ogrvelw';
$config['cipher_method'] = 'AES-256-CBC';
$config['useragent'] = 'Roundcube Webmail'; // Hide version number
//$config['username_domain'] = 'premafirm.com';
$config['mime_types'] = '/etc/mime.types';
$config['max_message_size'] = '15M';

// USER INTERFACE
$config['create_default_folders'] = true;
$config['quota_zero_as_unlimited'] = true;
$config['spellcheck_engine'] = 'pspell';

// USER PREFERENCES
$config['default_charset'] = 'UTF-8';
//$config['addressbook_sort_col'] = 'name';
$config['draft_autosave'] = 60;
$config['default_list_mode'] = 'threads';
$config['autoexpand_threads'] = 2;
$config['check_all_folders'] = true;
$config['default_font_size'] = '12pt';
$config['message_show_email'] = true;
$config['layout'] = 'widescreen';   // three columns
//$config['skip_deleted'] = true;

// PLUGINS
$config['plugins'] = array('managesieve', 'password', 'zipdownload');

