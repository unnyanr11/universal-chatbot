<?php
/** Install on your server through an mu-plugin. Keep UCB_IDENTITY_SECRET in private server config. */
add_filter('universal_chatbot_identity_assertion', function ($assertion, $assistant_id) {
    if (!is_user_logged_in() || !defined('UCB_IDENTITY_SECRET')) { return ''; }
    $claims = array('assistant_id' => $assistant_id, 'sub' => 'wp-user:' . get_current_user_id(), 'exp' => time() + 120, 'nonce' => bin2hex(random_bytes(24)));
    $base64url = function ($value) { return rtrim(strtr(base64_encode($value), '+/', '-_'), '='); };
    $payload = $base64url(wp_json_encode($claims));
    return $payload . '.' . $base64url(hash_hmac('sha256', $payload, UCB_IDENTITY_SECRET, true));
}, 10, 2);
// Exclude signed pages from full-page/shared caches; assertions are private, short-lived and one-use.
