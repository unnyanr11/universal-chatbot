<?php
require_once ABSPATH . 'wp-admin/includes/template.php';
do_action('admin_init');
$original = get_option('ucb_settings');
$bad = sanitize_option('ucb_settings', array('origin' => 'https://user:password@bad.example', 'assistant' => 'bad', 'enabled' => true));
if ($bad !== $original) { throw new Exception('Credential URL was accepted'); }
$bad = sanitize_option('ucb_settings', array('origin' => 'javascript:alert(1)', 'assistant' => 'bad', 'enabled' => true));
if ($bad !== $original) { throw new Exception('Non-HTTP origin was accepted'); }
$good = sanitize_option('ucb_settings', array('origin' => 'https://chat.example.test', 'assistant' => 'synthetic-widget', 'enabled' => true));
if ($good['origin'] !== 'https://chat.example.test' || $good['assistant'] !== 'synthetic-widget') { throw new Exception('Valid settings were rejected'); }
echo "WordPress settings validation passed.\n";
