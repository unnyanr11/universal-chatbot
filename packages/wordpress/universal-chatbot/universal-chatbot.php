<?php
/**
 * Plugin Name: Universal Chatbot
 * Description: Add a published Assistant Studio chatbot without editing your theme.
 * Version: 0.4.0
 * Requires at least: 6.3
 * Requires PHP: 7.4
 * License: MIT
 */
if (!defined('ABSPATH')) { exit; }

add_action('admin_init', function () {
    register_setting('ucb_settings', 'ucb_settings', array('type' => 'array', 'sanitize_callback' => function ($input) {
        $input = is_array($input) ? $input : array();
        $origin = isset($input['origin']) && is_string($input['origin']) ? untrailingslashit(esc_url_raw($input['origin'], array('https', 'http'))) : '';
        $parts = wp_parse_url($origin);
        if (!$parts || empty($parts['host']) || !empty($parts['user']) || !empty($parts['pass']) || !empty($parts['query']) || !empty($parts['fragment']) || (!empty($parts['path']) && $parts['path'] !== '/')) {
            add_settings_error('ucb_settings', 'invalid_origin', 'Enter the application origin without a path, query or credentials.');
            return get_option('ucb_settings', array());
        }
        if ($parts['scheme'] !== 'https' && !in_array($parts['host'], array('localhost', '127.0.0.1'), true)) {
            add_settings_error('ucb_settings', 'https_required', 'Use HTTPS outside localhost.');
            return get_option('ucb_settings', array());
        }
        $assistant = isset($input['assistant']) && is_string($input['assistant']) ? sanitize_text_field($input['assistant']) : '';
        if (!preg_match('/^[A-Za-z0-9_-]{1,100}$/D', $assistant)) {
            add_settings_error('ucb_settings', 'invalid_assistant', 'Enter a valid assistant ID.');
            return get_option('ucb_settings', array());
        }
        return array('origin' => $origin, 'assistant' => $assistant, 'enabled' => !empty($input['enabled']));
    }));
});
add_action('admin_menu', function () {
    add_options_page('Universal Chatbot', 'Universal Chatbot', 'manage_options', 'universal-chatbot', function () {
        if (!current_user_can('manage_options')) { return; }
        $settings = get_option('ucb_settings', array());
        ?><div class="wrap"><h1>Universal Chatbot</h1><p>Publish your assistant and allow this website's host in Assistant Studio first. No AI API key belongs in this plugin.</p><?php settings_errors(); ?><form action="options.php" method="post"><?php settings_fields('ucb_settings'); ?>
        <p><label>Application origin <input type="url" name="ucb_settings[origin]" value="<?php echo esc_attr($settings['origin'] ?? ''); ?>" placeholder="https://chat.example.com" required></label></p>
        <p><label>Assistant ID <input name="ucb_settings[assistant]" value="<?php echo esc_attr($settings['assistant'] ?? ''); ?>" required></label></p>
        <p><label><input type="checkbox" name="ucb_settings[enabled]" value="1" <?php checked(!empty($settings['enabled'])); ?>> Enable chatbot</label></p>
        <?php submit_button(); ?></form><p>After saving, open your public website, click Chat with us and test a question. Run the installation checker in Assistant Studio. Disable this checkbox to remove the widget.</p></div><?php
    });
});
add_action('wp_enqueue_scripts', function () {
    $settings = get_option('ucb_settings', array());
    if (empty($settings['enabled']) || empty($settings['origin']) || empty($settings['assistant'])) { return; }
    wp_enqueue_script('universal-chatbot', $settings['origin'] . '/widget-loader.js', array(), '0.4.0', array('strategy' => 'defer', 'in_footer' => true));
});
add_filter('script_loader_tag', function ($tag, $handle) {
    if ($handle !== 'universal-chatbot') { return $tag; }
    $settings = get_option('ucb_settings', array());
    $identity = apply_filters('universal_chatbot_identity_assertion', '', $settings['assistant'] ?? '');
    return str_replace('<script ', '<script data-public="1" data-assistant="' . esc_attr($settings['assistant'] ?? '') . '"' . ($identity ? ' data-identity="' . esc_attr($identity) . '"' : '') . ' ', $tag);
}, 10, 2);
